from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

# Import các logic từ Phase 1, 2, 3
from backend_pipeline import parse_tfrecord_to_json, rule_based_qa
from ai_agent import generate_qa_report
from cvat_parser import evaluate_annotations

app = FastAPI(
    title="VectorNet QA/QC Pipeline API",
    description="API chạy luồng trích xuất dữ liệu, Rule-based QA/QC và AI QA/QC Agent",
    version="1.0.0"
)

# Cấu hình CORS để Frontend Next.js gọi được API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RunRequest(BaseModel):
    tfrecord_path: str = "waymo_mini_dataset/uncompressed/scenario/validation/uncompressed_scenario_validation_validation.tfrecord-00049-of-00150"
    simulate_error: bool = False

@app.post("/api/qaqc/run")
async def run_pipeline(req: RunRequest):
    try:
        # ---------------------------------------------------------
        # Phase 1: Parse Data (Trích xuất HD Map & Agent Dynamics)
        # ---------------------------------------------------------
        data = parse_tfrecord_to_json(req.tfrecord_path)
        
        # --- MÔ PHỎNG LỖI (Simulate Error) ---
        if req.simulate_error and "tracks" in data:
            if len(data["tracks"]) > 0 and len(data["tracks"][0].get("states", [])) > 0:
                # Tiêm lỗi Vận tốc cực cao
                data["tracks"][0]["states"][0]["velocity"] = 350.0
            if len(data["tracks"]) > 1 and len(data["tracks"][1].get("states", [])) > 2:
                # Tiêm lỗi Missing Frame
                data["tracks"][1]["states"][1]["valid"] = False
        
        # ---------------------------------------------------------
        # Phase 2: Rule-based QA (Check Vận tốc, Missing Frame, Map Boundary)
        # ---------------------------------------------------------
        data_with_flags = rule_based_qa(data)
        
        # ---------------------------------------------------------
        # Phase 3: AI Agent Report (Phân tích lỗi & Quyết định bằng Gemini)
        # ---------------------------------------------------------
        # Lọc gọn dữ liệu để tránh gửi chuỗi JSON quá lớn vượt giới hạn token của LLM
        summary_data = {
            "scenario_id": data_with_flags.get("scenario_id"),
            "tracks_count": len(data_with_flags.get("tracks", [])),
            "map_features_count": len(data_with_flags.get("map_features", [])),
            "qa_flags": data_with_flags.get("qa_flags", [])
        }
        
        # Gọi Gemini
        ai_report = generate_qa_report(summary_data)
        
        # Đính kèm AI report vào output cuối cùng
        data_with_flags["ai_report_markdown"] = ai_report
        
        # Loại bỏ trường decision cứng nhắc của Phase 2 nếu có
        if "decision" in data_with_flags:
            del data_with_flags["decision"]
            
        return data_with_flags
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import zipfile
import io

@app.post("/api/qaqc/cvat")
async def cvat_qaqc(gt_file: UploadFile = File(...), sub_file: UploadFile = File(...)):
    try:
        def read_file_or_zip(upload_file: UploadFile):
            content = upload_file.file.read()
            if upload_file.filename.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    # Tìm file JSON hoặc XML đầu tiên trong zip
                    for filename in z.namelist():
                        if filename.endswith('.json') or filename.endswith('.xml'):
                            return z.read(filename).decode('utf-8')
                raise Exception("Không tìm thấy file .json hoặc .xml nào trong file ZIP.")
            return content.decode('utf-8')

        gt_str = read_file_or_zip(gt_file)
        sub_str = read_file_or_zip(sub_file)
        
        report = evaluate_annotations(sub_str, gt_str)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Khởi chạy server FastAPI tại http://localhost:8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
