from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]

with (ROOT / 'data/processed/vic_hourly.csv').open() as f:
    rows = list(csv.DictReader(f))

results = []

for i in range(1, len(rows)):
    current = rows[i]
    previous = rows[i - 1]

    # 只评估九月：按被预测小时的日期选择
    if not current['hour_start'].startswith('2026-09'):
        continue

    predicted = float(previous['mean_price'])
    actual = float(current['mean_price'])

    results.append({
        'target_hour': current['hour_start'],
        'predicted_price': predicted,
        'actual_price': actual,
        'absolute_error': abs(predicted - actual)
    })

if len(results) != 720:
    raise ValueError('九月应该有720个小时，请检查输入')

mae = sum(r['absolute_error'] for r in results) / len(results)

output = ROOT / 'data/processed/vic_baseline_validation.csv'

with output.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)

print('验证月份：2026年9月')
print('预测小时数：', len(results))
print('MAE：', round(mae, 2), 'AUD/MWh')
print('结果已保存：', output)
# 第二个基准：使用昨天同一小时的均价
daily_errors = []

for i in range(24, len(rows)):
    current = rows[i]

    if not current['hour_start'].startswith('2026-09'):
        continue

    predicted = float(rows[i - 24]['mean_price'])
    actual = float(current['mean_price'])

    daily_errors.append(abs(predicted - actual))

if len(daily_errors) != 720:
    raise ValueError('九月应该有720条预测')

daily_mae = sum(daily_errors) / len(daily_errors)

print()
print('两个基准在九月的比较：')
print('上一小时基准 MAE：', round(mae, 2), 'AUD/MWh')
print('昨天同小时基准 MAE：', round(daily_mae, 2), 'AUD/MWh')