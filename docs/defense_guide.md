# CẨM NANG BẢO VỆ ĐỒ ÁN — ShardMasters
## Hướng dẫn ôn tập & Trả lời phản biện dành cho Đàm Công Tú

Tài liệu này được thiết kế để giúp bạn chuẩn bị tốt nhất cho buổi bảo vệ đồ án **"Đánh giá hiệu quả mở rộng ngang trong cơ sở dữ liệu phân tán (Horizontal Scaling Efficiency via Hash-based Sharding)"** (Đề tài #94). 

Tài liệu tập trung vào các câu hỏi mà thầy cô phản biện thường đặt ra, cách trả lời ngắn gọn, trực diện, đi vào bản chất kỹ thuật mà không bị "màu mè" hay quá phức tạp, giúp bạn tự tin làm chủ toàn bộ mã nguồn của mình.

---

## 💡 Phần 1: Lời khuyên vàng khi thuyết trình & trả lời phản biện

1. **Hiểu rõ những gì mình làm:** Hệ thống của bạn là **mô hình mô phỏng (Simulation)** chạy trên `localhost`, sử dụng **Flask (Python)** để làm API và **SQLite** để làm database cho mỗi Node. Đừng cố gắng nói rằng đây là hệ thống chạy trên Cloud tầm cỡ Google hay AWS. Hãy nhấn mạnh đây là **mô hình nghiên cứu thực nghiệm**.
2. **Ngắn gọn & Tự tin:** Trả lời trực tiếp vào câu hỏi của thầy cô, sau đó mới giải thích thêm.
3. **Thừa nhận giới hạn:** Nếu thầy hỏi những tính năng nâng cao (như đồng bộ hóa giao dịch 2PC, tự động phục hồi replication, consistent hashing), hãy tự tin trả lời: *"Dự án của em tập trung vào đánh giá hiệu năng sharding và tốc độ xử lý (Speedup). Các tính năng giao dịch và chịu lỗi nâng cao nằm ngoài phạm vi đề tài này và em đã đưa vào hướng phát triển tương lai trong báo cáo."* (Thầy cô rất thích sự trung thực và hiểu rõ phạm vi nghiên cứu).

---

## 🙋‍♂️ Phần 2: Bộ câu hỏi bảo vệ kinh điển & Gợi ý trả lời

### 📂 Chủ đề 1: Kiến trúc và Công nghệ hệ thống

#### **Câu hỏi 1:** Tại sao em lại chọn SQLite làm Database cho từng Node mà không dùng MySQL, PostgreSQL hay MongoDB?
* **Gợi ý trả lời:** 
  > "Thưa thầy/cô, hệ thống của em là một mô hình mô phỏng được thiết kế để đo lường và đánh giá hiệu năng sharding trên môi trường `localhost`. 
  > 
  > **SQLite** có ưu điểm lớn là **gọn nhẹ, dạng file-based**, không cần cài đặt dịch vụ (service) chạy ngầm phức tạp. Việc mô phỏng nhiều node độc lập trở nên rất đơn giản bằng cách tạo ra các file `.db` khác nhau (ví dụ: `node_0.db`, `node_1.db`). 
  > 
  > Mặc dù SQLite chạy cục bộ, nhưng các tầng logic xử lý phân tán (phân mảnh dữ liệu, truy vấn song song, tổng hợp kết quả tại Coordinator) hoàn toàn mô phỏng đúng nguyên lý của một hệ cơ sở dữ liệu phân tán thực tế."

#### **Câu hỏi 2:** Vai trò của Coordinator trong hệ thống là gì? Nếu không có Coordinator thì sao?
* **Gợi ý trả lời:**
  > "Coordinator đóng vai trò là **Middleware (tầng trung gian)** điều phối. Nó có 3 nhiệm vụ chính:
  > 1. Nhận yêu cầu truy vấn toàn cục từ Client (qua endpoint `GET /aggregate`).
  > 2. Phân phối truy vấn song song đến tất cả các Node lưu trữ bằng `ThreadPoolExecutor`.
  > 3. Thu thập kết quả cục bộ từ các Node phản hồi, thực hiện phép gộp kết quả (Merge/Reduce) và trả về kết quả cuối cùng cho Client.
  > 
  > Nếu không có Coordinator, Client sẽ phải tự biết dữ liệu nằm ở những node nào, tự gửi request đến từng node và tự viết logic gộp kết quả. Điều này vi phạm nguyên tắc **Trong suốt phân tán (Distribution Transparency)** — nghĩa là Client không cần biết dữ liệu được phân mảnh thế nào hay nằm ở đâu, chỉ cần gửi truy vấn đến một đầu mối duy nhất."

---

### 🧮 Chủ đề 2: Chiến lược phân mảnh dữ liệu (Sharding Strategy)

#### **Câu hỏi 3:** Hãy giải thích chiến lược phân mảnh (sharding) dữ liệu trong đồ án của em. Tại sao lại chọn Hash-based sharding theo cột `UserID`?
* **Gợi ý trả lời:**
  > "Hệ thống của em sử dụng phương pháp **Phân mảnh ngang sơ cấp (Primary Horizontal Fragmentation)** dựa trên thuật toán băm modulo:
  > $$\text{node\_id} = \text{UserID} \pmod N$$
  > (Trong đó $N$ là tổng số node trong hệ thống, $N \in \{1, 2, 4\}$).
  > 
  > Em chọn cột **`UserID` làm khóa phân mảnh (sharding key)** vì:
  > 1. **Phân bố đều (Even Distribution):** Dữ liệu được chia đều lên các node (mỗi node nhận khoảng $1\text{M}/N$ dòng), tránh hiện tượng lệch dữ liệu (data skew).
  > 2. **Tối ưu cực đại cho truy vấn GROUP BY:** Truy vấn chính của hệ thống là `GROUP BY UserID`. Vì khóa phân mảnh trùng với khóa GROUP BY, hệ thống đạt trạng thái **embarrassingly parallel** (song song lý tưởng). Mỗi `UserID` chỉ xuất hiện trên **đúng một node**. Các node có thể tính toán COUNT độc lập mà không cần re-aggregate cộng dồn chéo và không cần trao đổi dữ liệu (data shuffling) giữa các node."

#### **Câu hỏi 4:** Nếu thầy muốn GROUP BY theo một cột khác cột phân mảnh, ví dụ `GROUP BY Action` hoặc `GROUP BY Timestamp`, hệ thống của em sẽ phải xử lý như thế nào?
* **Gợi ý trả lời:**
  > "Nếu `GROUP BY` theo một cột khác (như `Action`), dữ liệu của cùng một loại hành động (ví dụ: 'click') sẽ nằm rải rác trên **tất cả các node**.
  > 
  > Khi đó, quy trình xử lý tại Coordinator sẽ phức tạp hơn:
  > 1. Các node vẫn chạy GROUP BY cục bộ và trả về danh sách đếm từng hành động của node đó.
  > 2. Coordinator nhận dữ liệu về sẽ **bắt buộc phải thực hiện bước cộng dồn (re-aggregation/reduce)**: cộng giá trị COUNT của từng hành động từ tất cả các node lại với nhau.
  > 
  > Điều này làm tăng chi phí tính toán (CPU-bound) tại Coordinator và tăng lượng dữ liệu truyền qua mạng, dẫn đến hiệu năng (Speedup) của hệ thống sẽ thấp hơn so với khi GROUP BY theo khóa phân mảnh."

#### **Câu hỏi 5:** Hãy chứng minh tính đúng đắn của phân mảnh (Fragmentation Correctness) trong hệ thống của em?
* **Gợi ý trả lời:**
  > "Theo lý thuyết của *Özsu & Valduriez*, một thiết kế phân mảnh đúng đắn phải thỏa mãn 3 tiêu chí:
  > 1. **Completeness (Tính đầy đủ):** Mọi dòng dữ liệu của bảng gốc phải thuộc về ít nhất một phân mảnh. Với hàm hash modulo `UserID % N`, mọi giá trị nguyên của UserID đều cho ra một node_id hợp lệ từ $0$ đến $N-1$, đảm bảo không bỏ sót bản ghi nào.
  > 2. **Reconstruction (Tính tái tạo):** Bảng gốc có thể được khôi phục hoàn toàn từ các phân mảnh. Phép toán tái tạo ở đây là phép `UNION` tất cả các phân mảnh lại với nhau.
  > 3. **Disjointness (Tính tách biệt):** Các phân mảnh không được chồng lấn dữ liệu. Vì hàm modulo là hàm ánh xạ đơn trị (mỗi UserID chỉ cho ra một kết quả modulo duy nhất), nên một bản ghi chỉ có thể nằm trên đúng một node, đảm bảo các phân mảnh hoàn toàn tách biệt."

---

### ⚡ Chủ đề 3: Xử lý truy vấn và Hiệu năng (Speedup & Amdahl's Law)

#### **Câu hỏi 6:** Hãy giải thích kết quả Speedup và Efficiency thực tế mà em đo được trong thí nghiệm.
* **Gợi ý trả lời:**
  > "Thưa thầy, kết quả đo thực nghiệm trên hệ thống của em (chạy 5 lần sau 2 lần warmup) như sau:
  > - **Thời gian thực thi trung vị (Median Time - điển hình):** 1 Node là **223.8 ms**, 2 Nodes giảm xuống còn **93.5 ms** (Speedup = **2.40x**), 4 Nodes giảm xuống còn **86.4 ms** (Speedup = **2.59x**).
  > - **Thời gian thực thi trung bình (Mean Time):** 1 Node là **232.2 ms**, 2 Nodes là **106.3 ms** (Speedup = **2.19x**), 4 Nodes là **89.8 ms** (Speedup = **2.59x**).
  > 
  > Ở cấu hình 2 nodes, hệ thống đạt hiệu năng siêu tuyến tính (super-linear) rất tốt. Khi lên 4 nodes, thời gian thực thi tiếp tục giảm nhưng tốc độ tăng tốc chậm lại (Speedup đạt 2.59x) do chi phí truyền thông HTTP và merge kết quả bắt đầu chiếm ưu thế."

#### **Câu hỏi 7:** Tại sao Speedup của hệ thống lại đạt trên mức tuyến tính (Super-linear Speedup, ví dụ 2 node đạt 2.40x)? 
* **Gợi ý trả lời:**
  > "Thưa thầy, hiện tượng tốc độ tăng tốc vượt tuyến tính (Super-linear Speedup) ở cấu hình 2 nodes trong thực nghiệm xảy ra do hai yếu tố vật lý và thuật toán:
  > 
  > 1. **Hiệu ứng Cache bộ đệm (OS Page Cache Fitting):** Khi chia dữ liệu 1 triệu bản ghi thành các phần nhỏ (500k bản ghi/node), kích thước tệp SQLite của mỗi node chỉ còn khoảng 20MB. Tệp nhỏ này dễ dàng nằm trọn trong RAM cache của hệ điều hành. Các node SQLite sau đó đọc dữ liệu trực tiếp từ RAM thay vì ổ đĩa cứng, giúp triệt tiêu hoàn toàn độ trễ I/O đĩa.
  > 2. **Giảm độ sâu cây chỉ mục (B-Tree Index Depth Reduction):** SQLite sử dụng cấu trúc B-Tree để lưu chỉ mục. Khi số bản ghi trên mỗi node giảm tuyến tính còn $1/N$, chiều cao của cây chỉ mục giảm xuống, làm giảm độ phức tạp tính toán GROUP BY cục bộ trên mỗi node nhanh hơn mức tuyến tính ($O(M \log M)$ với $M = R/N$)."

#### **Câu hỏi 8:** Định luật Amdahl áp dụng như thế nào vào đồ án của em? Serial Fraction ($f$) thể hiện điều gì?
* **Gợi ý trả lời:**
  > "Định luật Amdahl chỉ ra rằng tốc độ tăng tốc (Speedup) tối đa của hệ thống song song bị giới hạn bởi phần công việc tuần tự không thể song song hóa được, gọi là **Serial Fraction ($f$)**.
  > 
  > Trong hệ thống của em, từ kết quả thực nghiệm:
  > - Ở cấu hình **2 nodes**, Serial Fraction $f$ âm nhẹ (khoảng **-16.5%** tính theo trung vị) phản ánh trực quan mặt toán học của hiện tượng **Super-linear Speedup** do RAM cache mang lại.
  > - Ở cấu hình **4 nodes**, Serial Fraction $f$ dương (khoảng **18.1%**) thể hiện chi phí truyền tải qua mạng (HTTP) và việc merge kết quả từ điển tại Coordinator. Lúc này, thời gian xử lý cơ sở dữ liệu đã quá nhỏ, nên chi phí tuần tự bắt đầu chi phối và giới hạn Speedup ở mức 2.59x."


---

### 🛡️ Chủ đề 4: Khả năng chịu lỗi (Fault Tolerance)

#### **Câu hỏi 9:** Nếu một node trong hệ thống bị sập giữa chừng, hệ thống của em sẽ xử lý ra sao?
* **Gợi ý trả lời:**
  > "Hệ thống của em thiết kế cơ chế **Graceful Degradation (Suy giảm chất lượng mềm dẻo)**:
  > 1. Coordinator phát hiện node lỗi thông qua lỗi kết nối (Connection Error) hoặc quá thời gian chờ (Timeout = 10 giây).
  > 2. Thay vì bị crash hoặc báo lỗi toàn bộ hệ thống, Coordinator vẫn tiếp tục thu thập kết quả từ các node hoạt động bình thường còn lại và thực hiện gộp dữ liệu.
  > 3. Response trả về Client sẽ có trường `"status": "partial"` (thay vì `"success"`) và đính kèm danh sách các node bị sập (`failed_nodes`).
  > 
  > Kết quả trả về cho client vẫn đúng đắn nhưng sẽ **bị thiếu dữ liệu** tương ứng với phân mảnh của node bị lỗi (ví dụ nếu sập 1 trong 4 node, kết quả sẽ bị mất khoảng 25% số lượng bản ghi và user)."

#### **Câu hỏi 10:** Tại sao thời gian thực thi (execution time) sau khi node sập lại tăng lên (ví dụ từ ~90ms lên ~4 giây) trong khi số lượng node cần truy vấn ít đi?
* **Gợi ý trả lời:**
  > "Thưa thầy, thời gian thực thi tổng thể đo tại Coordinator tăng lên là do **chi phí phát hiện lỗi kết nối (Timeout/Connection Error detect overhead)**.
  > 
  > Khi Node 2 bị sập, luồng (thread) của Coordinator gửi truy vấn đến Node 2 sẽ cố gắng tạo kết nối TCP nhưng không nhận được phản hồi. Lúc này, luồng đó phải đợi cho đến khi hệ thống báo lỗi kết nối (Connection Refused / Timeout). Khoảng thời gian chờ báo lỗi này mất vài giây (trong môi trường Windows cục bộ thường là từ 2 đến 4 giây).
  > 
  > Do Coordinator phải đợi **tất cả** các luồng gửi đi (gồm cả các luồng thành công và luồng thất bại) kết thúc hoặc báo lỗi xong thì mới có thể tổng hợp kết quả trả về cho Client, nên tổng thời gian xử lý bị kéo dài. Đây là hành vi thực tế của các hệ thống phân tán khi phát hiện và cô lập node lỗi."

#### **Câu hỏi 11:** Hạn chế lớn nhất trong thiết kế chịu lỗi của em là gì? Hướng khắc phục?
* **Gợi ý trả lời:**
  > "Hạn chế lớn nhất hiện tại của hệ thống là **chưa hỗ trợ cơ chế nhân bản dữ liệu (Replication)**. Do đó, dữ liệu trên node bị sập sẽ bị mất hoàn toàn trong kết quả truy vấn, khiến kết quả chỉ mang tính chất một phần (partial).
  > 
  > **Hướng khắc phục:** Trong thực tế, mỗi phân mảnh (shard) cần được cấu hình dưới dạng một nhóm nhân bản (Replica Set) gồm 1 node chính (Primary) và 1 hoặc nhiều node phụ (Secondary/Replica). Khi node Primary bị sập, hệ thống sẽ tự động chuyển hướng truy vấn sang node Replica để đảm bảo tính sẵn sàng (Availability) và tính toàn vẹn dữ liệu (Completeness)."

---

## 🛠️ Phần 3: Cheat Sheet kỹ thuật (Thông số cần nhớ nằm lòng)

* **Số bản ghi dữ liệu:** 1,000,000 dòng `User_Logs`.
* **Kích thước file CSV gốc:** ~40 MB.
* **Số UserID duy nhất:** 200,000 người dùng.
* **Cổng chạy dịch vụ (Port configuration):**
  * Để tránh xung đột cổng (do trạng thái `TIME_WAIT` của socket Windows), các cổng được cách ly theo cấu hình:
    * **Cấu hình 1 Node:** Node chạy ở port `5100`, Coordinator chạy ở port `8001`.
    * **Cấu hình 2 Nodes:** Các Node chạy ở port `5200-5201`, Coordinator chạy ở port `8002`.
    * **Cấu hình 4 Nodes (và Bài test lỗi):** Các Node chạy ở port `5400-5403`, Coordinator chạy ở port `8004`.
  * **Cơ sở dữ liệu SQLite cho từng Node:** Lưu tại `node/node_0.db` đến `node_3.db`.
* **Thời gian Timeout kết nối đến Node:** 5 giây để kiểm tra health check, 10 giây cho truy vấn `/query`.
* **Định luật Amdahl (Amdahl's Law):** $S(n) \le \frac{1}{f + \frac{1-f}{n}}$

---

## 🚀 Phần 4: Lịch trình tự tin bảo vệ (Nếu thầy yêu cầu demo tại chỗ)

Nếu thầy bảo: *"Em chạy thử hệ thống lên cho thầy xem nào"*, hãy bình tĩnh thực hiện các bước sau:

1. **Bước 1: Chạy benchmark chính thức** (để tạo lại toàn bộ dữ liệu, phân mảnh, khởi động node và lấy kết quả):
   ```powershell
   python benchmark/run_benchmark.py
   ```
   *Giải thích với thầy:* "Lệnh này sẽ tự động phân mảnh dữ liệu 1 triệu bản ghi, nạp vào cơ sở dữ liệu SQLite của từng node, khởi chạy các tiến trình Flask độc lập cho Coordinator và Nodes, sau đó thực hiện đo thời gian thực thi của các cấu hình 1, 2, và 4 nodes."

2. **Bước 2: Chạy bài kiểm tra khả năng chịu lỗi (Failure Test):**
   ```powershell
   python benchmark/failure_test.py
   ```
   *Giải thích với thầy:* "Lệnh này sẽ khởi động cấu hình 4 node, chạy truy vấn baseline, sau đó giết chết Node 2 để mô phỏng sự cố và chạy lại truy vấn để thầy thấy hệ thống vẫn hoạt động bình thường nhưng trả về kết quả trạng thái `partial` bị thiếu dữ liệu của Node 2."

3. **Bước 3: Vẽ lại các biểu đồ phân tích:**
   ```powershell
   python analysis/analyze.py
   ```
   *Giải thích với thầy:* "Lệnh này sẽ phân tích kết quả benchmark đã ghi nhận và cập nhật trực quan hóa thành các biểu đồ Speedup Ratio, Execution Time và Parallel Efficiency trong thư mục `analysis/charts/`."
