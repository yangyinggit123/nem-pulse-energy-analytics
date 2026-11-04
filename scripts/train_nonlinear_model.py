from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

ROOT = Path(__file__).resolve().parents[1]

df = pd.read_csv(
    ROOT / 'data/processed/vic_hourly.csv',
    parse_dates=['hour_start']
).sort_values('hour_start')

if len(df) != 8760 or df['hour_start'].duplicated().any() or not df['hour_start'].diff().dropna().eq(pd.Timedelta(hours=1)).all():
    raise ValueError('输入小时数据不完整或时间不连续')

# 每一行要预测的是这一小时的平均电价
# shift：取之前已发生的数据，不使用未来实际值
df['price_lag_1'] = df['mean_price'].shift(1)
df['price_lag_24'] = df['mean_price'].shift(24)
df['demand_lag_1'] = df['mean_demand_mw'].shift(1)

# 用正弦、余弦表示小时，让23点与0点在模型里相邻
hour = df['hour_start'].dt.hour
df['hour_sin'] = np.sin(2 * np.pi * hour / 24)
df['hour_cos'] = np.cos(2 * np.pi * hour / 24)

# 星期几同样按周期表示
weekday = df['hour_start'].dt.day_of_week
df['weekday_sin'] = np.sin(2 * np.pi * weekday / 7)
df['weekday_cos'] = np.cos(2 * np.pi * weekday / 7)

features = [
    'price_lag_1',
    'price_lag_24',
    'demand_lag_1',
    'hour_sin',
    'hour_cos',
    'weekday_sin',
    'weekday_cos'
]

df = df.dropna(subset=features).copy()

# 训练：2025年11月至2026年8月
train = df[
    df['hour_start'] < '2026-09-01'
].copy()

# 验证：2026年9月
validation = df[
    (df['hour_start'] >= '2026-09-01')
    & (df['hour_start'] < '2026-10-01')
].copy()

if len(validation) != 720:
    raise ValueError('九月验证集应该有720行')

# 首次非线性实验：预先固定参数，不用九月反复调参。
# 关闭自动早停，避免在训练期内部随机切分时间数据。
from sklearn.ensemble import HistGradientBoostingRegressor

nonlinear = HistGradientBoostingRegressor(
    loss='squared_error',
    learning_rate=0.05,
    max_iter=100,
    max_leaf_nodes=15,
    min_samples_leaf=30,
    early_stopping=False,
    random_state=42
)

ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
ridge.fit(train[features], train['mean_price'])
nonlinear.fit(train[features], train['mean_price'])

actual = validation['mean_price']
result = validation[['hour_start', 'mean_price']].copy()
result = result.rename(columns={'mean_price': 'actual_price'})
result['baseline_prediction'] = validation['price_lag_1']
result['ridge_prediction'] = ridge.predict(validation[features])
result['nonlinear_prediction'] = nonlinear.predict(validation[features])

metrics = []
for label, column in [
    ('Previous-hour baseline', 'baseline_prediction'),
    ('Ridge', 'ridge_prediction'),
    ('Gradient boosting trees', 'nonlinear_prediction')
]:
    error = mean_absolute_error(actual, result[column])
    metrics.append({'model': label, 'validation_mae': error})
    result[column + '_absolute_error'] = (result[column] - actual).abs()

print('训练小时数：', len(train))
print('验证小时数：', len(validation))
print('验证集：2026年9月；十月测试集未评估')
print(pd.DataFrame(metrics).to_string(index=False, float_format=lambda x: f'{x:.2f}'))
baseline_mae = metrics[0]['validation_mae']
nonlinear_mae = metrics[2]['validation_mae']
print('非线性模型相对基准误差降低：', round((baseline_mae - nonlinear_mae) / baseline_mae * 100, 2), '%')

output = ROOT / 'data/processed'
result.to_csv(output / 'vic_nonlinear_validation.csv', index=False)
pd.DataFrame(metrics).to_csv(output / 'vic_model_comparison.csv', index=False)

# 与之前相同的一周，仅用于观察预测走势。
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
week = result[(result['hour_start'] >= '2026-09-01') & (result['hour_start'] < '2026-09-08')]
fig, ax = plt.subplots(figsize=(13, 5))
for col, label, color, style in [
    ('actual_price', 'Actual', 'black', '-'),
    ('baseline_prediction', 'Previous-hour baseline', '#087f8c', '--'),
    ('nonlinear_prediction', 'Gradient boosting trees', '#a846b5', '-')
]:
    ax.plot(week['hour_start'], week[col], label=label, color=color, linestyle=style)
ax.set_title('VIC1 | Next-hour rolling forecasts | 1–7 September 2026')
ax.set_ylabel('Hourly mean price (AUD/MWh)')
ax.set_xlabel('Target hour starting — NEM time (AEST)')
ax.axhline(0, color='gray', linewidth=.7)
ax.legend()
ax.grid(alpha=.2)
fig.autofmt_xdate()
fig.tight_layout()
fig_path = ROOT / 'reports/figures/vic_nonlinear_comparison.png'
fig_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(fig_path, dpi=160)
plt.close(fig)
print('对比图已保存：', fig_path)
