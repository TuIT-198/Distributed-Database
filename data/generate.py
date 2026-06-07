"""
Tạo dữ liệu User_Logs gồm 1 triệu bản ghi.
Schema: LogID (int), UserID (int), Action (str), Timestamp (datetime)
"""

import csv
import sys
import os
import random
from datetime import datetime, timedelta
from collections import Counter

# Đặt seed để đảm bảo tính tái tạo được của dữ liệu
random.seed(42)

# Cấu hình tham số sinh dữ liệu
TOTAL_ROWS = 1_000_000
MAX_USER_ID = 200_000
ACTIONS = ['login', 'logout', 'click', 'purchase', 'view',
           'search', 'upload', 'download', 'share', 'comment']
PROGRESS_INTERVAL = 200_000

# Mốc thời gian: toàn bộ năm 2024
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 12, 31, 23, 59, 59)
TOTAL_SECONDS = int((END_DATE - START_DATE).total_seconds())


def random_timestamp():
    """Sinh một thời điểm ngẫu nhiên trong năm 2024."""
    offset = random.randint(0, TOTAL_SECONDS)
    return (START_DATE + timedelta(seconds=offset)).strftime('%Y-%m-%d %H:%M:%S')


def generate_data(output_path: str):
    """Sinh toàn bộ dữ liệu và ghi ra file CSV với bộ đệm."""
    # Theo dõi thống kê
    unique_users = set()
    action_counter = Counter()

    # Mở file với bộ đệm lớn (64KB) để tăng hiệu suất ghi
    with open(output_path, 'w', newline='', encoding='utf-8', buffering=65536) as f:
        writer = csv.writer(f)
        # Ghi dòng tiêu đề
        writer.writerow(['LogID', 'UserID', 'Action', 'Timestamp'])

        for log_id in range(1, TOTAL_ROWS + 1):
            user_id = random.randint(1, MAX_USER_ID)
            action = random.choice(ACTIONS)
            timestamp = random_timestamp()

            writer.writerow([log_id, user_id, action, timestamp])

            # Cập nhật thống kê
            unique_users.add(user_id)
            action_counter[action] += 1

            # In tiến trình mỗi 200K dòng
            if log_id % PROGRESS_INTERVAL == 0:
                print(f"[Tiến trình] Đã ghi {log_id:,} / {TOTAL_ROWS:,} dòng "
                      f"({log_id * 100 // TOTAL_ROWS}%)")

    return unique_users, action_counter


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    # Xác định đường dẫn file đầu ra cùng thư mục với script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, 'user_logs.csv')

    print(f"Bắt đầu sinh {TOTAL_ROWS:,} bản ghi User_Logs...")
    print(f"File đầu ra: {output_file}")
    print("-" * 50)

    unique_users, action_counter = generate_data(output_file)

    # In thống kê cuối cùng
    print("-" * 50)
    print(f"Tổng số dòng:       {TOTAL_ROWS:,}")
    print(f"Số người dùng duy nhất: {len(unique_users):,}")
    print()
    print("Phân bố hành động:")
    for action in ACTIONS:
        count = action_counter[action]
        pct = count * 100 / TOTAL_ROWS
        print(f"  {action:<12} : {count:>8,} ({pct:.2f}%)")
    print("-" * 50)
    print("Hoàn tất!")