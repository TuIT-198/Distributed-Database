# TÀI LIỆU THIẾT KẾ HỆ THỐNG — ShardMasters

**Mã đề tài:** #94 — Horizontal Scaling Efficiency: "Sharding Gains"  
**Nhóm:** ShardMasters — Đàm Công Tú  
**Phiên bản:** 1.0  
**Ngày cập nhật:** 03/06/2026

---

## 1. Tổng quan hệ thống

### 1.1 Mô tả

ShardMasters là hệ thống mô phỏng cơ sở dữ liệu phân tán được thiết kế để **đo lường và phân tích hiệu quả mở rộng ngang** (horizontal scaling efficiency) thông qua kỹ thuật **hash-based sharding**. Hệ thống phân tán dữ liệu 1 triệu bản ghi `User_Logs` lên nhiều node và thực thi truy vấn aggregation song song, sau đó tổng hợp kết quả tại một coordinator trung tâm.

### 1.2 Vấn đề cần giải quyết

Khi khối lượng dữ liệu tăng trưởng vượt quá năng lực xử lý của một server đơn lẻ, mở rộng ngang bằng cách thêm node là giải pháp phổ biến. Tuy nhiên, việc thêm node không đảm bảo tăng tốc tuyến tính do các chi phí phát sinh: truyền thông mạng, đồng bộ hóa, và tổng hợp kết quả. Hệ thống ShardMasters cung cấp một bộ công cụ benchmark để **đo lường chính xác tỷ lệ tăng tốc (Speedup)** và **xác định các yếu tố giới hạn hiệu năng** trong môi trường phân tán.

### 1.3 Phạm vi

- Hỗ trợ cấu hình 1, 2, và 4 nodes
- Truy vấn benchmark: `SELECT UserID, COUNT(*) FROM logs GROUP BY UserID`
- Mô phỏng trên localhost bằng các tiến trình Flask riêng biệt
- Phân tích kết quả dựa trên Speedup, Efficiency, và Amdahl's Law

---

## 2. Kiến trúc phân tán

### 2.1 Mô hình kiến trúc

Hệ thống tuân theo kiến trúc **Client-Coordinator-Node** (3-tier), một mô hình phổ biến trong các hệ quản trị cơ sở dữ liệu phân tán hiện đại:

```
┌─────────────────────────────────────────────────────────┐
│                     CLIENT / BENCHMARK                   │
│                   (benchmark.py)                         │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP GET /aggregate
                       ▼
              ┌─────────────────┐
              │   COORDINATOR   │
              │  (Port 8000)    │
              │ Merge & Reduce  │
              └──┬──────┬────┬──┘
                 │      │    │
     ┌───────────┘      │    └───────────┐
     │ POST /query      │               │
     ▼                  ▼               ▼
┌──────────┐     ┌──────────┐    ┌──────────┐
│  Node 0  │     │  Node 1  │    │  Node 2  │  ...
│ Port 5000│     │ Port 5001│    │ Port 5002│
│ SQLite   │     │ SQLite   │    │ SQLite   │
│ Shard 0  │     │ Shard 1  │    │ Shard 2  │
└──────────┘     └──────────┘    └──────────┘

Sharding: node_id = UserID % N (Hash-based Horizontal Fragmentation)
```

### 2.2 Vai trò từng thành phần

**Tầng Client (Benchmark Layer):**
Client đóng vai trò là tầng giao tiếp bên ngoài, gửi truy vấn aggregation đến Coordinator thông qua HTTP REST API. Trong ngữ cảnh benchmark, Client thực hiện nhiều lần chạy (runs) với các cấu hình node khác nhau, đo thời gian end-to-end, và ghi kết quả ra file CSV/JSON để phân tích sau.

**Tầng Coordinator (Middleware Layer):**
Coordinator là thành phần trung tâm điều phối, chịu trách nhiệm:
- Nhận truy vấn từ Client qua endpoint `GET /aggregate`.
- Phân phối truy vấn song song đến tất cả Node đang hoạt động bằng `concurrent.futures.ThreadPoolExecutor`.
- Thu thập kết quả từ các Node, thực hiện merge bằng phép cộng dồn (additive aggregation) trên các bộ đếm COUNT.
- Trả kết quả đã merge về Client kèm thông tin timing và trạng thái (success/partial).

**Tầng Node (Data Layer):**
Mỗi Node là một tiến trình Flask độc lập, lưu trữ một **shard** (phân mảnh) của dữ liệu trong cơ sở dữ liệu SQLite riêng biệt. Khi nhận truy vấn từ Coordinator qua endpoint `POST /query`, Node thực thi truy vấn SQL cục bộ trên shard của mình và trả kết quả dưới dạng JSON. Mỗi Node được gán cổng động cách ly theo cấu hình chạy để tránh xung đột socket TIME_WAIT trên Windows (ví dụ: cấu hình 4 node chạy cổng 5400–5403, cấu hình 2 node chạy cổng 5200–5201, cấu hình 1 node chạy cổng 5100).

---

## 3. Chiến lược phân mảnh (Fragmentation Strategy)

### 3.1 Phương pháp: Hash-based Horizontal Fragmentation

Dữ liệu được phân mảnh ngang theo hàm hash trên cột `UserID`:

```
node_id = UserID % N
```

Trong đó **N** là tổng số node trong hệ thống (N ∈ {1, 2, 4}).

### 3.2 Lý do chọn Hash-based Fragmentation

- **Phân bố đều (Even Distribution):** Hàm modulo đảm bảo mỗi node nhận xấp xỉ 1M/N bản ghi, tránh hiện tượng data skew.
- **Tối ưu cho truy vấn GROUP BY:** Khóa phân mảnh (`UserID`) trùng với khóa GROUP BY trong truy vấn benchmark. Điều này có nghĩa mỗi `UserID` chỉ tồn tại trên **đúng một node**, loại bỏ hoàn toàn nhu cầu re-aggregate giữa các node — đây là trường hợp lý tưởng cho xử lý song song.
- **Đơn giản và xác định (Deterministic):** Hàm hash modulo dễ triển khai, dễ kiểm chứng, và cho kết quả xác định.

### 3.3 Tính đúng đắn

Theo Özsu & Valduriez (2020, Chapter 3), một phân mảnh đúng đắn phải thỏa mãn ba tiêu chí:

1. **Completeness (Đầy đủ):** Mọi bản ghi `r ∈ R` đều được ánh xạ vào một fragment `Fᵢ`. Với hàm hash xác định `UserID % N`, mọi giá trị UserID đều cho ra một `node_id` hợp lệ trong khoảng `[0, N-1]`.

2. **Reconstruction (Tái tạo):** Bảng gốc có thể tái tạo bằng phép `UNION` tất cả các fragment: `R = F₀ ∪ F₁ ∪ ... ∪ F_{N-1}`.

3. **Disjointness (Tách biệt):** Các fragment không chồng lấn: `Fᵢ ∩ Fⱼ = ∅` với mọi `i ≠ j`. Hàm hash ánh xạ mỗi UserID vào đúng một node, đảm bảo không có bản ghi nào xuất hiện trên hai fragment khác nhau.

---

## 4. Xử lý truy vấn phân tán (Distributed Query Processing)

### 4.1 Truy vấn benchmark

```sql
SELECT UserID, COUNT(*) AS log_count
FROM logs
GROUP BY UserID
```

### 4.2 Quy trình xử lý

Quy trình xử lý truy vấn phân tán trong ShardMasters gồm 4 bước, tuân theo mô hình **scatter-gather** (phân tán — thu thập):

| Bước | Thành phần | Hành động |
|------|-----------|----------|
| **1. Nhận truy vấn** | Coordinator | Nhận `GET /aggregate` từ Client, khởi tạo timer. |
| **2. Phân phối (Scatter)** | Coordinator → Nodes | Gửi `POST /query` song song đến tất cả N nodes bằng `ThreadPoolExecutor`. |
| **3. Thực thi cục bộ** | Mỗi Node | Thực thi SQL `SELECT UserID, COUNT(*) FROM logs GROUP BY UserID` trên shard cục bộ (SQLite). Index trên `UserID` tối ưu phép GROUP BY. |
| **4. Thu thập & Merge (Gather)** | Coordinator | Thu thập JSON response từ các Node, merge kết quả bằng phép cộng dồn trên dictionary `{UserID: count}`. Dừng timer, trả kết quả cho Client. |

### 4.3 Đặc tính quan trọng

Do dữ liệu được phân mảnh theo `UserID` (chính là khóa GROUP BY), mỗi `UserID` **chỉ tồn tại trên đúng một node**. Điều này mang lại một lợi thế quan trọng: kết quả `COUNT(*)` từ mỗi node đã là **kết quả cuối cùng** cho các UserID trên node đó. Coordinator chỉ cần **hợp nhất (union)** các tập kết quả mà không cần tính toán lại (re-aggregate).

Đây là khác biệt cơ bản so với trường hợp phân mảnh theo khóa khác (ví dụ: phân mảnh theo `Timestamp`), khi đó cùng một `UserID` có thể xuất hiện trên nhiều node và cần cộng dồn COUNT từ tất cả các node.

Tham khảo: Özsu & Valduriez, Chapter 8 — *Query Processing*.

---

## 5. Giao thức truyền thông (Communication Protocol)

### 5.1 REST API Specification

| Endpoint | Method | Thành phần | Mô tả |
|----------|--------|-----------|--------|
| `/aggregate` | GET | Coordinator | Nhận truy vấn từ Client, trigger distributed query, trả kết quả merge. |
| `/query` | POST | Node | Nhận truy vấn từ Coordinator, thực thi cục bộ, trả kết quả. |
| `/health` | GET | Node | Health check — trả về trạng thái node (up/down). |
| `/health` | GET | Coordinator | Kiểm tra trạng thái coordinator và tất cả nodes. |
| `/info` | GET | Node | Thông tin chi tiết: node_id, db_path, row_count, db_size_bytes. |

### 5.2 Định dạng Request/Response

**Client → Coordinator: `GET /aggregate`**

```json
// Response
{
  "status": "success",
  "nodes_total": 4,
  "nodes_responded": 4,
  "unique_users": 200000,
  "total_logs": 1000000,
  "execution_time_ms": 85.2,
  "node_times_ms": [42.1, 38.5, 41.2, 39.8],
  "query_times_ms": [35.2, 32.8, 34.1, 33.5],
  "merge_time_ms": 0.01
}
```

**Coordinator → Node: `POST /query`**

```json
// Request body: không có (truy vấn được cài sẵn trong node)

// Response — summary kết quả GROUP BY từ node
{
  "node_id": 0,
  "unique_users": 50000,
  "total_logs": 250000,
  "query_time_ms": 35.2
}
```

**Coordinator: `GET /health`**

```json
// Response
{
  "coordinator": "ok",
  "nodes": [
    {"url": "http://localhost:5000", "status": "ok", "row_count": 250000},
    {"url": "http://localhost:5001", "status": "ok", "row_count": 250000}
  ]
}
```

**Node: `GET /health`**

```json
// Response
{
  "status": "ok",
  "node_id": 0,
  "row_count": 250000
}
```

**Node: `GET /info`**

```json
// Response
{
  "node_id": 0,
  "db_path": "node/node_0.db",
  "row_count": 250000,
  "db_size_bytes": 15728640
}
```

### 5.3 Timeout & Retry Policy

| Tham số | Giá trị | Lý do |
|---------|---------|-------|
| **Request timeout** | 10 giây | Đủ dài cho truy vấn trên 250K–1M bản ghi |
| **Retry** | 0 lần | Trong benchmark mode, failure được ghi nhận thay vì retry để đo chính xác hiệu năng |
| **Connection timeout** | 5 giây | Phát hiện nhanh node không khả dụng |

---

## 6. Xử lý lỗi (Failure Handling)

### 6.1 Phát hiện lỗi node (Node Failure Detection)

Coordinator phát hiện node failure thông qua hai cơ chế:

1. **Health Check:** Trước khi gửi truy vấn, Coordinator gọi `GET /health` đến từng node. Node không phản hồi trong 5 giây được đánh dấu `unavailable`.
2. **Request Timeout:** Nếu node không trả response trong 10 giây sau khi nhận truy vấn, Coordinator coi node đó là `failed`.

### 6.2 Graceful Degradation

Khi một hoặc nhiều node bị lỗi, Coordinator **không crash** mà thực hiện **graceful degradation**:

- Merge kết quả từ các node còn lại (healthy nodes).
- Đặt trường `status` trong response là `"partial"` thay vì `"success"`.
- Ghi nhận danh sách `failed_nodes` trong response để Client biết node nào không phản hồi.
- Client/Benchmark ghi nhận kết quả partial riêng biệt cho phân tích.

```json
{
  "status": "partial",
  "node_count": 4,
  "healthy_nodes": 3,
  "failed_nodes": [2],
  "total_users": 150123,
  "total_logs": 750000,
  "execution_time_ms": 82.7,
  "results": { "...": "..." }
}
```

### 6.3 Giới hạn hiện tại

- **Không có replication:** Dữ liệu trên node bị lỗi sẽ bị mất trong kết quả query. Hệ thống hiện tại chưa hỗ trợ sao lưu dữ liệu (replication).
- **Không có tự động khôi phục:** Node bị lỗi cần restart thủ công.
- **Partial results:** Client cần tự xử lý logic khi nhận kết quả partial.

---

## 7. Mô hình hiệu năng (Performance Model)

### 7.1 Công thức Speedup và Efficiency

| Chỉ số | Công thức | Giải thích |
|--------|-----------|-----------|
| **Speedup** | S(n) = T₁ / Tₙ | Tỷ lệ giảm thời gian khi tăng từ 1 lên n nodes |
| **Efficiency** | E(n) = S(n) / n | Hiệu quả sử dụng mỗi node (lý tưởng = 1.0) |
| **Serial Fraction** | f = (1/S(n) − 1/n) / (1 − 1/n) | Phần không song song hóa được, suy từ kết quả đo |

### 7.2 Amdahl's Law

Định luật Amdahl đặt giới hạn lý thuyết cho speedup:

```
S(n) ≤ 1 / (f + (1 − f) / n)
```

Trong đó:
- **f** = serial fraction (phần tuần tự, không thể song song hóa)
- **n** = số node
- Khi n → ∞: S(n) → 1/f (giới hạn trên)

### 7.3 Các yếu tố giới hạn hiệu năng (Expected Bottlenecks)

| Yếu tố | Loại | Ảnh hưởng |
|--------|------|----------|
| **Network I/O** | Serial overhead | HTTP round-trip latency (~1–5ms mỗi request trên localhost). Trong môi trường thực tế (cross-machine), latency có thể lên đến 10–100ms. |
| **Merge Computation** | Serial overhead | Coordinator merge N tập kết quả thành 1 dictionary. Complexity: O(Σ|Rᵢ|) với |Rᵢ| là số UserID trên node i. |
| **Thread Synchronization** | Parallel overhead | `ThreadPoolExecutor` tạo và quản lý thread pool, chi phí context switching giữa các thread. |
| **Python GIL** | Parallel overhead | Global Interpreter Lock giới hạn true parallelism cho CPU-bound tasks. Tuy nhiên, workload chủ yếu là I/O-bound (network + disk) nên ảnh hưởng được giảm thiểu. |
| **SQLite Connection Setup** | Per-query overhead | Mỗi truy vấn cần mở connection đến SQLite database, tạo overhead cố định. |

### 7.4 Dự đoán hiệu năng

Với workload embarrassingly parallel (GROUP BY key = fragmentation key) và trên localhost (network latency thấp), dự đoán:
- **Speedup 2 nodes:** ~1.7–1.9x (Efficiency ~85–95%)
- **Speedup 4 nodes:** ~3.0–3.5x (Efficiency ~75–87%)
- **Serial fraction f:** ước tính ~5–15%, chủ yếu từ merge và network overhead

---

## Tài liệu tham khảo

1. **Özsu, M.T. & Valduriez, P.** (2020). *Principles of Distributed Database Systems*, 4th Edition. Springer.
   - Chapter 3: Fragmentation
   - Chapter 8: Query Processing
   - Chapter 14: Parallel Database Systems
2. **Amdahl, G.** (1967). *Validity of the Single Processor Approach to Achieving Large-Scale Computing Capabilities*. AFIPS Conference Proceedings.
3. **DeWitt, D. & Gray, J.** (1992). *Parallel Database Systems: The Future of High Performance Database Systems*. Communications of the ACM, 35(6).
