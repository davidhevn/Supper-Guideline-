# 📊 Kịch bản Thuyết trình: VectorNet QA/QC Pipeline

**Slide 1: Tiêu đề**
* **Tiêu đề lớn:** Tự động hóa Pipeline Kiểm duyệt Dữ liệu Xe Tự Lái
* **Tiêu đề phụ:** Ứng dụng Rule-based & LLM Agent cho Mô hình VectorNet (Waymo Dataset)
* **Người trình bày:** [Tên của bạn]

---

**Slide 2: Nỗi đau của Kỹ sư AI (Pain Points)**
* **Vấn đề:** Dữ liệu thô từ cảm biến (Lidar, Camera) luôn tiềm ẩn nhiễu (Noise).
* **Các lỗi vật lý chết người:**
  * Xe tự nhiên "dịch chuyển tức thời" (Missing frames / Bị đứt gãy tọa độ).
  * Vận tốc phi vật lý (VD: Một chiếc xe chạy 350km/h trong thành phố).
  * Xe văng ra khỏi giới hạn bản đồ (Out-of-bounds).
* **Hậu quả:** Mô hình VectorNet học sai hành vi, gây ra tai nạn trong mô phỏng tự lái. Kiểm duyệt thủ công hàng ngàn kịch bản là điều bất khả thi!

---

**Slide 3: Giải pháp của chúng tôi**
* Xây dựng một **Chốt chặn tự động (Automated Gatekeeper)** End-to-End ngay trước bước Training.
* **3 Màng lọc Dữ liệu:**
  1. **Phase 1 (Data Extraction):** Giải nén file `.tfrecord`, tách riêng Bản đồ (HD Map) và Quỹ đạo xe (Agent Dynamics).
  2. **Phase 2 (Rule-based QA):** Lọc "cứng" bằng các thuật toán kiểm tra vật lý.
  3. **Phase 3 (AI Agent):** Lọc "mềm" bằng LLM (Gemini) để phân tích lỗi và ra quyết định PASS/FAIL thông minh.

---

**Slide 4: Kiến trúc Hệ thống (Architecture)**
* *(Gợi ý: Hãy chèn một sơ đồ flow-chart đơn giản ở slide này)*
* **Backend Core:** Python + FastAPI (Xử lý mượt mà dữ liệu lớn, Parse TFRecord cực nhanh).
* **AI Brain:** Google Gemini API (gemini-1.5-flash).
* **Frontend Dashboard:** Next.js + TailwindCSS + Canvas API (Hiển thị thời gian thực quỹ đạo xe và bản đồ).
* **Data Flow:** UI ➡️ POST Request ➡️ Parse Data ➡️ Rule QA ➡️ LLM Agent ➡️ Trả JSON tổng hợp ➡️ Render báo cáo và Đổi màu Xanh/Đỏ trên Dashboard.

---

**Slide 5: Chốt chặn Rule-Based (Phase 2)**
* Thuật toán kiểm tra giới hạn vật lý nghiêm ngặt:
  * **Rule 1 (Missing Frames):** Quét cờ `valid` của Protobuf, bắt thóp các xe bị đứt gãy tọa độ giữa chừng.
  * **Rule 2 (Kinematics Anomalies):** Cảnh báo ngay lập tức nếu $Vận tốc > 200 km/h$.
  * **Rule 3 (Map Boundary):** Kiểm tra giới hạn Bounding box (cộng thêm 10m an toàn) để đảm bảo xe không bay khỏi bản đồ.

---

**Slide 6: Bộ não AI Agent (Phase 3)**
* **Tại sao cần AI?** Thay vì viết hàng tá code `if-else` khô khan để in lỗi, hãy nhường việc đánh giá và ra quyết định cho AI.
* **Input:** Bảng tóm tắt Scenario + Các cờ lỗi (`qa_flags`).
* **Prompt Engineering:** Ép AI đóng vai Kỹ sư QA/QC Xe tự lái thâm niên.
* **Output:** Báo cáo Markdown 3 phần chuyên nghiệp: Tổng quan (Overview), Phân tích Dị thường (Anomalies), Quyết định Chấp nhận hay Từ chối (Decision).

---

**Slide 7: Showcase / Live Demo (Cảnh quan trọng nhất)**
* *(Lúc này bạn sẽ bật Video Demo quay màn hình Dashboard)*
* **Bước 1 (Dữ liệu hoàn hảo):** Bấm "Run QA/QC Pipeline (Normal)". Hệ thống mượt mà báo ✅ PASS màu Xanh. Các xe (chấm tròn) di chuyển đúng vạch kẻ đường (Canvas).
* **Bước 2 (Highlight):** Bấm "Simulate Error (Tiêm lỗi)". Backend giả lập một xe phóng 350km/h và một xe đứt tọa độ.
* **Kết quả:** Màn hình chớp ❌ FAIL màu Đỏ cực gắt. AI Agent viết báo cáo vạch trần chính xác 2 lỗi vừa tạo. Chặn đứng nguy cơ dữ liệu rác!

---

**Slide 8: Tổng kết & Hướng phát triển Tương lai**
* **Kết quả đạt được:** Hoàn thành MVP đáp ứng tiêu chuẩn tự động hóa của Data Pipeline hiện đại. Giải quyết được bài toán khó nhất trước khi train mô hình.
* **Tương lai (Scale-up):**
  * Hỗ trợ quét hàng loạt (Batch Processing) hàng ngàn file `.tfrecord` tự động trong đêm.
  * Đưa visualization lên 3D (VD: WebGL, Three.js) thay vì 2D Canvas.
  * **Auto-healing:** Dùng AI không chỉ để "mắng" mà còn để nội suy (interpolate), vá lỗi tự động cho các đoạn khung hình bị mất.

---

**Slide 9: Lời cảm ơn & Q/A**
* Cảm ơn Hội đồng đánh giá và các thầy cô đã lắng nghe phần trình bày.
* Q/A: (Dành thời gian trả lời các câu hỏi từ ban giám khảo).
