from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]

df = pd.read_csv(
    ROOT / 'data/processed/vic_ridge_validation.csv',
    parse_dates=['hour_start']
)

# 展示九月第一周，不用于重新选择验证集
week = df[
    (df['hour_start'] >= '2026-09-01')
    & (df['hour_start'] < '2026-09-08')
].sort_values('hour_start')

fig, ax = plt.subplots(figsize=(13, 5))

ax.plot(
    week['hour_start'], week['actual_price'],
    label='Actual', color='black', linewidth=2
)

ax.plot(
    week['hour_start'], week['baseline_prediction'],
    label='Previous-hour baseline',
    color='#087f8c', linestyle='--', alpha=0.8
)

ax.plot(
    week['hour_start'], week['model_prediction'],
    label='Ridge prediction',
    color='#db6d28', alpha=0.8
)

ax.set_title('VIC1 | Next-hour forecasts | 1–7 September 2026')
ax.set_ylabel('Hourly mean price (AUD/MWh)')
ax.set_xlabel('Target hour starting — NEM time (AEST)')
ax.axhline(0, color='gray', linewidth=0.7)
ax.legend()
ax.grid(alpha=0.2)

fig.autofmt_xdate()
fig.tight_layout()

output = ROOT / 'reports/figures/vic_forecast_comparison.png'
output.parent.mkdir(parents=True, exist_ok=True)

fig.savefig(output, dpi=160)
plt.close(fig)

print('图片已保存：', output)