"""
Failure Test - Kiểm tra khả năng chịu lỗi khi một node bị sập.

Quy trình:
1. Khởi tạo 4 node và coordinator
2. Chạy truy vấn baseline (tất cả node hoạt động)
3. Giết node 2 (mô phỏng sự cố)
4. Chạy truy vấn sau khi node sập
5. So sánh kết quả để đánh giá mức suy giảm
"""

import os
import sys
import time
import glob
import subprocess
from pathlib import Path

import requests

# === Cấu hình ===
NUM_NODES = 4
NODE_BASE_PORT = 5400
COORDINATOR_PORT = 8004
STARTUP_WAIT = 3
KILLED_NODE = 2  # Node sẽ bị giết để kiểm tra

# Xác định thư mục gốc dự án
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


def cleanup_processes(coordinator_proc, node_procs):
    """Dọn dẹp tất cả tiến trình."""
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


def cleanup_db_files():
    """Xóa tất cả file database node_*.db."""
    db_pattern = os.path.join(PROJECT_ROOT, "node", "node_*.db")
    for db_file in glob.glob(db_pattern):
        try:
            os.remove(db_file)
        except OSError:
            pass


def wait_for_health(url, max_retries=15, interval=1):
    """Chờ coordinator sẵn sàng."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(f"{url}/health", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                all_ok = all(
                    n["status"] == "ok" for n in data.get("nodes", [])
                )
                if all_ok:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def main():
    """Hàm chính: chạy bài kiểm tra khả năng chịu lỗi."""
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("Kiểm tra khả năng chịu lỗi")
    print("=" * 60)

    coordinator_proc = None
    node_procs = []

    try:
        # === Bước 1: Thiết lập hệ thống ===
        print(f"\nPhân mảnh dữ liệu cho {NUM_NODES} node...")
        subprocess.run(
            [sys.executable, os.path.join("data", "shard.py"), "--nodes", str(NUM_NODES)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )

        print(f"Khởi tạo database cho {NUM_NODES} node...")
        for i in range(NUM_NODES):
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

        print(f"Khởi động {NUM_NODES} node...")
        for i in range(NUM_NODES):
            env = {**os.environ, "NODE_ID": str(i), "DB_DIR": "node",
                   "NODE_PORT": str(NODE_BASE_PORT + i)}
            proc = subprocess.Popen(
                [sys.executable, os.path.join("node", "node_app.py")],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            node_procs.append(proc)

        # Khởi động coordinator
        node_urls = [f"http://localhost:{NODE_BASE_PORT + i}" for i in range(NUM_NODES)]
        coordinator_proc = subprocess.Popen(
            [
                sys.executable,
                os.path.join("coordinator", "coordinator.py"),
                "--nodes", ",".join(node_urls),
                "--port", str(COORDINATOR_PORT),
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        time.sleep(STARTUP_WAIT)

        # Chờ tất cả node sẵn sàng
        print("Chờ hệ thống sẵn sàng...")
        coordinator_url = f"http://localhost:{COORDINATOR_PORT}"
        if not wait_for_health(coordinator_url):
            print("Không thể khởi động hệ thống. Thoát.")
            return

        print("Tất cả node đã sẵn sàng!\n")

        # === Bước 2: Truy vấn baseline ===
        print("Chạy truy vấn baseline (tất cả node hoạt động)...")
        resp = requests.get(f"{coordinator_url}/aggregate", timeout=30)
        resp.raise_for_status()
        baseline = resp.json()

        print(f"Baseline: {baseline['nodes_responded']} nodes, "
              f"{baseline['unique_users']} users, "
              f"{baseline['execution_time_ms']:.1f} ms")

        # === Bước 3: Giết node 2 ===
        print(f"\nKill node {KILLED_NODE} (mô phỏng sự cố)...")
        killed_proc = node_procs[KILLED_NODE]
        killed_proc.terminate()
        try:
            killed_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            killed_proc.kill()

        # Chờ hệ thống nhận biết node đã sập
        time.sleep(1)

        # === Bước 4: Truy vấn sau sự cố ===
        print("Chạy truy vấn sau khi node sập...")
        resp = requests.get(f"{coordinator_url}/aggregate", timeout=30)
        resp.raise_for_status()
        after_failure = resp.json()

        print(f"After failure: {after_failure['nodes_responded']} nodes, "
              f"{after_failure['unique_users']} users, "
              f"{after_failure['execution_time_ms']:.1f} ms")

        # === Bước 5: So sánh kết quả ===
        print("\n" + "=" * 60)
        print("KẾT QUẢ SO SÁNH")
        print("=" * 60)

        print(f"\n{'Chỉ số':<25} {'Baseline':>12} {'Sau lỗi':>12} {'Thay đổi':>12}")
        print(f"{'-'*25} {'-'*12} {'-'*12} {'-'*12}")

        # Số node phản hồi
        b_nodes = baseline["nodes_responded"]
        a_nodes = after_failure["nodes_responded"]
        print(f"{'Node phản hồi':<25} {b_nodes:>12} {a_nodes:>12} {a_nodes - b_nodes:>+12}")

        # Số user
        b_users = baseline["unique_users"]
        a_users = after_failure["unique_users"]
        user_loss = b_users - a_users
        user_pct = (user_loss / b_users * 100) if b_users > 0 else 0
        print(f"{'Unique users':<25} {b_users:>12} {a_users:>12} {-user_loss:>+12}")

        # Tổng log
        b_logs = baseline["total_logs"]
        a_logs = after_failure["total_logs"]
        log_loss = b_logs - a_logs
        log_pct = (log_loss / b_logs * 100) if b_logs > 0 else 0
        print(f"{'Total logs':<25} {b_logs:>12} {a_logs:>12} {-log_loss:>+12}")

        # Thời gian thực thi
        b_time = baseline["execution_time_ms"]
        a_time = after_failure["execution_time_ms"]
        print(f"{'Thời gian (ms)':<25} {b_time:>12.1f} {a_time:>12.1f} {a_time - b_time:>+12.1f}")

        # Trạng thái
        print(f"\nTrạng thái baseline:    {baseline['status']}")
        print(f"Trạng thái sau lỗi:    {after_failure['status']}")

        # Tóm tắt
        print(f"\n  Tóm tắt:")
        print(f"     - Mất {user_pct:.1f}% unique users do node {KILLED_NODE} sập")
        print(f"     - Mất {log_pct:.1f}% log records")
        print(f"     - Hệ thống vẫn hoạt động với trạng thái '{after_failure['status']}'")
        print(f"     → Kết luận: Hệ thống chịu lỗi tốt, tiếp tục phục vụ dù mất 1 node")

    except Exception as e:
        print(f"\nBài kiểm tra thất bại: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Dọn dẹp tất cả tiến trình và file DB
        print("\nDừng tất cả tiến trình...")
        cleanup_processes(coordinator_proc, node_procs)
        cleanup_db_files()
        print("Đã dọn dẹp xong.")


if __name__ == "__main__":
    main()
