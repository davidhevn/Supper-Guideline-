# 🎯 CVAT Labeler QA/QC Pipeline - MVP Tracker

**Mục tiêu:** Xây dựng hệ thống tự động chấm điểm và đánh giá chất lượng người dán nhãn (Labeler) trên nền tảng CVAT dựa vào việc so sánh với tập dữ liệu chuẩn (Golden Set). AI Agent sẽ đóng vai trò Giám khảo để chỉ ra lỗi sai và nhắc nhở theo Guideline (V1, V2, V3).

## Phase 0: Tài liệu & Guideline
- [x] **Guideline V1.0 (Draft):** Soạn thảo Guideline dán nhãn Traffic Sign với 5 Edge Cases và bảng nhãn chuẩn.
- [x] **Guideline V1.1:** Cập nhật 4 Labels chính + 5 Attributes.
- [x] **Guideline V1.2:** Chuẩn hóa theo GTSDB. Bổ sung **Bẫy Ánh xạ** (5.2), Exclusion (5.3), Quy tắc Atomic (5.1), `readable` thêm giá trị `uncertain`. Xem tại: `guideline/LABELING_GUIDELINE_V1.md`

## Phase 1: CVAT Data Adapter (Python)
- [x] **Viết Adapter Parser:** Xử lý file export JSON từ CVAT, trích xuất cấu trúc dữ liệu của User Label và Ground Truth.
- [x] **Data Mapping:** Đồng bộ hóa cấu trúc object giữa 2 tập dữ liệu để chuẩn bị so sánh.

## Phase 2: Rule-based Comparison (6 Rules)
- [x] **Rule 1 - IoU:** Kiểm tra độ lệch Bounding Box (ngưỡng 0.7).
- [x] **Rule 2 - Label Mismatch:** Kiểm tra nhãn chính có bị chọn sai không.
- [x] **Rule 3 - Attribute Mismatch:** Kiểm tra `sign_class`, `occluded`, `truncated`, `readable`.
- [x] **Rule 4 - Atomic Check:** Phát hiện Box bao trùm ≥ 2 GT Objects (gộp cụm trái phép).
- [x] **Rule 5 - Family Mapping Trap:** Dictionary bẫy ánh xạ GTSDB (stop/no_entry/give_way/priority_road → `other`).
- [x] **Rule 6 - Attribute Format Validation:** Kiểm tra `readable` chỉ nhận `yes`/`no`/`uncertain`, `sign_class` không để trống.
- [ ] **Thuật toán Poly/Line (Nâng cao):** Tính toán độ lệch khoảng cách cho đường ranh giới (Lane, Polygon).

## Phase 3: AI Evaluator Agent (Gemini)
- [ ] **Tạo System Prompt Mới:** AI đóng vai trò Giám khảo QA/QC, đối chiếu lỗi với Guideline dán nhãn.
- [ ] **Feedback Generation:** Nhận xét cụ thể từng lỗi sai và hướng dẫn khắc phục theo Guideline V1.1.

## Phase 4: Dashboard Integration (Next.js & FastAPI)
- [ ] **Cập nhật Backend API:** Chuyển đổi endpoint `/api/qaqc/run` sang luồng xử lý của CVAT.
- [ ] **Nâng cấp Giao diện Frontend:** Thay thế HD Map cũ bằng giao diện so sánh hộp bounding box (User Box vs Ground Truth Box).
- [ ] **Hiển thị Báo cáo Điểm:** Đưa AI feedback ra màn hình, highlight các object bị đánh dấu đỏ (lỗi).
