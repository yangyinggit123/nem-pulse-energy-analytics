from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import csv

ROOT = Path(__file__).resolve().parents[1]
db_path = ROOT / 'data/nem_pulse.db'

if not db_path.exists():
    raise FileNotFoundError('数据库不存在，请检查项目位置')

query = """
SELECT
    strftime(
        '%Y-%m-%d %H:00:00',
        datetime(settlement_date, '-5 minutes')
    ) AS hour_start,
    AVG(rrp) AS mean_price,
    AVG(total_demand) AS mean_demand_mw,
    COUNT(*) AS intervals
FROM price_demand
WHERE region = 'VIC1'
GROUP BY hour_start
ORDER BY hour_start;
"""

with sqlite3.connect(db_path) as conn:
    rows = conn.execute(query).fetchall()

# 检查每小时都有12条五分钟记录
if len(rows) != 8760 or any(row[3] != 12 for row in rows):
    raise ValueError('小时数量或每小时记录数不符合预期')

# 检查时间连续，并覆盖预期的一整年
start = datetime(2025, 11, 1)

for i, row in enumerate(rows):
    actual = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
    if actual != start + timedelta(hours=i):
        raise ValueError(f'时间不连续：{row[0]}')

output = ROOT / 'data/processed/vic_hourly.csv'
output.parent.mkdir(parents=True, exist_ok=True)

with output.open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'hour_start', 'mean_price',
        'mean_demand_mw', 'intervals'
    ])
    writer.writerows(rows)

print('已生成：', output)
print('小时记录数：', len(rows))
print('前3行：')
for row in rows[:3]:
    print(row)