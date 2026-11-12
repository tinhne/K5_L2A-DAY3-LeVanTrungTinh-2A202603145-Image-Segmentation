# Phiếu quy tắc gán nhãn Day 3

## Chọn đúng loại trước khi vẽ

| Loại | Câu hỏi | Task | Export |
| --- | --- | --- | --- |
| Semantic | Pixel nhìn thấy thuộc **loại vùng** nào? | `easy_semantic`, `cp3_thin`, `cp4_curb`, `cp6_coverage` | Segmentation mask 1.1 |
| Instance | Pixel nhìn thấy thuộc **vật nào**? | `medium_instance`, `cp1_holes`, `cp2_slice`, `cp5_occlusion` | COCO 1.0 |
| Panoptic | Vùng thuộc loại nào **và** vật đếm được nào? | `hard_panoptic` | COCO 1.0 |

### Class phải đọc từ đúng `classes.json`

- **Easy:** `road`, `sidewalk`, `building`, `vegetation`, `sky`.
- **Medium và cp1/cp2/cp5:** `person`, `bicycle`, `car`, `motorcycle`, `bus`, `truck`.
- **Hard:** 5 stuff (`road`, `sidewalk`, `building`, `vegetation`, `sky`) và 7 thing (`person`, `car`, `bus`, `truck`, `motorcycle`, `bicycle`, `traffic light`).
- **cp3:** `pole`, `traffic sign`, `sky`, `road`; **cp4:** `road`, `sidewalk`; **cp6:** `road`, `sidewalk`, `building`, `vegetation`, `sky`, `car`, `person`.

Tên lớp phải giống từng chữ: `traffic sign` khác `traffic_sign`. Không dán `classes.json` vào CVAT; nếu dùng **Labels → Raw**, dán `cvat-labels.json` của chính task.

## Quy tắc hình học

- Chỉ vẽ **phần nhìn thấy**, không tự đoán biên phía sau vật che.
- Semantic: tô kín vùng thuộc lớp; không bỏ sót mảng rõ ràng hoặc để khe chưa gán.
- Instance: mỗi vật đếm được là một mask riêng. Hai vật cùng lớp sát nhau vẫn là **hai instance**.
- Một vật bị che có thể có các vùng nhìn thấy rời nhau nhưng vẫn là **một instance**.
- `cp1_holes`: kính, cửa sổ và khe nằm trong mask vật; **không khoét lỗ tùy tiện**.
- `cp3_thin`: phóng to, dùng brush khoảng **2–3 px** cho cột/biển và kiểm lại đầu nét.
- `cp4_curb`: ranh `road`–`sidewalk` theo chức năng và bó vỉa, không chỉ theo màu/asphalt.
- `hard_panoptic`: stuff có thể là vùng lớn; thing phải tách từng vật (`car #1`, `car #2`), không để mask chồng lấn.
- Kính/chi tiết trên xe không tự động là lỗ; áp dụng quy tắc của task.

## Quy trình nhanh trong CVAT

1. Tạo task đúng tên, tải đúng ảnh và nạp đúng class list.
2. Chọn Brush/Polygon; vẽ từ vùng lớn đến chi tiết, phóng to để sửa biên.
3. Với instance/panoptic, đếm lại từng vật; với semantic, rà toàn ảnh để tìm vùng bỏ sót.
4. Bấm **Save**, xem lại danh sách Objects, rồi export đúng format ở bảng trên.

## Tự kiểm trước export

1. Đúng ảnh và đúng loại semantic/instance/panoptic chưa?
2. Mọi tên lớp có khớp `classes.json` không?
3. Có vật thiếu, vật thừa, gộp hai vật hoặc tách sai một vật không?
4. Mask có tràn sang nền/bóng, chồng lấn hoặc bỏ sót vùng rõ ràng không?
5. Đã Save, export đúng format và kiểm ZIP chưa?

Khi không chắc, ghi ảnh/vị trí, dấu hiệu nhìn thấy, quy tắc đã dùng và điều cần hỏi trong `report/individual/MSSV_HoTen.md`. Không ép đoán cho đủ coverage.
