from pathlib import Path
from datetime import datetime
import csv
import math
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
db_path = ROOT / 'data/nem_pulse.db'
files = sorted((ROOT / 'data/raw').glob('PRICE_AND_DEMAND_*.csv'))

if not db_path.exists():
    raise ValueError('请先运行 create_database.py')

if len(files) != 24:
    raise ValueError(f'应该找到24个CSV，实际找到{len(files)}个')

with sqlite3.connect(db_path) as conn:
    before = conn.execute(
        "SELECT COUNT(*) FROM price_demand"
    ).fetchone()[0]

    for path in files:
        records = []

        with path.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # 统一时间格式，方便以后用 SQL 查询
                timestamp = datetime.strptime(
                    row['SETTLEMENTDATE'],
                    '%Y/%m/%d %H:%M:%S'
                ).strftime('%Y-%m-%d %H:%M:%S')

                demand = float(row['TOTALDEMAND'])
                price = float(row['RRP'])

                if not all(math.isfinite(v) for v in [demand, price]):
                    raise ValueError(f'{path.name}：发现无效数字')

                records.append((
                    row['REGION'],
                    timestamp,
                    demand,
                    price,
                    row['PERIODTYPE']
                ))

        conn.executemany("""
            INSERT INTO price_demand (
                region, settlement_date, total_demand,
                rrp, period_type
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(region, settlement_date) DO UPDATE SET
                total_demand = excluded.total_demand,
                rrp = excluded.rrp,
                period_type = excluded.period_type
        """, records)

        print('已处理：', path.name, '记录数：', len(records))

    after = conn.execute(
        "SELECT COUNT(*) FROM price_demand"
    ).fetchone()[0]

    if after != 210240:
        raise ValueError(f'总记录数不符合预期：{after}')

print('导入完成')
print('新增记录数：', after - before)
print('数据库总记录数：', after)