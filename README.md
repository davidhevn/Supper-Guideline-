# 🚀 VectorNet QA/QC Pipeline (MVP)

## 📖 Giới thiệu Dự án
Trong quá trình huấn luyện các mô hình dự đoán quỹ đạo xe tự lái như **VectorNet**, chất lượng dữ liệu đầu vào (HD Maps, Agent Dynamics) đóng vai trò sống còn. Một tọa độ bị đứt gãy hoặc một xe chạy với vận tốc phi lý (VD: 300km/h) có thể làm sụp đổ toàn bộ quá trình hội tụ của mô hình.

**VectorNet QA/QC Pipeline** là một công cụ tự động hóa toàn diện (End-to-End) giúp đọc, trích xuất dữ liệu thô từ **Waymo Open Dataset (.tfrecord)**, đưa qua màng lọc kiểm tra lỗi vật lý (Rule-based), và cuối cùng sử dụng **Trí tuệ Nhân tạo (Gemini AI Agent)** để đánh giá, ra quyết định PASS/FAIL trước khi nghiệm thu dữ liệu.

---

## 🛠️ Công nghệ sử dụng (Tech Stack)
* **Backend:** Python, FastAPI, TensorFlow (Waymo Open Dataset API).
* **AI Agent:** Google Gemini (gemini-1.5-flash) - Ra quyết định đánh giá.
* **Frontend:** Next.js, TailwindCSS, HTML Canvas API, React Markdown.

---

## ⚙️ Hướng dẫn Cài đặt & Khởi chạy

### 1. Cài đặt Backend (FastAPI)
```bash
# Di chuyển vào thư mục backend
cd my_vectornet_project

# Tạo môi trường ảo (Khuyến nghị)
python -m venv venv
# Windows: venv\Scripts\activate
# MacOS/Linux: source venv/bin/activate

# Cài đặt thư viện
pip install fastapi uvicorn google-generativeai pydantic python-dotenv tensorflow waymo-open-dataset-tf-2-12-0

# Cấu hình AI Agent
# Tạo file .env tại thư mục my_vectornet_project và thêm dòng sau:
GEMINI_API_KEY="Điền_API_Key_Của_Bạn_Vào_Đây"

# Chạy Backend Server
python main.py
# API sẽ chạy tại: http://localhost:8000
```

### 2. Cài đặt Frontend (Next.js)
```bash
# Mở một Terminal mới, di chuyển vào thư mục frontend
cd my_vectornet_project/frontend

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
