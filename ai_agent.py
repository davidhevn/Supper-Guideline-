import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Nạp biến môi trường từ file .env
load_dotenv()

# Cấu hình Gemini API (Tuyệt đối không hardcode key)
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def generate_qa_report(scenario_json_data):
    """
    Hàm gọi Gemini API để đóng vai trò Kỹ sư QA/QC đánh giá kịch bản dữ liệu.
    """
    if not api_key:
        return "⚠️ **Lỗi:** Chưa cấu hình `GEMINI_API_KEY` trong file `.env`. Hệ thống AI Agent đang tạm vô hiệu hóa."
        
    try:
        # Khởi tạo mô hình
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Thiết lập System Prompt và ghép dữ liệu vào
        prompt = f"""
Bạn là một Chuyên gia QA/QC Dữ liệu Xe tự lái dày dặn kinh nghiệm, chuyên phân tích và làm sạch dữ liệu từ Waymo Open Dataset phục vụ huấn luyện mô hình VectorNet.
Nhiệm vụ của bạn là đọc dữ liệu Tóm tắt Kịch bản (Scenario) dưới đây và đưa ra Báo cáo nghiệm thu bằng định dạng Markdown.

Hãy tập trung đánh giá mảng `qa_flags` do hệ thống logic Rule-based quét được trước đó. 
- Nếu mảng này CÓ dữ liệu, kịch bản đang chứa lỗi vật lý (như vận tốc phi lý, mất tọa độ, văng khỏi bản đồ). Bạn phải giải thích mức độ nghiêm trọng của lỗi này.
- Nếu mảng này RỖNG, kịch bản hoàn toàn sạch và đạt chuẩn. Hãy xác nhận điều này.

Dữ liệu đầu vào:
```json
{json.dumps(scenario_json_data, ensure_ascii=False, indent=2)}
```

Yêu cầu định dạng báo cáo Output bắt buộc theo 3 phần Markdown sau:
### 1. Tổng quan (Overview)
[Viết 1-2 câu tóm tắt mã Scenario ID và quy mô số lượng object trong kịch bản]

### 2. Phân tích Dị thường (Anomalies)
[Phân tích chuyên sâu về các lỗi trong qa_flags. Nếu không có lỗi, hãy khen ngợi chất lượng của hệ thống cảm biến SDV]

### 3. Quyết định (Decision)
[Kết luận là **✅ PASS (Chấp nhận)** hay **❌ FAIL (Từ chối)** và giải thích lý do ngắn gọn tác động của nó tới mô hình VectorNet]
"""
        
        # Gọi API
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"⚠️ **Lỗi khi gọi Gemini API:** {str(e)}"
