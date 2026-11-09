"""Expanding-window, monthly-frozen models. Retrospective development, not a fresh test.
Raw targets remain in chronological order; lag features precede quality filtering.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,sqlite3,hashlib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed';REPORT=ROOT/'reports';FIG=REPORT/'figures'
PARAMS=dict(learning_rate=.05,max_iter=100,max_leaf_nodes=15,min_samples_leaf=30,early_stopping=False,random_state=42)
BASE=['price_lag_1','price_lag_24','demand_lag_1','hour_sin','hour_cos','weekday_sin','weekday_cos']
EXTRA=['aemo_hour_price','aemo_total_demand_two_period_mean','aemo_available_generation_two_period_mean','aemo_available_load_two_period_mean','aemo_net_interchange_two_period_mean','aemo_ss_solar_uigf_two_period_mean','aemo_ss_wind_uigf_two_period_mean']
MONTHS=['2026-08','2026-09','2026-10']
LABELS={'previous_hour':'Previous-hour baseline','aemo_reference':'AEMO reference','history_tree':'History-only tree','augmented_tree':'Tree + AEMO features'}
protocol=dict(data_start='2025-11-01',data_end_exclusive='2026-11-01',evaluation_months=MONTHS,training_rule='All eligible earlier months; refit once before each evaluation month; freeze throughout month',parameters=PARAMS,base_features=BASE,added_features=EXTRA,quality_rule='Exclude reports older than 60 minutes and missing lag features; all methods evaluated on identical remaining targets',independent_test=False,availability='Generated-time proxy; publication unverified; completed-hour actuals assumed available at origin',high_price_threshold_aud_mwh=300,created_at_utc=datetime.now(timezone.utc).isoformat())
protocol['input_sha256']=hashlib.sha256((OUT/'predispatch_year_features.csv').read_bytes()).hexdigest()
(REPORT/'year_forecast_protocol.json').write_text(json.dumps(protocol,indent=2))
with sqlite3.connect(ROOT/'data/nem_pulse.db') as conn:
 actual=pd.read_sql_query('SELECT region,settlement_date,rrp,total_demand FROM price_demand ORDER BY region,settlement_date',conn)
 forecasts=pd.read_sql_query('SELECT * FROM predispatch_hourly_features',conn)
actual['hour_start']=(pd.to_datetime(actual.settlement_date)-pd.Timedelta(minutes=5)).dt.floor('h')
hourly=actual.groupby(['region','hour_start'],as_index=False).agg(price=('rrp','mean'),demand=('total_demand','mean'),n=('rrp','size'))
assert len(hourly)==17520 and hourly.n.eq(12).all()
forecasts['forecast_origin']=pd.to_datetime(forecasts.forecast_origin)
assert len(forecasts)==17520 and not forecasts.duplicated(['region','forecast_origin']).any()
assert (pd.to_datetime(forecasts.report_generated_at)<=forecasts.forecast_origin).all()
metrics=[];results=[];quality=[]
for region in ['TAS1','VIC1']:
 h=hourly[hourly.region.eq(region)].sort_values('hour_start').copy()
 assert h.hour_start.diff().dropna().eq(pd.Timedelta(hours=1)).all()
 h['price_lag_1']=h.price.shift(1);h['price_lag_24']=h.price.shift(24);h['demand_lag_1']=h.demand.shift(1)
 for prefix,v,period in [('hour',h.hour_start.dt.hour,24),('weekday',h.hour_start.dt.day_of_week,7)]:
  h[prefix+'_sin']=np.sin(2*np.pi*v/period);h[prefix+'_cos']=np.cos(2*np.pi*v/period)
 d=h.merge(forecasts[forecasts.region.eq(region)],left_on=['region','hour_start'],right_on=['region','forecast_origin'],validate='one_to_one')
 assert np.allclose(d.price,d.actual_hour_mean_label)
 lag=d.previous_hour_price.notna();assert np.allclose(d.loc[lag,'price_lag_1'],d.loc[lag,'previous_hour_price'])
 valid=d.forecast_age_minutes.le(60)&d[BASE+EXTRA].notna().all(axis=1)
 assert np.isfinite(d.loc[valid,BASE+EXTRA].to_numpy()).all()
 for month in MONTHS:
  start=pd.Timestamp(month+'-01');end=start+pd.offsets.MonthBegin(1)
  train=d[valid & d.hour_start.lt(start)].copy();val=d[valid & d.hour_start.ge(start)&d.hour_start.lt(end)].copy()
  assert train.hour_start.max()<val.hour_start.min()
  expected=int((end-start).total_seconds()/3600);assert len(val)==expected
  val['previous_hour']=val.price_lag_1;val['aemo_reference']=val.aemo_hour_price
  for name,features in [('history_tree',BASE),('augmented_tree',BASE+EXTRA)]:
   model=HistGradientBoostingRegressor(**PARAMS);model.fit(train[features],train.price);val[name]=model.predict(val[features])
  for name in LABELS:
   err=val[name]-val.price;high=val.price.gt(300)
   metrics.append(dict(region=region,month=month,model=name,train_hours=len(train),evaluation_hours=len(val),mae=err.abs().mean(),rmse=np.sqrt((err**2).mean()),p95_absolute_error=err.abs().quantile(.95),max_absolute_error=err.abs().max(),high_price_hours=int(high.sum()),high_price_mae=float(err[high].abs().mean()) if high.any() else None))
  results.append(val[['region','hour_start','price']+list(LABELS)].rename(columns={'price':'actual_price'}).assign(month=month))
  quality.append(dict(region=region,month=month,train_hours=len(train),train_first=str(train.hour_start.min()),train_last=str(train.hour_start.max()),evaluation_hours=len(val)))
  print('Completed',region,month,'train',len(train),'evaluate',len(val),flush=True)
pred=pd.concat(results,ignore_index=True);m=pd.DataFrame(metrics)
assert len(pred)==4416 and not pred.duplicated(['region','hour_start']).any()
pred.to_csv(OUT/'year_forecast_predictions.csv',index=False);m.to_csv(OUT/'year_forecast_metrics.csv',index=False)
# Compact, directly generated website payload; retain full precision in CSVs.
web=dict(protocol=protocol,splits=quality,metrics=json.loads(m.to_json(orient='records',double_precision=8)),predictions=json.loads(pred.assign(hour_start=pred.hour_start.dt.strftime('%Y-%m-%d %H:%M:%S')).to_json(orient='records',double_precision=5)))
(OUT/'year_forecast_web.json').write_text(json.dumps(web,separators=(',',':'),allow_nan=False))
fig,axes=plt.subplots(2,1,figsize=(14,9))
for ax,region in zip(axes,['TAS1','VIC1']):
 week=pred[pred.region.eq(region)&pred.hour_start.ge('2026-10-01')&pred.hour_start.lt('2026-10-08')]
 for col,color in [('actual_price','#111111'),('previous_hour','#087f8c'),('aemo_reference','#e47f17'),('augmented_tree','#a846b5')]:
  ax.plot(week.hour_start,week[col],label='Actual' if col=='actual_price' else LABELS[col],color=color,linewidth=1.2)
 ax.set_title(region+' | Frozen model trained through September');ax.set_ylabel('AUD/MWh');ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('1–7 October 2026 | Retrospective evaluation; no independent test claim')
fig.autofmt_xdate();fig.tight_layout();fig.savefig(FIG/'year_forecast_october.png',dpi=150);plt.close(fig)
lines=['# Expanded-history forecast evaluation','',
 'Data: November 2025–October 2026. Monthly-frozen models trained on eligible earlier months only; August, September and October evaluated separately.',
 'Earlier experiments already examined these periods. This is retrospective development evaluation, not a new independent test. Parameters were fixed before this run and not selected using these results.',
 'The models do not train on all twelve months and then score those same months. October models train through September. No final production model is fitted through October.',
 'Both trees use identical training targets. Excluded from training: first 24 hours for lag-24 construction and two stale-report origins per region in March. Completed-hour actual availability and generated-time proxies remain limitations.','',
 '| Region | Month | Training hours | Baseline MAE | AEMO MAE | History tree MAE | Augmented tree MAE |','|---|---|---:|---:|---:|---:|---:|']
for row in quality:
 vals=m[m.region.eq(row['region'])&m.month.eq(row['month'])].set_index('model').mae
 lines.append(f"| {row['region']} | {row['month']} | {row['train_hours']} | {vals['previous_hour']:.2f} | {vals['aemo_reference']:.2f} | {vals['history_tree']:.2f} | {vals['augmented_tree']:.2f} |")
lines+=['','All errors are AUD/MWh. Hourly averaging hides five-minute spikes. High-price hours use an illustrative actual hourly mean >300 AUD/MWh threshold; small counts do not establish reliable tail forecasting.',
 'These are point forecasts. Earlier interval estimates are not automatically transferable to this refitted model. Procurement savings, hedging benefits and risk alerts have not been validated.',
 'V0.5 will add simulated retailer customer loads and unhedged cost exposure. V1.0 will automate data quality checks and reporting.']
(REPORT/'year_forecast_report.md').write_text('\n'.join(lines))
print(m[['region','month','model','mae','rmse','high_price_hours','high_price_mae']].round(3).to_string(index=False))
