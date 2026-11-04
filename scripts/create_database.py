from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
db_path = ROOT / 'data/nem_pulse.db'

with sqlite3.connect(db_path) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_demand (
            region TEXT NOT NULL,
            settlement_date TEXT NOT NULL,
            total_demand REAL NOT NULL,
            rrp REAL NOT NULL,
            period_type TEXT NOT NULL,
            PRIMARY KEY (region, settlement_date)
        )
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM price_demand"
    ).fetchone()[0]

print('数据库位置：', db_path)
print('当前记录数：', count)