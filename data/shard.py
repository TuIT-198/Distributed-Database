"""
Sharding ngang dựa trên hàm băm (hash-based horizontal sharding).
Phân chia user_logs.csv thành N phân mảnh theo công thức: UserID % N
"""

import argparse
import sys
import csv
import os


def get_shard_id(user_id: int, num_nodes: int) -> int:
    """Hàm sharding: xác định phân mảnh dựa trên UserID."""
    return user_id % num_nodes


def shard_data(input_path: str, output_dir: str, num_nodes: int):
    """Đọc file CSV đầu vào và phân chia dữ liệu vào các phân mảnh."""
    # Tạo thư mục đầu ra nếu chưa tồn tại
    os.makedirs(output_dir, exist_ok=True)

    # Mở tất cả file đầu ra cùng lúc để ghi song song
    writers = {}
    files = {}
    row_counts = {}

    try:
        for node_id in range(num_nodes):
            file_path = os.path.join(output_dir, f'node_{node_id}.csv')
            f = open(file_path, 'w', newline='', encoding='utf-8')
            files[node_id] = f
            writers[node_id] = csv.writer(f)
            # Ghi dòng tiêu đề cho mỗi phân mảnh
            writers[node_id].writerow(['LogID', 'UserID', 'Action', 'Timestamp'])
            row_counts[node_id] = 0

        # Đọc file đầu vào và phân phối từng dòng
        total_rows = 0
        with open(input_path, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            # Bỏ qua dòng tiêu đề
            next(reader)

            for row in reader:
                user_id = int(row[1])
                shard_id = get_shard_id(user_id, num_nodes)
                writers[shard_id].writerow(row)
                row_counts[shard_id] += 1
                total_rows += 1

    finally:
        # Đóng tất cả file đầu ra
        for f in files.values():
            f.close()

    return total_rows, row_counts


def print_stats(total_rows: int, row_counts: dict, num_nodes: int):
    """In thống kê phân bố dữ liệu cho từng phân mảnh."""
    print("-" * 50)
    print(f"{'Node ID':<10} {'Số dòng':>12} {'Tỷ lệ (%)':>12}")
    print("-" * 50)

    verified_total = 0
    for node_id in range(num_nodes):
        count = row_counts[node_id]
        pct = count * 100 / total_rows if total_rows > 0 else 0
        print(f"{node_id:<10} {count:>12,} {pct:>11.2f}%")
        verified_total += count

    print("-" * 50)
    print(f"{'Tổng':<10} {verified_total:>12,}")

    # Xác minh tổng số dòng khớp với đầu vào
    if verified_total == total_rows:
        print(f"✓ Xác minh thành công: tổng số dòng khớp ({total_rows:,})")
    else:
        print(f"✗ LỖI: Tổng dòng phân mảnh ({verified_total:,}) "
              f"≠ dòng đầu vào ({total_rows:,})")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    # Phân tích tham số dòng lệnh
    parser = argparse.ArgumentParser(
        description='Phân mảnh ngang dữ liệu User_Logs theo UserID'
    )
    parser.add_argument(
        '--nodes', type=int, default=4, choices=[1, 2, 3, 4],
        help='Số lượng node phân mảnh (mặc định: 4)'
    )
    args = parser.parse_args()

    # Xác định đường dẫn dựa trên vị trí script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, 'user_logs.csv')
    output_dir = os.path.join(script_dir, 'shards')

    print(f"Bắt đầu phân mảnh dữ liệu với {args.nodes} node...")
    print(f"File đầu vào:    {input_file}")
    print(f"Thư mục đầu ra:  {output_dir}")
    print()

    # Kiểm tra file đầu vào tồn tại
    if not os.path.exists(input_file):
        print(f"LỖI: Không tìm thấy file đầu vào: {input_file}")
        print("Hãy chạy generate.py trước để tạo dữ liệu.")
        exit(1)

    total_rows, row_counts = shard_data(input_file, output_dir, args.nodes)
    print_stats(total_rows, row_counts, args.nodes)
    print("\nHoàn tất phân mảnh!")