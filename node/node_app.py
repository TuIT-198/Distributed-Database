import sqlite3
import os
from flask import Flask, request, jsonify

node_id = os.environ.get('NODE_ID', '0')
db_path = f'node_{node_id}.db'

app = Flask(__name__)

def get_count_groupby():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT UserID, COUNT(*) FROM logs GROUP BY UserID')
    rows = cur.fetchall()
    conn.close()
    return dict(rows)   # { user_id: count }

@app.route('/query', methods=['POST'])
def handle_query():
    # Ở đây ta cứng nhắc query COUNT GROUP BY theo yêu cầu đề bài
    # Có thể mở rộng nhận SQL nhưng đơn giản là trả về dict
    result = get_count_groupby()
    return jsonify(result)

if __name__ == '__main__':
    port = 5000 + int(node_id)
    app.run(host='0.0.0.0', port=port)