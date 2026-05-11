import csv
import sqlite3
import sys

node_id = int(sys.argv[1])  # 0,1,2,3
csv_path = f'../data/shards/node_{node_id}.csv'
db_path = f'node_{node_id}.db'

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute('DROP TABLE IF EXISTS logs')
cur.execute('''
    CREATE TABLE logs (
        LogID INTEGER,
        UserID INTEGER,
        Action TEXT,
        Timestamp TEXT
    )
''')
with open(csv_path, 'r') as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    for row in reader:
        cur.execute('INSERT INTO logs VALUES (?,?,?,?)', row)
conn.commit()
conn.close()
print(f'Node {node_id} database created with {cur.rowcount} rows')