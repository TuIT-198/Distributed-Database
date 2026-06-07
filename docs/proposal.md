# ĐỀ XUẤT ĐỒ ÁN MÔN CƠ SỞ DỮ LIỆU PHÂN TÁN

**Mã đề tài:** #94 — Horizontal Scaling Efficiency: "Sharding Gains"  
**Phân loại:** Horizontal Fragmentation / Sharding  
**Ngày nộp:** 12/06/2026

---

## 1. Thông tin đồ án

| Mục | Chi tiết |
|-----|---------|
| **Tên nhóm** | ShardMasters |
| **Thành viên** | Đàm Công Tú |
| **Mã đề tài** | #94 |
| **Tên đồ án** | Đánh giá hiệu quả mở rộng ngang — Phân tích tỷ lệ tăng tốc khi Sharding cơ sở dữ liệu phân tán |
| **Tên tiếng Anh** | Horizontal Scaling Efficiency: Sharding Gains |
| **Môn học** | Cơ sở dữ liệu phân tán (Distributed Database) |
| **Hạn nộp** | 12/06/2026 |

---

## 2. Mục tiêu & Vấn đề nghiên cứu

### 2.1 Bối cảnh

Trong bối cảnh các hệ thống dữ liệu ngày càng tăng trưởng về quy mô, **horizontal scaling** (mở rộng ngang) bằng cách phân tán dữ liệu trên nhiều node là chiến lược phổ biến để đảm bảo hiệu năng. **Sharding** — hay phân mảnh ngang (horizontal fragmentation) — chia dữ liệu thành các phần nhỏ hơn và phân phối lên các node độc lập, cho phép xử lý song song các truy vấn.

Tuy nhiên, liệu tăng số node có đồng nghĩa với giảm thời gian thực thi một cách tuyến tính? Câu hỏi này là trọng tâm nghiên cứu của đồ án.

### 2.2 Câu hỏi nghiên cứu

> **Khi tăng số lượng node trong hệ thống cơ sở dữ liệu phân tán sử dụng horizontal sharding, thời gian thực thi truy vấn aggregation có giảm tuyến tính theo số node hay không? Nếu không, đâu là các yếu tố gây ra overhead?**

Các yếu tố overhead cần phân tích bao gồm:
- **Chi phí truyền thông mạng** (network communication overhead): HTTP round-trip latency giữa Coordinator và các Node.
- **Thời gian merge kết quả** (merge/reduce cost): Coordinator phải tổng hợp kết quả từ tất cả các Node.
- **Serial fraction** theo Amdahl's Law: phần không thể song song hóa trong pipeline xử lý.
- **Thread synchronization overhead**: chi phí quản lý song song hóa bằng `concurrent.futures`.

### 2.3 Giả thuyết

Với truy vấn `COUNT(*) GROUP BY UserID` trên dữ liệu được phân mảnh theo khóa `UserID`, mỗi nhóm (group) chỉ tồn tại trên đúng một node. Đây là trường hợp **embarrassingly parallel** — do đó, speedup kỳ vọng sẽ **gần tuyến tính** (near-linear), với overhead chủ yếu đến từ network I/O và merge.

### 2.4 Thuật toán chính

| Thuật toán | Mô tả |
|-----------|-------|
| **Horizontal Hash-based Fragmentation** | Phân mảnh dữ liệu theo hàm hash: `node_id = UserID % N`. Đảm bảo phân bố đều dữ liệu lên N nodes. |
| **Distributed Query Processing** | Coordinator phân phối truy vấn song song đến các node qua HTTP REST API, thu thập và merge kết quả. |
| **Parallel Aggregation** | Mỗi node thực thi `COUNT(*) GROUP BY UserID` cục bộ trên shard của mình. Coordinator merge bằng cách cộng dồn (additive aggregation). Do phân mảnh theo `UserID`, mỗi user chỉ nằm trên 1 node → kết quả COUNT từ mỗi node đã là kết quả cuối cùng, không cần re-aggregate. |

---

## 3. Đặc tả dữ liệu

### 3.1 Nguồn dữ liệu

- **Loại:** Synthetic dataset (dữ liệu tổng hợp) sinh bằng Python script (`data/generate.py`).
- **Lý do:** Đảm bảo kiểm soát hoàn toàn phân bố dữ liệu, kích thước, và tính tái lập (reproducibility) cho benchmark.

### 3.2 Kích thước & Schema

- **Số bản ghi:** 1,000,000 dòng
- **Kích thước ước tính:** ~40MB (CSV format)
- **Số người dùng duy nhất:** 200,000 UserID (1 → 200,000)

| Thuộc tính | Kiểu dữ liệu | Mô tả | Giá trị |
|-----------|--------------|-------|---------|
| `LogID` | INTEGER (PK) | ID bản ghi, khóa chính | Tuần tự 1 → 1,000,000 |
| `UserID` | INTEGER | ID người dùng | Ngẫu nhiên 1 → 200,000 |
| `Action` | TEXT | Hành vi người dùng | `login`, `logout`, `click`, `purchase`, `view`, `search`, `upload`, `download`, `share`, `comment` |
| `Timestamp` | TEXT (ISO 8601) | Thời điểm ghi nhận | Ngẫu nhiên trong năm 2024 |

### 3.3 Chiến lược phân mảnh

- **Phương pháp:** Hash-based Horizontal Fragmentation
- **Hàm phân mảnh:** `node_id = UserID % N` (N = 1, 2, 4)
- **Khóa phân mảnh (Fragmentation Key):** `UserID`
- **Lý do chọn `UserID`:** Truy vấn benchmark sử dụng `GROUP BY UserID`, nên phân mảnh theo `UserID` đảm bảo mỗi nhóm hoàn toàn nằm trên một node, loại bỏ nhu cầu re-aggregate giữa các node.

**Tính đúng đắn của phân mảnh (Fragmentation Correctness):**

| Tiêu chí | Đảm bảo | Giải thích |
|---------|---------|-----------|
| **Completeness** (Đầy đủ) | ✅ | Mọi bản ghi đều được ánh xạ vào đúng một fragment thông qua hàm hash xác định (deterministic). |
| **Reconstruction** (Tái tạo) | ✅ | `UNION` tất cả các fragment = bảng gốc ban đầu. |
| **Disjointness** (Tách biệt) | ✅ | Hàm hash ánh xạ mỗi `UserID` vào đúng một node → không có bản ghi trùng lặp giữa các fragment. |

---

## 4. Kiến trúc hệ thống

### 4.1 Tổng quan

Hệ thống sử dụng kiến trúc **3-tier** (Client → Coordinator → Node), mô phỏng cơ sở dữ liệu phân tán trên localhost bằng các tiến trình Flask riêng biệt.

### 4.2 Sơ đồ kiến trúc

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

### 4.3 Vai trò từng thành phần

| Thành phần | Port | Vai trò |
|-----------|------|---------|
| **Client (Benchmark)** | — | Gửi truy vấn aggregation đến Coordinator, đo thời gian end-to-end, ghi kết quả ra CSV/JSON. |
| **Coordinator** | 8000 | Nhận truy vấn từ Client, phân phối song song đến tất cả Node qua `concurrent.futures.ThreadPoolExecutor`, thu thập kết quả, merge (cộng dồn COUNT), trả về cho Client kèm timing. |
| **Node** (×N) | 5000 + i | Lưu trữ shard dữ liệu trong SQLite, thực thi truy vấn `SELECT UserID, COUNT(*) FROM logs GROUP BY UserID` cục bộ, trả kết quả cho Coordinator qua REST API. |

### 4.4 Giao thức truyền thông

- **Client ↔ Coordinator:** `HTTP GET /aggregate`
- **Coordinator ↔ Node:** `HTTP POST /query`
- **Định dạng dữ liệu:** JSON
- **Timeout:** 30 giây mỗi request
- **Retry:** 0 (trong benchmark mode, failure được ghi nhận thay vì retry)

---

## 5. Tech Stack & Kế hoạch triển khai

### 5.1 Ngôn ngữ & Nền tảng

- **Ngôn ngữ:** Python 3.10+
- **Triển khai:** Localhost processes — mỗi node là một tiến trình Flask trên port riêng
- **Hệ điều hành:** Windows / macOS / Linux (cross-platform)

### 5.2 Thư viện

| Thư viện | Phiên bản | Mục đích |
|---------|----------|--------|
| `Flask` | ≥ 2.3 | HTTP server cho các Node và Coordinator |
| `requests` | ≥ 2.28 | HTTP client để Coordinator gọi đến các Node |
| `sqlite3` | Built-in | Storage engine — mỗi node một SQLite database |
| `matplotlib` | ≥ 3.7 | Vẽ biểu đồ Speedup, Efficiency |
| `csv` | Built-in | Đọc/ghi dữ liệu CSV |
| `json` | Built-in | Serialization kết quả benchmark |
| `subprocess` | Built-in | Quản lý tiến trình Flask (start/stop nodes) |
| `concurrent.futures` | Built-in | Parallel query execution (ThreadPoolExecutor) |
| `time` | Built-in | Đo thời gian thực thi (high-resolution timer) |
| `random` | Built-in | Sinh dữ liệu ngẫu nhiên |

### 5.3 Kế hoạch triển khai

```
[Sinh dữ liệu] → [Phân mảnh] → [Khởi tạo DB] → [Khởi động Nodes] → [Benchmark] → [Phân tích]
  generate.py      shard.py      init_db.py      node_app.py       benchmark.py   analyze.py
```

Pipeline hoàn toàn tự động hóa qua script `benchmark/run_benchmark.py`.

---

## 6. Tiêu chí đánh giá & Phân tích

### 6.1 Chỉ số định lượng

| Chỉ số | Công thức | Ý nghĩa |
|--------|-----------|----------|
| **Speedup Ratio** | S(n) = T₁ / Tₙ | Tỷ lệ tăng tốc khi sử dụng n nodes so với 1 node. S(n) = n là tuyến tính lý tưởng. |
| **Efficiency** | E(n) = S(n) / n | Hiệu quả sử dụng tài nguyên. E(n) = 1.0 (100%) là lý tưởng. |
| **Serial Fraction** | f = (1/S(n) − 1/n) / (1 − 1/n) | Phần không thể song song hóa, suy từ Amdahl's Law. |

Trong đó:
- **T₁** = thời gian thực thi trung bình trên 1 node (baseline)
- **Tₙ** = thời gian thực thi trung bình trên n nodes

### 6.2 Phương pháp đo lường

- **Số lần chạy:** 5 runs (sau 2 warmup runs) cho mỗi cấu hình
- **Cấu hình:** 1 node, 2 nodes, 4 nodes
- **Đo lường:** End-to-end execution time tại Coordinator (bao gồm network + query + merge)
- **Loại bỏ nhiễu:** Warmup runs để SQLite cache pages; lấy trung bình 5 runs

### 6.3 Kịch bản lỗi (Failure Scenario)

| Kịch bản | Mô tả | Kết quả kỳ vọng |
|---------|-------|-----------------|
| **Kill Node** | Kill Node 2 đang chạy giữa chừng trong cấu hình 4 nodes | Coordinator phát hiện timeout, trả về kết quả partial từ 3 nodes còn lại |
| **Kiểm chứng** | So sánh kết quả đầy đủ (4 nodes) vs partial (3 nodes) | ~25% dữ liệu bị mất (users ánh xạ đến Node 2), thời gian phản hồi tương đương hoặc ngắn hơn |
| **Graceful Degradation** | Coordinator trả về status `'partial'` thay vì crash | Hệ thống vẫn hoạt động, client biết kết quả không đầy đủ |

---

## 7. Các mốc thực hiện (Milestones)

| Mốc | Thời gian | Nội dung chi tiết | Sản phẩm | Trạng thái |
|-----|-----------|-------------------|----------|------------|
| **M1** | Tuần 1–2 | Thiết lập môi trường phát triển, viết script sinh dữ liệu (`generate.py`), phân mảnh dữ liệu (`shard.py`), tạo dataset 1M dòng | `data/generate.py`, `data/shard.py`, `data/user_logs.csv`, `data/shards/` | ✅ Hoàn thành |
| **M2** | Tuần 3–5 | Xây dựng Node Flask server (`node_app.py`), Coordinator (`coordinator.py`), script khởi tạo DB (`init_db.py`), đảm bảo REST API hoạt động end-to-end | `node/node_app.py`, `node/init_db.py`, `coordinator/coordinator.py` | ✅ Hoàn thành |
| **M3** | Tuần 6–8 | Xây dựng benchmark suite (`benchmark.py`), one-click pipeline (`run_benchmark.py`), failure testing (`failure_test.py`) | `benchmark/benchmark.py`, `benchmark/run_benchmark.py`, `benchmark/failure_test.py` | ✅ Hoàn thành |
| **M4** | Tuần 9–10 | Phân tích kết quả (`analyze.py`), vẽ biểu đồ Speedup & Efficiency, viết báo cáo phân tích (`report.md`) | `analysis/analyze.py`, `analysis/report.md`, `analysis/charts/` | ✅ Hoàn thành |
| **M5** | Tuần 11–12 | Review toàn bộ codebase, viết tài liệu (`proposal.md`, `design_document.md`), quay video demo, nộp bài | `docs/proposal.md`, `docs/design_document.md`, `demo/video_demo.mp4` | 🔄 Đang thực hiện |

---

## Phụ lục: Tài liệu tham khảo

1. **Özsu, M.T. & Valduriez, P.** (2020). *Principles of Distributed Database Systems*, 4th Edition. Springer.
2. **Amdahl, G.** (1967). *Validity of the Single Processor Approach to Achieving Large-Scale Computing Capabilities*. AFIPS Conference Proceedings, Vol. 30, pp. 483–485.
3. **DeWitt, D. & Gray, J.** (1992). *Parallel Database Systems: The Future of High Performance Database Systems*. Communications of the ACM, 35(6), pp. 85–98.

---

> **Ghi chú:** Đề xuất này được viết cho đồ án cá nhân môn Cơ sở dữ liệu phân tán. Mọi dữ liệu sử dụng trong dự án đều là dữ liệu tổng hợp (synthetic) phục vụ mục đích học thuật.
