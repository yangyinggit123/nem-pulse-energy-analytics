"""Build monthly checkpoints and validate the full year; safely resume after downloads."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import csv,json,re,sqlite3,subprocess,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/predispatch';OUT=ROOT/'data/processed';REPORT=ROOT/'reports'
plan=json.loads((ROOT/'data/predispatch_year_download_plan.json').read_text())
months=[f'2025-{m:02d}' for m in (11,12)]+[f'2026-{m:02d}' for m in range(1,11)]
for month in months:
 start=datetime.strptime(month,'%Y-%m');end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
 needed=[r for r in plan if re.findall(r'\d{8}',r['file'])[0]<=(end-timedelta(days=1)).strftime('%Y%m%d') and re.findall(r'\d{8}',r['file'])[1]>=(start-timedelta(days=1)).strftime('%Y%m%d')]
 feature=OUT/f'predispatch_{month}_features.csv';quality=REPORT/f'predispatch_{month}_quality.json'
 if feature.exists() and quality.exists():
  q=json.loads(quality.read_text())
  if q.get('hourly_feature_rows')==int((end-start).total_seconds()/3600)*2:
   print('Reusing validated monthly checkpoint',month,flush=True);continue
 print('Waiting for archives:',month,flush=True)
 deadline=time.monotonic()+10800
 while not all((RAW/r['file']).exists() and (RAW/r['file']).stat().st_size==r['bytes'] for r in needed):
  if time.monotonic()>deadline:raise TimeoutError('Downloads not ready for '+month)
  time.sleep(5)
 print('Building',month,flush=True)
 subprocess.run([sys.executable,str(ROOT/'scripts/prepare_predispatch_year_month.py'),'--month',month],check=True)
# Export exactly the intended year, preserving existing shorter experiments.
with sqlite3.connect(ROOT/'data/nem_pulse.db') as conn:
 conn.row_factory=sqlite3.Row
 rows=[dict(r) for r in conn.execute("SELECT * FROM predispatch_hourly_features WHERE forecast_origin>='2025-11-01 00:00:00' AND forecast_origin<'2026-11-01 00:00:00' ORDER BY forecast_origin,region")]
 assert len(rows)==17520,len(rows)
 for region in ('TAS1','VIC1'):
  r=[x for x in rows if x['region']==region]
  assert len(r)==8760
  times=[datetime.fromisoformat(x['forecast_origin']) for x in r]
  assert times[0]==datetime(2025,11,1) and times[-1]==datetime(2026,10,31,23)
  assert all(b-a==timedelta(hours=1) for a,b in zip(times,times[1:]))
  assert all(x['report_generated_at']<=x['forecast_origin'] and x['target_halfhour_periods']==2 for x in r)
 nulls={k:sum(x[k] is None for x in rows) for k in rows[0]}
 assert nulls['previous_hour_price']==2 and nulls['previous_hour_demand_mw']==2
 assert all(v==0 for k,v in nulls.items() if k not in ('previous_hour_price','previous_hour_demand_mw')),nulls
 assert conn.execute('SELECT COUNT(*) FROM price_demand').fetchone()[0]==210240
 assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 conn.execute('CREATE INDEX IF NOT EXISTS idx_predispatch_hourly_origin ON predispatch_hourly_features(forecast_origin,region)')
 conn.execute('CREATE VIEW IF NOT EXISTS predispatch_hourly_model_input AS SELECT * FROM predispatch_hourly_features WHERE forecast_age_minutes<=60 AND previous_hour_price IS NOT NULL AND previous_hour_demand_mw IS NOT NULL')
 eligible=conn.execute('SELECT count(*) FROM predispatch_hourly_model_input').fetchone()[0]
 assert eligible==17514,eligible
with (OUT/'predispatch_year_features.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
monthly=[json.loads((REPORT/f'predispatch_{m}_quality.json').read_text()) for m in months]
quality=dict(start='2025-11-01 00:00:00',end_exclusive='2026-11-01 00:00:00',days=365,hourly_rows=len(rows),rows_per_region={'TAS1':8760,'VIC1':8760},selected_halfhour_rows=sum(q['forecast_version_rows'] for q in monthly),null_features=nulls,missing_previous_hour_explanation='The first historical hour has no preceding observations; both lag columns are NULL for each region. Do not fill with future data.',max_report_age_minutes=max(x['forecast_age_minutes'] for x in rows),stale_report_issues=[i for q in monthly for i in q['stale_report_issues']],actual_rows_preserved=210240,report_generated_time_only_proxy=True,model_retrained=False,validated_at_utc=datetime.now(timezone.utc).isoformat())
quality.update(default_model_input_rows=eligible,default_model_input_view='predispatch_hourly_model_input',default_model_input_rule='Exclude report age >60 minutes and first-hour missing historical lags; threshold is a project convention, not an AEMO standard.')
(REPORT/'predispatch_year_quality.json').write_text(json.dumps(quality,indent=2))
print('YEAR COMPLETE',json.dumps(quality),flush=True)
