# Issue Guideline — các chỗ còn mơ hồ / mâu thuẫn trong `LABELING_GUIDELINE_V1.md` (V1.2)

Rà soát ngày 2026-09-26, người rà: Phong. Mỗi issue có **trích nguyên văn**, **vì sao gây khó**, **dẫn chứng** trên
3 ảnh của nhóm (`data/raw/00054.png`, `00177.png`, `00366.png`) hoặc bảng GTSDB chính thức, và **đề xuất sửa**.
Đây là đề xuất — nhóm quyết định rồi ghi vào mục 7 (Lịch sử thay đổi) của guideline.

Mức độ theo hậu quả khi chấm tự động:

- **critical**: người gán làm đúng chữ trong guideline vẫn bị chấm sai, hoặc sai nhãn lớp.
- **major**: hai người hợp lý sẽ làm khác nhau, nên kết quả chấm không ổn định.
- **minor**: câu chữ hoặc trình bày.

| ID | Mục | Vấn đề | Mức | Trạng thái |
|---|---|---|---|---|
| G-01 | 4 | Bảng mã sai so với GTSDB: 27–31, 32, 41, 42; thiếu 6, 16 | critical | open |
| G-02 | 2, 4, 5.2 | Không nói rõ chỉ gán 43 lớp GTSDB hay mọi biển giao thông | critical | open |
| G-03 | 5.1 | Biển phụ phải vẽ, nhưng GT GTSDB không có; `sign_class` của biển phụ bỏ trống | critical | open |
| G-04 | 3, 4 | `sign_class` là ô text tự gõ, không có danh sách tên chuẩn | major | open |
| G-05 | 5.4, 5.5 | Box khi bị che thì vẽ "bao trọn" (ước lượng), bị cắt mép thì "không ước lượng" | major | open |
| G-06 | 5.4, 5.5 | Ngưỡng 15 px: không rõ cạnh nào, đo thế nào; không có sai số | major | open |
| G-07 | 3, 5.4 | `readable`: không định nghĩa yes / no / uncertain; không nói quan hệ với `sign_class` và label | major | open |
| G-08 | 3 | `relevant_to_ego` là checkbox, không có tiêu chí, không có giá trị "không biết" | major | open |
| G-09 | 1 | Không có đường escalate khi không chắc | major | open |
| G-10 | 5.1 | Chưa định nghĩa "sát" mặt biển; IoU 0.7 quá gắt với biển 18–24 px | major | open |
| G-11 | (thiếu) | Không có rule cho ảnh tối, nhoè, ngược sáng | major | open |
| G-12 | 5.3 | Loại trừ còn mơ hồ: LED, "hỏng > 70%", biển xoay nghiêng/nhìn cạnh | minor | open |
| G-13 | 2 | Mô tả `danger` là "nền vàng" — biển Đức nền trắng | minor | open |
| G-14 | 3, 6 | Không nói ảnh không có biển thì nộp gì | minor | open |
| G-15 | đầu file, 7 | Tên file V1 nhưng nội dung V1.2; lịch sử không ghi lý do | minor | open |

---

## G-01 · Bảng mã (mục 4) sai so với GTSDB — **critical**

**Nguyên văn:**

- `27–31 | end_of_* | other | Biển "Hết cấm"`
- `32–41 | mandatory_* | mandatory`
- `42 | end_of_all_restrictions | other`

Bảng cũng không có mã 6 và 16.

**Theo GTSDB** (43 lớp, cách chia nhóm chính thức của benchmark):

| Mã | Biển thật | Nhóm đúng | Guideline ghi |
|---|---|---|---|
| 6 | End of speed limit 80 | other | (không có trong bảng; 5.2 có `end_of_speed_limit_80` nhưng không có mã) |
| 16 | No trucks (> 3.5 t) | prohibitory | (không có) |
| 27 | Pedestrians | **danger** | other |
| 28 | Children crossing | **danger** | other |
| 29 | Bicycles crossing | **danger** | other |
| 30 | Ice / snow | **danger** | other |
| 31 | Wild animals | **danger** | other |
| 32 | End of all speed and passing limits | **other** | mandatory |
| 41 | End of no passing | **other** | mandatory |
| 42 | End of no passing (trucks) | other | other, nhưng sai tên (`end_of_all_restrictions` là mã **32**) |

**Dẫn chứng:** `00054.png` có biển *đi bộ qua đường* (mã 27, box 1113,436 40×38). Làm đúng theo bảng mục 4 thì
người gán sẽ chọn `other`, còn GT GTSDB ghi `danger`. Kết quả là bị chấm `wrong_label`, mức critical, dù đã theo sát
guideline. Lỗi này lặp lại ở `backend/cvat_parser.py` (`FAMILY_MAPPING_TRAP`, ghi "GTSDB #42 = hết tất cả hạn chế").

**Đề xuất:** thay mục 4 bằng bảng đủ 43 dòng (mã · tên · `sign_class` · nhóm), sinh ra từ danh sách GTSDB chuẩn.
Sửa `FAMILY_MAPPING_TRAP` cho khớp.

## G-02 · Không rõ phạm vi: chỉ 43 lớp GTSDB hay mọi biển? — **critical**

**Nguyên văn:** mục 2 `other | Tất cả loại còn lại | Mọi hình dạng khác`. Mục 1 lại ghi "theo chuẩn GTSDB".

**Vì sao khó:** GTSDB chỉ gán 43 lớp. Các biển không thuộc 43 lớp đó (biển chỉ đường, biển thông tin, biển tên
đường…) có phải vẽ và gán `other` không?

**Dẫn chứng:**

- `00177.png`: biển chỉ đường vàng cỡ lớn (Bochum / Dortmund / Hagen, khoảng x 770–890, y 295–415). GT không có box.
- `00054.png`: biển vàng nhỏ khoảng (1030, 465) và biển chữ nhật "W52" trên tường. GT không có.
- `00366.png`: hai biển chỉ đường xanh trên cao tốc (khoảng x 660–715, y 560–575). GT không có.

Người gán hiểu "other = tất cả loại còn lại" sẽ vẽ các biển này. Khi chấm, chúng thành box `extra`, bị trừ precision.

**Đề xuất:** ghi một câu rõ ràng: *"Chỉ gán 43 lớp GTSDB (bảng mục 4). Biển chỉ đường, biển thông tin, biển tên đường,
biển nhà/công ty: không gán."* Nếu nhóm muốn giữ các biển đó thì phải bổ sung chúng vào GT và đặt `sign_class`
riêng, ví dụ `direction_sign`.

## G-03 · Biển phụ: guideline bắt vẽ, GT không có — **critical**

**Nguyên văn:** mục 5.1 `Biển chính + biển phụ: Mỗi biển 1 box. Biển phụ gán nhãn other.`

**Vì sao khó:**

1. GTSDB không gán biển phụ, nên box biển phụ luôn bị chấm là `extra`.
2. `sign_class` của biển phụ nên ghi gì? 43 lớp không có biển phụ, mà mục 3 lại bắt buộc điền.

**Dẫn chứng:** `00054.png` có biển phụ nhỏ ngay dưới biển *tốc độ tối đa 20* (khoảng 1118–1147, 504–518). GT chỉ có
box biển 20.

**Đề xuất:** chọn một trong hai hướng:

- **(a)** *Không vẽ biển phụ*: khớp GTSDB, đơn giản nhất.
- **(b)** Vẽ biển phụ với `sign_class = supplementary_panel`, đồng thời bổ sung vào GT. Nếu chọn cách này, cấu hình
  chấm phải bỏ qua biển phụ khi GT là GTSDB gốc.

## G-04 · `sign_class` tự gõ, không có tên chuẩn — **major**

**Nguyên văn:** mục 3 `sign_class | Text | Mã GTSDB (xem bảng mục 4)`. Mục 4 chỉ cho mẫu tên như `danger_*`,
`mandatory_*`, `end_of_*`, `speed_limit_20 → speed_limit_120`.

**Vì sao khó:** cùng một biển, mỗi người có thể gõ một kiểu: `curve_left` / `danger_curve_left` / `bend_left` /
`19`. Chấm tự động so khớp chữ, nên đúng biển vẫn bị tính sai. Ngoài ra bảng dùng tên `speed_limit_20 → 120` mà
không nói có tồn tại `speed_limit_90` hay không (GTSDB không có 90).

**Đề xuất:** đổi `sign_class` trong CVAT thành **select**, gồm 43 giá trị cố định theo dạng `NN_ten`, ví dụ
`27_pedestrians`, cộng thêm `unknown`. Khi đó label (nhóm biển) suy ra được từ `sign_class`, và kiểm được luôn lỗi
"bẫy ánh xạ" (mục 5.2) bằng một bảng tra.

## G-05 · Box khi bị che: ước lượng hay không? — **major**

**Nguyên văn:**

- 5.4: `Biển bị che 50–70%: Vẽ box bao trọn + occluded` và `< 50%: Vẽ box bao trọn (kể cả phần bị che)`.
- 5.5 (bị cắt mép ảnh): `Box kéo đến tận mép ảnh, không ước lượng phần ngoài.`

**Vì sao khó:**

1. Bị che thì vẽ cả phần không nhìn thấy (phải đoán), bị cắt mép thì không được đoán. Hai quy ước ngược nhau mà
   không nêu lý do.
2. "Che bao nhiêu %" đo bằng gì: diện tích mặt biển hay chiều cao? Ranh giới 50% và 70% sẽ mỗi người ước một kiểu.
3. Hàng 50–70% và hàng < 50% cho cùng một hành động, vậy hai hàng tách ra để làm gì?
4. `guideline/sample_images/README.md` coi "chỉ vẽ phần nhìn thấy" là **sai**. Card 03 của lab lại quy ước ngược lại.

**Đề xuất:** chọn **một** quy ước cho cả hai trường hợp. Khuyến nghị: *box chỉ bao phần nhìn thấy*, bật `occluded`
hoặc `truncated`. Cách này không phải đoán, và IoU ổn định hơn. Gộp hai hàng 50–70% và < 50% thành một, giữ ngưỡng
"> 70% thì bỏ qua", kèm một câu hướng dẫn cách ước lượng.

## G-06 · Ngưỡng 15 px chưa định nghĩa — **major**

**Nguyên văn:** 5.4 `Box < 15 × 15 pixel → Bỏ qua`. 5.5 `Chỉ bỏ qua nếu phần nhìn thấy < 15px.`

**Vì sao khó:**

- Box 20×12 thì sao: "< 15×15" nghĩa là cả hai cạnh cùng < 15, hay chỉ một cạnh?
- Đo trên ảnh gốc hay trên màn hình đã zoom?
- Biển gần đúng 15 px thì người vẽ, người không, vì không có sai số cho phép.

**Dẫn chứng:** biển nhỏ nhất trong dữ liệu là *keep right* ở `00177.png`, 18×18 px, chỉ trên ngưỡng 3 px. Người gán
đo lệch 1–2 px là sẽ quyết định khác nhau.

**Đề xuất:** viết thành *"Bỏ qua nếu **cạnh ngắn** của box < 15 px, đo trên ảnh gốc (zoom
100%)"*. Nói thêm: biển nằm trong khoảng 13–17 px thì cứ vẽ, và QA không tính lỗi ở cả hai phía.

## G-07 · `readable` chưa có định nghĩa — **major**

**Nguyên văn:** mục 3 `readable | yes / no / uncertain | Bắt buộc chọn 1 trong 3`. 5.4 `Biển đủ lớn, không đọc
được nội dung → readable = uncertain`.

**Vì sao khó:**

1. `no` khác `uncertain` ở chỗ nào? Theo 5.4, "không đọc được" lại là `uncertain`, vậy khi nào mới dùng `no`?
2. Không đọc được nội dung thì `sign_class` phải là `unknown`? Còn label (nhóm biển) chọn theo hình dạng và màu, hay
   cũng bỏ?
3. Được zoom bao nhiêu? Zoom rồi đoán nội dung có được tính là "đọc được" không?

**Dẫn chứng:** `00366.png` là ảnh chạng vạng, nhoè do chuyển động. Hai cặp biển 24–28 px xếp chồng (tốc độ tối đa
120 + cấm xe tải vượt) chỉ đọc được con số nếu zoom mạnh. Đây đúng là chỗ mỗi người sẽ chọn một giá trị `readable`
khác nhau.

**Đề xuất:** định nghĩa bằng tiêu chí quan sát được:

- `yes`: đọc được đúng loại biển ở mức zoom ≤ 200%.
- `uncertain`: thấy rõ hình dạng và màu, nhưng không chắc loại biển. Khi đó vẫn chọn nhóm biển, còn
  `sign_class = unknown`.
- `no`: không nhận ra được cả nhóm biển. Khi đó chọn luôn *bỏ qua*, hoặc escalate (xem G-09).

## G-08 · `relevant_to_ego` không có tiêu chí — **major**

**Nguyên văn:** mục 3 `relevant_to_ego | Checkbox | Tích nếu có hiệu lực với làn xe tự lái`.

**Vì sao khó:** ảnh đơn không cho biết xe sẽ đi làn nào hay rẽ hướng nào. Checkbox chỉ có đúng/sai, không có
"không biết", nên người gán buộc phải đoán. Mặc định để trống lại thành `false`, tức là "không liên quan" một cách
im lặng.

**Dẫn chứng:** `00177.png` có 2 biển STOP ở hai phía nhánh rẽ, cộng với biển *nhường đường* ở bên phải. Biển nào có
hiệu lực với xe mình tuỳ vào hướng đi, mà hướng đi không suy ra được từ ảnh.

**Đề xuất:** đổi thành select `yes / no / unknown`, mặc định `unknown`. Thêm tiêu chí: `yes` chỉ khi biển đặt ở phía
làn của xe mình **và** không có mũi tên hay biển phụ giới hạn làn khác. Nếu không có cách kiểm thì bỏ attribute này
khỏi phần chấm.

## G-09 · Không có đường escalate — **major**

**Nguyên văn:** mục 1 `Nếu nghi ngờ → Đọc lại Guideline, không tự ý sáng tạo quy tắc mới.`

**Vì sao khó:** guideline không phủ hết mọi tình huống (xem G-02, G-03, G-11). Khi đọc lại vẫn không quyết được thì
người gán chỉ còn cách đoán. Lỗi do đoán sẽ bị tính là lỗi thao tác, trong khi nguyên nhân thật là guideline thiếu
rule, nên nhóm không học được gì từ lỗi đó.

**Đề xuất:** thêm checkbox `needs_review` trên từng box, ghi rõ khi nào được bật. QA quy định box có `needs_review`
thì không tính là lỗi mà đưa vào danh sách edge case để bổ sung rule.

## G-10 · Chưa định nghĩa "sát"; IoU 0.7 gắt với biển nhỏ — **major**

**Nguyên văn:** 5.1 chỉ liệt kê những gì phải loại khỏi box (cột, dây, bệ, bóng). Hệ thống QA dùng
`IOU_THRESHOLD = 0.7`.

**Vì sao khó:** không nói box có lấy **viền, khung** của mặt biển hay không, và có được chừa lề 1–2 px không. Với
biển nhỏ, lệch 2 px là rớt ngưỡng. Ví dụ biển 18×18 (`00177.png`) bị lệch 2 px theo cả hai chiều thì IoU chỉ còn
16·16 / (2·324 − 256) = **0.65 < 0.7**, bị tính sai dù người gán vẽ cẩn thận.

**Đề xuất:** ghi *"box ôm sát mép ngoài của viền biển, không chừa lề"*. Ngưỡng IoU nên đi theo kích thước, ví dụ
0.5 nếu cạnh < 32 px và 0.7 nếu lớn hơn. Card 03 của lab dùng 0.6.

## G-11 · Chưa có rule cho điều kiện nhìn kém — **major**

**Vì sao khó:** guideline không nhắc gì tới ảnh tối, chạng vạng, nhoè hay ngược sáng. Trong khi đó 1 trong 3 ảnh
của nhóm (`00366.png`) thuộc loại này.

**Đề xuất:** thêm một mục riêng. Điều kiện nhìn kém *không* đổi cách vẽ box; `readable` chọn theo G-07; không được
tăng độ sáng hay dùng bộ lọc rồi đoán nội dung. Thêm một ví dụ lấy từ `00366.png`.

## G-12 · Mục loại trừ (5.3) còn mơ hồ — **minor**

- **Màn hình LED:** ở Đức, biển điện tử báo tốc độ trên cao tốc là biển có hiệu lực pháp lý. Nên nói rõ *vẫn gán*
  hay *không gán*, kèm lý do.
- **"Biển bị hỏng > 70% diện tích":** "hỏng" gồm cả phai màu, bẩn, bị vẽ bậy không? Đo bằng cách nào?
- **Biển xoay nghiêng hoặc nhìn từ cạnh:** chưa có rule. Mới chỉ có "mặt sau thì không gán". Ví dụ ở `00177.png`,
  góc trái có tấm biển xám hình chữ nhật (khoảng x 150–230, y 335–425), trông như mặt sau của biển. Nên đưa vào
  `sample_images/` làm ví dụ loại trừ.

## G-13 · Mô tả `danger` "nền vàng" — **minor**

**Nguyên văn:** mục 2 `danger | Tam giác, viền đỏ, nền vàng`.

**Vì sao khó:** biển cảnh báo của Đức (GTSDB) nền **trắng**. Biển *đi bộ qua đường* ở `00054.png` là ví dụ. Nền vàng
chỉ có ở biển tạm thời, và ở một số nước khác. Người mới gặp tam giác nền trắng có thể nghi đó không phải `danger`.

**Đề xuất:** sửa thành "tam giác đỉnh hướng lên, viền đỏ, nền trắng (biển tạm thời có thể nền vàng)".

## G-14 · Ảnh không có biển — **minor**

Guideline chưa nói ảnh không có biển nào thì nộp gì. Nên thêm câu: *"không vẽ gì, vẫn Save"*. Bộ GTSDB 28 ảnh của lab
có 2 ảnh negative, nên tình huống này sẽ gặp.

## G-15 · Phiên bản và lịch sử — **minor**

Tên file là `LABELING_GUIDELINE_V1.md` nhưng nội dung là V1.2. Mục 7 ghi cả 3 phiên bản cùng ngày và không ghi *lý
do* thay đổi. Đề xuất: giữ tên file cố định (`LABELING_GUIDELINE.md`), phiên bản chỉ ghi trong nội dung. Mỗi dòng
lịch sử thêm cột "Lý do / bằng chứng", ví dụ "G-01, ảnh 00054".

---

## Ưu tiên sửa

1. **G-01, G-02, G-03**: sửa xong thì người gán làm đúng guideline mới không bị chấm sai oan.
2. **G-04, G-07, G-09**: giảm việc mỗi người gõ và chọn một kiểu. Có thể làm cùng lúc với việc đổi schema CVAT sang
   select.
3. Các issue còn lại: làm khi ra bản V1.3.

Khi sửa xong một issue, đổi cột **Trạng thái** thành `fixed (V1.x)` và ghi số issue vào mục 7 của guideline.
