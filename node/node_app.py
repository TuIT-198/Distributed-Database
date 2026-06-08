"""
Ứng dụng Flask cho storage node - phục vụ truy vấn qua REST API.
Mỗi node chạy trên cổng 5000 + NODE_ID.
"""

import json
import logging
import sys
import os
import sqlite3
import time

from flask import Flask, Response, jsonify, request

# Đọc cấu hình từ biến môi trường
NODE_ID = int(os.environ.get('NODE_ID', '0'))
DB_DIR = os.environ.get('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get('NODE_PORT', 5000 + NODE_ID))

# Đường dẫn đến file database
db_path = os.path.join(DB_DIR, f'node_{NODE_ID}.db')

# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Tắt cảnh báo server phát triển để đầu ra benchmark sạch hơn
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


def get_db_connection():
    """Tạo kết nối đến cơ sở dữ liệu SQLite."""
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    return conn


def get_row_count():
    """Lấy tổng số dòng trong bảng logs."""
    conn = get_db_connection()
    if conn is None:
        return -1
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM logs')
        count = cursor.fetchone()[0]
        return count
    finally:
        conn.close()


@app.before_request
def log_request_start():
    """Ghi nhận thời điểm bắt đầu xử lý yêu cầu."""
    request._start_time = time.time()


@app.after_request
def log_request_end(response):
    """Ghi log cho mỗi yêu cầu: phương thức, endpoint, thời gian phản hồi (ms)."""
    elapsed_ms = (time.time() - request._start_time) * 1000
    app.logger.info(
        f"{request.method} {request.path} - {response.status_code} - {elapsed_ms:.2f}ms"
    )
    return response


@app.route('/health', methods=['GET'])
def health():
    """Kiểm tra trạng thái hoạt động của node."""
    if not os.path.exists(db_path):
        return jsonify({
            'status': 'error',
            'message': 'Database not found'
        }), 503

    row_count = get_row_count()
    return jsonify({
        'status': 'ok',
        'node_id': NODE_ID,
        'row_count': row_count
    })


@app.route('/query', methods=['POST'])
def query():
    """
    Truy vấn đếm số log theo từng UserID (GROUP BY).

    Node thực thi truy vấn GROUP BY cục bộ trên shard của mình,
    sau đó trả về kết quả tổng hợp (summary) thay vì toàn bộ dữ liệu.

    Lý do: Với hash-based sharding theo UserID, mỗi UserID chỉ tồn tại
    trên đúng 1 node → kết quả COUNT từ mỗi node đã là kết quả cuối cùng.
    Coordinator chỉ cần gộp (union) các tập kết quả.
    """
    if not os.path.exists(db_path):
        return jsonify({
            'status': 'error',
            'message': 'Database not found'
        }), 503

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Đo thời gian thực thi truy vấn SQL
        query_start = time.time()

        # Truy vấn GROUP BY sử dụng chỉ mục idx_userid
        cursor.execute('SELECT UserID, COUNT(*) FROM logs GROUP BY UserID')
        rows = cursor.fetchall()

        query_time_ms = (time.time() - query_start) * 1000

        # Tính toán tổng hợp từ kết quả GROUP BY
        unique_users = len(rows)
        total_logs = sum(row[1] for row in rows)

        # Trả về summary thay vì toàn bộ dict 200K entries
        # → Giảm kích thước response từ ~3MB xuống ~200 bytes
        return jsonify({
            'node_id': NODE_ID,
            'unique_users': unique_users,
            'total_logs': total_logs,
            'query_time_ms': round(query_time_ms, 2)
        })
    finally:
        conn.close()

@app.route('/info', methods=['GET'])
def info():
    """Trả về thông tin chi tiết của node."""
    if not os.path.exists(db_path):
        return jsonify({
            'status': 'error',
            'message': 'Database not found'
        }), 503

    row_count = get_row_count()
    db_size = os.path.getsize(db_path)

    return jsonify({
        'node_id': NODE_ID,
        'db_path': db_path,
        'row_count': row_count,
        'db_size_bytes': db_size
    })

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(f"Khởi động Node {NODE_ID} trên cổng {PORT}")
    print(f"Database: {db_path}")

    if os.path.exists(db_path):
        print(f"Trạng thái: Database tồn tại ({get_row_count():,} dòng)")
    else:
        print("Trạng thái: Database chưa được khởi tạo")

    # Chạy server Flask
    app.run(host='0.0.0.0', port=PORT, debug=False)