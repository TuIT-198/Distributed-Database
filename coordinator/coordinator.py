from flask import Flask, request, jsonify
import requests
import threading
import time

app = Flask(__name__)

NODES = [
    'http://localhost:5000/query',
    'http://localhost:5001/query',
    'http://localhost:5002/query',
    'http://localhost:5003/query'
]
TIMEOUT = 5  # seconds

def query_node(url, results, idx):
    try:
        resp = requests.post(url, json={}, timeout=TIMEOUT)
        if resp.status_code == 200:
            results[idx] = resp.json()
        else:
            results[idx] = {}
    except Exception as e:
        print(f"Node {idx} failed: {e}")
        results[idx] = {}

@app.route('/aggregate', methods=['GET'])
def aggregate():
    start_time = time.time()
    results = [None] * len(NODES)
    threads = []
    for i, url in enumerate(NODES):
        t = threading.Thread(target=query_node, args=(url, results, i))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    
    # Merge kết quả: cộng dồn count theo UserID
    merged = {}
    for r in results:
        if r:
            for uid, cnt in r.items():
                merged[uid] = merged.get(uid, 0) + cnt
    elapsed = time.time() - start_time
    return jsonify({
        'status': 'success',
        'result_size': len(merged),
        'execution_time_seconds': elapsed,
        'data': merged   # có thể bỏ data nếu quá lớn
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)