#!/usr/bin/env python3
"""cvat_eval (Phong) — dựng CVAT cho người gán + chấm theo GT. Chạy như nhau trên Windows / macOS / Linux.

    python sign.py install                      # tạo .venv + cài thư viện (1 lần)
    python sign.py selftest                     # tự kiểm, không cần CVAT
    python sign.py init                         # khai báo CVAT (URL, tài khoản admin) → .env
    python sign.py use --images data/images/X --gt data/gt/Y.xml   # đổi sang data + GT của bạn
    python sign.py show                         # đang dùng data/GT/schema nào
    python sign.py setup an binh                # GOLD + tài khoản/task cho từng người
    python sign.py list                         # task nào giao cho ai
    python sign.py evaluate                     # export + chấm → reports/<name>/summary.md (+ data/qa_reports của nhóm)
    python sign.py pack                         # zip RIÊNG TƯ (có data + GT) để chuyển cho người trong nhóm

Cấu hình nằm ở project.json (đường dẫn tương đối so với thư mục này).
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
VPY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PROJECT = HERE / "project.json"
PATH_KEYS = ("images", "gt", "labels", "guide", "eval_config", "group_repo")
PACK_SKIP = {".venv", "exports", "reports", "dist", "__pycache__", ".env", ".pytest_cache", "selftest_report"}

for stream in (sys.stdout, sys.stderr):  # console Windows cũ không phải UTF-8
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def reexec_in_venv() -> None:
    if VENV.exists() and Path(sys.prefix).resolve() == VENV.resolve():
        return
    if not VPY.exists():
        sys.exit("Chưa cài thư viện. Chạy trước:  python sign.py install")
    sys.exit(subprocess.call([str(VPY), str(Path(__file__)), *sys.argv[1:]]))


def load_project() -> dict:
    raw = json.loads(PROJECT.read_text(encoding="utf-8"))
    p = dict(raw)
    for k in PATH_KEYS:
        if p.get(k):
            p[k] = (HERE / p[k]).resolve()
    return p


def need(p: dict, *keys: str) -> None:
    for k in keys:
        if not p.get(k) or not Path(p[k]).exists():
            sys.exit(f"project.json: '{k}' = {p.get(k)} không tồn tại. Xem README mục 'Dữ liệu' hoặc chạy `python sign.py use`.")


# ─────────────────────────── commands ───────────────────────────


def cmd_install(args) -> None:
    if sys.version_info < (3, 10):
        sys.exit(f"Cần Python ≥ 3.10 (đang là {sys.version.split()[0]}). Cài Python mới từ python.org rồi chạy lại.")
    if not VPY.exists():
        print(f"• Tạo môi trường ảo {VENV}")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    print("• Cài thư viện từ requirements.txt")
    subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", "-r", str(HERE / "requirements.txt")])
    print("✓ Xong. Tiếp theo:  python sign.py selftest   rồi   python sign.py init")


def cmd_selftest(args) -> None:
    """1) chạy bộ test tổng hợp (không cần data); 2) nếu có GT tham chiếu thì chấm một bài giả lập 4 lỗi."""
    import importlib.util
    import inspect

    spec = importlib.util.spec_from_file_location("test_evaluate", HERE / "tests" / "test_evaluate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tests = [(n, f) for n, f in inspect.getmembers(mod, inspect.isfunction) if n.startswith("test_")]
    for name, fn in tests:
        with tempfile.TemporaryDirectory() as tmp:
            fn(Path(tmp))
    print(f"✓ {len(tests)} test tổng hợp đạt")

    ref = HERE / "data" / "gt" / "gt_gtsdb28_ref.xml"
    if not ref.exists():
        print("  (bỏ qua bước chấm dữ liệu thật: chưa có data/gt/gt_gtsdb28_ref.xml — xem README mục 'Dữ liệu')")
        return
    import xml.etree.ElementTree as ET
    import evaluate

    out = HERE / "reports" / "selftest"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    root = ET.parse(ref).getroot()
    for img in list(root.findall("image")):
        n = Path(img.get("name")).stem
        if n not in {"GTS01", "GTS03", "GTS06", "GTS07", "GTS12"}:
            root.remove(img)
            continue
        bx = img.findall("box")
        if n == "GTS01":
            img.remove(bx[2])                                                     # sót 1 biển nhỏ
        if n == "GTS03":
            bx[0].set("label", "prohibitory")                                     # sai nhóm biển (GT: danger)
        if n == "GTS06":
            bx[0].find("attribute[@name='sign_class']").text = "unknown"          # không đọc được class
        if n == "GTS07":                                                          # box thừa trên ảnh không có biển
            ET.SubElement(img, "box", label="other", source="manual", occluded="0",
                          xtl="600", ytl="300", xbr="630", ybr="330", z_order="0")
    pred = out / "bai_gia_lap.xml"
    ET.ElementTree(root).write(pred, encoding="utf-8", xml_declaration=True)
    images = HERE / "data" / "images" / "gtsdb28"
    evaluate.main(["--gt", str(ref), "--pred", str(pred), "--labels", str(HERE / "schema" / "labels_v1.2.json"),
                   "--config", str(HERE / "schema" / "eval_reference.json"), "--out", str(out)]
                  + (["--images", str(images)] if images.exists() else []))
    got: dict = {}
    for r in csv.DictReader((out / "objects.csv").open(encoding="utf-8")):
        got[r["status"]] = got.get(r["status"], 0) + 1
    want = {"correct": 9, "wrong_label": 1, "missing": 1, "extra": 1, "annotator_unknown": 1}
    if got != want:
        sys.exit(f"✗ selftest sai: mong {want}, nhận {got}")
    print(f"✓ Chấm dữ liệu thật: phát hiện đủ 4 lỗi cài sẵn → {out / 'summary.md'}")


def cmd_init(args) -> None:
    url = args.url or input("CVAT URL [http://localhost:8080]: ").strip() or "http://localhost:8080"
    user = args.user or input("Tài khoản admin CVAT (username hoặc email): ").strip()
    pw = args.password or getpass.getpass("Mật khẩu (không hiện khi gõ): ")
    (HERE / ".env").write_text(f"CVAT_URL={url}\nCVAT_ADMIN_USER={user}\nCVAT_ADMIN_PASSWORD={pw}\n", encoding="utf-8")
    print(f"• Ghi {HERE / '.env'}")
    cmd_check(args)


def cmd_check(args) -> None:
    import cvat_env
    cvat_env.cmd_check(args)


def cmd_use(args) -> None:
    raw = json.loads(PROJECT.read_text(encoding="utf-8"))
    for key in ("name", "images", "gt", "gt_format", "labels", "guide", "eval_config"):
        val = getattr(args, key)
        if val is None:
            continue
        if key in PATH_KEYS and val == "":
            raw[key] = ""                     # --gt "" = chưa có GT
            continue
        if key in PATH_KEYS:
            path = Path(val).resolve()
            if not path.exists():
                sys.exit(f"Không thấy {path}")
            val = os.path.relpath(path, HERE).replace(os.sep, "/")
        raw[key] = val
    PROJECT.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cmd_show(args)


def cmd_show(args) -> None:
    p = load_project()
    for k in ("name", "images", "gt", "gt_format", "labels", "guide", "eval_config", "group_repo"):
        v = p.get(k)
        ok = "" if k in ("name", "gt_format") else ("✓" if v and Path(v).exists() else
                                                    "(chưa có — GOLD tạo trống)" if k == "gt" and not v else "✗ không có")
        extra = f" ({len([f for f in Path(v).iterdir() if f.is_file()])} file)" if k == "images" and ok == "✓" else ""
        print(f"  {k:<12} {v}{extra} {ok}")


def cmd_setup(args) -> None:
    import cvat_env

    p = load_project()
    need(p, "images", "labels")
    images = args.images.resolve() if args.images else p["images"]
    guide = p["guide"] if p.get("guide") and Path(p["guide"]).exists() else None
    client, url = cvat_env.connect()
    if not args.no_gold:
        if p.get("gt"):
            need(p, "gt")
        else:
            print("  (project chưa có GT → GOLD tạo trống, tự gán GT trên CVAT)")
        # GOLD luôn gồm toàn bộ ảnh của project; GT chỉ được nạp khi task vừa tạo mới
        gold = cvat_env.create_task(client, f"{p['name']}-GOLD", p["labels"], p["images"], guide,
                                    args.replace_gold, p.get("gt") or None, p.get("gt_format", "CVAT 1.1"))
        print(f"  GOLD: {url}/tasks/{gold.id} (chỉ admin thấy — chỉnh thành gold ở đây nếu cần)")
    for u in args.users:
        user = cvat_env.ensure_user(client, url, u, args.password, None)
        task = cvat_env.create_task(client, f"{p['name']}-{u}", p["labels"], images, guide, args.replace)
        jobs = cvat_env.assign(client, task, user)
        print(f"  → {u}: đăng nhập {url} · job " + ", ".join(f"{url}/tasks/{task.id}/jobs/{j}" for j in jobs))
    cvat_env.cmd_list(argparse.Namespace(name=p["name"]))


def cmd_list(args) -> None:
    import cvat_env
    cvat_env.cmd_list(argparse.Namespace(name=load_project()["name"]))


def cmd_evaluate(args) -> None:
    import cvat_env
    import evaluate

    p = load_project()
    name = p["name"]
    exports = HERE / "exports" / name
    out = HERE / "reports" / name
    shutil.rmtree(exports, ignore_errors=True)
    cvat_env.cmd_collect(argparse.Namespace(name=name, out=exports, hint=False))
    preds = sorted(x for x in exports.glob("*.zip") if x.name != "gold.zip")
    if not preds:
        sys.exit(f"Chưa có task người gán nào (chạy: python sign.py setup <tên>)")
    argv = ["--gt", str(exports / "gold.zip"), "--pred", *map(str, preds), "--labels", str(p["labels"]),
            "--out", str(out)]
    if p.get("eval_config"):
        argv += ["--config", str(p["eval_config"])]
    if p.get("images") and Path(p["images"]).exists():
        argv += ["--images", str(p["images"])]
    evaluate.main(argv)
    if p.get("group_repo") and (Path(p["group_repo"]) / "data").exists():
        write_group_reports(Path(p["group_repo"]), name, exports, out)


def write_group_reports(repo: Path, name: str, exports: Path, out: Path) -> None:
    """Ghi theo quy ước repo nhóm: data/user_submissions/<người>/ + data/qa_reports/report_<người>_<name>.json
    (cùng khung summary/qa_flags/details với cvat_parser.py). Hai thư mục này đã bị .gitignore của nhóm chặn."""
    rows: dict = {}
    for r in csv.DictReader((out / "objects.csv").open(encoding="utf-8")):
        rows.setdefault(r["annotator"], []).append(r)
    for ann, rs in rows.items():
        sub = repo / "data" / "user_submissions" / ann
        sub.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(exports / f"{ann}.zip") as zf:
            (sub / f"submission_{name}.xml").write_bytes(zf.read("annotations.xml"))
        details = []
        for r in rs:
            if r["status"] in ("in_ignore", "out_of_scope"):
                continue
            errors = [] if r["status"] == "correct" else [
                {"rule": s, "status": "FAIL", "severity": r["severity"], "detail": r["detail"]}
                for s in r["status"].split("+")]
            details.append({"sample_id": r["sample_id"], "gt": r["gt"], "user": r["pred"],
                            "iou": r["geo_score"], "status": "PASS" if not errors else "FAIL", "errors": errors})
        gt_rows = [d for d in details if d["gt"]]
        passed = sum(d["status"] == "PASS" for d in gt_rows)
        score = round(100.0 * passed / len(gt_rows), 1) if gt_rows else 0.0
        report = {
            "labeler": ann, "scene": name, "evaluated_at": datetime.now().isoformat(timespec="seconds"),
            "tool": "members/phong/cvat_eval",
            "summary": {"total_objects": len(gt_rows), "pass": passed, "fail": len(gt_rows) - passed,
                        "extra_objects": sum(1 for d in details if not d["gt"]),
                        "score_percent": score, "verdict": "PASS" if score >= 80 else "FAIL"},
            "qa_flags": [d for d in details if d["status"] == "FAIL"],
            "details": details,
        }
        dst = repo / "data" / "qa_reports" / f"report_{ann}_{name}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  → {dst.relative_to(repo)} · {sub.relative_to(repo)}/submission_{name}.xml")


def cmd_pack(args) -> None:
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / "cvat_eval_phong.zip"
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(HERE.rglob("*")):
            rel = f.relative_to(HERE)
            if f.is_dir() or PACK_SKIP & set(rel.parts):
                continue
            zf.write(f, Path("cvat_eval") / rel)
            n += 1
    print(f"✓ {out} ({n} file, {out.stat().st_size / 1e6:.1f} MB)\n"
          "  ⚠ Zip CÓ data + GT: chỉ gửi riêng cho người trong nhóm (Drive), KHÔNG đưa lên GitHub. Không chứa .env.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install", help="tạo .venv + cài thư viện")
    sub.add_parser("selftest", help="tự kiểm offline")
    i = sub.add_parser("init", help="khai báo CVAT → .env")
    i.add_argument("--url")
    i.add_argument("--user")
    i.add_argument("--password")
    sub.add_parser("check", help="kiểm kết nối CVAT")
    u = sub.add_parser("use", help="đổi data/GT/schema trong project.json")
    u.add_argument("--name", help="tiền tố task CVAT (đổi khi dùng bộ data khác để không lẫn task)")
    u.add_argument("--images", help="thư mục ảnh")
    u.add_argument("--gt", help='file GT (CVAT 1.1 .xml/.zip hoặc COCO .json); --gt "" = chưa có GT')
    u.add_argument("--gt-format", dest="gt_format", help='"CVAT 1.1" hoặc "COCO 1.0"')
    u.add_argument("--labels", help="labels JSON cho CVAT")
    u.add_argument("--guide", help="guideline .md dán vào Guide")
    u.add_argument("--eval-config", dest="eval_config", help="cấu hình chấm .json")
    sub.add_parser("show", help="xem project.json đang trỏ tới đâu")
    s = sub.add_parser("setup", help="tạo GOLD + tài khoản/task cho từng người")
    s.add_argument("users", nargs="*", help="tên tài khoản người gán")
    s.add_argument("--password", default="VinUni@2026", help="mật khẩu cho tài khoản mới (mặc định VinUni@2026)")
    s.add_argument("--images", type=Path, help="chỉ giao ảnh trong thư mục này (vd một split blind)")
    s.add_argument("--replace", action="store_true", help="xoá task người gán cùng tên rồi tạo lại (MẤT bài đã gán)")
    s.add_argument("--replace-gold", action="store_true", help="tạo lại GOLD từ file GT (MẤT chỉnh sửa trên CVAT)")
    s.add_argument("--no-gold", action="store_true", help="không đụng tới GOLD")
    sub.add_parser("list", help="liệt kê task")
    sub.add_parser("evaluate", help="export + chấm")
    sub.add_parser("pack", help="zip riêng tư (có data) cho người trong nhóm")
    args = ap.parse_args()
    if args.cmd not in ("install", "pack", "use", "show"):
        reexec_in_venv()
    sys.path.insert(0, str(HERE))
    {"install": cmd_install, "selftest": cmd_selftest, "init": cmd_init, "check": cmd_check, "use": cmd_use,
     "show": cmd_show, "setup": cmd_setup, "list": cmd_list, "evaluate": cmd_evaluate, "pack": cmd_pack}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
