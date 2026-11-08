"""Fixed August training / September development comparison; no tuning on September."""
from pathlib import Path
import json
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed'
PARAMS = dict(learning_rate=.05, max_iter=100, max_leaf_nodes=15,
              min_samples_leaf=30, early_stopping=False, random_state=42)
base = ['price_lag_1', 'price_lag_24', 'demand_lag_1',
        'hour_sin', 'hour_cos', 'weekday_sin', 'weekday_cos']
extra = ['aemo_hour_price', 'aemo_total_demand_two_period_mean',
         'aemo_available_generation_two_period_mean', 'aemo_available_load_two_period_mean',
         'aemo_net_interchange_two_period_mean', 'aemo_ss_solar_uigf_two_period_mean',
         'aemo_ss_wind_uigf_two_period_mean']
protocol = dict(training='2026-08', development='2026-09', regions=['TAS1', 'VIC1'],
                parameters=PARAMS, historical_features=base, added_features=extra,
                independent_test=False, availability='report generation time proxy; publication unverified',
                forecast='rolling next-hour mean; prior-hour actuals assumed available at origin')
(ROOT / 'reports/augmented_forecast_protocol.json').write_text(json.dumps(protocol, indent=2))
with sqlite3.connect(ROOT / 'data/nem_pulse.db') as conn:
    actual = pd.read_sql_query('SELECT region, settlement_date, rrp, total_demand FROM price_demand ORDER BY region, settlement_date', conn)
    forecasts = pd.read_sql_query('SELECT * FROM predispatch_hourly_features', conn)
actual['hour_start'] = (pd.to_datetime(actual['settlement_date']) - pd.Timedelta(minutes=5)).dt.floor('h')
hourly = actual.groupby(['region', 'hour_start'], as_index=False).agg(price=('rrp','mean'), demand=('total_demand','mean'), n=('rrp','size'))
assert hourly['n'].eq(12).all()
forecasts['forecast_origin'] = pd.to_datetime(forecasts['forecast_origin'])
assert not forecasts.duplicated(['region', 'forecast_origin']).any()
assert (pd.to_datetime(forecasts['report_generated_at']) <= forecasts['forecast_origin']).all()
metrics, results = [], []
fig, axes = plt.subplots(2, 1, figsize=(14, 9))
for ax, region in zip(axes, ['TAS1','VIC1']):
    h = hourly[hourly.region.eq(region)].sort_values('hour_start').copy()
    assert h.hour_start.diff().dropna().eq(pd.Timedelta(hours=1)).all()
    h['price_lag_1'] = h.price.shift(1)
    h['price_lag_24'] = h.price.shift(24)
    h['demand_lag_1'] = h.demand.shift(1)
    for prefix, values, period in [('hour',h.hour_start.dt.hour,24),('weekday',h.hour_start.dt.day_of_week,7)]:
        h[prefix+'_sin'] = np.sin(2*np.pi*values/period)
        h[prefix+'_cos'] = np.cos(2*np.pi*values/period)
    d = h.merge(forecasts[forecasts.region.eq(region)], left_on=['region','hour_start'], right_on=['region','forecast_origin'], validate='one_to_one')
    assert np.allclose(d.price, d.actual_hour_mean_label)
    assert np.allclose(d.price_lag_1, d.previous_hour_price)
    assert not d[base+extra].isna().any().any()
    train = d[d.hour_start.lt('2026-09-01')]
    val = d[d.hour_start.ge('2026-09-01')].copy()
    assert len(train)==744 and len(val)==720
    val['previous_hour'] = val.price_lag_1
    val['aemo_reference'] = val.aemo_hour_price
    for name, features in [('history_tree',base),('augmented_tree',base+extra)]:
        model = HistGradientBoostingRegressor(**PARAMS)
        model.fit(train[features], train.price)
        val[name] = model.predict(val[features])
    names = ['previous_hour','aemo_reference','history_tree','augmented_tree']
    for name in names:
        err = val[name]-val.price
        metrics.append(dict(region=region,model=name,train_hours=len(train),evaluation_hours=len(val),
                            mae=err.abs().mean(),rmse=np.sqrt((err**2).mean()),
                            p95_absolute_error=err.abs().quantile(.95),max_absolute_error=err.abs().max()))
    results.append(val[['region','hour_start','price']+names].rename(columns={'price':'actual_price'}))
    week=val[val.hour_start.lt('2026-09-08')]
    for col,label in [('price','Actual'),('previous_hour','Previous hour'),('aemo_reference','AEMO reference'),('augmented_tree','Augmented tree')]:
        ax.plot(week.hour_start,week[col],label=label,linewidth=1.2)
    ax.set_title(region+' | Same 168 target hours')
    ax.set_ylabel('AUD/MWh'); ax.grid(alpha=.2); ax.legend(fontsize=8)
pd.concat(results).to_csv(OUT / 'augmented_forecast_development_predictions.csv',index=False)
m = pd.DataFrame(metrics)
m.to_csv(OUT / 'augmented_forecast_development_metrics.csv',index=False)
fig.suptitle('1–7 September 2026 | Development diagnostic, not an independent test')
fig.autofmt_xdate(); fig.tight_layout()
fig.savefig(ROOT / 'reports/figures/augmented_forecast_development.png',dpi=150)
plt.close(fig)
text = ['# Added predispatch features: development comparison', '',
        'Training: August 2026 (744 hours per region). Evaluation: September 2026 (720 hours per region).',
        'Both trees use the same training rows and fixed parameters. The historical-only tree is retrained on August for this controlled comparison; it is not the earlier longer-history model.',
        'September has been examined before. October has also already been tested. These are development results, not a new independent test.',
        'Report generation time is only a proxy for publication availability. Prior-hour actuals are assumed available at the forecast origin.', '',
        'region, model, MAE, RMSE (AUD/MWh)']
text += [f"- {r.region}, {r.model}: {r.mae:.2f}, {r.rmse:.2f}" for r in m.itertuples()]
text += ['', 'No website update or operational deployment was performed. These forecasts do not yet establish procurement savings.',
         'Next: evaluate price-error and upper-tail risk diagnostics, then build V0.5 simulated retailer portfolio exposure. V1.0 adds automated quality checks and reports.']
(ROOT / 'reports/augmented_forecast_development.md').write_text('\n'.join(text))
print(m.round(3).to_string(index=False))
