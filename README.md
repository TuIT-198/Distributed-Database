# 🔀 ShardMasters — Horizontal Scaling Efficiency

> **Đồ án môn Cơ sở dữ liệu phân tán | Project #94 — "Sharding Gains"**

`Python 3.10+` • `Flask` • `SQLite` • `matplotlib`

---

## 📝 Mô tả

Hệ thống mô phỏng cơ sở dữ liệu phân tán sử dụng **horizontal hash-based sharding** để đánh giá hiệu quả mở rộng ngang. Dự án đo lường **Speedup Ratio** (tỷ lệ tăng tốc) khi phân tán truy vấn aggregation `COUNT(*) GROUP BY UserID` trên tập dữ liệu 1 triệu bản ghi `User_Logs` với các cấu hình 1 → 2 → 4 nodes. Kết quả được phân tích dựa trên lý thuyết **Amdahl's Law** và các chỉ số **Efficiency** nhằm làm rõ giới hạn của horizontal scaling trong hệ thống phân tán.

---

## 🏗️ Kiến trúc hệ thống

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

Hệ thống sử dụng kiến trúc **Client → Coordinator → Node** (3-tier):

- **Client/Benchmark**: Gửi truy vấn aggregation đến Coordinator và đo thời gian phản hồi.
- **Coordinator** (Port 8000): Nhận truy vấn từ Client, phân phối song song đến các Node qua REST API, thu thập và merge kết quả.
- **Node** (Port 5000+): Mỗi node lưu trữ một shard dữ liệu trong SQLite, thực thi truy vấn cục bộ và trả về kết quả.

---

## 📁 Cấu trúc dự án

```
ShardMasters/
├── README.md
├── requirements.txt
├── data/
│   ├── generate.py          # Sinh 1M dòng user_logs.csv
│   ├── shard.py             # Hash-based sharding (UserID % N)
│   ├── user_logs.csv        # Dataset gốc (~40MB)
│   └── shards/              # CSV shards cho từng node
├── node/
│   ├── init_db.py           # Import CSV → SQLite + INDEX
│   └── node_app.py          # Flask node (REST API)
├── coordinator/
│   └── coordinator.py       # Phân phối query + merge kết quả
├── benchmark/
│   ├── benchmark.py         # Benchmark tự động 1/2/4 nodes
│   ├── run_benchmark.py     # One-click pipeline
│   └── failure_test.py      # Mô phỏng node failure
├── analysis/
│   ├── analyze.py           # Tính Speedup + vẽ biểu đồ
│   ├── report.md            # Báo cáo phân tích
│   └── charts/              # Biểu đồ PNG
├── results/                 # Kết quả benchmark (CSV + JSON)
├── docs/
│   ├── proposal.md          # Project Proposal
│   └── design_document.md   # Design Document
└── demo/
    └── video_demo.mp4       # Video demo
```

---

## 💻 Yêu cầu hệ thống

- **Python** 3.10 trở lên
- **pip** (Python package manager)
- Hệ điều hành: Windows / macOS / Linux

---

## ⚙️ Cài đặt

```bash
# Clone repository
git clone <repo-url>
cd ShardMasters

# Cài đặt dependencies
pip install -r requirements.txt
```

---

## 🚀 Hướng dẫn sử dụng

### Chạy nhanh (One-click Pipeline)

Chạy toàn bộ pipeline từ sinh dữ liệu → phân mảnh → benchmark → phân tích chỉ với một lệnh:

```bash
python benchmark/run_benchmark.py
```

### Chạy từng bước

#### Bước 1: Sinh dữ liệu (1 triệu bản ghi)

```bash
python data/generate.py
```

Tạo file `data/user_logs.csv` chứa 1,000,000 dòng dữ liệu User_Logs.

#### Bước 2: Phân mảnh dữ liệu (Hash-based Sharding)

```bash
python data/shard.py --nodes 4
```

Phân mảnh `user_logs.csv` thành N file CSV trong thư mục `data/shards/` theo công thức `node_id = UserID % N`.

#### Bước 3: Khởi tạo cơ sở dữ liệu SQLite

```bash
python node/init_db.py 0 --csv-dir data/shards --db-dir node
```

Import CSV shard vào SQLite database, tạo INDEX trên cột `UserID` để tối ưu truy vấn GROUP BY.

#### Bước 4: Chạy benchmark

```bash
python benchmark/benchmark.py
```

Tự động benchmark truy vấn aggregation trên cấu hình 1, 2, và 4 nodes. Kết quả lưu trong thư mục `results/`.

#### Bước 5: Phân tích kết quả

```bash
python analysis/analyze.py
```

Tính toán Speedup, Efficiency và vẽ biểu đồ lưu vào `analysis/charts/`.

#### Bước 6: Test failure (Mô phỏng lỗi node)

```bash
python benchmark/failure_test.py
```

Mô phỏng tình huống một node bị lỗi giữa chừng, kiểm tra khả năng degradation graceful của coordinator.

---

## 📊 Kết quả Benchmark

### Chi tiết thời gian thực thi (ms)
| Nodes | Mean (ms) | Median (ms) | P99 (ms) | Std (ms) | Min (ms) | Max (ms) |
| :---: | :-------: | :---------: | :------: | :------: | :------: | :------: |
|   1   |   232.2   |    223.8    |  286.6   |   32.8   |  205.4   |  289.1   |
|   2   |   106.3   |     93.5    |  154.0   |   28.1   |   93.4   |  156.4   |
|   4   |    89.8   |     86.4    |  100.6   |    9.3   |   78.3   |  100.7   |

### Tốc độ tăng tốc (Speedup) & Hiệu suất (Efficiency)
- **Dựa trên giá trị trung bình (Mean-based):**
  * **2 Nodes:** Speedup = **2.185x**, Efficiency = **109.3%**
  * **4 Nodes:** Speedup = **2.587x**, Efficiency = **64.7%**
- **Dựa trên trung vị (Median-based — Khuyên dùng vì loại bỏ outliers):**
  * **2 Nodes:** Speedup = **2.395x**, Efficiency = **119.7%**
  * **4 Nodes:** Speedup = **2.590x**, Efficiency = **64.8%**

> **Ghi chú:** Kết quả đo trên localhost qua 5 lượt chạy thực tế (sau 2 warmup runs). Thời gian đo = max(query_time) trên các node (thời gian thực thi SQL thực tế). Speedup siêu tuyến tính (super-linear) ở cấu hình 2 nodes đạt được nhờ hiệu ứng RAM cache bộ đệm trang đĩa (OS Page Cache) và tối ưu độ sâu cây chỉ mục SQLite B-Tree khi dữ liệu phân mảnh nhỏ đi.


---

## 📐 Công thức

| Chỉ số | Công thức | Ý nghĩa |
|--------|-----------|----------|
| **Speedup** | S(n) = T₁ / Tₙ | Tỷ lệ tăng tốc khi sử dụng n nodes so với 1 node |
| **Efficiency** | E(n) = S(n) / n | Hiệu quả sử dụng tài nguyên (≤ 1.0 = 100%) |
| **Amdahl's Law** | S(n) ≤ 1 / (f + (1−f)/n) | Giới hạn tăng tốc với f là phần tuần tự |

---

## 📚 Tài liệu tham khảo

1. **Özsu, M.T. & Valduriez, P.** (2020). *Principles of Distributed Database Systems*, 4th Edition. Springer.
2. **Amdahl, G.** (1967). *Validity of the Single Processor Approach to Achieving Large-Scale Computing Capabilities*. AFIPS Conference Proceedings.
3. **DeWitt, D. & Gray, J.** (1992). *Parallel Database Systems: The Future of High Performance Database Systems*. Communications of the ACM.

---

## 👤 Thành viên

| Họ tên | Vai trò |
|--------|---------|
| **Đàm Công Tú** | Developer & Analyst |

**Tên nhóm:** ShardMasters

---

## 📄 License

MIT License

```
MIT License

Copyright (c) 2026 ShardMasters — Đàm Công Tú

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
