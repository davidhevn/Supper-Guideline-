"""Test evaluate.py bằng bài/GT tổng hợp theo schema Guideline V1.2 (không cần CVAT). Chạy qua `python sign.py selftest`."""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import evaluate as ev  # noqa: E402

HEAD = '<?xml version="1.0" encoding="utf-8"?><annotations><version>1.1</version>'


def box(label, x1, y1, x2, y2, **attrs):
    a = "".join(f'<attribute name="{k}">{v}</attribute>' for k, v in attrs.items())
    return f'<box label="{label}" source="manual" occluded="0" xtl="{x1}" ytl="{y1}" xbr="{x2}" ybr="{y2}" z_order="0">{a}</box>'


def img(i, name, *items, w=1360, h=800):
    return f'<image id="{i}" name="{name}" width="{w}" height="{h}">{"".join(items)}</image>'


def write(tmp, name, *images):
    p = tmp / f"{name}.xml"
    p.write_text(HEAD + "".join(images) + "</annotations>", encoding="utf-8")
    return p


def sign(label, x1, y1, x2, y2, cls, readable="yes"):
    return box(label, x1, y1, x2, y2, readable=readable, sign_class=cls, occluded="false", truncated="false")


def gold(tmp):
    return write(tmp, "gold",
                 img(0, "00054.png", sign("danger", 100, 100, 140, 138, "pedestrian_crossing"),
                     sign("prohibitory", 500, 100, 530, 130, "speed_limit_20"),
                     sign("mandatory", 900, 50, 912, 62, "keep_right")),        # biển rất nhỏ
                 img(1, "00177.png", sign("other", 200, 200, 243, 243, "stop")))


def run(tmp, preds, **cfg_over):
    cfg = ev.load_config(None)
    cfg.update(cfg_over)
    gt = ev.parse_export(gold(tmp))
    rows, names = [], []
    for p in preds:
        d = ev.parse_export(p)
        r, _ = ev.compare(gt, d, cfg, ["prohibitory", "mandatory", "danger", "other"])
        rows += r
        names.append(d.name)
    return gt, cfg, rows, names


def test_perfect_copy_is_all_correct(tmp_path):
    g = gold(tmp_path)
    same = tmp_path / "copy.xml"
    same.write_bytes(g.read_bytes())
    gt, cfg, rows, _ = run(tmp_path, [same])
    assert {r.status for r in rows} == {"correct"}
    m = ev.metrics(rows, cfg)
    assert m["full_ok"] == m["units"] == 4 and m["precision"] == m["recall"] == 100.0


def test_error_types(tmp_path):
    an = write(tmp_path, "an",
               img(0, "00054.png", sign("danger", 102, 101, 141, 139, "speed_limit_30"),       # sai sign_class
                   sign("prohibitory", 506, 106, 536, 136, "speed_limit_20"),                   # IoU≈0.47 → không khớp
                   sign("prohibitory", 300, 300, 330, 330, "no_overtaking")),                   # thừa
               img(1, "00177.png", box("prohibitory", 200, 200, 243, 243, readable="__undefined__",
                                       sign_class="stop")))                                     # bẫy ánh xạ + chưa gán
    gt, cfg, rows, names = run(tmp_path, [an])
    by = {(r.sample, r.status) for r in rows}
    assert ("00054", "wrong_attr") in by
    assert ("00054", "extra") in by
    assert sum(1 for r in rows if r.status == "missing") == 2            # biển 500,100 lệch quá + biển nhỏ
    trap = [r for r in rows if r.sample == "00177"][0]
    assert trap.status == "wrong_label" and trap.severity == "critical"
    assert any(c["suggested_tags"] == "edge;small_far" for c in ev.edge_candidates(rows, names, gt, cfg))


def test_loose_box_and_unknown(tmp_path):
    an = write(tmp_path, "an",
               img(0, "00054.png", sign("danger", 104, 104, 144, 142, "pedestrian_crossing"),   # IoU≈0.68 → lệch
                   sign("prohibitory", 500, 100, 530, 130, "unknown", readable="uncertain"),
                   sign("mandatory", 900, 50, 912, 62, "keep_right")),
               img(1, "00177.png", sign("other", 200, 200, 243, 243, "stop")))
    gt, cfg, rows, _ = run(tmp_path, [an])
    st = {r.gt.attrs["sign_class"]: r.status for r in rows}
    assert st["pedestrian_crossing"] == "geometry_loose"
    assert st["speed_limit_20"] == "annotator_unknown"
    cfg["severity"]["attr:sign_class"] = "major"
    rows, _ = ev.compare(gt, ev.parse_export(an), cfg, [])
    assert next(r for r in rows if r.status == "annotator_unknown").severity == "question"


def test_consensus_edge_case_and_extra_merge(tmp_path):
    preds = []
    for name, dx in (("an", 0), ("binh", 3)):
        preds.append(write(tmp_path, name,
                           img(0, "00054.png", sign("other", 100, 100, 140, 138, "pedestrian_crossing"),  # cả hai: other
                               sign("prohibitory", 500, 100, 530, 130, "speed_limit_20"),
                               sign("mandatory", 900, 50, 912, 62, "keep_right"),
                               sign("other", 700 + dx, 400, 740 + dx, 440, "advert")),                   # cả hai vẽ thừa
                           img(1, "00177.png", sign("other", 200, 200, 243, 243, "stop"))))
    gt, cfg, rows, names = run(tmp_path, preds)
    cands = ev.edge_candidates(rows, names, gt, cfg)
    assert len(cands) == 2 and all(c["annotators"] == "an;binh" for c in cands)
    assert {c["statuses"] for c in cands} == {"wrong_label", "extra"}


def test_single_execution_error_not_candidate(tmp_path):
    an = write(tmp_path, "an",
               img(0, "00054.png", sign("danger", 100, 100, 140, 138, "bend"),
                   sign("prohibitory", 500, 100, 530, 130, "speed_limit_20"),
                   sign("mandatory", 900, 50, 912, 62, "keep_right")),
               img(1, "00177.png", sign("other", 200, 200, 243, 243, "stop")))
    gt, cfg, rows, names = run(tmp_path, [an])
    assert [r.status for r in rows].count("wrong_attr") == 1
    assert ev.edge_candidates(rows, names, gt, cfg) == []


def test_normalize_and_ignore_attrs(tmp_path):
    an = write(tmp_path, "an",
               img(0, "00054.png", sign("danger", 100, 100, 140, 138, "Pedestrian crossing", readable="no"),
                   sign("prohibitory", 500, 100, 530, 130, "speed-limit-20"),
                   sign("mandatory", 900, 50, 912, 62, "keep_right")),
               img(1, "00177.png", sign("other", 200, 200, 243, 243, "stop")))
    gt, cfg, rows, _ = run(tmp_path, [an], ignore_attrs=["readable"])
    assert {r.status for r in rows} == {"correct"}


def test_subset_images_and_empty_submission(tmp_path):
    only = write(tmp_path, "only", img(1, "00177.png", sign("other", 200, 200, 243, 243, "stop")))
    gt, cfg, rows, _ = run(tmp_path, [only])
    assert {r.sample for r in rows} == {"00177"} and rows[0].status == "correct"
    empty = write(tmp_path, "empty", img(0, "00054.png"), img(1, "00177.png"))
    out = tmp_path / "rep"
    assert ev.main(["--gt", str(gold(tmp_path)), "--pred", str(empty), "--out", str(out)]) == 0
    assert "bài trống" in (out / "summary.md").read_text(encoding="utf-8")
    assert list(csv.DictReader((out / "objects.csv").open(encoding="utf-8"))) == []


def test_coco_json_matches_cvat_xml(tmp_path):
    coco = {"images": [{"id": 1, "file_name": "00177.png", "width": 1360, "height": 800}],
            "categories": [{"id": 1, "name": "other"}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [200, 200, 43, 43],
                             "attributes": {"sign_class": "stop", "occluded": False}}]}
    g = tmp_path / "gt.json"
    g.write_text(json.dumps(coco), encoding="utf-8")
    p = write(tmp_path, "p", img(0, "00177.png", box("other", 200, 200, 243, 243, sign_class="stop", occluded="false")))
    rows, _ = ev.compare(ev.parse_export(g), ev.parse_export(p), ev.load_config(None), [])
    assert [r.status for r in rows] == ["correct"]


def test_unknown_label_flagged_by_schema(tmp_path):
    p = write(tmp_path, "p", img(0, "00177.png", box("traffic_light", 10, 10, 30, 50)))
    g = write(tmp_path, "g", img(0, "00177.png"))
    rows, _ = ev.compare(ev.parse_export(g), ev.parse_export(p), ev.load_config(None), ["other"])
    assert {r.status for r in rows} == {"schema", "extra"}
