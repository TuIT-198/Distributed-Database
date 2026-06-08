"""
Benchmark - Đo hiệu suất hệ thống phân tán với các cấu hình node khác nhau.
Tự động hóa quy trình benchmark cho 1, 2, 4 node:
- Phân mảnh dữ liệu
- Khởi tạo database cho từng node
- Khởi động các tiến trình node và coordinator
- Thực hiện warmup và benchmark
- Thu thập và xuất kết quả
"""
import os
import sys
import time
import json
import glob
import subprocess
import statistics
from datetime import datetime
from pathlib import Path
import requests
# === Cấu hình benchmark ===
CONFIGS = [1, 2, 4]              
RUNS_PER_CONFIG = 5   
WARMUP_RUNS = 2                
NODE_BASE_PORT = 5000            
COORDINATOR_BASE_PORT = 8000    
STARTUP_WAIT = 5                
# Xác định thư mục cha của benchmark
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
# Dọn dẹp tất cả tiến trình: coordinator và các node.
def cleanup_processes(coordinator_proc, node_procs):
    all_procs = []
    if coordinator_proc:
        all_procs.append(coordinator_proc)
    all_procs.extend([p for p in node_procs if p])
    for proc in all_procs:
        if proc.poll() is None:
            try:
                proc.kill() 
                proc.wait(timeout=5)
            except Exception:
                pass
#Xóa tất cả file database node_*.db trong thư mục node/.
def cleanup_db_files():
    db_pattern = os.path.join(PROJECT_ROOT, "node", "node_*.db")
    for db_file in glob.glob(db_pattern):
        try:
            os.remove(db_file)
        except OSError:
            pass
"""
    Chờ coordinator sẵn sàng bằng cách poll endpoint /health.
    Trả về True nếu thành công, False nếu hết số lần thử.
"""
def wait_for_health(url, max_retries=15, interval=1):
    for attempt in range(max_retries):
        try:
            resp = requests.get(f"{url}/health", timeout=30)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        except Exception:
            pass
        time.sleep(interval)
    return False
"""
    Chạy benchmark cho một cấu hình node cụ thể.
    Trả về danh sách thời gian thực thi cho mỗi lần chạy.
"""
def run_benchmark_for_config(n_nodes):
    coordinator_port = COORDINATOR_BASE_PORT + n_nodes
    print(f"\n{'=' * 50}")
    print(f"=== Benchmarking với {n_nodes} node ===")
    print(f"{'=' * 50}")
    coordinator_proc = None
    node_procs = []
    try:
        print(f"Phân mảnh dữ liệu cho {n_nodes} node...")
        subprocess.run(
            [sys.executable, os.path.join("data", "shard.py"), "--nodes", str(n_nodes)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        print(f"Khởi tạo database cho {n_nodes} node...")
        for i in range(n_nodes):
            subprocess.run(
                [
                    sys.executable,
                    os.path.join("node", "init_db.py"),
                    str(i),
                    "--csv-dir", os.path.join("data", "shards"),
                    "--db-dir", "node",
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
            )
        # Khởi động các tiến trình node
        # Dùng port range riêng cho mỗi cấu hình để tránh TIME_WAIT conflict
        node_base = NODE_BASE_PORT + n_nodes * 100  # 5100, 5200, 5400
        print(f"Khởi động {n_nodes} node (port {node_base}-{node_base + n_nodes - 1})...")
        for i in range(n_nodes):
            env = {**os.environ, "NODE_ID": str(i), "DB_DIR": "node",
                   "NODE_PORT": str(node_base + i)}
            proc = subprocess.Popen(
                [sys.executable, os.path.join("node", "node_app.py")],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            node_procs.append(proc)
        print("Khởi động coordinator...")
        node_urls = [f"http://localhost:{node_base + i}" for i in range(n_nodes)]
        coordinator_proc = subprocess.Popen(
            [
                sys.executable,
                os.path.join("coordinator", "coordinator.py"),
                "--nodes", ",".join(node_urls),
                "--port", str(coordinator_port),
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Chờ khởi động
        time.sleep(STARTUP_WAIT)
        print("Kiểm tra trạng thái hệ thống...")
        coordinator_url = f"http://localhost:{coordinator_port}"
        if not wait_for_health(coordinator_url):
            # Debug: kiểm tra coordinator có crash không
            if coordinator_proc.poll() is not None:
                stderr_out = coordinator_proc.stderr.read().decode('utf-8', errors='replace')
                print(f"Coordinator đã thoát với mã: {coordinator_proc.returncode}")
                if stderr_out:
                    print(f"Stderr: {stderr_out[:500]}")
            # Kiểm tra node nào đang chạy
            for i, proc in enumerate(node_procs):
                if proc.poll() is not None:
                    print(f"Node {i} đã thoát với mã: {proc.returncode}")
            print(f"Không thể kết nối đến coordinator sau nhiều lần thử. Bỏ qua cấu hình {n_nodes} node.")
            return None

        # Warmup - Khởi động nóng để ổn định hiệu suất
        print(f"Warmup ({WARMUP_RUNS} lần)...")
        for _ in range(WARMUP_RUNS):
            try:
                requests.get(f"{coordinator_url}/aggregate", timeout=30)
            except Exception:
                pass

        # Benchmark chính
        print(f"Benchmark ({RUNS_PER_CONFIG} lần):")
        times = []
        for run_idx in range(1, RUNS_PER_CONFIG + 1):
            try:
                resp = requests.get(f"{coordinator_url}/aggregate", timeout=60)
                resp.raise_for_status()
                result = resp.json()
                # Đo thời gian query thực tế trên node
                # max(query_times_ms) = thời gian node chậm nhất (bottleneck)
                query_times = result.get("query_times_ms", [])
                if query_times:
                    exec_time = max(query_times)
                else:
                    exec_time = result["execution_time_ms"]
                times.append(exec_time)
                print(f"  Run {run_idx}: {exec_time:.1f} ms")
            except Exception as e:
                print(f"  Run {run_idx}: LỖI - {e}")

        return times

    finally:
        # Dọn dẹp tiến trình
        cleanup_processes(coordinator_proc, node_procs)
        cleanup_db_files()
        # Chờ giải phóng port
        time.sleep(3)


def print_summary_table(summary):
    """In bảng tổng kết benchmark với định dạng đẹp."""
    configs = summary.get("configs", {})
    speedup = summary.get("speedup", {})
    efficiency = summary.get("efficiency", {})

    print()
    print("╔══════════╦═══════════════╦═══════════════╦═══════════════╦═══════════╦════════════╦════════════╗")
    print("║  Nodes   ║   Mean (ms)   ║  Median (ms)  ║   P99 (ms)    ║ Std (ms)  ║  Speedup   ║ Efficiency ║")
    print("╠══════════╬═══════════════╬═══════════════╬═══════════════╬═══════════╬════════════╬════════════╣")

    for n_str in sorted(configs.keys(), key=lambda x: int(x)):
        cfg = configs[n_str]
        sp = speedup.get(n_str, 1.0)
        eff = efficiency.get(n_str, 1.0)
        print(
            f"║    {n_str:<5} ║   {cfg['mean_ms']:>8.1f}    ║   {cfg['median_ms']:>8.1f}    ║   {cfg['p99_ms']:>8.1f}    ║   {cfg['std_ms']:>5.1f}   "
            f"║   {sp:>5.3f}x   ║  {eff * 100:>5.1f}%    ║"
        )

    print("╚══════════╩═══════════════╩═══════════════╩═══════════════╩═══════════╩════════════╩════════════╝")


def main():
    """Hàm chính: chạy benchmark và xuất kết quả."""
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("Hiệu suất Horizontal Scaling")
    print("=" * 60)
    # Tạo thư mục kết quả
    results_dir = os.path.join(PROJECT_ROOT, "results")
    os.makedirs(results_dir, exist_ok=True)
    # Lưu tất cả kết quả benchmark
    all_results = {}  # {n_nodes_str: [times]}
    csv_rows = []     # Dữ liệu cho file CSV

    for n_nodes in CONFIGS:
        times = run_benchmark_for_config(n_nodes)
        if times and len(times) > 0:
            all_results[str(n_nodes)] = times
            for run_idx, t in enumerate(times, 1):
                csv_rows.append((n_nodes, run_idx, t))
        else:
            print(f"\nCấu hình {n_nodes} node thất bại hoặc không có kết quả.")

    if not all_results:
        print("\nKhông có kết quả benchmark nào. Kết thúc.")
        sys.exit(1)

    # === Xuất file CSV ===
    csv_path = os.path.join(results_dir, "benchmark_results.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("nodes,run,execution_time_ms\n")
        for nodes, run, t in csv_rows:
            f.write(f"{nodes},{run},{t:.1f}\n")
    print(f"\nĐã lưu kết quả CSV: {csv_path}")

    # === Tính toán thống kê ===
    configs_summary = {}
    for n_str, times in all_results.items():
        mean_ms = statistics.mean(times)
        std_ms = statistics.stdev(times) if len(times) > 1 else 0.0
        
        # Tính median và P99 (tail latency) sử dụng linear interpolation
        sorted_times = sorted(times)
        median_ms = statistics.median(times)
        
        n_len = len(sorted_times)
        if n_len == 1:
            p99_ms = sorted_times[0]
        else:
            k_val = (n_len - 1) * 0.99
            idx_val = int(k_val)
            frac_val = k_val - idx_val
            p99_ms = sorted_times[idx_val] + frac_val * (sorted_times[idx_val + 1] - sorted_times[idx_val])
        
        configs_summary[n_str] = {
            "mean_ms": round(mean_ms, 2),
            "median_ms": round(median_ms, 2),
            "std_ms": round(std_ms, 2),
            "p99_ms": round(p99_ms, 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "runs": [round(t, 2) for t in times],
        }

    # Tính speedup và efficiency so với 1 node
    baseline_mean = configs_summary.get("1", {}).get("mean_ms", None)
    speedup_dict = {}
    efficiency_dict = {}

    for n_str in configs_summary:
        n = int(n_str)
        if baseline_mean and baseline_mean > 0:
            sp = baseline_mean / configs_summary[n_str]["mean_ms"]
            speedup_dict[n_str] = round(sp, 4)
            efficiency_dict[n_str] = round(sp / n, 4)
        else:
            speedup_dict[n_str] = 1.0
            efficiency_dict[n_str] = 1.0

    # === Xuất file JSON ===
    summary = {
        "timestamp": datetime.now().isoformat(),
        "configs": configs_summary,
        "speedup": speedup_dict,
        "efficiency": efficiency_dict,
    }

    json_path = os.path.join(results_dir, "benchmark_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Đã lưu tổng kết JSON: {json_path}")

    # === In bảng tổng kết ===
    print_summary_table(summary)

    print(f"\nBenchmark xong. Kết quả tại: {results_dir}")


if __name__ == "__main__":
    main()
