"""
Khởi tạo cơ sở dữ liệu SQLite cho một node từ file CSV phân mảnh.
Tạo bảng logs và chỉ mục idx_userid để tối ưu truy vấn GROUP BY.
"""

import argparse
import sys
import csv
import os
import sqlite3

# Kích thước batch cho INSERT hàng loạt
BATCH_SIZE = 10_000


def init_database(node_id: int, csv_dir: str, db_dir: str):
    """Khởi tạo cơ sở dữ liệu SQLite từ file CSV phân mảnh."""
    # Xác định đường dẫn file CSV và file database
    csv_path = os.path.join(csv_dir, f'node_{node_id}.csv')
    db_path = os.path.join(db_dir, f'node_{node_id}.db')

    print(f"Khởi tạo database cho Node {node_id}")
    print(f"  File CSV:      {csv_path}")
    print(f"  File database: {db_path}")

    # Kiểm tra file CSV tồn tại
    if not os.path.exists(csv_path):
        print(f"Không tìm thấy file CSV: {csv_path}")
        print("Hãy chạy shard.py trước để tạo các phân mảnh.")
        exit(1)

    # Tạo thư mục database nếu chưa tồn tại
    os.makedirs(db_dir, exist_ok=True)

    # Xóa database cũ nếu tồn tại
    if os.path.exists(db_path):
        os.remove(db_path)
        print("  Đã xóa database cũ.")

    # Kết nối và tạo bảng
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tạo bảng logs
    cursor.execute('''
        CREATE TABLE logs (
            LogID     INTEGER,
            UserID    INTEGER,
            Action    TEXT,
            Timestamp TEXT
        )
    ''')

    #Tạo chỉ mục trên UserID để tối ưu truy vấn GROUP BY
    cursor.execute('CREATE INDEX idx_userid ON logs(UserID)')

    # Đọc toàn bộ dữ liệu từ CSV
    print("Đang đọc dữ liệu từ CSV...")
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            # Chuyển đổi kiểu dữ liệu: LogID và UserID thành int
            rows.append((int(row[0]), int(row[1]), row[2], row[3]))

    total_rows = len(rows)
    print(f"  Đã đọc {total_rows:,} dòng từ CSV.")

    # Chèn dữ liệu theo batch để tối ưu hiệu suất
    print(f"Đang chèn dữ liệu (batch size = {BATCH_SIZE:,})...")
    for i in range(0, total_rows, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        cursor.executemany(
            'INSERT INTO logs (LogID, UserID, Action, Timestamp) VALUES (?, ?, ?, ?)',
            batch
        )

    # Lưu thay đổi
    conn.commit()

    # Xác minh số dòng đã chèn
    cursor.execute('SELECT COUNT(*) FROM logs')
    db_count = cursor.fetchone()[0]

    conn.close()

    print(f"  Số dòng đã chèn: {db_count:,}")
    if db_count == total_rows:
        print(f"Xác minh thành công: {db_count:,} dòng khớp.")
    else:
        print(f"LỖI: CSV có {total_rows:,} dòng nhưng DB có {db_count:,} dòng.")

    print("Hoàn tất khởi tạo database!")

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    # Phân tích tham số dòng lệnh
    parser = argparse.ArgumentParser(
        description='Khởi tạo cơ sở dữ liệu SQLite cho một node'
    )
    parser.add_argument(
        'node_id', type=int,
        help='ID của node cần khởi tạo (ví dụ: 0, 1, 2, 3)'
    )
    parser.add_argument(
        '--csv-dir', type=str, default=None,
        help='Thư mục chứa file CSV phân mảnh (mặc định: ../data/shards)'
    )
    parser.add_argument(
        '--db-dir', type=str, default=None,
        help='Thư mục lưu file database (mặc định: thư mục chứa script)'
    )
    args = parser.parse_args()

    # Xác định đường dẫn mặc định dựa trên vị trí script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    csv_dir = args.csv_dir if args.csv_dir else os.path.join(script_dir, '..', 'data', 'shards')
    db_dir = args.db_dir if args.db_dir else script_dir

    # Chuẩn hóa đường dẫn
    csv_dir = os.path.abspath(csv_dir)
    db_dir = os.path.abspath(db_dir)

    init_database(args.node_id, csv_dir, db_dir)