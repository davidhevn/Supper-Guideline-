# 📂 data/qa_reports — Báo cáo QA/QC tự động

Thư mục này chứa các file báo cáo được sinh ra tự động bởi `cvat_parser.py` sau khi chạy pipeline đánh giá.

## Cấu trúc file báo cáo

```json
{
  "labeler": "labeler_A",
  "scene": "scene_001",
  "evaluated_at": "2026-09-26T10:00:00",
  "summary": {
    "total_objects": 5,
    "pass": 3,
    "fail": 2,
    "score_percent": 60.0,
    "verdict": "FAIL"
  },
  "qa_flags": [ ... ],
  "details": [ ... ]
}
```

## Cách chạy

```bash
# Chay danh gia cho tung labeler
python cvat_parser.py \
  --gt data/ground_truth/gt_scene_001.json \
  --submission data/user_submissions/labeler_A/submission_scene_001.json \
  --output data/qa_reports/report_labeler_A_scene_001.json
```
