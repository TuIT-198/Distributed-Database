import csv
import random
from datetime import datetime, timedelta

NUM_ROWS = 1_000_000
START_DATE = datetime(2024, 1, 1)

def random_timestamp():
    return START_DATE + timedelta(seconds=random.randint(0, 31_536_000))

with open('user_logs.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['LogID', 'UserID', 'Action', 'Timestamp'])
    for i in range(1, NUM_ROWS+1):
        user_id = random.randint(1, 200_000)
        action = random.choice(['login','logout','click','purchase','view'])
        ts = random_timestamp()
        writer.writerow([i, user_id, action, ts])
print("Generated user_logs.csv")