# cvat_eval — dựng CVAT cho người gán nhãn + chấm theo GT (phần cá nhân của Phong)

Công cụ cá nhân nằm trong repo nhóm, **không sửa file nào của nhóm**. Nó dùng chung với nhóm:

| Của nhóm | cvat_eval dùng thế nào |
|---|---|
| `LABELING_GUIDELINE_V1.md` (V1.2) | dán thẳng vào nút **Guide** của mọi task CVAT — nhóm sửa guideline thì chạy `setup --replace` để dán lại |
| 4 label `prohibitory/mandatory/danger/other` + 5 attribute | `schema/labels_v1.2.json` |
| `IOU_THRESHOLD = 0.7`, Rule 3 so `sign_class/occluded/truncated/readable` | `schema/eval_v1.2.json`: box IoU < 0.7 → `geometry_loose`, so đúng 4 attribute đó |
| `data/user_submissions/<người>/`, `data/qa_reports/` | `evaluate` ghi bài nộp + `report_<người>_<name>.json` (khung `summary/qa_flags/details`, PASS khi ≥ 80%) vào đúng chỗ đó |
| Quy định **không push ảnh/GT** | `data/` của thư mục này bị `.gitignore`; data chia sẻ riêng qua Drive |

Khác `cvat_parser.py`: tool này ghép box người gán ↔ GT **theo vị trí (IoU) trên từng ảnh**, không theo `id`, nên đọc
được export CVAT thật (nhiều ảnh, id hai bên khác nhau). Nó cũng dựng luôn task/tài khoản trên CVAT, vẽ ảnh
overlay, và liệt kê **ứng viên edge case mới**.

## Chạy nhanh (Windows / macOS / Linux)

Windows gõ `py`, macOS/Linux gõ `python3` thay cho `python`. Cần Python ≥ 3.10; máy chủ cần Docker + CVAT 2.74.1
(bản Day 2).

```bash
git clone https://github.com/davidhevn/Supper-Guideline-.git
cd Supper-Guideline-/members/phong/cvat_eval
# chép data/ nhận qua Drive vào đây (xem "Dữ liệu")
python sign.py install          # 1 lần: tạo .venv, cài cvat-sdk 2.74.1 + numpy + Pillow
python sign.py selftest         # tự kiểm, không cần CVAT
python sign.py init             # URL CVAT + tài khoản admin → .env (không bao giờ lên git)
python sign.py show             # đang dùng data/GT/schema nào
python sign.py setup an binh    # task GOLD + mỗi người 1 tài khoản + 1 task riêng
python sign.py evaluate         # export + chấm → reports/<name>/summary.md
```

Người gán chỉ cần **trình duyệt**: đăng nhập tài khoản được tạo (mật khẩu mặc định `VinUni@2026`, đổi bằng
`--password`) → **Jobs** → mở job → đọc **Guide** → gán → **Save**. Họ chỉ thấy task của mình, không mở được GOLD.

## Dữ liệu

`data/` không lên GitHub. Bố cục:

```
data/images/<bộ ảnh>/     ảnh; tên file = sample_id
data/gt/<file GT>         CVAT for images 1.1 (.xml / .zip export) hoặc COCO 1.0 (.json)
```

Bộ khởi đầu (`python sign.py pack` → `dist/cvat_eval_phong.zip`, gửi riêng qua Drive): 28 ảnh GTSDB `GTS01–28`
của lab Day 9 + `gt_gtsdb28_ref.xml` = GT GTSDB đổi sang schema V1.2 (55 box). GT này chỉ đúng **box + nhóm biển +
sign_class**; readable/occluded/truncated để mặc định, nên dùng với `schema/eval_reference.json`.

### Thêm data + GT của riêng bạn

1. Chép ảnh vào `data/images/<tên bộ>/`.
2. Có GT: đặt vào `data/gt/`. Chưa có: `--gt ""` ở bước 3 → GOLD tạo trống, bạn tự gán GT trên CVAT (bước 4).
3. Trỏ project sang bộ mới (đổi `--name` để task không lẫn bộ cũ):
   ```bash
   python sign.py use --name mydata --images data/images/mydata --gt data/gt/gt_mydata.xml \
       --gt-format "CVAT 1.1" --eval-config schema/eval_v1.2.json
   python sign.py show
   ```
   GT dạng COCO: `--gt data/gt/x.json --gt-format "COCO 1.0"`. GT tự làm theo guideline (có readable/occluded/…)
   thì dùng `schema/eval_v1.2.json`; GT chỉ có box + nhóm biển thì dùng `schema/eval_reference.json`.
4. `python sign.py setup an binh` → task `mydata-GOLD` nạp sẵn GT (chỉnh tiếp trên CVAT nếu cần) + task cho từng
   người. **Không dùng lại ảnh GOLD làm ví dụ trong guideline.**
5. Chỉ giao một phần ảnh (vd bộ blind): `python sign.py setup peer1 --images data/images/mydata_blind`. Khi chấm,
   ảnh GOLD không có trong bài được bỏ qua, không tính thiếu.

## Kết quả chấm

`reports/<name>/`:

| File | Nội dung |
|---|---|
| `summary.md` | mỗi người: đúng hoàn toàn, precision, recall, độ đúng từng attribute, lỗi critical/major/minor; bảng lỗi; **ứng viên edge case** |
| `objects.csv` | mỗi object × người một dòng |
| `edge_case_candidates.csv` | chỗ nghi guideline thiếu / gold sai, kèm gợi ý `guideline_gap` / `data_ambiguity` |
| `viz/<người>/<ảnh>.jpg` | xanh lá = đúng · xanh dương = GT bị thiếu/sai · vàng = khớp nhưng sai label/attribute · đỏ = thừa |

Thêm theo quy ước nhóm: `data/user_submissions/<người>/submission_<name>.xml` và
`data/qa_reports/report_<người>_<name>.json` ở gốc repo (đều bị `.gitignore` của nhóm chặn).

Loại lỗi: `missing` (sót biển), `extra` (box thừa — kể cả trên ảnh không có biển), `wrong_label` (sai nhóm biển —
bẫy ánh xạ 5.2), `wrong_attr` (sai sign_class/readable/occluded/truncated), `unassigned_attr` (readable còn
`__undefined__`), `annotator_unknown` (chọn unknown/uncertain khi GT chắc chắn), `geometry_loose` (IoU < 0.7).

Ứng viên edge case chỉ báo khi có tín hiệu phân vân: ≥ 2 người cùng lệch GT, box thừa, chọn unknown/uncertain, biển
rất nhỏ bị sót. Một người sai lẻ → nhiều khả năng lỗi thao tác, chỉ nằm trong bảng lỗi.

## Cho máy khác cùng Wi-Fi vào CVAT của máy chủ

CVAT mặc định chỉ nhận `localhost`. Trên máy chủ, trong thư mục CVAT:

| Windows (PowerShell) | macOS / Linux |
|---|---|
| `$env:CVAT_HOST="192.168.1.10"; docker compose up -d` | `CVAT_HOST=192.168.1.10 docker compose up -d` |

(IP: Windows `ipconfig`, macOS `ipconfig getifaddr en0`, Linux `hostname -I`.) Windows: mở cổng 8080 ở firewall.
Rồi `python sign.py init` với `http://192.168.1.10:8080`; mọi người vào bằng địa chỉ này. Mạng trường chặn thì dùng
hotspot điện thoại.

## Lỗi thường gặp

| Thông báo | Xử lý |
|---|---|
| `Chưa cài thư viện` | `python sign.py install` |
| `Cần Python ≥ 3.10` / `python` không nhận | cài Python từ python.org (Windows tick *Add to PATH*), Windows thử `py` |
| `project.json: 'images' … không tồn tại` | chưa chép `data/` từ Drive, hoặc `python sign.py use …` |
| không kết nối / `401` | CVAT chưa bật (`docker compose start`) hoặc sai tài khoản → `python sign.py init` |
| `superuser=False` | tạo admin: `docker exec -it cvat_server bash -ic "python3 ~/manage.py createsuperuser"` |
| mật khẩu người gán bị từ chối | ≥ 8 ký tự, không quá phổ biến |
| cảnh báo `not compatible with SDK` | CVAT khác 2.74.1; sửa `requirements.txt` cho khớp rồi `install` lại |

## File

| File | Là gì |
|---|---|
| `sign.py` | lệnh chính |
| `project.json` | đang dùng data/GT/schema/guideline/config nào |
| `cvat_env.py` | phần CVAT: tạo task, tài khoản, giao job, export |
| `evaluate.py` | phần chấm (chạy riêng được: `python evaluate.py --help`) |
| `schema/labels_v1.2.json` | labels CVAT theo Guideline V1.2 (`readable` mặc định `__undefined__` để buộc chọn) |
| `schema/eval_v1.2.json`, `schema/eval_reference.json` | cấu hình chấm cho GT tự làm / GT tham chiếu |
| `tests/test_evaluate.py` | test tổng hợp (chạy trong `selftest`) |
