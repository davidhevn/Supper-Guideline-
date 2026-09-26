# 🎯 Kịch bản Thuyết trình Pitching: Automated CVAT QA/QC Pipeline (5 Slides)

> **Hướng dẫn:** File này được thiết kế theo chuẩn Pitching Demo. 5 Slide là con số hoàn hảo để trình bày nhanh, tập trung vào Nỗi đau (Problem) - Giải pháp (Solution) - Trực quan (Demo) - Chỉ số (Metrics) - Tương lai (Vision).

---

## Slide 1: The Problem (Nỗi đau của quy trình dán nhãn)
* **Tiêu đề:** Nút thắt cổ chai trong quy trình Data Labeling.
* **Nội dung trình bày:**
  * Thu thập dữ liệu thì nhanh, nhưng dán nhãn (Labeling) và kiểm duyệt (QA/QC) lại tốn 80% thời gian của dự án AI.
  * **Các lỗi sai "kinh điển" của Labeler (Human Errors):**
    1. Rơi vào **Bẫy Ánh xạ (Mapping Traps)**: Thấy biển STOP màu đỏ là gán ngay nhãn `prohibitory` (Cấm), trong khi chuẩn quốc tế GTSDB quy định nó phải là `other`.
    2. **Gộp cụm sai quy tắc (Atomic Violation)**: Gom 2-3 biển báo vào chung 1 bounding box to đùng thay vì tách riêng.
    3. **Quên thuộc tính (Attributes)**: Bỏ sót các thông tin sống còn cho xe tự lái như bị che khuất (`occluded`) hay bị cắt mép (`truncated`).
  * **Hậu quả:** Model Computer Vision học sai, nhận diện kém. QA Lead kiệt sức vì phải review hàng ngàn ảnh bằng mắt thường.

---

## Slide 2: The Solution (Giải pháp của chúng tôi)
* **Tiêu đề:** Automated CVAT QA/QC Gatekeeper
* **Nội dung trình bày:**
  * Chúng tôi xây dựng một **Chốt chặn tự động (Gatekeeper)** thay thế hoàn toàn sức người trong khâu chấm điểm.
  * **Cơ chế hoạt động (The 6-Rules Engine):**
    * **Rule 1 (IoU):** Phát hiện box vẽ bị thụt hoặc quá rộng so với chuẩn.
    * **Rule 2 & 5 (Semantic Logic):** Phát hiện sai nhãn và đặc biệt là hệ thống từ điển phát hiện "Bẫy Ánh xạ" (vd: User cố tình gán STOP thành Cấm -> Phạt ngay).
    * **Rule 3 & 6 (Attributes):** Kiểm tra tính toàn vẹn của dữ liệu (điền đủ, điền đúng định dạng).
    * **Rule 4 (Atomic Check):** Thuật toán chống gộp cụm trái phép.

---

## Slide 3: Live Demo & Architecture (Sản phẩm thực tế)
* **Tiêu đề:** Từ CVAT đến Báo cáo tự động chỉ trong 1 giây.
* **Nội dung trình bày (kết hợp show Demo):**
  * *(Mở màn hình Terminal hoặc UI lên)*
  * **Kiến trúc luồng (Flow):** 
    1. Labeler làm việc trên CVAT -> Xuất file COCO JSON / XML.
    2. QA Lead chuẩn bị 1 file Ground Truth (đáp án chuẩn) cắm sẵn vào hệ thống.
    3. Đẩy file của Labeler qua API.
  * **Thực hành Demo:** Chúng ta cùng xem hệ thống "bắt tại trận" 1 bài nộp sai. 
  * *(Chạy script)* -> Màn hình in ra lỗi đỏ chót: *Lỗi Rule 5 - Bẫy ánh xạ nhãn! Cảnh báo gộp cụm! Cảnh báo quên tích Occluded!*
  * Mỗi lỗi đều đi kèm một **Hint (Gợi ý)** trích xuất thẳng từ *Guideline V1.2* để Labeler biết chỗ sửa.

---

## Slide 4: Metrics that Matter (Chỉ số đo lường)
* **Tiêu đề:** Không chỉ tìm lỗi, chúng tôi đo lường chất lượng nhân sự.
* **Nội dung trình bày:**
  * Báo cáo đầu ra không chỉ có Pass/Fail, mà tự động tính toán các chỉ số khắt khe nhất để đánh giá Labeler:
    * 🎯 **Attribute Completion Rate:** Đo mức độ cẩn thận của Labeler (họ có chịu điền đủ các checkbox/dropdown không?).
    * 🎯 **Precision & Recall per class:** Biết chính xác Labeler đang yếu ở nhóm biển báo nào (vd: Thường xuyên bỏ sót biển Danger, hay nhận diện nhầm biển Mandatory).
  * Từ các Data này, Project Manager dễ dàng quyết định thưởng/phạt hoặc training lại nhân sự.

---

## Slide 5: The Vision (Tương lai của dự án)
* **Tiêu đề:** Mở rộng quy mô & Tích hợp AI (Next Steps).
* **Nội dung trình bày:**
  * MVP hiện tại đã xử lý trọn vẹn logic (Rule-based) cực kỳ chặt chẽ.
  * **Giai đoạn tiếp theo (Phase 3 & 4):**
    1. **Tích hợp LLM Agent (Gemini):** Truyền kết quả JSON này cho AI để AI viết nhận xét bằng ngôn ngữ tự nhiên, đóng vai "Thầy giáo" gửi email nhắc nhở Labeler một cách mềm mỏng.
    2. **Đánh giá chéo (Cross-validation):** Nâng cấp lên Guideline V2/V3, phát đề ngẫu nhiên (chèn Golden Set) ẩn vào task của Labeler trên CVAT để chấm điểm ngầm.
  * **Lời kết:** Cảm ơn mọi người đã lắng nghe! (Q&A)
