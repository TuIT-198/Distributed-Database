"""
Coordinator - Điều phối truy vấn đến các node và gộp kết quả.

Phân phối truy vấn song song đến các node shard, gộp kết quả,
và trả về thống kê tổng hợp. Hỗ trợ xử lý lỗi từng phần khi
một hoặc nhiều node không phản hồi.
"""

import os
import sys
import time
import json
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, jsonify
import requests

# === Cấu hình ===
DEFAULT_TIMEOUT = 10  # Thời gian chờ tối đa cho mỗi node (giây)

app = Flask(__name__)

# Biến toàn cục lưu danh sách node URLs
node_urls = []


def parse_args():
    """Phân tích tham số dòng lệnh."""
    parser = argparse.ArgumentParser(description="Coordinator cho hệ thống phân tán")
    parser.add_argument(
        "--nodes",
        type=str,
        default=None,
        help="Danh sách URL các node, phân tách bằng dấu phẩy (ghi đè biến môi trường NODES)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port cho coordinator (mặc định: 8000)",
    )
    return parser.parse_args()


def get_node_urls(cli_nodes=None):
    """Lấy danh sách URL node từ CLI arg hoặc biến môi trường."""
    if cli_nodes:
        raw = cli_nodes
    else:
        raw = os.environ.get("NODES", "http://localhost:5000")

    urls = [u.strip() for u in raw.split(",") if u.strip()]
    return urls


def query_single_node(url):
    """
    Gửi truy vấn đến một node và đo thời gian phản hồi.
    Node trả về summary: {node_id, unique_users, total_logs, query_time_ms}
    """
    start = time.time()
    try:
        resp = requests.post(f"{url}/query", timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        elapsed_ms = (time.time() - start) * 1000
        data = resp.json()
        return (url, data, elapsed_ms, None)
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        return (url, None, elapsed_ms, str(e))


@app.route("/aggregate", methods=["GET"])
def aggregate():
    """
    Endpoint tổng hợp: gửi truy vấn song song đến tất cả node,
    gộp kết quả summary và trả về thống kê tổng hợp.
    """
    total_start = time.time()

    nodes_total = len(node_urls)
    node_results = []
    node_times_ms = []
    query_times_ms = []
    failed_nodes = []

    # Gửi truy vấn song song đến các node
    with ThreadPoolExecutor(max_workers=nodes_total) as executor:
        futures = {
            executor.submit(query_single_node, url): url for url in node_urls
        }
        for future in as_completed(futures):
            url, data, elapsed_ms, error = future.result()
            node_times_ms.append(elapsed_ms)
            if error is None and data is not None:
                node_results.append(data)
                # Ghi nhận thời gian query SQL thực tế trên node
                query_times_ms.append(data.get('query_time_ms', 0))
            else:
                failed_nodes.append({"url": url, "error": error})

    # Đo thời gian gộp kết quả
    merge_start = time.time()

    # Gộp kết quả summary từ các node
    # Do hash-based sharding, mỗi UserID chỉ trên 1 node
    # → unique_users tổng = tổng unique_users từ mỗi node
    # → total_logs tổng = tổng total_logs từ mỗi node
    total_unique_users = sum(r.get('unique_users', 0) for r in node_results)
    total_logs = sum(r.get('total_logs', 0) for r in node_results)

    merge_time_ms = (time.time() - merge_start) * 1000
    execution_time_ms = (time.time() - total_start) * 1000

    # Xác định trạng thái
    nodes_responded = len(node_results)
    status = "success" if nodes_responded == nodes_total else "partial"

    return jsonify({
        "status": status,
        "nodes_total": nodes_total,
        "nodes_responded": nodes_responded,
        "unique_users": total_unique_users,
        "total_logs": total_logs,
        "execution_time_ms": round(execution_time_ms, 2),
        "node_times_ms": [round(t, 2) for t in node_times_ms],
        "query_times_ms": [round(t, 2) for t in query_times_ms],
        "merge_time_ms": round(merge_time_ms, 2),
    })


@app.route("/health", methods=["GET"])
def health():
    """Endpoint kiểm tra sức khỏe coordinator và tất cả node."""
    nodes_status = []

    for url in node_urls:
        try:
            resp = requests.get(f"{url}/health", timeout=5)
            resp.raise_for_status()
            info = resp.json()
            nodes_status.append({
                "url": url,
                "status": "ok",
                "row_count": info.get("row_count"),
            })
        except Exception:
            nodes_status.append({
                "url": url,
                "status": "down",
                "row_count": None,
            })

    return jsonify({
        "coordinator": "ok",
        "nodes": nodes_status,
    })


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    args = parse_args()

    # Lấy danh sách node URLs
    node_urls = get_node_urls(cli_nodes=args.nodes)

    # Xác định port
    port = args.port or int(os.environ.get("PORT", 8000))

    # Tắt cảnh báo Flask dev server
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    print(f"[Coordinator] Khởi động trên port {port}")
    print(f"[Coordinator] Các node: {node_urls}")

    app.run(host="0.0.0.0", port=port)