# 📂 data/ground_truth — Đáp án chuẩn (Golden Set)

> ⚠️ **MẬT — KHÔNG chia sẻ file này với Labeler trước khi họ hoàn thành task.**

Thư mục này chứa các file JSON đáp án chuẩn do **QA Lead / Chuyên gia** tự tay dán nhãn, dùng để đối chiếu với bài nộp của labeler.

## Cấu trúc file JSON (chuẩn CVAT export)

```json
{
  "annotations": [
    {
      "id": 1,
      "label": "prohibitory",
      "bbox": [x_min, y_min, x_max, y_max],
      "case_type": "general",
      "attributes": {
        "readable": "yes",
        "sign_class": "speed_limit_50",
        "occluded": false,
        "truncated": false,
        "relevant_to_ego": true
      }
    }
  ]
}
```

## Quy tắc đặt tên file

```
gt_{scene_id}.json
Ví dụ: gt_scene_001.json
```

## Lưu ý bảo mật

- Thư mục này **KHÔNG được push lên GitHub** (xem `.gitignore`).
- Lưu trữ trên Google Drive với quyền truy cập hạn chế.
- Chỉ QA Lead mới có quyền tạo/sửa file trong thư mục này.
