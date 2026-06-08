"""
Run Benchmark - Script chạy toàn bộ pipeline benchmark một lần nhấn.

Quy trình:
1. Kiểm tra các thư viện phụ thuộc
2. Tạo dữ liệu nếu chưa có
3. Chạy benchmark
4. Chạy phân tích và tạo biểu đồ
"""

import os
import sys
import subprocess
from pathlib import Path

# Xác định thư mục gốc dự án
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

def check_dependencies():
    """
    Kiểm tra các thư viện Python cần thiết.
    Trả về True nếu tất cả đã được cài đặt, False nếu thiếu.
    """
    missing = []
    # Kiểm tra Flask
    try:
        import flask  # noqa: F401
    except ImportError:
        missing.append("flask")
    # Kiểm tra requests
    try:
        import requests  # noqa: F401
    except ImportError:
        missing.append("requests")
    # Kiểm tra matplotlib
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        missing.append("matplotlib")
    if missing:
        print("[LỖI] Thiếu các thư viện sau:")
        for lib in missing:
            print(f"  - {lib}")
        print()
        print("Hãy cài đặt bằng lệnh:")
        print(f"  pip install {' '.join(missing)}")
        return False

    print("Tất cả thư viện phụ thuộc đã sẵn sàng.")
    return True


def main():
    """Hàm chính: chạy toàn bộ pipeline benchmark."""
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("  ShardMasters — Full Benchmark Pipeline")
    print("=" * 60)
    print()
    # Bước 1: Kiểm tra thư viện phụ thuộc
    print("Kiểm tra thư viện phụ thuộc...")
    if not check_dependencies():
        sys.exit(1)
    # Bước 2: Kiểm tra và tạo dữ liệu nếu cần
    print()
    print("Kiểm tra dữ liệu...")
    data_file = os.path.join(PROJECT_ROOT, "data", "user_logs.csv")
    if not os.path.exists(data_file):
        print("Chưa có file dữ liệu. Đang tạo dữ liệu mẫu...")
        try:
            subprocess.run(
                [sys.executable, os.path.join("data", "generate.py")],
                cwd=PROJECT_ROOT,
                check=True,
            )
            print("Đã tạo dữ liệu thành công.")
        except subprocess.CalledProcessError as e:
            print(f"Không thể tạo dữ liệu: {e}")
            sys.exit(1)
    else:
        print(f"Dữ liệu đã tồn tại: {data_file}")

    # Bước 3: Chạy benchmark
    print()
    print("Chạy benchmark...")
    print("-" * 40)
    try:
        subprocess.run(
            [sys.executable, os.path.join("benchmark", "benchmark.py")],
            cwd=PROJECT_ROOT,
            check=True,
        )
        print("[OK] Benchmark hoàn tất.")
    except subprocess.CalledProcessError as e:
        print(f"Benchmark thất bại: {e}")
        print("Kiểm tra lại các node và coordinator.")
        sys.exit(1)

    # Bước 4: Chạy phân tích và tạo biểu đồ
    print()
    print("Phân tích kết quả và tạo biểu đồ...")
    print("-" * 40)
    try:
        subprocess.run(
            [sys.executable, os.path.join("analysis", "analyze.py")],
            cwd=PROJECT_ROOT,
            check=True,
        )
        print("Phân tích hoàn tất.")
    except subprocess.CalledProcessError as e:
        print(f"Phân tích thất bại: {e}")
        print("Kiểm tra file results/benchmark_summary.json.")
        sys.exit(1)

    # Hoàn tất
    print()
    print("=" * 60)
    print("Pipeline complete!")
    print("Check results/ and analysis/charts/ for output.")
    print("=" * 60)

if __name__ == "__main__":
    main()
