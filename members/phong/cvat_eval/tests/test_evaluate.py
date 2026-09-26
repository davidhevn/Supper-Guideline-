"""Test evaluate.py bằng export CVAT 1.1 tổng hợp (không cần CVAT). Chạy: python -m pytest tests/"""

import csv
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import evaluate as ev  # noqa: E402

HEAD = '<?xml version="1.0" encoding="utf-8"?><annotations><version>1.1</version>'


def box(label, x1, y1, x2, y2, **attrs):
    a = "".join(f'<attribute name="{k}">{v}</attribute>' for k, v in attrs.items())
    return f'<box label="{label}" source="manual" occluded="0" xtl="{x1}" ytl="{y1}" xbr="{x2}" ybr="{y2}" z_order="0">{a}</box>'


def img(i, name, *items, w=1000, h=600):
    return f'<image id="{i}" name="{name}" width="{w}" height="{h}">{"".join(items)}</image>'


def write(tmp, name, *images, as_zip=False):
    xml = HEAD + "".join(images) + "</annotations>"
    if as_zip:
        p = tmp / f"{name}.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("annotations.xml", xml)
        return p
    p = tmp / f"{name}.xml"
    p.write_text(xml, encoding="utf-8")
    return p


def gold(tmp):
    return write(
        tmp, "gold",
        img(0, "BDD01.jpg",
            box("traffic_light", 100, 100, 130, 170, state="red", needs_review="false"),
            box("traffic_light", 500, 90, 530, 160, state="green", needs_review="false"),
            box("traffic_light", 900, 50, 905, 58, state="red", needs_review="false"),  # rất nhỏ
            '<polyline label="lane" source="manual" occluded="0" points="0,600;400,300" z_order="0"></polyline>'),
        img(1, "BDD02.jpg",
            box("traffic_light", 200, 200, 240, 280, state="yellow", needs_review="true"),
            box("ignore_region", 600, 0, 1000, 300),
            '<tag label="image_escalate" source="manual"></tag>'),
        as_zip=True,
    )


CFG = {"ignore_labels": ["ignore_region"], "escalate_tags": ["image_escalate"],
       "severity": {"attr:state": "critical"}}


def run(tmp, preds):
    cfg = ev.load_config(None)
    cfg.update({k: v for k, v in CFG.items() if k != "severity"})
    cfg["severity"].update(CFG["severity"])
    gt = ev.parse_export(gold(tmp))
    rows, names = [], []
    for p in preds:
        d = ev.parse_export(p)
        r, _ = ev.compare(gt, d, cfg, {})
        rows += r
        names.append(d.name)
    return gt, cfg, rows, names


def statuses(rows, ann):
    return sorted(r.status for r in rows if r.annotator == ann)


def test_perfect_copy_is_all_correct(tmp_path):
    same = gold(tmp_path)
    renamed = tmp_path / "perfect.zip"
    same.rename(renamed)
    gt, cfg, rows, _ = run(tmp_path, [renamed])
    assert set(r.status for r in rows) == {"correct"}
    m = ev.metrics(rows)
    assert m["full_ok"] == m["units"] == 6  # 4 object + 1 object ảnh 2 + 1 tag
    assert m["precision"] == m["recall"] == 100.0


def test_error_types(tmp_path):
    an = write(
        tmp_path, "an",
        img(0, "BDD01.jpg",
            box("traffic_light", 102, 101, 131, 171, state="green", needs_review="false"),   # sai state → critical
            box("traffic_light", 505, 100, 535, 165, state="green", needs_review="false"),   # IoU≈0.59 → loose
            '<polyline label="lane" source="manual" occluded="0" points="5,600;405,300" z_order="0"></polyline>',
            box("traffic_light", 300, 300, 330, 360, state="red", needs_review="false")),    # thừa
        img(1, "BDD02.jpg",
            box("traffic_light", 200, 200, 240, 280, state="__undefined__", needs_review="false"),
            box("traffic_light", 700, 50, 730, 100, state="red", needs_review="false")),    # trong vùng ignore
    )
    gt, cfg, rows, names = run(tmp_path, [an])
    by = {(r.sample, r.status) for r in rows}
    assert ("BDD01", "wrong_attr") in by
    assert ("BDD01", "geometry_loose") in by
    assert ("BDD01", "missing") in by           # đèn nhỏ 900,50
    assert ("BDD01", "extra") in by
    assert any(r.sample == "BDD02" and set(r.status.split("+")) == {"unassigned_attr", "missing_escalation"}
               for r in rows)
    assert ("BDD02", "in_ignore") in by
    assert ("BDD02", "missing_escalation") in by  # tag ảnh image_escalate
    crit = [r for r in rows if r.severity == "critical"]
    # sai state và state còn __undefined__ đều là critical escape vì attr:state = critical
    assert len(crit) == 2 and any("state: GT=red" in r.detail for r in crit)
    lane = [r for r in rows if r.gt is not None and r.gt.label == "lane"]
    assert lane[0].status == "correct"


def test_wrong_label_and_consensus_edge_case(tmp_path):
    preds = []
    for name in ("an", "binh"):
        preds.append(write(
            tmp_path, name,
            img(0, "BDD01.jpg",
                box("traffic_sign", 100, 100, 130, 170),                        # cả hai gọi là biển báo
                box("traffic_light", 500, 90, 530, 160, state="green", needs_review="false"),
                box("traffic_light", 900, 50, 905, 58, state="red", needs_review="false"),
                '<polyline label="lane" source="manual" occluded="0" points="0,600;400,300" z_order="0"></polyline>'),
            img(1, "BDD02.jpg",
                box("traffic_light", 200, 200, 240, 280, state="yellow", needs_review="true"),
                '<tag label="image_escalate" source="manual"></tag>'),
        ))
    gt, cfg, rows, names = run(tmp_path, preds)
    assert statuses(rows, "an").count("wrong_label") == 1
    cands = ev.edge_candidates(rows, names, gt, cfg)
    assert len(cands) == 1
    c = cands[0]
    assert c["sample_id"] == "BDD01" and c["annotators"] == "an;binh"
    assert c["suggested_diagnosis"] == "guideline_gap"


def test_single_execution_error_not_candidate(tmp_path):
    an = write(
        tmp_path, "an",
        img(0, "BDD01.jpg",
            box("traffic_light", 100, 100, 130, 170, state="green", needs_review="false"),
            box("traffic_light", 500, 90, 530, 160, state="green", needs_review="false"),
            box("traffic_light", 900, 50, 905, 58, state="red", needs_review="false"),
            '<polyline label="lane" source="manual" occluded="0" points="0,600;400,300" z_order="0"></polyline>'),
        img(1, "BDD02.jpg",
            box("traffic_light", 200, 200, 240, 280, state="yellow", needs_review="true"),
            '<tag label="image_escalate" source="manual"></tag>'),
    )
    gt, cfg, rows, names = run(tmp_path, [an])
    assert ev.edge_candidates(rows, names, gt, cfg) == []


def test_polygon_iou_and_schema(tmp_path):
    g = write(tmp_path, "g", img(0, "A.jpg",
              '<polygon label="road" source="manual" occluded="0" points="0,0;100,0;100,100;0,100" z_order="0"></polygon>'))
    p = write(tmp_path, "p", img(0, "A.jpg",
              '<polygon label="road" source="manual" occluded="0" points="0,0;100,0;100,50;0,50" z_order="0"></polygon>',
              box("road", 500, 500, 520, 520)))
    cfg = ev.load_config(None)
    schema = {"road": {"name": "road", "type": "polygon"}}
    rows, _ = ev.compare(ev.parse_export(g), ev.parse_export(p), cfg, schema)
    pair = [r for r in rows if r.gt is not None][0]
    assert abs(pair.score - 0.5) < 0.03 and "geometry_loose" in pair.status
    assert any(r.status == "schema" and "khai báo polygon" in r.detail for r in rows)


def test_cli_writes_report(tmp_path):
    g = gold(tmp_path)
    an = write(tmp_path, "an", img(0, "BDD01.jpg"), img(1, "BDD02.jpg"))
    out = tmp_path / "rep"
    assert ev.main(["--gt", str(g), "--pred", str(an), "--out", str(out)]) == 0
    text = (out / "summary.md").read_text(encoding="utf-8")
    assert "Tổng quan theo annotator" in text
    # bài trống (chưa gán gì) bị bỏ qua thay vì chấm thành "thiếu hết"
    assert "export trống" in text
    assert list(csv.DictReader((out / "objects.csv").open(encoding="utf-8"))) == []


def test_extras_from_two_annotators_merge_by_iou(tmp_path):
    preds = []
    for name, dx in (("an", 0), ("binh", 4)):
        preds.append(write(
            tmp_path, name,
            img(0, "BDD01.jpg",
                box("traffic_light", 100, 100, 130, 170, state="red", needs_review="false"),
                box("traffic_light", 500, 90, 530, 160, state="green", needs_review="false"),
                box("traffic_light", 900, 50, 905, 58, state="red", needs_review="false"),
                '<polyline label="lane" source="manual" occluded="0" points="0,600;400,300" z_order="0"></polyline>',
                box("traffic_light", 300 + dx, 300, 330 + dx, 360, state="red", needs_review="false")),
            img(1, "BDD02.jpg",
                box("traffic_light", 200, 200, 240, 280, state="yellow", needs_review="true"),
                '<tag label="image_escalate" source="manual"></tag>'),
        ))
    gt, cfg, rows, names = run(tmp_path, preds)
    cands = ev.edge_candidates(rows, names, gt, cfg)
    assert len(cands) == 1 and cands[0]["annotators"] == "an;binh" and cands[0]["statuses"] == "extra"


def test_ignore_attrs_and_pred_filter(tmp_path):
    line = ('<polyline label="lane_marking" source="manual" occluded="0" points="0,600;400,300" z_order="0">'
            '<attribute name="laneTypes">{}</attribute></polyline>')
    g = write(tmp_path, "g", img(0, "A.jpg", line.format("road curb"),
              box("traffic_light", 100, 100, 130, 170, state="unknown")))
    p = write(tmp_path, "p", img(0, "A.jpg", line.format("road curb"),
              '<polyline label="lane_marking" source="manual" occluded="0" points="600,600;700,300" z_order="0">'
              '<attribute name="laneTypes">single white</attribute></polyline>',
              box("traffic_light", 100, 100, 130, 170, state="red")))
    cfg = ev.load_config(None)
    cfg["pred_filter"] = {"lane_marking": {"laneTypes": ["road curb"]}}
    cfg["per_label"] = {"traffic_light": {"ignore_attrs": ["state"]}}
    rows, _ = ev.compare(ev.parse_export(g), ev.parse_export(p), cfg, {})
    st = sorted(r.status for r in rows)
    assert st == ["correct", "correct", "out_of_scope"]
    m = ev.metrics(rows)
    assert m["precision"] == 100.0 and "state" not in m["attr_acc"]


def test_pred_on_subset_of_gold_images(tmp_path):
    # task annotator chỉ có BDD02 (một split) → BDD01 của GOLD không bị tính missing
    an = write(tmp_path, "an", img(1, "BDD02.jpg",
               box("traffic_light", 200, 200, 240, 280, state="yellow", needs_review="true"),
               '<tag label="image_escalate" source="manual"></tag>'))
    gt, cfg, rows, names = run(tmp_path, [an])
    assert {r.sample for r in rows} == {"BDD02"}
    assert all(r.status in ("correct", "in_ignore") for r in rows)


def test_normalize_text_attrs(tmp_path):
    def sign(cls):
        return (f'<box label="prohibitory" source="manual" occluded="0" xtl="10" ytl="10" xbr="40" ybr="40" z_order="0">'
                f'<attribute name="sign_class">{cls}</attribute></box>')
    g = write(tmp_path, "g", img(0, "A.png", sign("speed_limit_50")))
    p = write(tmp_path, "p", img(0, "A.png", sign("Speed limit 50")))
    cfg = ev.load_config(None)
    rows, _ = ev.compare(ev.parse_export(g), ev.parse_export(p), cfg, {})
    assert rows[0].status == "wrong_attr"          # mặc định so chính xác
    cfg["normalize_text"] = True
    rows, _ = ev.compare(ev.parse_export(g), ev.parse_export(p), cfg, {})
    assert rows[0].status == "correct"


def test_coco_json_matches_cvat_xml(tmp_path):
    import json
    coco = {"images": [{"id": 1, "file_name": "A.png", "width": 100, "height": 100}],
            "categories": [{"id": 1, "name": "other"}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 10, 30, 30], "segmentation": [],
                             "attributes": {"sign_class": "stop", "occluded": False}}]}
    g = tmp_path / "gt.json"
    g.write_text(json.dumps(coco), encoding="utf-8")
    p = write(tmp_path, "p", img(0, "A.png",
              '<box label="other" source="manual" occluded="0" xtl="10" ytl="10" xbr="40" ybr="40" z_order="0">'
              '<attribute name="sign_class">stop</attribute><attribute name="occluded">false</attribute></box>'))
    rows, _ = ev.compare(ev.parse_export(g), ev.parse_export(p), ev.load_config(None), {})
    assert [r.status for r in rows] == ["correct"]
