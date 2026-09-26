# 🚀 VECTORNET QA/QC PIPELINE - MVP TRACKER

**Mục tiêu dự án:** Xây dựng một luồng (pipeline) đọc dữ liệu thô (.tfrecord) từ Waymo Open Dataset, tự động kiểm tra lỗi (QA/QC) bằng Rule-based và AI Agent, sau đó hiển thị báo cáo lên Web Dashboard để nghiệm thu dữ liệu trước khi đưa vào huấn luyện mô hình VectorNet.

## Phase 1: Data Extraction (Backend - Python)
- [x] **Khởi tạo môi trường:** Setup venv, cài đặt `tensorflow`, `waymo-open-dataset-tf-2-12-0`. (Đã xử lý bằng local protobuf trick).
- [x] **Đọc TFRecord:** Viết script `parse_tfrecord.py` load thành công 1 kịch bản (scenario) từ file `.tfrecord` trong tập validation.
- [x] **Trích xuất HD Maps:** Lọc lấy tọa độ `map_features` (vạch kẻ đường, ranh giới làn, biển báo) định dạng vector.
- [x] **Trích xuất Agent Dynamics:** Lọc lấy `tracks` (tọa độ x,y, vận tốc, hướng của xe/người đi bộ qua các mốc thời gian).
- [x] **Xuất JSON:** Serialize toàn bộ dữ liệu trên thành một file `scenario_mock.json` có cấu trúc rõ ràng, nhẹ (< 5MB) để làm đầu vào cho các bước sau.

## Phase 2: Rule-based QA/QC Logic (Backend - Python)
- [x] **Viết hàm Rule 1 (Missing Data):** Kiểm tra xem có xe nào bị mất tọa độ (missing frames) ở giữa kịch bản không.
- [x] **Viết hàm Rule 2 (Anomalies Kinematics):** Kiểm tra xem có xe/người nào có vận tốc, gia tốc vượt ngưỡng vật lý vô lý không (VD: > 200km/h).
- [x] **Viết hàm Rule 3 (Map Boundary):** Kiểm tra sơ bộ xem xe SDC (xe tự lái) có đang bị văng ra khỏi giới hạn bản đồ không.
- [x] **Gắn cờ lỗi (Error Flagging):** Đẩy kết quả của các hàm Rule-based vào chung file JSON xuất ra (ví dụ thêm trường `qa_flags: []`).

## Phase 3: AI QA/QC Agent Integration (LLM/Gemini API)
- [x] **Tạo Prompt Template:** Viết file prompt system định nghĩa vai trò của Kỹ sư QA/QC Dữ liệu.
- [x] **Tích hợp LLM API:** Viết hàm gọi API (Gemini/OpenAI) trong Python hoặc n8n.
- [x] **Xử lý Input/Output:** Truyền `scenario_mock.json` (kèm QA flags) vào prompt. Lấy kết quả trả về dưới dạng Markdown (Tổng quan, Dị thường, Pass/Fail).
- [x] **Đóng gói API:** Wrap toàn bộ Phase 1, 2, 3 thành 1 API endpoint bằng FastAPI hoặc Flask (VD: `POST /api/qaqc/run`).

## Phase 4: Frontend Visualization Dashboard (Next.js)
- [x] **Khởi tạo Next.js:** Setup project, TailwindCSS.
- [x] **Tạo Layout:** Chia màn hình làm 2 phần: Bên trái (Bản đồ trực quan), Bên phải (Bảng điều khiển & Report).
- [x] **Vẽ HD Map & Xe (Visualization):** Dùng thẻ `<canvas>` hoặc thư viện chart (như Plotly.js) đọc file JSON trả về từ API và vẽ lại cấu trúc đường giao thông (các đường line) và vị trí xe (các chấm tròn). *(Xe đã vẽ theo data thật, Map đang vẽ tĩnh)*.
- [x] **Hiển thị AI Report:** Render đoạn Markdown nhận được từ LLM ra UI ở bảng bên phải đẹp mắt.
- [x] **Nút Action:** Thêm nút "Run QA/QC Pipeline" để gọi API backend và cập nhật UI.

## Phase 5: MVP Review & Demo Preparation
- [x] **Kiểm thử luồng (E2E Test):** Tải 1 file từ tập `training` và 1 file từ tập `testing` chạy thử qua toàn bộ pipeline xem có crash không.
- [x] **Tối ưu UI/UX:** Chỉnh sửa màu sắc cảnh báo (Đỏ cho Fail, Xanh cho Pass).
- [x] **Quay Video Demo:** Record lại màn hình quá trình upload 1 kịch bản lỗi và hệ thống tự động bắt được lỗi đó.
