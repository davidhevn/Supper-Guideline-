#!/usr/bin/env python3
"""Phần CVAT của cvat_eval: kết nối, tạo task (GOLD / người gán), tạo tài khoản, giao job, export.

Không chạy trực tiếp — gọi qua `python sign.py ...`. Đăng nhập đọc CVAT_URL / CVAT_ADMIN_USER / CVAT_ADMIN_PASSWORD
từ .env cạnh file này (tạo bằng `python sign.py init`).

GOLD và bài của từng người nằm ở các task RIÊNG; người gán chỉ được giao job của mình nên không mở được GOLD.
"""

from __future__ import annotations

import os
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
        raise SystemExit(f"Không có ảnh trong {folder} (kiểm `images` trong project.json)")
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
    from cvat_sdk.api_client.exceptions import ApiException

    try:
        with ApiClient(Configuration(host=url)) as anon:
            anon.auth_api.create_register(models.RegisterSerializerExRequest(
                username=username, email=email or f"{username}@annotator.local",
                password1=password, password2=password, first_name=username, last_name="annotator"))
    except ApiException as e:
        raise SystemExit(f"CVAT không tạo được tài khoản '{username}' ({e.status}): {e.body}\n"
                         "→ mật khẩu cần ≥ 8 ký tự, không quá phổ biến, không giống tên đăng nhập; đổi bằng --password")
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


def cmd_collect(args) -> None:
    client, _ = connect()
    tasks = [t for t in client.tasks.list() if t.name.startswith(f"{args.name}-")]
    if not tasks:
        raise SystemExit(f"Không có task nào tên '{args.name}-*'")
    for t in sorted(tasks, key=lambda t: t.id):
        suffix = t.name[len(args.name) + 1:]
        export(client, t.id, args.out / f"{'gold' if suffix == 'GOLD' else suffix}.zip")


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
