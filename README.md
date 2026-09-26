# 🚀 VectorNet QA/QC Pipeline (MVP)

## 📖 Giới thiệu Dự án
Trong quá trình huấn luyện các mô hình dự đoán quỹ đạo xe tự lái như **VectorNet**, chất lượng dữ liệu đầu vào (HD Maps, Agent Dynamics) đóng vai trò sống còn. Một tọa độ bị đứt gãy hoặc một xe chạy với vận tốc phi lý (VD: 300km/h) có thể làm sụp đổ toàn bộ quá trình hội tụ của mô hình.

**VectorNet QA/QC Pipeline** là một công cụ tự động hóa toàn diện (End-to-End) giúp đọc, trích xuất dữ liệu thô từ **Waymo Open Dataset (.tfrecord)**, đưa qua màng lọc kiểm tra lỗi vật lý (Rule-based), và cuối cùng sử dụng **Trí tuệ Nhân tạo (Gemini AI Agent)** để đánh giá, ra quyết định PASS/FAIL trước khi nghiệm thu dữ liệu.

---

## 🗂️ Cấu trúc thư mục

```
├── backend/                  # Python: API + pipeline + QA/QC
│   ├── main.py               #   FastAPI (POST /api/qaqc/run)
│   ├── backend_pipeline.py   #   đọc TFRecord Waymo + rule-based QA
│   ├── ai_agent.py           #   Gemini AI Agent viết báo cáo
│   ├── cvat_parser.py        #   chấm bài gán nhãn CVAT (Traffic Sign, 6 rules)
│   ├── read_waymo.py         #   script đọc thử TFRecord
│   └── test_backend_pipeline.py
├── frontend/                 # Next.js dashboard
├── guideline/                # Guideline gán nhãn Traffic Sign
│   ├── LABELING_GUIDELINE_V1.md
│   └── sample_images/
├── data/                     # raw/ (ảnh) · ground_truth/ · user_submissions/ · qa_reports/ — GT & bài nộp KHÔNG push
├── docs/                     # tracker, kiến trúc, workflow, slide, prompt, paper VectorNet
├── members/                  # công cụ cá nhân của từng thành viên (vd members/phong/cvat_eval)
└── agent_skills/, skills-lock.json   # skill cho AI coding agent
```

Mọi lệnh bên dưới chạy từ **gốc repo**.

---

## 🛠️ Công nghệ sử dụng (Tech Stack)
* **Backend:** Python, FastAPI, TensorFlow (Waymo Open Dataset API).
* **AI Agent:** Google Gemini (gemini-1.5-flash) - Ra quyết định đánh giá.
* **Frontend:** Next.js, TailwindCSS, HTML Canvas API, React Markdown.

---

## ⚙️ Hướng dẫn Cài đặt & Khởi chạy

### 1. Cài đặt Backend (FastAPI)
```bash
# Đứng ở gốc repo (không cd vào backend/ — đường dẫn waymo_mini_dataset/ và frontend/public tính từ gốc)

# Tạo môi trường ảo (Khuyến nghị)
python -m venv venv
# Windows: venv\Scripts\activate
# MacOS/Linux: source venv/bin/activate

# Cài đặt thư viện
pip install fastapi uvicorn google-generativeai pydantic python-dotenv tensorflow waymo-open-dataset-tf-2-12-0

# Cấu hình AI Agent
# Tạo file .env ở gốc repo và thêm dòng sau:
GEMINI_API_KEY="Điền_API_Key_Của_Bạn_Vào_Đây"

# Chạy Backend Server
python backend/main.py
# API sẽ chạy tại: http://localhost:8000
```

### 2. Cài đặt Frontend (Next.js)
```bash
# Mở một Terminal mới, di chuyển vào thư mục frontend
cd frontend

# Cài đặt thư viện UI và Markdown
npm install
npm install react-markdown

# Chạy Frontend Dashboard
npm run dev
# Dashboard sẽ chạy tại: http://localhost:3000
```

---

## 🎬 Hướng dẫn Kịch bản Demo
Khi thuyết trình, hãy mở Dashboard tại `http://localhost:3000` và thực hiện 2 thao tác sau:

1. **Demo Dữ liệu Sạch (Normal Run):**
   * Bấm nút **"▶ Run QA/QC Pipeline (Normal)"**.
   * Kết quả: Khung viền Bảng điều khiển đổi màu **Xanh (✅ PASS)**. AI Agent đánh giá dữ liệu hoàn hảo, mô phỏng (Canvas) hiển thị tọa độ xe khớp tuyệt đối với HD Map.

2. **Demo Bắt lỗi (Simulate Error) - Highlight của bài:**
   * Bấm nút **"⚠️ Simulate Error (Tiêm lỗi)"**.
   * Kết quả: Backend cố tình "tiêm" 2 lỗi: 1 xe tăng tốc lên 350km/h và 1 xe bị xóa tọa độ (Missing Frames). 
   * Giao diện đổi màu **Đỏ (❌ FAIL)** rực rỡ cảnh báo. Báo cáo AI Markdown sẽ phân tích chính xác từng vi phạm vật lý này và từ chối đưa dữ liệu rác vào mô hình VectorNet.

---

## 🚦 Traffic Sign — Chấm bài gán nhãn CVAT

* Guideline: [`guideline/LABELING_GUIDELINE_V1.md`](guideline/LABELING_GUIDELINE_V1.md) · chỗ còn mơ hồ: [`guideline/ISSUE_GUIDELINE.md`](guideline/ISSUE_GUIDELINE.md) · tiến độ: [`docs/CVAT_QAQC_TRACKER.md`](docs/CVAT_QAQC_TRACKER.md)
* Chấm mẫu 6 rules: `python backend/cvat_parser.py`
* Dựng task CVAT cho người gán + chấm theo GT trên nhiều ảnh: [`members/phong/cvat_eval`](members/phong/cvat_eval/README.md)
* Kiểm thử backend: `cd backend && python -m unittest test_backend_pipeline`
