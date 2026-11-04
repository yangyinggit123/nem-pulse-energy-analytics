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

# 标准化和模型都只在训练集上拟合
model = make_pipeline(
    StandardScaler(),
    Ridge(alpha=1.0)
)

model.fit(train[features], train['mean_price'])

predictions = model.predict(validation[features])
actual = validation['mean_price']

model_mae = mean_absolute_error(actual, predictions)
baseline_mae = mean_absolute_error(
    actual, validation['price_lag_1']
)

print('训练小时数：', len(train))
print('验证小时数：', len(validation))
print('上一小时基准 MAE：', round(baseline_mae, 2))
print('Ridge 模型 MAE：', round(model_mae, 2))
print('误差单位：AUD/MWh')
improvement = (baseline_mae - model_mae) / baseline_mae * 100
print('相对基准误差降低：', round(improvement, 2), '%')
print('如果为负数，说明模型比基准更差。')

result = validation[['hour_start', 'mean_price']].copy()
result = result.rename(columns={'mean_price': 'actual_price'})
result['baseline_prediction'] = validation['price_lag_1']
result['model_prediction'] = predictions

# 分别计算模型和基准的绝对误差
result['model_error'] = (
    result['model_prediction'] - result['actual_price']
).abs()

result['baseline_error'] = (
    result['baseline_prediction'] - result['actual_price']
).abs()

# 按模型误差从大到小排列
worst = result.nlargest(10, 'model_error')

print('\nRidge误差最大的十个小时：')
print(worst.to_string(index=False, float_format=lambda value: f'{value:.2f}'))

# 保存误差明细
result.to_csv(
    ROOT / 'data/processed/vic_ridge_validation.csv',
    index=False
)