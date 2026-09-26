# data/ — không lên GitHub (xem .gitignore)

Repo nhóm để public, còn quy định của nhóm là ảnh và GT **không push**. Mọi thứ trong thư mục này chỉ nằm trên máy
bạn, hoặc được chia sẻ riêng qua Drive (`python sign.py pack` tạo zip có kèm data).

```
data/
├── images/<bộ ảnh>/      ảnh .jpg/.png — tên file = sample_id
├── gt/<file GT>          CVAT for images 1.1 (.xml hoặc .zip export) hoặc COCO 1.0 (.json)
└── ATTRIBUTION.txt       nguồn/giấy phép ảnh
```

Bộ có sẵn (bản chia sẻ riêng của Phong): `images/gtsdb28/` gồm 28 ảnh GTSDB GTS01–28 của lab Day 9, và
`gt/gt_gtsdb28_ref.xml` là GT tham chiếu GTSDB đã đổi sang schema Guideline V1.2 (55 box, label = nhóm biển, có
`sign_class`). GT này **không có** readable/occluded/truncated thật (đặt mặc định), nên đi kèm
`schema/eval_reference.json`, file cấu hình không chấm các attribute đó.
