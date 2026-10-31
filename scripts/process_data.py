"""运行：python scripts/process_data.py；输入文件保留原样，异常值不静默删除。"""
from pathlib import Path
import hashlib
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed'
FIG = ROOT / 'reports/figures'
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)
frames, quality, summary = [], {}, []
# 以区间结束时间定义十月：00:05 起，至 11 月 1 日 00:00。
expected = pd.date_range('2026-10-01 00:05', '2026-11-01 00:00', freq='5min')
for region in ['TAS1', 'VIC1']:
    path = ROOT / 'data/raw' / f'PRICE_AND_DEMAND_202610_{region}.csv'
    df = pd.read_csv(path)
    required = ['REGION', 'SETTLEMENTDATE', 'TOTALDEMAND', 'RRP', 'PERIODTYPE']
    if list(df.columns) != required:
        raise ValueError(f'{region}: 未预期的字段 {list(df.columns)}')
    df['SETTLEMENTDATE'] = pd.to_datetime(df['SETTLEMENTDATE'], format='%Y/%m/%d %H:%M:%S', errors='raise')
    for col in ['TOTALDEMAND', 'RRP']:
        df[col] = pd.to_numeric(df[col], errors='raise')
    if df[required].isna().any().any() or not df['REGION'].eq(region).all():
        raise ValueError(f'{region}: 空值或区域错误')
    if not df['PERIODTYPE'].eq('TRADE').all():
        raise ValueError(f'{region}: 存在非 TRADE 数据，请单独检查')
    if df.duplicated(['REGION', 'SETTLEMENTDATE']).any():
        raise ValueError(f'{region}: 重复时间键，请先核查，不自动删除')
    df = df.sort_values('SETTLEMENTDATE')
    times = pd.DatetimeIndex(df['SETTLEMENTDATE'])
    quality[region] = dict(rows=len(df), first=str(times.min()), last=str(times.max()),
        missing_intervals=len(expected.difference(times)), outside_intervals=len(times.difference(expected)),
        columns=required, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if len(times.difference(expected)):
        raise ValueError(f'{region}: 时间超出预期十月区间')
    p, d = df['RRP'], df['TOTALDEMAND']
    summary.append(dict(region=region, intervals=len(df), price_mean=p.mean(), price_median=p.median(),
        price_min=p.min(), price_max=p.max(), price_std=p.std(), price_p95=p.quantile(.95),
        negative_price_pct=p.lt(0).mean()*100, demand_mean_mw=d.mean(), demand_peak_mw=d.max(),
        demand_weighted_price=(p*d).sum()/d.sum()))
    frames.append(df)
long = pd.concat(frames).sort_values(['SETTLEMENTDATE', 'REGION'])
long.to_csv(OUT / 'price_demand_clean.csv', index=False)
a, b = frames
wide = a[['SETTLEMENTDATE', 'RRP', 'TOTALDEMAND']].merge(
    b[['SETTLEMENTDATE', 'RRP', 'TOTALDEMAND']], on='SETTLEMENTDATE', how='outer',
    suffixes=('_TAS1', '_VIC1'), validate='one_to_one', indicator=True).sort_values('SETTLEMENTDATE')
quality['alignment'] = wide['_merge'].value_counts().to_dict()
wide['spread_tas_minus_vic'] = wide['RRP_TAS1'] - wide['RRP_VIC1']
wide.drop(columns='_merge').to_csv(OUT / 'tas_vic_aligned.csv', index=False)
# 区间结束时间回移 5 分钟以分配至区间所在日，避免午夜跨日错分。
wide['date'] = (wide['SETTLEMENTDATE'] - pd.Timedelta(minutes=5)).dt.floor('D')
daily = wide.groupby('date').agg(tas_price=('RRP_TAS1','mean'), vic_price=('RRP_VIC1','mean'),
    spread=('spread_tas_minus_vic','mean'), tas_demand=('TOTALDEMAND_TAS1','mean'),
    vic_demand=('TOTALDEMAND_VIC1','mean'), tas_n=('RRP_TAS1','count'), vic_n=('RRP_VIC1','count'))
daily.to_csv(OUT / 'daily_summary.csv')
pd.DataFrame(summary).to_csv(OUT / 'monthly_summary.csv', index=False)
paired = wide.dropna(subset=['RRP_TAS1','RRP_VIC1'])
s = paired['spread_tas_minus_vic']
quality['spread'] = dict(paired_intervals=len(s), mean=s.mean(), median=s.median(), min=s.min(), max=s.max(),
    tas_higher_pct=s.gt(0).mean()*100, equal_pct=s.eq(0).mean()*100)
(OUT / 'quality_report.json').write_text(json.dumps(quality, indent=2, ensure_ascii=False), encoding='utf-8')
fig, axes = plt.subplots(3, 1, figsize=(12,10), sharex=True)
axes[0].plot(daily.index, daily.tas_price, label='TAS1', color='#087f8c')
axes[0].plot(daily.index, daily.vic_price, label='VIC1', color='#db6d28')
axes[0].set_ylabel('Mean RRP (AUD/MWh)'); axes[0].legend()
axes[1].bar(daily.index, daily.spread, color=['#087f8c' if x>=0 else '#db6d28' for x in daily.spread])
axes[1].axhline(0, color='black', linewidth=.7); axes[1].set_ylabel('TAS1 - VIC1 (AUD/MWh)')
axes[2].plot(daily.index, daily.tas_demand, label='TAS1', color='#087f8c')
axes[2].plot(daily.index, daily.vic_demand, label='VIC1', color='#db6d28')
axes[2].set_ylabel('Mean demand (MW)'); axes[2].legend()
for ax in axes: ax.grid(alpha=.2)
fig.suptitle('NEM Pulse V0.2 | October 2026 | Uploaded AEMO observations')
fig.text(.05,.015,'Daily arithmetic means; interval-end timestamps shifted 5 min for day grouping. Missing intervals are not filled.',fontsize=9)
fig.autofmt_xdate(); fig.tight_layout(rect=[0,.04,1,.96])
fig.savefig(FIG / 'tas_vs_vic_oct2026.png', dpi=170)
plt.close(fig)
print(pd.DataFrame(summary).round(3).to_string(index=False))
print(json.dumps(quality, ensure_ascii=False, indent=2))
