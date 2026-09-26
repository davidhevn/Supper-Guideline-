# 🎯 Kịch bản Thuyết trình: Automated CVAT QA/QC Pipeline & Traffic Sign Guideline (7 Slides)

> **Dành cho:** Anh DavidHE thuyết trình Pitching / Báo cáo đồ án.
> **Thời lượng khuyến nghị:** 5 – 7 phút (Mỗi slide 45 - 60 giây).
> **Điểm nhấn kịch bản:** Thực chiến, có dữ liệu thật từ bài nộp của Annotator Dũng, minh họa rõ ràng vòng lặp: *Guideline V1 ➔ Annotator làm thử ➔ Gatekeeper bắt lỗi ➔ Đúc kết cải tiến Guideline V2*.

---

## 📌 Tổng quan 7 Slide:
1. **Slide 1: Title** – Automated CVAT QA/QC Gatekeeper
2. **Slide 2: The Problem** – Nỗi đau kiểm duyệt thủ công & Vấn đề Guideline
3. **Slide 3: The Engine** – Bộ lọc 6 Rules tự động hóa 100%
4. **Slide 4: Live Case Study** – Chấm điểm thực tế bài nộp của Annotator Nguyễn Hữu Dũng
5. **Slide 5: Error Deep-Dive** – Mổ xẻ 3 lỗi chí mạng (Bẫy Ánh xạ, Thụt Box, Lỗi Thuộc tính)
6. **Slide 6: Guideline Evolution** – Từ phản hồi thực tế đến Guideline V2
7. **Slide 7: Vision & AI Agent** – Định hướng tích hợp LLM & Golden Set

---

## Slide 1: Title & Giới thiệu
* **Tiêu đề:** Automated CVAT QA/QC Gatekeeper & Traffic Sign Guideline
* **Phụ đề:** Chốt chặn tự động hóa dữ liệu gán nhãn xe tự lái & Chuẩn hóa Guideline V2
* **Người trình bày:** Hoàng Võ Minh Tuấn (DavidHE) & Nhóm sinh viên thực hiện:
  1. Hoàng Võ Minh Tuấn (MSV: 2A202602166)
  2. Dương Văn Long (MSV: 2A202602156)
  3. Nguyễn Thành Đạt (MSV: 2A202602151)
  4. Nguyễn Đại Hoàng (MSV: 2A202602208)
  5. Hoàng Việt Anh (MSV: 2A202602204)
  6. Mạc Phú Phong (MSV: 2A202602236)
* 🎙️ **Lời thoại gợi ý:**
  > *"Kính chào thầy và các bạn! Hôm nay em xin đại diện nhóm gồm 6 thành viên trình bày về **Automated CVAT QA/QC Gatekeeper** — công cụ tự động hóa kiểm soát chất lượng dữ liệu dán nhãn cho xe tự lái, cùng quá trình thử nghiệm thực tế với bài nộp của annotator để nâng cấp bộ quy chuẩn Guideline từ V1 lên V2."*

---

## Slide 2: The Problem (Nỗi đau của quy trình dán nhãn)
* **Tiêu đề:** Nút thắt cổ chai trong quy trình Data Labeling
* **Nội dung chính:**
  * Thu thập dữ liệu chỉ chiếm 20% thời gian, nhưng **gán nhãn và kiểm duyệt (QA/QC) ngốn tới 80% thời gian và ngân sách**.
  * **Tại sao kiểm duyệt bằng mắt thất bại?**
    * Mắt người dễ mỏi mệt, không thể đo chính xác tọa độ điểm ảnh (IoU).
    * Tiêu chuẩn Guideline dài 10-20 trang khiến Annotator dễ đọc lướt, hiểu sai hoặc quên tick thuộc tính.
    * Đưa dữ liệu bẩn vào huấn luyện sẽ làm lệch pha mô hình nhận diện xe tự lái, gây tai nạn nghiêm trọng trong thực tế.
* 🎙️ **Lời thoại gợi ý:**
  > *"Để huấn luyện xe tự lái nhận diện biển báo, chúng ta cần hàng chục ngàn ảnh gán nhãn chuẩn xác. Nhưng thực tế, QA Lead phải căng mắt soi từng tấm ảnh. Con người thì luôn có sai sót: nhầm nhóm biển, vẽ box lẹm viền, hoặc quên tick ô che khuất. Nếu không có bộ lọc tự động, 'rác' sẽ tràn vào tập train mô hình."*

---

## Slide 3: The Solution (Bộ lọc tự động: 6-Rules Engine)
* **Tiêu đề:** Cơ chế Chốt chặn tự động (The 6-Rules Engine)
* **Nội dung chính:**
  * **Rule 1 (IoU Threshold ≥ 0.7):** Đo độ lệch pixel, phát hiện box bị thụt (quá nhỏ) hoặc thừa (quá rộng).
  * **Rule 2 (Label Mismatch):** Kiểm tra sai nhãn danh mục chính (`prohibitory`, `danger`, `mandatory`, `other`).
  * **Rule 3 (Attribute Mismatch):** So khớp các thuộc tính bắt buộc: `sign_class`, `occluded`, `truncated`, `readable`.
  * **Rule 4 (Atomic Check):** Chống gộp cụm — cấm gom nhiều biển báo xếp chồng vào chung 1 bounding box.
  * **Rule 5 (Family Mapping Trap):** Bẫy ánh xạ chuẩn GTSDB — bắt các ca hiểm hóc (biển STOP màu đỏ nhưng theo chuẩn quốc tế bắt buộc là `other`, không phải `prohibitory`).
  * **Rule 6 (Attribute Format):** Kiểm tra giá trị hợp lệ (chống bỏ trống `sign_class`, ép `readable` đúng 3 giá trị `yes/no/uncertain`).
* 🎙️ **Lời thoại gợi ý:**
  > *"Nhóm đã chuyển hóa toàn bộ bộ quy chuẩn nghiệp vụ thành 6 Rules toán học và logic chặt chẽ. Hệ thống tự động so sánh bài nộp của Annotator với Golden Set (Ground Truth), chạy xong chỉ trong 0.2 giây thay vì mất hàng giờ soi tay."*

---

## Slide 4: Live Case Study (Chấm điểm bài nộp Annotator Nguyễn Hữu Dũng)
* **Tiêu đề:** Đưa vào thực tế: Đánh giá bài nộp của Annotator Dũng
* **Dữ liệu thực tế:** 
  * 3 ảnh đường phố độ phân giải cao (`00054.png`, `00177.png`, `00366.png`) với 12 biển báo chuẩn.
  * Annotator Dũng nhận Guideline V1 và tự thực hiện gắn nhãn trên công cụ CVAT.
* **Bảng kết quả Gatekeeper trả về:**
  * 🔴 **Điểm tổng kết:** **0.0% (0 / 12 objects đạt chuẩn)** ➔ **Kết luận: ❌ FAIL**
  * 📊 **Chỉ số kỹ năng (Metrics):**
    * **Attribute Completion Rate:** `80.0%` (có điền nhưng thiếu các trường then chốt).
    * **Precision (prohibitory):** `75.0%` | **Recall:** `100.0%` (Tất cả biển đều bị dán là biển cấm).
    * **Precision (other):** `0.0%` | **Recall:** `0.0%` (Hoàn toàn bỏ quên nhóm biển khác).
* 🎙️ **Lời thoại gợi ý:**
  > *"Đây là kết quả thực tế khi nhóm đưa Guideline V1 cho bạn Dũng làm bài test. Kết quả trả về 0% đạt chuẩn! Nhìn qua thì tưởng bạn làm tệ, nhưng khi nhìn sâu vào metrics, ta thấy bạn đạt Recall 100% nhóm biển cấm. Vậy chuyện gì thực sự đã xảy ra? Hãy cùng mổ xẻ ở slide tiếp theo."*

---

## Slide 5: Error Deep-Dive (Mổ xẻ 3 lỗi chí mạng)
* **Tiêu đề:** Mổ xẻ 3 lỗi kinh điển được phát hiện từ bài làm của Dũng
* **3 Lỗi chi tiết:**
  1. 🛑 **Lỗi 1: Dính Bẫy Ánh Xạ GTSDB (Rule 5) & Thiên vị nhãn mặc định (G-16):**
     * Biển **STOP** (bát giác đỏ), **Give Way** (tam giác ngược), **No Entry** (tròn đỏ) đều bị Dũng gán thành `prohibitory`.
     * *Nguyên nhân:* Nhãn đầu tiên trong CVAT mặc định là `prohibitory`. Labeler có xu hướng giữ nguyên nhãn mặc định khi thấy biển màu đỏ.
  2. 📐 **Lỗi 2: Lệch tọa độ / Box bị thụt (Rule 1 - IoU 0.25 < 0.7):**
     * Tại Object #2: Kích thước chuẩn là `70.96 x 21.7 px`, bài nộp chỉ vẽ `35.48 x 10.85 px`.
     * Hậu quả: Box bị thụt một nửa, lẹm mất 50% thông tin biển báo.
  3. 📝 **Lỗi 3: Bỏ trống 100% thuộc tính `sign_class` (Rule 3 & Rule 6):**
     * Toàn bộ 12 objects Dũng đều để `sign_class = ""` (trống rỗng).
     * *Nguyên nhân:* CVAT cho phép trường text bỏ trống mà không cảnh báo bắt buộc điền!
* 🎙️ **Lời thoại gợi ý:**
  > *"Ba lỗi này là minh chứng rõ nhất: Thứ nhất, bạn rơi vào đúng 'Bẫy ánh xạ' mà chúng em dự báo trước. Thứ hai, vẽ box thiếu kích thước. Và thứ ba, lỗi im lặng tai hại nhất: CVAT cho phép bỏ trống `sign_class` mà không hề cảnh báo. Nếu không có Rule 6 của Gatekeeper, tập dữ liệu này sẽ làm hỏng hoàn toàn model AI."*

---

## Slide 6: Guideline Evolution (Từ bài học thực tế đến Guideline V2)
* **Tiêu đề:** Đúc kết cải tiến: Nâng cấp Guideline V1 ➔ Guideline V2
* **Nội dung cải tiến (Dựa trên phản hồi thực nghiệm):**
  * 🔄 **Fix G-16 (Tránh lỗi mặc định):** Thêm nhãn giả định ban đầu `Select_Category...` trên CVAT để ép labeler phải chủ động chọn, không thể "nhắm mắt enter".
  * 📋 **Fix G-04 (Dropdown thay cho gõ tay):** Thay ô nhập tự do `sign_class` bằng danh sách Dropdown 43 mã GTSDB chuẩn, loại bỏ 100% lỗi gõ sai chính tả hay bỏ trống.
  * 📖 **Fix G-17 & G-20 (Bảng tra cứu trực quan có hình ảnh):** Bổ sung trực tiếp hình ảnh biển Stop, Give Way, No Entry vào phần Cảnh báo đỏ ngay trang đầu Guideline V2.
  * 📏 **Ngưỡng kích thước tối thiểu (Fix G-06):** Quy định rõ biển dưới 15x15 px hoặc quá mờ thì xử lý như thế nào.
* 🎙️ **Lời thoại gợi ý:**
  > *"Nhờ có dữ liệu thực nghiệm từ bạn Dũng, nhóm đã hoàn thiện tài liệu ISSUE_GUIDELINE với 20 vấn đề chi tiết, từ đó xuất bản Guideline V2. Bài học rút ra: Guideline tốt không phải là viết cho dài, mà là thiết kế sao cho người làm KHÔNG THỂ LÀM SAI."*

---

## Slide 7: Vision & Next Steps (Tương lai & Tích hợp AI Agent)
* **Tiêu đề:** Tầm nhìn: Hệ sinh thái QA/QC thông minh toàn diện
* **Các bước triển khai tiếp theo:**
  * 🤖 **AI QA/QC Agent (Google Gemini):** Nhúng LLM đọc JSON kết quả để tự động xuất báo cáo giải thích lỗi bằng ngôn ngữ tự nhiên, gửi email hướng dẫn tận tình cho từng Labeler.
  * 🕵️ **Hidden Benchmark (Golden Set ngầm):** Tự động trộn 5-10% ảnh đã có đáp án chuẩn vào các batch dán nhãn thông thường để chấm điểm ngầm và xếp hạng năng lực nhân sự liên tục.
  * 🌐 **Full-Stack Web Dashboard:** Hoàn thiện bảng điều khiển web tương tác trực tiếp cho QA Lead và Project Manager theo dõi thời gian thực.
* 🎙️ **Lời thoại gợi ý:**
  > *"Trong tương lai gần, hệ thống sẽ kết hợp cùng AI Agent của Google Gemini để tự động trò chuyện, đào tạo lại labeler khi họ làm sai. Chúng em tin rằng sự kết hợp giữa Rule-based chặt chẽ và Trí tuệ Nhân tạo linh hoạt chính là chìa khóa cho chất lượng dữ liệu AI. Em xin chân thành cảm ơn thầy và các bạn đã lắng nghe!"*
