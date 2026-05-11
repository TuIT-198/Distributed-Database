import csv
import os

NUM_NODES = 4
INPUT = 'user_logs.csv'
OUT_DIR = 'shards'
os.makedirs(OUT_DIR, exist_ok=True)

# Mở file writers
writers = {}
for n in range(NUM_NODES):
    f = open(f'{OUT_DIR}/node_{n}.csv', 'w', newline='')
    writer = csv.writer(f)
    writer.writerow(['LogID','UserID','Action','Timestamp'])
    writers[n] = f, writer

with open(INPUT, 'r') as infile:
    reader = csv.reader(infile)
    next(reader)  # skip header
    for row in reader:
        log_id, user_id, action, ts = row
        node_id = int(user_id) % NUM_NODES
        writers[node_id][1].writerow(row)

for f, _ in writers.values():
    f.close()
print("Sharding done. Check shards/ folder.")