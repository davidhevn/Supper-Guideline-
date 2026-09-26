#!/usr/bin/env python3
"""So export CVAT của annotator với export GT (gold) → đúng / sai / thiếu / thừa + ứng viên edge case.

Chạy offline, chỉ đọc file export "CVAT for images 1.1" (.zip hoặc annotations.xml), không cần CVAT đang chạy.
Chỉ cần Python 3. numpy + Pillow (cài bằng `python sign.py install`) chỉ dùng cho polygon/mask IoU và ảnh overlay.

    python evaluate.py --gt gold.zip --pred an.zip binh.zip \
        --labels schema/labels_v1.2.json \
        --config schema/eval_v1.2.json --images data/images/gtsdb28 --out reports/x/

Tool KHÔNG biết guideline viết gì. Nó so hình học + label + attribute + tag với GT, rồi gắn severity theo
eval_config.json. Việc kết luận "guideline thiếu" hay "annotator làm sai" vẫn là của nhóm — tool chỉ gợi ý.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

Point = Tuple[float, float]
SHAPE_TAGS = {"box", "polygon", "polyline", "points", "mask", "ellipse"}
AREA_KINDS = {"box", "polygon", "mask", "ellipse"}
UNDEF = "__undefined__"

DEFAULT_CONFIG = {
    # score >= iou_match thì coi là cùng một object; score < iou_good thì báo geometry_loose.
    # Với polyline/points, score = 1 - d / (2 * tol_px), nên d = tol_px ⇔ score 0.5.
    "iou_match": 0.5,
    "iou_good": 0.75,
    "polyline_tol_px": 15,
    "points_tol_px": 10,
    "per_label": {},
    "ignore_labels": [],
    "escalate_attrs": ["needs_review"],
    "escalate_tags": [],
    "unknown_values": ["unknown"],
    # attribute GT không phủ (vd. GT suy ra từ mask nên state luôn unknown) → không so; per_label cũng đặt được
    "ignore_attrs": [],
    # chỉ chấm object annotator có attribute nằm trong phạm vi GT, vd {"lane_marking": {"laneTypes": ["road curb"]}}
    "pred_filter": {},
    # so attribute dạng text không phân biệt hoa/thường, khoảng trắng/gạch ngang = gạch dưới ("Speed limit 50" = "speed_limit_50")
    "normalize_text": False,
    # object nhỏ hơn tỉ lệ này của diện tích ảnh bị gợi ý tag small_far khi bị bỏ sót
    "small_area_ratio": 0.001,
    "severity": {
        "missing": "major",
        "extra": "minor",
        "wrong_label": "major",
        "wrong_attr": "major",
        "unassigned_attr": "major",
        "annotator_unknown": "question",
        "geometry_loose": "minor",
        "missing_escalation": "major",
        "extra_escalation": "question",
        "tag_missing": "major",
        "tag_extra": "minor",
        "schema": "minor",
    },
}


# ─────────────────────────── parse CVAT for images / video 1.1 ───────────────────────────


@dataclass
class Obj:
    sample: str
    label: str
    kind: str
    points: List[Point]
    attrs: Dict[str, str]
    idx: int = -1
    mask_rle: Optional[List[int]] = None

    def bbox(self) -> Tuple[float, float, float, float]:
        xs = [p[0] for p in self.points] or [0.0]
        ys = [p[1] for p in self.points] or [0.0]
        return min(xs), min(ys), max(xs), max(ys)

    def area(self) -> float:
        if self.kind == "polygon" and len(self.points) >= 3:
            return abs(_shoelace(self.points))
        x1, y1, x2, y2 = self.bbox()
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    def short(self) -> str:
        attrs = ";".join(f"{k}={v}" for k, v in sorted(self.attrs.items()))
        return f"{self.label}[{attrs}]" if attrs else self.label


@dataclass
class Doc:
    name: str
    objects: Dict[str, List[Obj]] = field(default_factory=lambda: defaultdict(list))
    tags: Dict[str, List[Obj]] = field(default_factory=lambda: defaultdict(list))
    sizes: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    samples: List[str] = field(default_factory=list)


def _read_xml(path: Path) -> bytes:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            members = [n for n in zf.namelist() if Path(n).name == "annotations.xml"]
            if len(members) != 1:
                raise SystemExit(f"{path}: ZIP phải chứa đúng một annotations.xml (export CVAT for images 1.1)")
            return zf.read(members[0])
    return path.read_bytes()


def _pts(text: str) -> List[Point]:
    out = []
    for pair in (text or "").split(";"):
        if "," in pair:
            x, y = pair.split(",", 1)
            out.append((float(x), float(y)))
    return out


def _attrs(node: ET.Element) -> Dict[str, str]:
    return {a.get("name", ""): (a.text if a.text not in (None, "") else UNDEF) for a in node.findall("attribute")}


def _geom(node: ET.Element) -> Tuple[List[Point], Optional[List[int]]]:
    g = node.get
    if node.tag in ("polygon", "polyline", "points"):
        return _pts(g("points", "")), None
    if node.tag == "box":
        return [(float(g("xtl")), float(g("ytl"))), (float(g("xbr")), float(g("ybr")))], None
    if node.tag == "mask":
        left, top = float(g("left", 0)), float(g("top", 0))
        w, h = float(g("width", 0)), float(g("height", 0))
        rle = [int(v) for v in (g("rle") or "").replace(" ", "").split(",") if v != ""]
        return [(left, top), (left + w - 1, top + h - 1)], rle
    if node.tag == "ellipse":
        cx, cy, rx, ry = (float(g(k, 0)) for k in ("cx", "cy", "rx", "ry"))
        return [(cx - rx, cy - ry), (cx + rx, cy + ry)], None
    return [], None


def parse_export(path: Path) -> Doc:
    root = ET.fromstring(_read_xml(path))
    doc = Doc(name=path.stem)
    for image in root.findall("image"):
        sample = Path(image.get("name", "")).stem
        doc.samples.append(sample)
        doc.sizes[sample] = (int(image.get("width", 0)), int(image.get("height", 0)))
        for node in image:
            if node.tag == "tag":
                doc.tags[sample].append(Obj(sample, node.get("label", ""), "tag", [], _attrs(node)))
            elif node.tag in SHAPE_TAGS:
                pts, rle = _geom(node)
                doc.objects[sample].append(Obj(sample, node.get("label", ""), node.tag, pts, _attrs(node), mask_rle=rle))
    # CVAT for video 1.1 (task có track): ánh xạ frame → tên ảnh qua meta
    names = {}
    for node in root.findall(".//meta//frames//frame") + root.findall(".//meta//frames//image"):
        fid = node.get("id", node.get("frame", ""))
        if fid.isdigit() and node.get("name"):
            names[int(fid)] = Path(node.get("name")).stem
    for track in root.findall("track"):
        base = _attrs(track)
        for node in track:
            if node.tag not in SHAPE_TAGS or node.get("outside") == "1":
                continue
            frame = int(node.get("frame", 0))
            sample = names.get(frame, f"frame-{frame}")
            if sample not in doc.samples:
                doc.samples.append(sample)
            attrs = dict(base)
            attrs.update(_attrs(node))
            pts, rle = _geom(node)
            doc.objects[sample].append(Obj(sample, track.get("label", ""), node.tag, pts, attrs, mask_rle=rle))
    for sample, objs in doc.objects.items():
        for i, o in enumerate(objs):
            o.idx = i
    if not doc.samples:
        raise SystemExit(f"{path}: không có <image> nào — hãy export bằng CVAT for images 1.1")
    return doc


# ─────────────────────────── geometry ───────────────────────────


def _shoelace(pts: Sequence[Point]) -> float:
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def box_iou(a: Obj, b: Obj) -> float:
    ax1, ay1, ax2, ay2 = a.bbox()
    bx1, by1, bx2, by2 = b.bbox()
    iw, ih = max(0.0, min(ax2, bx2) - max(ax1, bx1)), max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _raster(o: Obj, box: Tuple[int, int, int, int]):
    """Mask bool của object trong khung box (x0, y0, x1, y1)."""
    import numpy as np
    from PIL import Image, ImageDraw

    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    if o.kind == "mask" and o.mask_rle:
        left, top, right, bottom = (int(round(v)) for v in o.bbox())
        mw, mh = right - left + 1, bottom - top + 1
        flat = np.zeros(mw * mh, dtype=bool)
        pos, val = 0, False
        for run in o.mask_rle:
            if val:
                flat[pos:pos + run] = True
            pos += run
            val = not val
        local = flat[: mw * mh].reshape(mh, mw)
        out = np.zeros((h, w), dtype=bool)
        sx0, sy0 = max(left, x0), max(top, y0)
        sx1, sy1 = min(left + mw, x1), min(top + mh, y1)
        if sx1 > sx0 and sy1 > sy0:
            out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = local[sy0 - top:sy1 - top, sx0 - left:sx1 - left]
        return out
    img = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(img)
    if o.kind == "polygon" and len(o.points) >= 3:
        draw.polygon([(x - x0, y - y0) for x, y in o.points], fill=1)
    elif o.kind == "ellipse":
        bx1, by1, bx2, by2 = o.bbox()
        draw.ellipse([bx1 - x0, by1 - y0, bx2 - x0, by2 - y0], fill=1)
    else:
        bx1, by1, bx2, by2 = o.bbox()
        draw.rectangle([bx1 - x0, by1 - y0, bx2 - x0, by2 - y0], fill=1)
    return np.array(img, dtype=bool)


def area_iou(a: Obj, b: Obj) -> float:
    if a.kind == "box" and b.kind == "box":
        return box_iou(a, b)
    if box_iou(a, b) == 0.0:
        return 0.0
    try:
        ax1, ay1, ax2, ay2 = a.bbox()
        bx1, by1, bx2, by2 = b.bbox()
        box = (int(math.floor(min(ax1, bx1))), int(math.floor(min(ay1, by1))),
               int(math.ceil(max(ax2, bx2))) + 1, int(math.ceil(max(ay2, by2))) + 1)
        ma, mb = _raster(a, box), _raster(b, box)
    except ImportError:  # không có numpy/Pillow → rơi về IoU theo bbox
        return box_iou(a, b)
    union = (ma | mb).sum()
    return float((ma & mb).sum()) / float(union) if union else 0.0


def _densify(pts: Sequence[Point], step: float = 4.0) -> List[Point]:
    if len(pts) < 2:
        return list(pts)
    out = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / step))
        out.extend((x1 + (x2 - x1) * t / n, y1 + (y2 - y1) * t / n) for t in range(n))
    out.append(pts[-1])
    return out


def _mean_nearest(src: Sequence[Point], dst: Sequence[Point]) -> float:
    return sum(min(math.hypot(x - u, y - v) for u, v in dst) for x, y in src) / len(src)


def line_score(a: Obj, b: Obj, tol: float) -> Tuple[float, float]:
    """Trả (score, khoảng cách trung bình px). Chamfer đối xứng giữa hai polyline/points."""
    if a.kind == "points":
        da, db = list(a.points), list(b.points)
    else:
        da, db = _densify(a.points), _densify(b.points)
    if not da or not db:
        return 0.0, float("inf")
    d = 0.5 * (_mean_nearest(da, db) + _mean_nearest(db, da))
    return max(0.0, 1.0 - d / (2.0 * tol)), d


def _cfg_for(cfg: dict, label: str, key: str):
    return cfg.get("per_label", {}).get(label, {}).get(key, cfg[key])


def similarity(g: Obj, p: Obj, cfg: dict) -> Tuple[float, str]:
    """Điểm giống nhau [0,1] + mô tả metric. 0 nếu hai loại geometry không so được."""
    if g.kind in AREA_KINDS and p.kind in AREA_KINDS:
        v = area_iou(g, p)
        return v, f"IoU={v:.2f}"
    if g.kind in ("polyline", "points") and p.kind == g.kind:
        tol = _cfg_for(cfg, g.label, "polyline_tol_px" if g.kind == "polyline" else "points_tol_px")
        s, d = line_score(g, p, tol)
        return s, f"dist={d:.1f}px(tol {tol})"
    return 0.0, "khác loại geometry"


def coverage(inner: Obj, region: Obj) -> float:
    """Tỉ lệ bbox của inner nằm trong region (dùng cho vùng ignore)."""
    ix1, iy1, ix2, iy2 = inner.bbox()
    rx1, ry1, rx2, ry2 = region.bbox()
    area = max(1e-6, (ix2 - ix1) * (iy2 - iy1))
    iw, ih = max(0.0, min(ix2, rx2) - max(ix1, rx1)), max(0.0, min(iy2, ry2) - max(iy1, ry1))
    return iw * ih / area


# ─────────────────────────── compare one annotator vs GT ───────────────────────────


@dataclass
class Row:
    annotator: str
    sample: str
    status: str            # correct | missing | extra | wrong_label | wrong_attr | ... (chuỗi ghép bằng '+')
    severity: str
    gt: Optional[Obj]
    pred: Optional[Obj]
    score: Optional[float]
    metric: str
    detail: str
    key: str               # định danh object GT để gộp nhiều annotator
    ignored_attrs: frozenset = frozenset()


SEV_ORDER = {"critical": 0, "major": 1, "minor": 2, "question": 3, "": 4}


def _sev(cfg: dict, kind: str, attr: Optional[str] = None) -> str:
    sev = cfg["severity"]
    if attr is not None and f"attr:{attr}" in sev:
        return sev[f"attr:{attr}"]
    return sev.get(kind, "minor")


def _worst(sevs: Sequence[str]) -> str:
    return min(sevs, key=lambda s: SEV_ORDER.get(s, 9)) if sevs else ""


def _norm(v: str) -> str:
    return "_".join(str(v).strip().lower().replace("-", " ").replace("_", " ").split())


def _obj_key(o: Obj) -> str:
    x1, y1, x2, y2 = o.bbox()
    return f"{o.sample}#{o.label}@{int(x1)},{int(y1)},{int(x2)},{int(y2)}"


def _is_true(v: Optional[str]) -> bool:
    return str(v).lower() in ("true", "1", "yes")


def compare(gt: Doc, pred: Doc, cfg: dict, schema: Dict[str, dict]) -> Tuple[List[Row], List[str]]:
    rows: List[Row] = []
    warnings: List[str] = []
    ann = pred.name
    ignore = set(cfg["ignore_labels"])
    esc_attrs = set(cfg["escalate_attrs"])
    unknowns = set(cfg["unknown_values"])

    missing_samples = [s for s in gt.samples if s not in pred.samples]
    extra_samples = [s for s in pred.samples if s not in gt.samples]
    # GOLD có thể là cả kho ảnh, còn task annotator chỉ là một split → chỉ chấm ảnh có ở cả hai
    if missing_samples:
        warnings.append(f"{ann}: {len(missing_samples)} ảnh GT không có trong bài, bỏ qua: {', '.join(missing_samples)}")
    if extra_samples:
        warnings.append(f"{ann}: có ảnh không nằm trong GT, bỏ qua: {', '.join(extra_samples)}")

    for sample in [s for s in gt.samples if s in pred.samples]:
        g_all = gt.objects.get(sample, [])
        p_all = pred.objects.get(sample, []) if sample in pred.samples else []
        g_ign = [o for o in g_all if o.label in ignore]
        g_objs = [o for o in g_all if o.label not in ignore]
        p_objs = []
        for o in p_all:
            if o.label in ignore:
                continue
            flt = cfg["pred_filter"].get(o.label, {})
            bad = [f"{k}={o.attrs.get(k, UNDEF)}" for k, allowed in flt.items() if o.attrs.get(k, UNDEF) not in allowed]
            if bad:
                rows.append(Row(ann, sample, "out_of_scope", "", None, o, None, "",
                                f"{', '.join(bad)} nằm ngoài phạm vi GT — không chấm", _obj_key(o)))
            else:
                p_objs.append(o)

        # schema check từ 03_cvat_labels.json
        for p in p_all:
            spec = schema.get(p.label)
            if schema and spec is None:
                rows.append(Row(ann, sample, "schema", _sev(cfg, "schema"), None, p, None, "",
                                f"label '{p.label}' không có trong labels JSON", _obj_key(p)))
                continue
            if spec and spec.get("type") not in (None, "any") and not _kind_ok(spec["type"], p.kind):
                rows.append(Row(ann, sample, "schema", _sev(cfg, "schema"), None, p, None, "",
                                f"label '{p.label}' khai báo {spec['type']} nhưng vẽ {p.kind}", _obj_key(p)))

        # ghép cặp greedy theo điểm giống, ưu tiên cùng label
        cands = []
        for gi, g in enumerate(g_objs):
            for pi, p in enumerate(p_objs):
                s, metric = similarity(g, p, cfg)
                if s >= _cfg_for(cfg, g.label, "iou_match"):
                    cands.append((s + (0.05 if g.label == p.label else 0.0), gi, pi, s, metric))
        cands.sort(key=lambda c: -c[0])
        used_g, used_p, pairs = set(), set(), []
        for _, gi, pi, s, metric in cands:
            if gi not in used_g and pi not in used_p:
                used_g.add(gi)
                used_p.add(pi)
                pairs.append((g_objs[gi], p_objs[pi], s, metric))

        for g, p, s, metric in pairs:
            issues, sevs, details = [], [], []
            if g.label != p.label:
                issues.append("wrong_label")
                sevs.append(_sev(cfg, "wrong_label"))
                details.append(f"label {g.label}→{p.label}")
            else:
                skip = set(_cfg_for(cfg, g.label, "ignore_attrs"))
                for name in sorted((set(g.attrs) | set(p.attrs)) - skip):
                    gv, pv = g.attrs.get(name, UNDEF), p.attrs.get(name, UNDEF)
                    if name in esc_attrs:
                        if _is_true(gv) and not _is_true(pv):
                            issues.append("missing_escalation")
                            sevs.append(_sev(cfg, "missing_escalation"))
                            details.append(f"GT {name}=true, annotator không escalate")
                        elif _is_true(pv) and not _is_true(gv):
                            issues.append("extra_escalation")
                            sevs.append(_sev(cfg, "extra_escalation"))
                            details.append(f"annotator bật {name} (GT không)")
                        continue
                    if gv == pv or (cfg["normalize_text"] and _norm(gv) == _norm(pv)):
                        continue
                    if pv == UNDEF:
                        issues.append("unassigned_attr")
                        sevs.append(_sev(cfg, "unassigned_attr", name))
                        details.append(f"{name} chưa gán (GT={gv})")
                    elif pv in unknowns:
                        issues.append("annotator_unknown")
                        sevs.append(_sev(cfg, "annotator_unknown"))
                        details.append(f"{name}: GT={gv}, annotator={pv}")
                    else:
                        issues.append("wrong_attr")
                        sevs.append(_sev(cfg, "wrong_attr", name))
                        details.append(f"{name}: GT={gv}, annotator={pv}")
            if s < _cfg_for(cfg, g.label, "iou_good"):
                issues.append("geometry_loose")
                sevs.append(_sev(cfg, "geometry_loose"))
                details.append(f"geometry lệch ({metric})")
            status = "+".join(dict.fromkeys(issues)) or "correct"
            rows.append(Row(ann, sample, status, _worst(sevs), g, p, s, metric, "; ".join(details), _obj_key(g),
                            frozenset(_cfg_for(cfg, g.label, "ignore_attrs"))))

        for gi, g in enumerate(g_objs):
            if gi in used_g:
                continue
            best = max((similarity(g, p, cfg) for p in p_objs), key=lambda x: x[0], default=(0.0, ""))
            hint = f" (object gần nhất {best[1]})" if best[0] > 0 else ""
            rows.append(Row(ann, sample, "missing", _sev(cfg, "missing"), g, None, None, "",
                            f"annotator không vẽ {g.short()}{hint}", _obj_key(g)))
        for pi, p in enumerate(p_objs):
            if pi in used_p:
                continue
            if any(coverage(p, r) >= 0.5 for r in g_ign):
                rows.append(Row(ann, sample, "in_ignore", "", None, p, None, "",
                                "nằm trong vùng ignore của GT — không tính", _obj_key(p)))
                continue
            rows.append(Row(ann, sample, "extra", _sev(cfg, "extra"), None, p, None, "",
                            f"annotator vẽ thêm {p.short()} không có trong GT", _obj_key(p)))

        # tag cả ảnh
        g_tags = Counter(t.label for t in gt.tags.get(sample, []))
        p_tags = Counter(t.label for t in pred.tags.get(sample, [])) if sample in pred.samples else Counter()
        for label in sorted(set(g_tags) | set(p_tags)):
            gn, pn = g_tags[label], p_tags[label]
            if gn and pn:
                rows.append(Row(ann, sample, "correct", "", None, None, None, "tag", f"tag {label}",
                                f"{sample}#tag:{label}"))
            elif gn:
                kind = "missing_escalation" if label in cfg["escalate_tags"] else "tag_missing"
                rows.append(Row(ann, sample, kind, _sev(cfg, kind), None, None, None, "tag",
                                f"GT có tag {label}, annotator không", f"{sample}#tag:{label}"))
            else:
                kind = "extra_escalation" if label in cfg["escalate_tags"] else "tag_extra"
                rows.append(Row(ann, sample, kind, _sev(cfg, kind), None, None, None, "tag",
                                f"annotator gắn tag {label}, GT không có", f"{sample}#tag:{label}"))
    return rows, warnings


def _kind_ok(declared: str, kind: str) -> bool:
    return {"rectangle": "box"}.get(declared, declared) == kind


# ─────────────────────────── edge-case candidates ───────────────────────────

# tín hiệu "annotator phân vân / thấy thứ GT không có" → nhiều khả năng rule chưa đủ
UNCERTAIN = {"extra", "extra_escalation", "annotator_unknown", "tag_extra"}
DEVIATION = {"missing", "wrong_label", "wrong_attr", "unassigned_attr", "missing_escalation", "tag_missing"}


def edge_candidates(rows: List[Row], annotators: List[str], gt: Doc, cfg: dict) -> List[dict]:
    by_key: Dict[str, List[Row]] = defaultdict(list)
    extras: List[Tuple[str, Row]] = []  # object thừa của các annotator khác nhau được gộp theo IoU
    for r in rows:
        if r.status in ("correct", "in_ignore", "out_of_scope", "schema"):
            continue
        if r.status == "extra" and r.pred is not None:
            same = next((k for k, first in extras if first.sample == r.sample and first.annotator != r.annotator
                         and similarity(first.pred, r.pred, cfg)[0] >= _cfg_for(cfg, first.pred.label, "iou_match")),
                        None)
            if same is None:
                extras.append((r.key, r))
            by_key[same or r.key].append(r)
            continue
        by_key[r.key].append(r)
    out = []
    n = len(annotators)
    for key, rs in by_key.items():
        who = sorted({r.annotator for r in rs})
        statuses = sorted({s for r in rs for s in r.status.split("+")})
        sample = rs[0].sample
        signals = []
        if len(who) >= 2:
            signals.append(f"{len(who)}/{n} annotator cùng lệch GT")
        if set(statuses) & UNCERTAIN:
            signals.append("annotator phân vân / thấy object GT không có")
        g = next((r.gt for r in rs if r.gt is not None), None)
        small = False
        if g is not None and sample in gt.sizes and all(gt.sizes[sample]):
            w, h = gt.sizes[sample]
            small = g.area() / float(w * h) < cfg["small_area_ratio"]
            if small and "missing" in statuses:
                signals.append("object rất nhỏ bị bỏ sót")
        if not signals:
            continue  # một người lệch, không có dấu hiệu phân vân → nhiều khả năng execution_error, xem objects.csv
        if len(who) >= 2 and n >= 2:
            diag = "guideline_gap"
            action = "revise_rule (hoặc kiểm lại gold — nếu mọi người cùng làm khác, gold có thể sai)"
        elif "extra" in statuses or "tag_extra" in statuses:
            diag = "guideline_gap"
            action = "kiểm gold có sót object không; nếu không sót → thêm rule inclusion/exclusion"
        elif set(statuses) & {"extra_escalation", "annotator_unknown"}:
            diag = "data_ambiguity"
            action = "add_example hoặc add_escalation (ghi rõ khi nào được dùng unknown/escalate)"
        else:
            diag = "data_ambiguity"
            action = "add_example (ví dụ object nhỏ/xa) hoặc tag small_far"
        tags = ["edge"] + (["small_far"] if small else []) + (["ambiguity"] if diag == "data_ambiguity" else [])
        out.append({
            "sample_id": sample,
            "object": key.split("#", 1)[1],
            "statuses": "+".join(statuses),
            "annotators": ";".join(who),
            "gt": g.short() if g is not None else "",
            "annotator_values": " || ".join(f"{r.annotator}: {r.pred.short() if r.pred else '—'} ({r.detail})" for r in rs),
            "signal": "; ".join(signals),
            "suggested_diagnosis": diag,
            "suggested_action": action,
            "suggested_tags": ";".join(tags),
            "worst_severity": _worst([r.severity for r in rs]),
        })
    out.sort(key=lambda d: (SEV_ORDER.get(d["worst_severity"], 9), -d["annotators"].count(";"), d["sample_id"]))
    return out


# ─────────────────────────── metrics + report ───────────────────────────


def metrics(rows: List[Row]) -> dict:
    shape_rows = [r for r in rows if r.metric != "tag" and r.status not in ("in_ignore", "out_of_scope", "schema")]
    matched = [r for r in shape_rows if r.gt is not None and r.pred is not None]
    n_gt = sum(1 for r in shape_rows if r.gt is not None)
    n_pred = sum(1 for r in shape_rows if r.pred is not None)
    label_ok = sum(1 for r in matched if r.gt.label == r.pred.label)
    attr_tot, attr_ok = Counter(), Counter()
    for r in matched:
        if r.gt.label != r.pred.label:
            continue
        for name, gv in r.gt.attrs.items():
            if name in r.ignored_attrs:
                continue
            attr_tot[name] += 1
            pv = r.pred.attrs.get(name, UNDEF)
            attr_ok[name] += int(pv == gv or _norm(pv) == _norm(gv))
    tag_rows = [r for r in rows if r.metric == "tag"]
    full_ok = sum(1 for r in shape_rows if r.status == "correct") + sum(1 for r in tag_rows if r.status == "correct")
    total_units = len(shape_rows) + len(tag_rows)
    sev = Counter(r.severity for r in rows if r.severity)
    status = Counter(s for r in rows if r.status != "correct" for s in r.status.split("+"))
    scores = [r.score for r in matched if r.score is not None]
    pct = lambda a, b: 100.0 * a / b if b else float("nan")
    return {
        "n_gt": n_gt, "n_pred": n_pred, "matched": len(matched),
        "precision": pct(len(matched), n_pred), "recall": pct(len(matched), n_gt),
        "label_acc": pct(label_ok, len(matched)),
        "attr_acc": {k: pct(attr_ok[k], attr_tot[k]) for k in sorted(attr_tot)},
        "mean_geo": (sum(scores) / len(scores)) if scores else float("nan"),
        "fully_correct": pct(full_ok, total_units), "full_ok": full_ok, "units": total_units,
        "severity": sev, "status": status,
    }


def _f(v: float) -> str:
    return "—" if v != v else f"{v:.1f}%"


def _g(v: float) -> str:
    return "—" if v != v else f"{v:.2f}"


VI_STATUS = {
    "missing": "thiếu (GT có, annotator không vẽ)",
    "extra": "thừa (annotator vẽ, GT không có)",
    "wrong_label": "sai label",
    "wrong_attr": "sai attribute",
    "unassigned_attr": "attribute còn __undefined__",
    "annotator_unknown": "annotator chọn unknown",
    "geometry_loose": "geometry lệch (khớp nhưng chưa sát)",
    "missing_escalation": "không escalate khi GT escalate",
    "extra_escalation": "escalate khi GT không",
    "tag_missing": "thiếu tag ảnh",
    "tag_extra": "thừa tag ảnh",
    "schema": "sai schema (label/shape không khớp labels JSON)",
    "in_ignore": "nằm trong vùng ignore (không tính)",
    "out_of_scope": "ngoài phạm vi GT (không tính)",
}


def write_report(out: Path, gt: Doc, all_rows: List[Row], per_ann: Dict[str, dict], cands: List[dict],
                 warnings: List[str], cfg: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "objects.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["annotator", "sample_id", "status", "severity", "gt", "pred", "geo_score", "metric", "detail",
                    "gt_bbox", "pred_bbox"])
        for r in sorted(all_rows, key=lambda r: (r.sample, r.key, r.annotator)):
            bb = lambda o: ",".join(str(int(v)) for v in o.bbox()) if o is not None and o.points else ""
            w.writerow([r.annotator, r.sample, r.status, r.severity, r.gt.short() if r.gt else "",
                        r.pred.short() if r.pred else "", f"{r.score:.3f}" if r.score is not None else "",
                        r.metric, r.detail, bb(r.gt), bb(r.pred)])
    fields = ["sample_id", "object", "statuses", "annotators", "gt", "annotator_values", "signal",
              "suggested_diagnosis", "suggested_action", "suggested_tags", "worst_severity"]
    with (out / "edge_case_candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cands)

    L = [f"# Báo cáo chấm annotator so với GT", "",
         f"GT: `{gt.name}` · {len(gt.samples)} ảnh · "
         f"{sum(len(v) for v in gt.objects.values())} object · {sum(len(v) for v in gt.tags.values())} tag", "",
         f"Ngưỡng: khớp khi điểm ≥ {cfg['iou_match']}, geometry tốt khi ≥ {cfg['iou_good']} "
         f"(polyline tol {cfg['polyline_tol_px']}px). Severity lấy từ config.", ""]
    if warnings:
        L += ["**Cảnh báo:**", ""] + [f"- {w}" for w in warnings] + [""]
    L += ["## Tổng quan theo annotator", "",
          "| Annotator | Đúng hoàn toàn | Precision | Recall | Label đúng | Geo TB | critical | major | minor | question |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for ann, m in per_ann.items():
        s = m["severity"]
        L.append(f"| {ann} | {m['full_ok']}/{m['units']} ({_f(m['fully_correct'])}) | {_f(m['precision'])} | "
                 f"{_f(m['recall'])} | {_f(m['label_acc'])} | "
                 f"{_g(m['mean_geo'])} | "
                 f"{s['critical']} | {s['major']} | {s['minor']} | {s['question']} |")
    L += ["", "- **Đúng hoàn toàn**: object GT được vẽ đúng label + mọi attribute + geometry đủ sát (tag ảnh cũng tính).",
          "- **Precision** = object annotator khớp GT / object annotator vẽ · **Recall** = khớp / object GT.",
          "- **critical** > 0 nghĩa là có *critical escape* — đọc kỹ các dòng đó trước.", ""]
    for ann, m in per_ann.items():
        L += [f"### {ann}", ""]
        if m["attr_acc"]:
            L.append("Độ đúng attribute (trên object khớp cùng label): " +
                     ", ".join(f"`{k}` {_f(v)}" for k, v in m["attr_acc"].items()))
            L.append("")
        if m["status"]:
            L += [f"- {VI_STATUS.get(k, k)}: **{v}**" for k, v in m["status"].most_common()]
        else:
            L.append("- Không có lỗi nào so với GT.")
        L.append("")
        errs = [r for r in all_rows if r.annotator == ann and r.status not in ("correct", "in_ignore", "out_of_scope")]
        errs.sort(key=lambda r: (SEV_ORDER.get(r.severity, 9), r.sample))
        if errs:
            L += ["| Ảnh | Lỗi | Severity | Chi tiết |", "|---|---|---|---|"]
            L += [f"| {r.sample} | {r.status} | {r.severity} | {r.detail} |" for r in errs[:60]]
            if len(errs) > 60:
                L.append(f"| … | còn {len(errs) - 60} dòng — xem objects.csv | | |")
            L.append("")
    L += ["## Ứng viên edge case mới", "",
          "Chỉ liệt kê chỗ có **tín hiệu phân vân** (nhiều annotator cùng lệch GT, annotator vẽ thứ GT không có, "
          "escalate/unknown khi GT chắc chắn, object rất nhỏ bị sót). Lỗi lẻ của một người không kèm tín hiệu "
          "nào thì nhiều khả năng là `execution_error` → xem bảng lỗi ở trên.", "",
          "Chẩn đoán là **gợi ý** theo enum của lab (`guideline_gap` / `data_ambiguity` / `execution_error`) — "
          "nhóm phải mở ảnh xem và tự kết luận. Trước khi sửa guideline, kiểm xem có phải **gold sai** không.", ""]
    if cands:
        L += ["| Ảnh | Object | Tín hiệu | GT | Annotator | Gợi ý chẩn đoán | Gợi ý xử lý |",
              "|---|---|---|---|---|---|---|"]
        for c in cands:
            L.append(f"| {c['sample_id']} | {c['object']} | {c['signal']} | {c['gt'] or '—'} | "
                     f"{c['annotator_values'].replace(' || ', '<br>')} | {c['suggested_diagnosis']} | {c['suggested_action']} |")
    else:
        L.append("Không có ứng viên nào.")
    L += ["", "File chi tiết: `objects.csv` (mỗi object × annotator một dòng), `edge_case_candidates.csv`, "
          "`viz/` (ảnh overlay nếu chạy với `--images`: xanh lá = đúng, xanh dương = GT bị thiếu/sai, vàng = annotator khớp GT nhưng có lỗi, đỏ = annotator vẽ thừa)."]
    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def draw_overlays(out: Path, images: Path, gt: Doc, rows: List[Row]) -> int:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("! Không có Pillow → bỏ qua ảnh overlay", file=sys.stderr)
        return 0
    files = {p.stem: p for p in images.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")}
    count = 0
    by_ann: Dict[str, List[Row]] = defaultdict(list)
    for r in rows:
        by_ann[r.annotator].append(r)
    for ann, rs in by_ann.items():
        d = out / "viz" / ann
        d.mkdir(parents=True, exist_ok=True)
        for sample in gt.samples:
            if sample not in files or not any(r.sample == sample for r in rs):
                continue
            img = Image.open(files[sample]).convert("RGB")
            draw = ImageDraw.Draw(img)
            for r in rs:
                if r.sample != sample:
                    continue
                if r.gt is not None:
                    _draw(draw, r.gt, (0, 200, 0) if r.status == "correct" else (0, 160, 255), 3)
                if r.pred is not None:
                    color = ((0, 200, 0) if r.status == "correct" else (255, 200, 0) if r.gt is not None
                             else (150, 150, 150) if r.status in ("in_ignore", "out_of_scope") else (255, 40, 40))
                    _draw(draw, r.pred, color, 2)
                    if r.status != "correct":
                        x1, y1, _, _ = r.pred.bbox()
                        draw.text((x1 + 2, max(0, y1 - 12)), r.status, fill=color)
                elif r.gt is not None and r.status != "correct":
                    x1, y1, _, _ = r.gt.bbox()
                    draw.text((x1 + 2, max(0, y1 - 12)), r.status, fill=(0, 160, 255))
            img.save(d / f"{sample}.jpg", quality=90)
            count += 1
    return count


def _draw(draw, o: Obj, color, width) -> None:
    if o.kind in ("polygon",) and len(o.points) >= 3:
        draw.line(o.points + [o.points[0]], fill=color, width=width)
    elif o.kind == "polyline" and len(o.points) >= 2:
        draw.line(o.points, fill=color, width=width)
    elif o.kind == "points":
        for x, y in o.points:
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], outline=color, width=width)
    elif o.points:
        draw.rectangle(o.bbox(), outline=color, width=width)


# ─────────────────────────── CLI ───────────────────────────


def load_config(path: Optional[Path]) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        user = json.loads(path.read_text(encoding="utf-8"))
        sev = user.pop("severity", {})
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
        cfg["severity"].update(sev)
    return cfg


def load_schema(path: Optional[Path]) -> Dict[str, dict]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["name"]: item for item in data if isinstance(item, dict) and "name" in item}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", required=True, type=Path, help="export GT/gold (CVAT for images 1.1 .zip/.xml)")
    ap.add_argument("--pred", required=True, nargs="+", type=Path, help="export của annotator (1 hoặc nhiều)")
    ap.add_argument("--labels", type=Path, help="03_cvat_labels.json để kiểm schema (tuỳ chọn)")
    ap.add_argument("--config", type=Path, help="eval_config.json (ngưỡng, severity, label ignore, escalate)")
    ap.add_argument("--images", type=Path, help="thư mục ảnh gốc → vẽ overlay vào <out>/viz/")
    ap.add_argument("--out", type=Path, default=Path("report"))
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    schema = load_schema(args.labels)
    gt = parse_export(args.gt)
    all_rows, warnings, per_ann, names = [], [], {}, []
    for p in args.pred:
        doc = parse_export(p)
        if not any(doc.objects.values()) and not any(doc.tags.values()):
            warnings.append(f"{doc.name}: export trống (chưa gán nhãn gì) — bỏ qua, không chấm")
            continue
        if doc.name in per_ann:
            doc.name = f"{doc.name}_{len(per_ann)}"
        rows, warn = compare(gt, doc, cfg, schema)
        all_rows += rows
        warnings += warn
        per_ann[doc.name] = metrics(rows)
        names.append(doc.name)
    cands = edge_candidates(all_rows, names, gt, cfg)
    write_report(args.out, gt, all_rows, per_ann, cands, warnings, cfg)
    n_viz = draw_overlays(args.out, args.images, gt, all_rows) if args.images else 0

    for w in warnings:
        print(f"! {w}")
    for ann, m in per_ann.items():
        s = m["severity"]
        print(f"{ann:>16}: đúng hoàn toàn {m['full_ok']}/{m['units']} · P {_f(m['precision'])} · "
              f"R {_f(m['recall'])} · critical {s['critical']} · major {s['major']} · minor {s['minor']}")
    print(f"Ứng viên edge case: {len(cands)}")
    print(f"→ {args.out / 'summary.md'}" + (f" · {n_viz} ảnh overlay trong {args.out / 'viz'}" if n_viz else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
