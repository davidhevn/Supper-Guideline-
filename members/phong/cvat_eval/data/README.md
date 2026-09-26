# data/ — dữ liệu riêng (không lên GitHub)

Mặc định tool dùng data chung của nhóm ở gốc repo (`data/raw/`, `data/ground_truth/`). Thư mục này chỉ để chứa bộ ảnh
và GT **riêng** mà bạn không muốn đặt vào data chung; mọi thứ trong đây đều bị `.gitignore` chặn, chỉ giữ README.
Trỏ tool sang đây bằng `python sign.py use --images data/images/<bộ> --gt data/gt/<file>`.
