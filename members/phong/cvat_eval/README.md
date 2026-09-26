# cvat_eval — dựng CVAT cho người gán nhãn + chấm theo GT (phần cá nhân của Phong)

Công cụ cá nhân nằm trong repo nhóm, **không sửa file nào của nhóm**. Nó dùng chung với nhóm:

| Của nhóm | cvat_eval dùng thế nào |
|---|---|
| `guideline/LABELING_GUIDELINE_V1.md` (V1.2) | dán thẳng vào nút **Guide** của mọi task CVAT — nhóm sửa guideline thì chạy `setup --replace` để dán lại |
| 4 label `prohibitory/mandatory/danger/other` + 5 attribute | `schema/labels_v1.2.json` |
| `IOU_THRESHOLD = 0.7`, Rule 3 so `sign_class/occluded/truncated/readable` | `schema/eval_v1.2.json`: box IoU < 0.7 → `geometry_loose`, so đúng 4 attribute đó |
| `data/raw/` (ảnh), `data/ground_truth/` (GT, gitignore) | **mặc định** đọc ảnh và GT ở đây (`project.json`) |
| `data/user_submissions/<người>/`, `data/qa_reports/` | `evaluate` ghi bài nộp + `report_<người>_<name>.json` (khung `summary/metrics/qa_flags/details` như `cvat_parser.py`, PASS khi ≥ 80%) |
| Định dạng GT CVAT XML / COCO JSON | đọc cả hai (GT nhóm dạng COCO: `data/ground_truth/*.json`) |
| Quy định **không push GT** | GT nằm trong `data/ground_truth/*.json` (đã bị `.gitignore` của nhóm chặn); chia sẻ riêng bằng `pack` |

Khác `backend/cvat_parser.py`: tool này ghép box người gán ↔ GT **theo vị trí (IoU) trên từng ảnh**, không theo `id`, nên đọc
được export CVAT thật (nhiều ảnh, id hai bên khác nhau). Nó cũng dựng luôn task/tài khoản trên CVAT, vẽ ảnh
overlay, và liệt kê **ứng viên edge case mới**.

## Chạy nhanh (Windows / macOS / Linux)

Windows gõ `py`, macOS/Linux gõ `python3` thay cho `python`. Cần Python ≥ 3.10; máy chủ cần Docker + CVAT 2.74.1
(bản Day 2).

```bash
git clone https://github.com/davidhevn/Supper-Guideline-.git
cd Supper-Guideline-/members/phong/cvat_eval
# GT không có trên git: giải nén zip GT nhận qua Drive tại GỐC repo (xem "Dữ liệu")
python sign.py install          # 1 lần: tạo .venv, cài cvat-sdk 2.74.1 + Pillow
python sign.py selftest         # tự kiểm, không cần CVAT
python sign.py init             # URL CVAT + tài khoản admin → .env (không bao giờ lên git)
python sign.py show             # đang dùng data/GT/schema nào
python sign.py setup an binh    # task GOLD + mỗi người 1 tài khoản + 1 task riêng
python sign.py evaluate         # export + chấm → reports/<name>/summary.md
```

Người gán chỉ cần **trình duyệt**: đăng nhập tài khoản được tạo (mật khẩu mặc định `VinUni@2026`, đổi bằng
`--password`) → **Jobs** → mở job → đọc **Guide** → gán → **Save**. Họ chỉ thấy task của mình, không mở được GOLD.

## Dữ liệu

Mặc định (`project.json`, tên task `grp`) dùng data chung của nhóm ở gốc repo:

| | Đường dẫn | Trên git? |
|---|---|---|
| Ảnh | `data/raw/` — 3 ảnh GTSDB `00054`, `00177`, `00366` | có (nhóm đã đẩy) |
| GT | `data/ground_truth/gt_gtsdb_raw.json` — COCO 1.0, schema V1.2, 12 biển | **không** (`data/ground_truth/*.json` bị gitignore) |

GT này dựng từ `gt.txt` gốc của GTSDB cho đúng 3 ảnh trên: **box + nhóm biển + sign_class là thật**;
readable/occluded/truncated/relevant_to_ego để mặc định, vì vậy đi kèm `schema/eval_reference.json` (không chấm các
attribute đó). Khi nhóm có GT tự gán đủ attribute theo guideline → đổi sang `schema/eval_v1.2.json`.

Chia GT cho người trong nhóm: `python sign.py pack` → `dist/cvat_eval_phong_kem_data.zip`, gửi riêng qua Drive, người
nhận **giải nén tại gốc repo** (file rơi đúng vào `data/ground_truth/`).

### Thêm ảnh + GT mới

1. Ảnh vào `data/raw/` của nhóm.
2. GT (CVAT 1.1 `.xml`/`.zip` hoặc COCO `.json`) vào `data/ground_truth/`. **Đặt đuôi `.json`** thì gitignore của
   nhóm tự chặn; file `.xml` ở đó **không** bị chặn — cẩn thận khi commit. Chưa có GT: `--gt ""` → GOLD tạo trống,
   tự gán trên CVAT.
3. Trỏ project sang bộ mới (đổi `--name` để task không lẫn bộ cũ):
   ```bash
   python sign.py use --name bo2 --images ../../../data/raw --gt ../../../data/ground_truth/gt_bo2.json \
       --gt-format "COCO 1.0" --eval-config schema/eval_v1.2.json
   python sign.py show
   ```
4. `python sign.py setup an binh` → task `bo2-GOLD` nạp sẵn GT + task cho từng người.
5. Chỉ giao một phần ảnh (vd bộ blind): `python sign.py setup peer1 --images <thư mục ảnh blind>`. Khi chấm, ảnh
   GOLD không có trong bài được bỏ qua, không tính thiếu.

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
| `project.json: 'gt' … không tồn tại` | chưa giải nén zip GT tại gốc repo, hoặc `python sign.py use …` |
| không kết nối / `401` | CVAT chưa bật (`docker compose start`) hoặc sai tài khoản → `python sign.py init` |
| `superuser=False` | tạo admin: `docker exec -it cvat_server bash -ic "python3 ~/manage.py createsuperuser"` |
| mật khẩu người gán bị từ chối | ≥ 8 ký tự, không quá phổ biến, không giống tên đăng nhập |
| cảnh báo `not compatible with SDK` | CVAT khác 2.74.1; sửa `requirements.txt` cho khớp rồi `install` lại |

## File

| File | Là gì |
|---|---|
| `sign.py` | lệnh chính |
| `project.json` | đang dùng data/GT/schema/guideline/config nào (mặc định: data chung của nhóm) |
| `cvat_env.py` | phần CVAT: tạo task, tài khoản, giao job, export |
| `evaluate.py` | phần chấm (chạy riêng được: `python evaluate.py --help`) |
| `schema/labels_v1.2.json` | labels CVAT theo Guideline V1.2 (`readable` mặc định `__undefined__` để buộc chọn) |
| `schema/eval_v1.2.json`, `schema/eval_reference.json` | cấu hình chấm cho GT tự làm / GT tham chiếu |
| `tests/test_evaluate.py` | test tổng hợp (chạy trong `selftest`) |
