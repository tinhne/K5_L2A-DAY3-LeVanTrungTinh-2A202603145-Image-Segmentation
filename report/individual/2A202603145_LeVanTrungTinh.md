# Báo cáo thực hành Day 3 — điền trực tiếp trong fork của bạn

**Cách dùng:** Thay mọi dấu `…` bằng bài làm thật của bạn trước khi nộp link fork trên [LMS](https://aithucchien.vinuni.edu.vn). Giữ nguyên bốn mục và bảng để coach đọc nhanh. Viết ngắn, cụ thể theo ảnh/vùng; không cần thuật ngữ chuyên sâu. Ví dụ trong [hướng dẫn mẫu](../../reports/REPORT_TEMPLATE.md) chỉ giúp hiểu cách điền, không phải câu trả lời để chép lại.

- Mã học viên theo lớp: 2A202603145
- Ngày / CVAT local: 11–12/11/2026 / CVAT 2.74.1 chạy local bằng Docker (cổng 8081)
- Công cụ đã dùng: CVAT (Brush/Polygon, Slice, sửa tay); SAM 3 chạy trên máy qua script `cvat-cli` để gợi ý mask, sau đó tôi kiểm và sửa lại trong CVAT. Ở medium_instance tôi chỉ thử SAM 3 sau khi đã tự vẽ.

Mã học viên là mã lớp cấp; không cần ghi họ tên trong report nếu kênh [LMS](https://aithucchien.vinuni.edu.vn) đã nhận diện bạn. Chỉ ghi công cụ thật sự đã dùng; không có SAM vẫn làm bài bình thường.

## 1. Bài đã nộp

Ghi tên ZIP đúng như file trong `submissions/` và số ảnh đã vẽ, Save. Chưa làm hoặc export lỗi thì ghi `chưa có`, không tạo ZIP rỗng. Cột điểm là điểm tối đa của task, **không phải điểm tự chấm**.

| Task            | File ZIP đúng tên   | Hoàn thành mấy ảnh | Điểm tối đa (coach chấm sau) |
| --------------- | ------------------- | -----------------: | ---------------------------: |
| easy_semantic   | easy_semantic.zip   |              3 / 3 |                           20 |
| medium_instance | medium_instance.zip |              3 / 3 |                           32 |
| hard_panoptic   | hard_panoptic.zip   |              2 / 2 |                           30 |
| cp1_holes       | cp1_holes.zip       |              1 / 1 |                            3 |
| cp2_slice       | cp2_slice.zip       |              1 / 1 |                            3 |
| cp5_occlusion   | cp5_occlusion.zip   |              1 / 1 |                            3 |
| cp3_thin        | cp3_thin.zip        |              1 / 1 |                            3 |
| cp4_curb        | cp4_curb.zip        |              1 / 1 |                            3 |
| cp6_coverage    | cp6_coverage.zip    |              1 / 1 |                            3 |
| **Tổng tối đa** |                     |                    |                      **100** |

Nếu export lỗi, ghi task, dữ liệu đã Save đến đâu và lỗi đã báo coach.

## 2. Một quyết định trước khi dùng gợi ý

Chọn object đầu tiên bạn tự vẽ ở `medium_instance`, trước khi xem bất kỳ đề xuất tự động nào cho object đó. Ghi ảnh/vị trí đủ để tìm lại; “quy tắc biên” là lý do bạn chọn hoặc dừng mask ở ranh đó.

- Ảnh, vị trí và object Medium đầu tiên tự vẽ: Ảnh đầu tiên của medium_instance (000000181542.jpg), người đàn ông đi xe máy đội mũ bảo hiểm ở bên trái hình, bị cô đi bộ phía trước che khuất một phần.
- Class và quy tắc tôi dùng để chọn biên: Class person. Tôi chỉ vẽ phần nhìn thấy, mask dừng ở ranh với cô đi bộ che phía trước, không vẽ phần bị che. Chân và thân là cùng một người nên nằm trong cùng một mask.
- Nếu dùng gợi ý sau đó: vùng gợi ý sai/đúng, hành động sửa/giữ và lý do: Sau khi vẽ xong tôi thử SAM 3 (chạy qua script). SAM 3 vẽ chưa đúng: nó tách phần chân bị che khuất và phần người thành hai mask. Vì vậy tôi không giữ đề xuất này.
- Nếu không dùng gợi ý: ghi “không dùng”; vẫn giải thích một quyết định gán nhãn của mình.

## 3. Một lỗi tôi tìm thấy và sửa

Chọn một lỗi **có thật** trong bài. Nếu công cụ lỗi khiến bạn chưa sửa được, ghi rõ đã thử gì và cần coach hỗ trợ gì; không ghi “đã sửa” khi chưa sửa.

- Task/ảnh/vùng: medium_instance, ảnh đầu tiên (000000181542.jpg), nhóm người đi xe máy bị che khuất một phần.
- Lỗi thuộc loại: gộp-tách. Nhiều người bị gộp thành một object person.
- Bằng chứng tôi nhìn thấy: Di chuột vào mask thì thấy nhiều người cùng thuộc một object person.
- Quy tắc và hành động sửa: Mỗi người là một instance riêng nên tôi dùng Slice để tách thành từng object.
- Sau sửa đã Save và export lại chưa? Đã Save và export lại.

Nếu bạn **đã xem Summary tự đánh giá trên GitHub Actions hoặc tự chạy script**, ghi ngắn một kết quả liên quan lỗi vừa sửa (ví dụ task, metric trước/sau nếu có): chưa có điểm. Scorecard ba tier tối đa **82**, không phải điểm cuối trên 100. Không tự ghi PASS/top 3/bonus; người phụ trách xác nhận theo tiêu chí lớp. Không đưa file ground truth vào fork.

## 4. Ba ca chưa chắc hoặc đã cân nhắc

Mỗi ca là một **vùng cụ thể** khiến bạn phải cân nhắc hai cách hiểu. Ghi dấu hiệu nhìn thấy hoặc quy tắc đã dùng, rồi nêu quyết định hoặc câu hỏi cho coach. Không cần ba lỗi; ca đã quyết định được cũng hợp lệ.

| Ảnh/vị trí                                                                    | Hai cách hiểu có thể                                                                             | Quy tắc/chứng cứ                                               | Quyết định hoặc câu hỏi cho coach                                                  |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| 1. 000000181542.jpg, hình người mẫu trong poster CHANEL phía trên xe bán tải  | Là person vì nhìn thấy hình người / không vẽ vì đó là hình in trên poster, không phải người thật | Quy tắc chỉ vẽ phần nhìn thấy, và poster là hình in            | Không vẽ. Đây là hình in trên poster, không phải người thật                        |
| 2. 000000181542.jpg, hành khách thấy qua cửa kính xe buýt (góc trên bên trái) | Có 1 số người nhìn thấy người / không vẽ vì bị kính và khung xe che, rất nhỏ                     | Quy tắc chỉ vẽ phần nhìn thấy, không đoán phần bị che          | Không vẽ. Hành khách bị kính và khung xe che, lại rất nhỏ                          |
| 3. 000000181542.jpg, chân và giày của người lái xe, nằm sau váy cô đi bộ      | Cùng mask với người lái xe / tách thành mảnh riêng                                               | Vật bị che vẫn là một instance; chân và thân là cùng một người | Giữ chân và thân trong cùng một mask. SAM 3 tách đôi nên tôi không dùng đề xuất đó |
