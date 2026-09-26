# 📂 data/user_submissions — Bài nộp của Labeler

Thư mục này chứa các file JSON annotation do từng Labeler export từ CVAT và nộp lại.

## Cấu trúc thư mục

```
user_submissions/
├── labeler_A/
│   ├── submission_scene_001.json
│   └── submission_scene_002.json
├── labeler_B/
│   └── submission_scene_001.json
└── ...
```

## Quy trình nộp bài

1. Labeler hoàn thành task trên CVAT.
2. Export file JSON từ CVAT theo định dạng **CVAT for images 1.1**.
3. Đặt tên file: `submission_{scene_id}.json`
4. Để file vào đúng thư mục tên mình: `user_submissions/{tên_labeler}/`

## Lưu ý

- Thư mục này **KHÔNG được push lên GitHub** (xem `.gitignore`).
- Chỉ QA Lead mới chạy script đánh giá trên thư mục này.
