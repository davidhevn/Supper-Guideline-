# 📋 Guideline Dán nhãn Biển báo Giao thông (Traffic Sign)
## Version 1.2 — Chuẩn GTSDB | Cập nhật Core Guidelines

> **Phiên bản này có hiệu lực ngay lập tức và thay thế toàn bộ V1.1.**
> Mọi submission vi phạm các quy tắc dưới đây sẽ bị hệ thống QA/QC tự động từ chối.

---

## 1. Mục tiêu

Xây dựng bộ dữ liệu dán nhãn Biển báo Giao thông theo chuẩn **GTSDB (German Traffic Sign Detection Benchmark)** áp dụng cho xe tự lái. Dữ liệu phải nhất quán, không mơ hồ, có thể kiểm chứng tự động bằng thuật toán IoU + Semantic Rule.

> **Nguyên tắc vàng:** Nếu nghi ngờ → Đọc lại Guideline, không tự ý sáng tạo quy tắc mới.

---

## 2. Cấu trúc Nhãn (Label Classes) theo GTSDB

| Nhãn | Ý nghĩa | Đặc điểm | Ví dụ biển thuộc nhóm |
|---|---|---|---|
| `prohibitory` | Biển **Cấm** | Tròn, viền đỏ, nền trắng | Speed limit (20→120), No overtaking, No trucks |
| `mandatory` | Biển **Hiệu lệnh** | Tròn, nền **xanh dương** | Ahead only, Turn right, Keep right |
| `danger` | Biển **Nguy hiểm** | Tam giác, viền đỏ, nền vàng | Curves, Bumpy road, Children, **Priority next intersection (11)** |
| `other` | **Tất cả loại còn lại** | Mọi hình dạng khác | Stop, Give way, No entry, Priority road, End-of-prohibition |

> ⚠️ **Lưu ý đặc biệt:** Nhóm `other` trong GTSDB có phạm vi **rộng hơn** so với tên gọi. Hãy đọc kỹ mục 5 (Bẫy Ánh xạ) trước khi quyết định nhãn.

---

## 3. Thuộc tính bắt buộc (Attributes)

| Attribute | Kiểu | Giá trị hợp lệ | Ghi chú |
|---|---|---|---|
| `readable` | Dropdown | **`yes` / `no` / `uncertain`** | Bắt buộc chọn 1 trong 3. Không để trống. |
| `sign_class` | Text | Mã GTSDB (xem bảng mục 4) | Bắt buộc điền. Nếu không rõ → `unknown` |
| `occluded` | Checkbox | `True / False` | Tích nếu bị **bất kỳ vật thể nào** che khuất |
| `truncated` | Checkbox | `True / False` | Tích nếu bị **mép ảnh** cắt lẹm |
| `relevant_to_ego` | Checkbox | `True / False` | Tích nếu có hiệu lực với làn xe tự lái |

---

## 4. Bảng Mã biển (sign_class) theo GTSDB

| Mã GTSDB | sign_class | Nhãn bắt buộc | Tên biển |
|---|---|---|---|
| 00–08 | `speed_limit_20` → `speed_limit_120` | `prohibitory` | Giới hạn tốc độ |
| 09 | `no_overtaking` | `prohibitory` | Cấm vượt |
| 10 | `no_overtaking_trucks` | `prohibitory` | Cấm vượt (xe tải) |
| **11** | `priority_next_intersection` | **`danger`** | **Ưu tiên giao lộ tiếp theo** |
| **12** | `priority_road` | **`other`** | **Đường ưu tiên** |
| **13** | `give_way` | **`other`** | **Nhường đường (tam giác ngược)** |
| **14** | `stop` | **`other`** | **Biển DỪNG (bát giác đỏ)** |
| 15 | `no_vehicles` | `prohibitory` | Cấm tất cả phương tiện |
| **17** | `no_entry` | **`other`** | **Cấm vào (tròn đỏ, ngang trắng)** |
| 18–26 | `danger_*` | `danger` | Các biển cảnh báo nguy hiểm |
| 27–31 | `end_of_*` | **`other`** | Biển "Hết cấm" (Gạch chéo) |
| 32–41 | `mandatory_*` | `mandatory` | Các biển hiệu lệnh |
| 42 | `end_of_all_restrictions` | `other` | Hết tất cả hạn chế |

---

## ⚡ 5. QUY TẮC CỐT LÕI (CRITICAL — Phải đọc kỹ)

---

### 5.1. 🧱 QUY TẮC ATOMIC — Bất khả xâm phạm

> **MỖI MẶT BIỂN BÁO = MỘT BOUNDING BOX RIÊNG BIỆT.**
> **Không có ngoại lệ nào cho quy tắc này.**

- **Cụm biển xếp chồng (Stack):** Vẽ **N box riêng biệt** cho N biển. Không bao giờ dùng 1 box ôm trọn cả cụm.
- **Biển chính + biển phụ:** Mỗi biển 1 box. Biển phụ gán nhãn `other`.
- **Loại trừ bắt buộc ra khỏi Bounding Box:**
  - ❌ Cột/Trụ đỡ biển
  - ❌ Dây treo biển
  - ❌ Bệ đỡ, móc treo
  - ❌ Bóng tối do biển tạo ra

---

### ⚠️ 5.2. BẪY ÁNH XẠ NHÃN (LABEL MAPPING TRAP) — NGUY HIỂM NHẤT

> **ĐÂY LÀ NGUỒN GỐC GÂY RA 80% LỖI NHÃN PHỔ BIẾN NHẤT.**
> Hệ thống QA/QC sẽ TỰ ĐỘNG phát hiện và từ chối bất kỳ submission nào vi phạm bảng sau.

#### 🚨 BẢNG BẪY — Các biển trông như `prohibitory` nhưng BẮT BUỘC là `other`:

| Biển báo | sign_class | ❌ Nhãn SAI (thường gán nhầm) | ✅ Nhãn ĐÚNG |
|---|---|---|---|
| Biển DỪNG (bát giác đỏ) | `stop` | ~~`prohibitory`~~ | **`other`** |
| Biển Nhường đường (tam giác ngược) | `give_way` | ~~`danger`~~ | **`other`** |
| Biển Cấm vào (tròn đỏ ngang trắng) | `no_entry` | ~~`prohibitory`~~ | **`other`** |
| Biển Đường ưu tiên (hình thoi vàng) | `priority_road` | ~~`danger`~~ | **`other`** |
| Biển Hết cấm (gạch chéo) | `end_of_speed_limit_*` | ~~`prohibitory`~~ | **`other`** |
| Biển Hết tất cả hạn chế | `end_of_all_restrictions` | ~~`prohibitory`~~ | **`other`** |

#### 🚨 BẢNG BẪY — Biển trông như `danger` nhưng BẮT BUỘC là `other` (và ngược lại):

| Biển báo | sign_class | ❌ Nhãn SAI | ✅ Nhãn ĐÚNG | Lý do |
|---|---|---|---|---|
| Ưu tiên giao lộ tiếp theo | `priority_next_intersection` | ~~`other`~~ | **`danger`** | GTSDB mã 11 = danger |
| Đường ưu tiên | `priority_road` | ~~`danger`~~ | **`other`** | GTSDB mã 12 = other |

> 💡 **Mẹo ghi nhớ:** `Stop`, `Give Way`, `No Entry` là 3 biển "ngoại lệ" hình dạng giống cấm nhưng GTSDB xếp vào `other`. Hãy thuộc lòng 3 biển này!

---

### 5.3. 🚫 EXCLUSION — Tuyệt đối KHÔNG dán nhãn

> **CÁC ĐỐI TƯỢNG SAU ĐÂY KHÔNG PHẢI BIỂN BÁO GIAO THÔNG. KHÔNG DÁN NHÃN.**

| Đối tượng | Lý do loại trừ |
|---|---|
| **Đèn tín hiệu (Traffic Light)** | Khác loại sensor, khác task |
| **Mặt sau của biển báo** | Không chứa thông tin điều khiển |
| **Biển quảng cáo thương mại** | Không phải biển giao thông pháp lý |
| **Màn hình LED hiển thị biển** | Không phải vật thể vật lý cố định |
| **Tranh vẽ tường / Đề-can** | Không có giá trị pháp lý giao thông |
| **Biển bị hỏng > 70% diện tích** | Model không học được thông tin hữu ích |

---

### 5.4. QUY TẮC KÍCH THƯỚC (Size Threshold)

| Trường hợp | Hành động |
|---|---|
| Box **< 15 × 15 pixel** | Bỏ qua — Không dán nhãn |
| Biển đủ lớn, không đọc được nội dung | Dán nhãn + `readable = uncertain` |
| Biển bị che **> 70%** | Bỏ qua — Không dán nhãn |
| Biển bị che **50–70%** | Vẽ box bao trọn + `occluded = True` |
| Biển bị che **< 50%** | Vẽ box bao trọn (kể cả phần bị che) + `occluded = True` |

---

### 5.5. QUY TẮC TRUNCATION (Biển bị cắt mép ảnh)

- Box kéo **đến tận mép ảnh**, không ước lượng phần ngoài.
- Tích `truncated = True`.
- **Chỉ bỏ qua** nếu phần nhìn thấy < 15px.

---

## 6. Checklist Tự kiểm tra trước khi nộp

- [ ] Mỗi mặt biển đã có 1 box riêng biệt chưa? (Không gộp cụm)
- [ ] Cột/trụ đỡ đã được loại ra khỏi box chưa?
- [ ] Tôi đã kiểm tra Bẫy Ánh xạ (mục 5.2) cho từng biển chưa?
- [ ] `sign_class` đã điền (không để trống)?
- [ ] `readable` đã chọn trong 3 giá trị: `yes` / `no` / `uncertain`?
- [ ] `occluded` và `truncated` đã được đánh đúng chưa?
- [ ] Không có đèn tín hiệu, mặt sau biển, biển quảng cáo bị dán nhãn nhầm?

---

## 7. Lịch sử thay đổi

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| V1.0 | 2026-09-26 | Phát hành lần đầu |
| V1.1 | 2026-09-26 | Cập nhật 4 Labels + 5 Attributes |
| **V1.2** | **2026-09-26** | **Chuẩn hóa theo GTSDB. Bổ sung Bẫy Ánh xạ (5.2), Exclusion (5.3), Size Threshold (5.4). `readable` thêm giá trị `uncertain`.** |
