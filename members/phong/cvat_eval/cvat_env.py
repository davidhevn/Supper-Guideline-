#!/usr/bin/env python3
"""Dựng môi trường CVAT cho vòng "người ngoài gán nhãn → chấm theo GT".

Mỗi task dùng cùng một labels JSON + guideline + bộ ảnh. Gold (GT) và bài của từng annotator nằm ở các task
RIÊNG, annotator chỉ được giao job của mình nên không mở được task gold.

    PY=.venv/bin/python        # Windows: .venv\Scripts\python.exe — thường dùng qua sign.py
    $PY cvat_env.py check
    $PY cvat_env.py gold      --name nhom1 --labels L.json --guideline G.md --images build/blind
    $PY cvat_env.py annotator --name nhom1 --user an --password 'Mk@12345' --labels L.json --guideline G.md --images build/blind
    $PY cvat_env.py export    --task 42 --out exports/an.zip
    $PY cvat_env.py collect   --name nhom1 --out exports/        # export gold + mọi task annotator của nhóm
    $PY cvat_env.py list      [--name nhom1]

Đăng nhập: đọc CVAT_URL / CVAT_ADMIN_USER / CVAT_ADMIN_PASSWORD từ .env cạnh file này (tạo bằng `python sign.py init`).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
EXPORT_FORMAT = "CVAT for images 1.1"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def load_env() -> None:
    for path in (HERE / ".env",):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")


def connect():
    from cvat_sdk import make_client

    load_env()
    url = os.environ.get("CVAT_URL", "http://localhost:8080")
    user = os.environ.get("CVAT_ADMIN_USER", "")
    pw = os.environ.get("CVAT_ADMIN_PASSWORD", "")
    if not user or not pw:
        raise SystemExit("Thiếu CVAT_ADMIN_USER / CVAT_ADMIN_PASSWORD — chạy: python sign.py init")
    host, _, port = url.rpartition(":")
    client = make_client(host, port=int(port), credentials=(user, pw)) if port.isdigit() \
        else make_client(url, credentials=(user, pw))
    client.config.status_check_period = 1
    return client, url


def images_in(folder: Path) -> List[Path]:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT)
    if not files:
        raise SystemExit(f"Không có ảnh trong {folder} (chạy `make pack SPLIT=blind` trong guideline-challenge/)")
    return files


def find_task(client, name: str):
    return [t for t in client.tasks.list() if t.name == name]


def find_user(client, username: str):
    users, _ = client.api_client.users_api.list(search=username)
    return next((u for u in users.results if u.username == username), None)


def ensure_user(client, url: str, username: str, password: Optional[str], email: Optional[str]):
    user = find_user(client, username)
    if user:
        print(f"  tài khoản '{username}' đã có (id {user.id}) — giữ nguyên mật khẩu cũ")
        return user
    if not password:
        raise SystemExit(f"Chưa có tài khoản '{username}' — cần --password để tạo")
    from cvat_sdk.api_client import ApiClient, Configuration, models

    # đăng ký qua endpoint công khai /api/auth/register (không cần quyền admin)
    with ApiClient(Configuration(host=url)) as anon:
        anon.auth_api.create_register(models.RegisterSerializerExRequest(
            username=username, email=email or f"{username}@annotator.local",
            password1=password, password2=password, first_name=username, last_name="annotator"))
    user = find_user(client, username)
    if user is None:
        raise SystemExit(f"Đã gọi register nhưng không thấy user '{username}' — admin phải mở Django admin kiểm tra")
    print(f"  tạo tài khoản '{username}' (id {user.id})")
    return user


def create_task(client, name: str, labels: Path, images: Path, guideline: Optional[Path],
                replace: bool, gt: Optional[Path] = None, gt_format: str = "CVAT 1.1"):
    import json
    from cvat_sdk.api_client import models
    from cvat_sdk.core.proxies.tasks import ResourceType

    old = find_task(client, name)
    if old and not replace:
        print(f"  task '{name}' đã có (#{old[0].id}) — dùng lại (thêm --replace để xoá tạo lại)")
        return old[0]
    for t in old:
        print(f"  xoá task cũ #{t.id} '{name}'")
        t.remove()
    spec = json.loads(labels.read_text(encoding="utf-8"))
    files = images_in(images)
    task = client.tasks.create_from_data(
        spec=models.TaskWriteRequest(name=name, labels=spec),
        resource_type=ResourceType.LOCAL,
        resources=[str(p) for p in files],
        data_params={"image_quality": 95, "sorting_method": "lexicographical"},
    )
    print(f"  tạo task #{task.id} '{name}' — {len(files)} ảnh")
    if guideline:
        client.api_client.guides_api.create(annotation_guide_write_request=models.AnnotationGuideWriteRequest(
            task_id=task.id, markdown=guideline.read_text(encoding="utf-8")))
        print(f"  dán guideline {guideline.name} vào Guide của task")
    if gt:
        task.import_annotations(gt_format, str(gt))
        print(f"  import GT ({gt_format}) từ {gt.name}")
    return task


def assign(client, task, user) -> List[int]:
    from cvat_sdk.api_client import models

    ids = []
    for job in task.get_jobs():
        if str(job.type) != "annotation":
            continue
        client.api_client.jobs_api.partial_update(job.id, patched_job_write_request=models.PatchedJobWriteRequest(
            assignee=user.id))
        ids.append(job.id)
    task.update(models.PatchedTaskWriteRequest(assignee_id=user.id))
    return ids


def export(client, task_id: int, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    task = client.tasks.retrieve(task_id)
    task.export_dataset(EXPORT_FORMAT, str(out), include_images=False)
    print(f"  export task #{task_id} '{task.name}' → {out}")
    return out


# ─────────────────────────── commands ───────────────────────────


def cmd_check(args) -> None:
    client, url = connect()
    about = client.api_client.server_api.retrieve_about()[0]
    me = client.api_client.users_api.retrieve_self()[0]
    print(f"✓ CVAT {about.version} tại {url} · đăng nhập {me.username} (superuser={me.is_superuser})")


def cmd_gold(args) -> None:
    client, url = connect()
    task = create_task(client, f"{args.name}-GOLD", args.labels, args.images, args.guideline, args.replace, args.gt, args.gt_format)
    print(f"→ Owner gán GT ở {url}/tasks/{task.id} rồi chạy: cvat_env.py collect --name {args.name}")


def cmd_annotator(args) -> None:
    client, url = connect()
    user = ensure_user(client, url, args.user, args.password, args.email)
    task = create_task(client, f"{args.name}-{args.user}", args.labels, args.images, args.guideline, args.replace)
    jobs = assign(client, task, user)
    print(f"→ Gửi cho {args.user}: mở {url} · đăng nhập '{args.user}' · vào Jobs → "
          + ", ".join(f"{url}/tasks/{task.id}/jobs/{j}" for j in jobs))


def cmd_export(args) -> None:
    client, _ = connect()
    export(client, args.task, args.out)


def cmd_collect(args) -> None:
    client, _ = connect()
    tasks = [t for t in client.tasks.list() if t.name.startswith(f"{args.name}-")]
    if not tasks:
        raise SystemExit(f"Không có task nào tên '{args.name}-*'")
    for t in sorted(tasks, key=lambda t: t.id):
        suffix = t.name[len(args.name) + 1:]
        export(client, t.id, args.out / f"{'gold' if suffix == 'GOLD' else suffix}.zip")
    if getattr(args, "hint", True):
        print(f"→ evaluate.py --gt {args.out / 'gold.zip'} --pred "
              + " ".join(str(args.out / f"{t.name[len(args.name) + 1:]}.zip") for t in tasks if not t.name.endswith("-GOLD")))


def cmd_list(args) -> None:
    client, url = connect()
    for t in sorted(client.tasks.list(), key=lambda t: t.id):
        if args.name and not t.name.startswith(f"{args.name}-"):
            continue
        jobs = t.get_jobs()
        info = ", ".join(
            f"job {j.id} {j.stage}/{j.state} → {j.assignee.username if j.assignee else '(chưa giao)'}" for j in jobs
            if str(j.type) == "annotation")
        print(f"#{t.id:<4} {t.name:<32} {t.size} ảnh · {info}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="kiểm kết nối + tài khoản")

    def task_args(p):
        p.add_argument("--name", required=True, help="tiền tố task, ví dụ tên nhóm")
        p.add_argument("--labels", required=True, type=Path, help="03_cvat_labels.json")
        p.add_argument("--images", required=True, type=Path, help="thư mục ảnh (vd build/blind)")
        p.add_argument("--guideline", type=Path, help="02_guideline.md → dán vào Guide của task")
        p.add_argument("--replace", action="store_true", help="xoá task cùng tên rồi tạo lại")

    g = sub.add_parser("gold", help="tạo task <name>-GOLD để owner gán GT")
    task_args(g)
    g.add_argument("--gt", type=Path, help="(tuỳ chọn) nạp sẵn GT có trước")
    g.add_argument("--gt-format", default="CVAT 1.1", help='định dạng file --gt, vd "COCO 1.0" (mặc định CVAT 1.1)')
    a = sub.add_parser("annotator", help="tạo tài khoản + task <name>-<user> và giao job")
    task_args(a)
    a.add_argument("--user", required=True)
    a.add_argument("--password", help="bắt buộc nếu tài khoản chưa có (≥ 8 ký tự, có chữ hoa + số)")
    a.add_argument("--email")
    e = sub.add_parser("export", help="export 1 task ra CVAT for images 1.1 (không kèm ảnh)")
    e.add_argument("--task", required=True, type=int)
    e.add_argument("--out", required=True, type=Path)
    c = sub.add_parser("collect", help="export task GOLD + mọi task annotator của nhóm")
    c.add_argument("--name", required=True)
    c.add_argument("--out", type=Path, default=Path("exports"))
    ls = sub.add_parser("list", help="liệt kê task + người được giao")
    ls.add_argument("--name")
    args = ap.parse_args(argv)
    {"check": cmd_check, "gold": cmd_gold, "annotator": cmd_annotator, "export": cmd_export,
     "collect": cmd_collect, "list": cmd_list}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
