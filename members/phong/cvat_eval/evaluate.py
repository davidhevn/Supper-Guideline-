#!/usr/bin/env python3
"""So bài của người gán với GT (bounding box biển báo) → đúng / sai / thiếu / thừa + ứng viên edge case.

Chạy offline, đọc export "CVAT for images 1.1" (.zip / annotations.xml) hoặc COCO 1.0 (.json), không cần CVAT.
Chỉ cần Python 3; Pillow (cài bằng `python sign.py install`) để vẽ ảnh overlay.

    python evaluate.py --gt ../../../data/ground_truth/gt.json --pred an.zip binh.zip \
        --labels schema/labels_v1.2.json --config schema/eval_v1.2.json --images ../../../data/raw --out reports/x/

Khác cvat_parser.py của nhóm: ghép box người gán ↔ GT theo IoU trên từng ảnh (không theo id), nên đọc được export
CVAT thật. Tool chỉ gợi ý nguyên nhân; kết luận "guideline thiếu" hay "làm sai" vẫn là của nhóm.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

UNDEF = "__undefined__"
CVAT_META_ATTRS = {"rotation", "track_id", "keyframe"}

DEFAULT_CONFIG = {
    "iou_match": 0.5,         # IoU ≥ ngưỡng này thì coi là cùng một biển
    "iou_good": 0.7,          # IoU < ngưỡng này thì báo geometry_loose (= IOU_THRESHOLD của cvat_parser.py)
    "unknown_values": ["unknown", "uncertain"],
    "ignore_attrs": [],       # attribute GT không có (vd GT GTSDB không có readable) → không so
    "normalize_text": True,   # "Speed limit 50" = "speed_limit_50"
    "small_area_ratio": 0.0006,  # biển nhỏ hơn tỉ lệ này của ảnh mà bị sót → gợi ý small_far
    "severity": {
        "missing": "major",
        "extra": "minor",
        "wrong_label": "critical",
        "wrong_attr": "minor",
        "unassigned_attr": "major",
        "annotator_unknown": "question",
        "geometry_loose": "minor",
        "schema": "minor",
    },
}


# ─────────────────────────── đọc CVAT XML / COCO ───────────────────────────


@dataclass
class Obj:
    sample: str
    label: str
    box: Tuple[float, float, float, float]  # x1, y1, x2, y2
    attrs: Dict[str, str]

    def area(self) -> float:
        x1, y1, x2, y2 = self.box
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    def short(self) -> str:
        attrs = ";".join(f"{k}={v}" for k, v in sorted(self.attrs.items()))
        return f"{self.label}[{attrs}]" if attrs else self.label


@dataclass
class Doc:
    name: str
    objects: Dict[str, List[Obj]] = field(default_factory=lambda: defaultdict(list))
    sizes: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    samples: List[str] = field(default_factory=list)


def _attr_str(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return UNDEF if v is None or v == "" else str(v)


def parse_coco(path: Path) -> Doc:
    """COCO 1.0 (export CVAT hoặc file GT trong data/ground_truth)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if "images" not in data or "categories" not in data:
        raise SystemExit(f"{path}: JSON không phải COCO (cần images + categories + annotations)")
    doc = Doc(name=path.stem)
    cats = {c["id"]: c["name"] for c in data["categories"]}
    by_id = {}
    for im in data["images"]:
        sample = Path(im["file_name"]).stem
        by_id[im["id"]] = sample
        doc.samples.append(sample)
        doc.sizes[sample] = (int(im.get("width", 0)), int(im.get("height", 0)))
    for a in data.get("annotations", []):
        x, y, w, h = a["bbox"]
        # export COCO của CVAT tự thêm rotation/track_id/keyframe — không phải attribute của label
        attrs = {k: _attr_str(v) for k, v in (a.get("attributes") or {}).items() if k not in CVAT_META_ATTRS}
        sample = by_id[a["image_id"]]
        doc.objects[sample].append(Obj(sample, cats.get(a["category_id"], "?"), (x, y, x + w, y + h), attrs))
    return doc


def parse_export(path: Path) -> Doc:
    if path.suffix.lower() == ".json":
        return parse_coco(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            members = [n for n in zf.namelist() if Path(n).name == "annotations.xml"]
            if len(members) != 1:
                raise SystemExit(f"{path}: ZIP phải chứa đúng một annotations.xml (export CVAT for images 1.1)")
            root = ET.fromstring(zf.read(members[0]))
    else:
        root = ET.fromstring(path.read_bytes())
    doc = Doc(name=path.stem)
    for image in root.findall("image"):
        sample = Path(image.get("name", "")).stem
        doc.samples.append(sample)
        doc.sizes[sample] = (int(image.get("width", 0)), int(image.get("height", 0)))
        for b in image.findall("box"):
            attrs = {a.get("name", ""): (a.text if a.text not in (None, "") else UNDEF) for a in b.findall("attribute")}
            box = tuple(float(b.get(k)) for k in ("xtl", "ytl", "xbr", "ybr"))
            doc.objects[sample].append(Obj(sample, b.get("label", ""), box, attrs))
    if not doc.samples:
        raise SystemExit(f"{path}: không có <image> nào — hãy export bằng CVAT for images 1.1")
    return doc


def iou(a: Obj, b: Obj) -> float:
    ax1, ay1, ax2, ay2 = a.box
    bx1, by1, bx2, by2 = b.box
    iw, ih = max(0.0, min(ax2, bx2) - max(ax1, bx1)), max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = a.area() + b.area() - inter
    return inter / union if union > 0 else 0.0


# ─────────────────────────── so một người với GT ───────────────────────────


@dataclass
class Row:
    annotator: str
    sample: str
    status: str            # correct | missing | extra | wrong_label | wrong_attr | ... (ghép bằng '+')
    severity: str
    gt: Optional[Obj]
    pred: Optional[Obj]
    score: Optional[float]
    detail: str
    key: str               # định danh biển GT để gộp nhiều người


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


def _key(o: Obj) -> str:
    x1, y1, x2, y2 = o.box
    return f"{o.sample}#{o.label}@{int(x1)},{int(y1)},{int(x2)},{int(y2)}"


def _same(cfg: dict, gv: str, pv: str) -> bool:
    return gv == pv or (cfg["normalize_text"] and _norm(gv) == _norm(pv))


def compare(gt: Doc, pred: Doc, cfg: dict, labels: Sequence[str]) -> Tuple[List[Row], List[str]]:
    rows: List[Row] = []
    warnings: List[str] = []
    ann = pred.name
    skip = set(cfg["ignore_attrs"])
    unknowns = set(cfg["unknown_values"])

    # GOLD có thể là cả kho ảnh, còn task người gán chỉ là một phần → chỉ chấm ảnh có ở cả hai
    missing = [s for s in gt.samples if s not in pred.samples]
    if missing:
        warnings.append(f"{ann}: {len(missing)} ảnh GT không có trong bài, bỏ qua: {', '.join(missing)}")
    extra = [s for s in pred.samples if s not in gt.samples]
    if extra:
        warnings.append(f"{ann}: có ảnh không nằm trong GT, bỏ qua: {', '.join(extra)}")

    for sample in [s for s in gt.samples if s in pred.samples]:
        g_objs = gt.objects.get(sample, [])
        p_objs = pred.objects.get(sample, [])
        for p in p_objs:
            if labels and p.label not in labels:
                rows.append(Row(ann, sample, "schema", _sev(cfg, "schema"), None, p, None,
                                f"label '{p.label}' không có trong labels JSON", _key(p)))

        # ghép cặp greedy theo IoU, ưu tiên cùng label
        cands = sorted(((iou(g, p) + (0.05 if g.label == p.label else 0.0), gi, pi)
                        for gi, g in enumerate(g_objs) for pi, p in enumerate(p_objs)
                        if iou(g, p) >= cfg["iou_match"]), reverse=True)
        used_g, used_p = set(), set()
        for _, gi, pi in cands:
            if gi in used_g or pi in used_p:
                continue
            used_g.add(gi)
            used_p.add(pi)
            g, p = g_objs[gi], p_objs[pi]
            s = iou(g, p)
            issues, sevs, details = [], [], []
            if g.label != p.label:
                issues.append("wrong_label")
                sevs.append(_sev(cfg, "wrong_label"))
                details.append(f"label {g.label}→{p.label}")
            else:
                for name in sorted((set(g.attrs) | set(p.attrs)) - skip):
                    gv, pv = g.attrs.get(name, UNDEF), p.attrs.get(name, UNDEF)
                    if _same(cfg, gv, pv):
                        continue
                    if pv == UNDEF:
                        kind, text = "unassigned_attr", f"{name} chưa gán (GT={gv})"
                    elif pv in unknowns:
                        kind, text = "annotator_unknown", f"{name}: GT={gv}, người gán={pv}"
                    else:
                        kind, text = "wrong_attr", f"{name}: GT={gv}, người gán={pv}"
                    issues.append(kind)
                    # chọn unknown là đường thoát guideline cho phép → giữ mức "question", không lấy mức của attribute
                    sevs.append(_sev(cfg, kind, None if kind == "annotator_unknown" else name))
                    details.append(text)
            if s < cfg["iou_good"]:
                issues.append("geometry_loose")
                sevs.append(_sev(cfg, "geometry_loose"))
                details.append(f"box lệch (IoU={s:.2f})")
            rows.append(Row(ann, sample, "+".join(dict.fromkeys(issues)) or "correct", _worst(sevs), g, p, s,
                            "; ".join(details), _key(g)))

        for gi, g in enumerate(g_objs):
            if gi not in used_g:
                best = max((iou(g, p) for p in p_objs), default=0.0)
                hint = f" (box gần nhất IoU={best:.2f})" if best > 0 else ""
                rows.append(Row(ann, sample, "missing", _sev(cfg, "missing"), g, None, None,
                                f"không vẽ {g.short()}{hint}", _key(g)))
        for pi, p in enumerate(p_objs):
            if pi not in used_p:
                rows.append(Row(ann, sample, "extra", _sev(cfg, "extra"), None, p, None,
                                f"vẽ thêm {p.short()} không có trong GT", _key(p)))
    return rows, warnings


# ─────────────────────────── ứng viên edge case ───────────────────────────

UNCERTAIN = {"extra", "annotator_unknown"}  # người gán phân vân / thấy thứ GT không có


def edge_candidates(rows: List[Row], annotators: List[str], gt: Doc, cfg: dict) -> List[dict]:
    by_key: Dict[str, List[Row]] = defaultdict(list)
    extras: List[Tuple[str, Row]] = []  # box thừa của nhiều người được gộp theo IoU
    for r in rows:
        if r.status in ("correct", "schema"):
            continue
        if r.status == "extra":
            same = next((k for k, first in extras if first.sample == r.sample and first.annotator != r.annotator
                         and iou(first.pred, r.pred) >= cfg["iou_match"]), None)
            if same is None:
                extras.append((r.key, r))
            by_key[same or r.key].append(r)
        else:
            by_key[r.key].append(r)
    out = []
    n = len(annotators)
    for key, rs in by_key.items():
        who = sorted({r.annotator for r in rs})
        statuses = sorted({s for r in rs for s in r.status.split("+")})
        sample = rs[0].sample
        signals = []
        if len(who) >= 2:
            signals.append(f"{len(who)}/{n} người cùng lệch GT")
        if set(statuses) & UNCERTAIN:
            signals.append("người gán phân vân / thấy biển GT không có")
        g = next((r.gt for r in rs if r.gt is not None), None)
        small = False
        if g is not None and all(gt.sizes.get(sample, (0, 0))):
            w, h = gt.sizes[sample]
            small = g.area() / float(w * h) < cfg["small_area_ratio"]
            if small and "missing" in statuses:
                signals.append("biển rất nhỏ bị sót")
        if not signals:
            continue  # một người lệch, không có dấu hiệu phân vân → nhiều khả năng lỗi thao tác
        if len(who) >= 2:
            diag, action = "guideline_gap", "sửa rule (hoặc kiểm lại GT — mọi người cùng làm khác thì GT có thể sai)"
        elif "extra" in statuses:
            diag, action = "guideline_gap", "kiểm GT có sót biển không; không sót → thêm rule loại trừ (mục 5.3/5.4)"
        elif "annotator_unknown" in statuses:
            diag, action = "data_ambiguity", "thêm ví dụ, ghi rõ khi nào được chọn unknown/uncertain"
        else:
            diag, action = "data_ambiguity", "thêm ví dụ biển nhỏ/xa, hoặc làm rõ ngưỡng 15×15 px"
        out.append({
            "sample_id": sample,
            "object": key.split("#", 1)[1],
            "statuses": "+".join(statuses),
            "annotators": ";".join(who),
            "gt": g.short() if g is not None else "",
            "annotator_values": " || ".join(f"{r.annotator}: {r.pred.short() if r.pred else '—'} ({r.detail})"
                                            for r in rs),
            "signal": "; ".join(signals),
            "suggested_diagnosis": diag,
            "suggested_action": action,
            "suggested_tags": ";".join(["edge"] + (["small_far"] if small else [])),
            "worst_severity": _worst([r.severity for r in rs]),
        })
    out.sort(key=lambda d: (SEV_ORDER.get(d["worst_severity"], 9), -d["annotators"].count(";"), d["sample_id"]))
    return out


# ─────────────────────────── số liệu + báo cáo ───────────────────────────


def metrics(rows: List[Row], cfg: dict) -> dict:
    rs = [r for r in rows if r.status != "schema"]
    matched = [r for r in rs if r.gt is not None and r.pred is not None]
    n_gt = sum(1 for r in rs if r.gt is not None)
    n_pred = sum(1 for r in rs if r.pred is not None)
    attr_tot, attr_ok = Counter(), Counter()
    for r in matched:
        if r.gt.label == r.pred.label:
            for name, gv in r.gt.attrs.items():
                if name not in cfg["ignore_attrs"]:
                    attr_tot[name] += 1
                    attr_ok[name] += int(_same(cfg, gv, r.pred.attrs.get(name, UNDEF)))
    pct = lambda a, b: 100.0 * a / b if b else float("nan")
    ious = [r.score for r in matched]
    full_ok = sum(1 for r in rs if r.status == "correct")
    return {
        "precision": pct(len(matched), n_pred), "recall": pct(len(matched), n_gt),
        "label_acc": pct(sum(1 for r in matched if r.gt.label == r.pred.label), len(matched)),
        "attr_acc": {k: pct(attr_ok[k], attr_tot[k]) for k in sorted(attr_tot)},
        "mean_iou": sum(ious) / len(ious) if ious else float("nan"),
        "full_ok": full_ok, "units": len(rs), "fully_correct": pct(full_ok, len(rs)),
        "severity": Counter(r.severity for r in rows if r.severity),
        "status": Counter(s for r in rows if r.status != "correct" for s in r.status.split("+")),
    }


def _f(v: float, pct: bool = True) -> str:
    return "—" if v != v else (f"{v:.1f}%" if pct else f"{v:.2f}")


VI_STATUS = {
    "missing": "sót biển (GT có, không vẽ)",
    "extra": "box thừa (GT không có)",
    "wrong_label": "sai nhóm biển (label)",
    "wrong_attr": "sai attribute",
    "unassigned_attr": "attribute chưa gán",
    "annotator_unknown": "chọn unknown/uncertain khi GT chắc chắn",
    "geometry_loose": "box lệch (IoU dưới ngưỡng)",
    "schema": "label không có trong labels JSON",
}


def write_report(out: Path, gt: Doc, rows: List[Row], per_ann: Dict[str, dict], cands: List[dict],
                 warnings: List[str], cfg: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    bb = lambda o: ",".join(str(int(v)) for v in o.box) if o is not None else ""
    with (out / "objects.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["annotator", "sample_id", "status", "severity", "gt", "pred", "iou", "detail", "gt_bbox", "pred_bbox"])
        for r in sorted(rows, key=lambda r: (r.sample, r.key, r.annotator)):
            w.writerow([r.annotator, r.sample, r.status, r.severity, r.gt.short() if r.gt else "",
                        r.pred.short() if r.pred else "", f"{r.score:.3f}" if r.score is not None else "",
                        r.detail, bb(r.gt), bb(r.pred)])
    with (out / "edge_case_candidates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sample_id", "object", "statuses", "annotators", "gt", "annotator_values",
                                          "signal", "suggested_diagnosis", "suggested_action", "suggested_tags",
                                          "worst_severity"])
        w.writeheader()
        w.writerows(cands)

    L = ["# Báo cáo chấm người gán so với GT", "",
         f"GT: `{gt.name}` · {len(gt.samples)} ảnh · {sum(len(v) for v in gt.objects.values())} biển. "
         f"Khớp khi IoU ≥ {cfg['iou_match']}, box đạt khi IoU ≥ {cfg['iou_good']}. "
         f"Không chấm: {', '.join(cfg['ignore_attrs']) or '—'}.", ""]
    if warnings:
        L += ["**Cảnh báo:**", ""] + [f"- {w}" for w in warnings] + [""]
    L += ["## Tổng quan", "",
          "| Người gán | Đúng hoàn toàn | Precision | Recall | Label đúng | IoU TB | critical | major | minor | question |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for ann, m in per_ann.items():
        s = m["severity"]
        L.append(f"| {ann} | {m['full_ok']}/{m['units']} ({_f(m['fully_correct'])}) | {_f(m['precision'])} | "
                 f"{_f(m['recall'])} | {_f(m['label_acc'])} | {_f(m['mean_iou'], False)} | "
                 f"{s['critical']} | {s['major']} | {s['minor']} | {s['question']} |")
    L += ["", "- **Đúng hoàn toàn**: biển GT được vẽ đúng nhóm biển + mọi attribute được chấm + box đạt ngưỡng.",
          "- **Precision** = box khớp GT / box đã vẽ · **Recall** = box khớp / biển trong GT.",
          "- **critical** > 0: có lỗi nghiêm trọng (mặc định: sai nhóm biển — bẫy ánh xạ mục 5.2), đọc trước.", ""]
    for ann, m in per_ann.items():
        L += [f"### {ann}", ""]
        if m["attr_acc"]:
            L += ["Độ đúng attribute (trên box khớp cùng label): " +
                  ", ".join(f"`{k}` {_f(v)}" for k, v in m["attr_acc"].items()), ""]
        L += [f"- {VI_STATUS.get(k, k)}: **{v}**" for k, v in m["status"].most_common()] or ["- Không có lỗi."]
        L.append("")
        errs = sorted((r for r in rows if r.annotator == ann and r.status != "correct"),
                      key=lambda r: (SEV_ORDER.get(r.severity, 9), r.sample))
        if errs:
            L += ["| Ảnh | Lỗi | Severity | Chi tiết |", "|---|---|---|---|"]
            L += [f"| {r.sample} | {r.status} | {r.severity} | {r.detail} |" for r in errs[:60]]
            if len(errs) > 60:
                L.append(f"| … | còn {len(errs) - 60} dòng — xem objects.csv | | |")
            L.append("")
    L += ["## Ứng viên edge case mới", "",
          "Chỉ liệt kê chỗ có **tín hiệu phân vân**: nhiều người cùng lệch GT, vẽ biển mà GT không có, chọn "
          "unknown/uncertain khi GT chắc chắn, biển rất nhỏ bị sót. Một người sai lẻ thì nhiều khả năng là lỗi thao "
          "tác → xem bảng lỗi ở trên. Chẩn đoán chỉ là **gợi ý**; kiểm xem có phải **GT sai** trước khi sửa guideline.", ""]
    if cands:
        L += ["| Ảnh | Biển | Tín hiệu | GT | Người gán | Gợi ý chẩn đoán | Gợi ý xử lý |", "|---|---|---|---|---|---|---|"]
        L += [f"| {c['sample_id']} | {c['object']} | {c['signal']} | {c['gt'] or '—'} | "
              f"{c['annotator_values'].replace(' || ', '<br>')} | {c['suggested_diagnosis']} | {c['suggested_action']} |"
              for c in cands]
    else:
        L.append("Không có ứng viên nào.")
    L += ["", "File chi tiết: `objects.csv`, `edge_case_candidates.csv`, `viz/` (xanh lá = đúng, xanh dương = GT bị "
          "sót/sai, vàng = khớp nhưng sai label/attribute/box, đỏ = box thừa)."]
    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def draw_overlays(out: Path, images: Path, gt: Doc, rows: List[Row]) -> int:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("! Không có Pillow → bỏ qua ảnh overlay", file=sys.stderr)
        return 0
    files = {p.stem: p for p in images.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp")}
    by_ann: Dict[str, List[Row]] = defaultdict(list)
    for r in rows:
        by_ann[r.annotator].append(r)
    count = 0
    for ann, rs in by_ann.items():
        d = out / "viz" / ann
        d.mkdir(parents=True, exist_ok=True)
        for sample in gt.samples:
            mine = [r for r in rs if r.sample == sample]
            if sample not in files or not mine:
                continue
            img = Image.open(files[sample]).convert("RGB")
            draw = ImageDraw.Draw(img)
            for r in mine:
                ok = r.status == "correct"
                if r.gt is not None:
                    draw.rectangle(r.gt.box, outline=(0, 200, 0) if ok else (0, 160, 255), width=3)
                if r.pred is not None:
                    color = (0, 200, 0) if ok else (255, 200, 0) if r.gt is not None else (255, 40, 40)
                    draw.rectangle(r.pred.box, outline=color, width=2)
                if not ok:
                    o = r.pred or r.gt
                    draw.text((o.box[0] + 2, max(0, o.box[1] - 12)), r.status,
                              fill=(0, 160, 255) if r.pred is None else color)
            img.save(d / f"{sample}.jpg", quality=90)
            count += 1
    return count


# ─────────────────────────── CLI ───────────────────────────


def load_config(path: Optional[Path]) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        user = json.loads(path.read_text(encoding="utf-8"))
        sev = user.pop("severity", {})
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
        cfg["severity"].update(sev)
    return cfg


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", required=True, type=Path, help="GT: CVAT for images 1.1 (.zip/.xml) hoặc COCO 1.0 (.json)")
    ap.add_argument("--pred", required=True, nargs="+", type=Path, help="bài của người gán (1 hoặc nhiều), cùng định dạng")
    ap.add_argument("--labels", type=Path, help="labels JSON của CVAT để bắt label lạ (tuỳ chọn)")
    ap.add_argument("--config", type=Path, help="cấu hình chấm (schema/eval_*.json)")
    ap.add_argument("--images", type=Path, help="thư mục ảnh → vẽ overlay vào <out>/viz/")
    ap.add_argument("--out", type=Path, default=Path("reports/manual"))
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    labels = [x["name"] for x in json.loads(args.labels.read_text(encoding="utf-8"))] if args.labels else []
    gt = parse_export(args.gt)
    rows, warnings, per_ann = [], [], {}
    for p in args.pred:
        doc = parse_export(p)
        if not any(doc.objects.values()):
            warnings.append(f"{doc.name}: bài trống (chưa gán gì) — bỏ qua, không chấm")
            continue
        if doc.name in per_ann:
            doc.name = f"{doc.name}_{len(per_ann)}"
        r, warn = compare(gt, doc, cfg, labels)
        rows += r
        warnings += warn
        per_ann[doc.name] = metrics(r, cfg)
    cands = edge_candidates(rows, list(per_ann), gt, cfg)
    write_report(args.out, gt, rows, per_ann, cands, warnings, cfg)
    n_viz = draw_overlays(args.out, args.images, gt, rows) if args.images else 0

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
