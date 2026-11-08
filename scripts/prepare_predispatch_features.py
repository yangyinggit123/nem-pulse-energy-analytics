"""Build Aug–Sep as-of-generated-time features. Retain only the selected hourly vintage.
Generation timestamps are proxies: actual publication/receipt time is NOT verified.
"""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from collections import defaultdict
from contextlib import ExitStack
from bisect import bisect_right
import csv,zipfile,io,re,json,hashlib,sqlite3,math
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/predispatch';OUT=ROOT/'data/processed';REPORT=ROOT/'reports'
START=datetime(2026,8,1);END=datetime(2026,10,1)
REGIONS=['TAS1','VIC1']
def iso(d):return d.strftime('%Y-%m-%d %H:%M:%S')
def parse(s):return datetime.strptime(s,'%Y/%m/%d %H:%M:%S')
# Discover official weekly archives; don't mistake the date in the file for publication time.
archives=[]
for p in sorted(RAW.glob('PUBLIC_PREDISPATCHIS_*.zip')):
 dates=re.findall(r'\d{8}',p.name)
 if len(dates)==2 and dates[0]<='20260930' and dates[1]>='20260731':archives.append(p)
if len(archives)!=10:raise ValueError('Expected the 10 weekly archives covering Aug–Sep plus lead-in')
origins=[START+timedelta(hours=i) for i in range(int((END-START).total_seconds()/3600))]
with ExitStack() as stack:
 zips={p.name:stack.enter_context(zipfile.ZipFile(p)) for p in archives}
 descriptors=[];manifest=[]
 for p in archives:
  z=zips[p.name]
  for name in z.namelist():
   match=re.search(r'_(\d{14})\.zip$',name,re.I)
   if match:
    generated=datetime.strptime(match[1],'%Y%m%d%H%M%S')
    if START-timedelta(hours=2)<=generated<END:descriptors.append((iso(generated),p.name,name))
  manifest.append(dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_url='https://www.nemweb.com.au/Reports/Archive/PredispatchIS_Reports/'+p.name,report_members=len(z.namelist())))
 descriptors.sort();times=[d[0] for d in descriptors]
 forecast_rows=[];features=[];issues=[];parsed_reports=set()
 for index,origin in enumerate(origins):
  origin_text=iso(origin);j=bisect_right(times,origin_text)-1
  if j<0:raise ValueError('Missing lead-in report')
  filename_time,archive_name,name=descriptors[j]
  ends=[iso(origin+timedelta(minutes=30)),iso(origin+timedelta(hours=1))]
  prices={};solutions={};generated=None
  with zipfile.ZipFile(io.BytesIO(zips[archive_name].read(name))) as report:
   for member in report.namelist():
    if not member.lower().endswith('.csv'):continue
    headers={}
    for line in report.read(member).decode('utf-8-sig').splitlines():
     if line.startswith('C,NEMP'):
      r=next(csv.reader([line]));generated=iso(parse(r[5]+' '+r[6]))
     elif line.startswith('I,PREDISPATCH,REGION_'):
      r=next(csv.reader([line]));headers[r[2]]=r[4:]
     elif line.startswith(('D,PREDISPATCH,REGION_PRICES,','D,PREDISPATCH,REGION_SOLUTION,')):
      r=next(csv.reader([line]));h=headers.get(r[2])
      if h is None or len(h)!=len(r[4:]):raise ValueError('Changed CSV schema')
      d=dict(zip(h,r[4:]));target=iso(parse(d['DATETIME']))
      if d['REGIONID'] not in REGIONS or target not in ends or d['RUNNO']!='1' or d['INTERVENTION']!='0':continue
      key=(d['REGIONID'],target,d['PREDISPATCHSEQNO'],d['PERIODID'])
      destination=prices if r[2]=='REGION_PRICES' else solutions
      if key in destination:raise ValueError('Duplicate price/solution within report')
      destination[key]=d
  if generated!=filename_time or generated>origin_text:raise ValueError('Filename/header time mismatch or future report')
  age=(origin-datetime.strptime(generated,'%Y-%m-%d %H:%M:%S')).total_seconds()/60
  if age>60:issues.append(dict(origin=origin_text,issue='report age over 60 minutes',age_minutes=age))
  parsed_reports.add((archive_name,name))
  for region in REGIONS:
   selected=[]
   for target in ends:
    keys=[k for k in prices if k[0]==region and k[1]==target]
    if len(keys)!=1:raise ValueError(f'Incomplete target periods at {origin_text} {region}')
    key=keys[0];p=prices[key];s=solutions.get(key)
    if s is None:raise ValueError('Price without corresponding regional solution')
    row=dict(region=region,predispatchseqno=p['PREDISPATCHSEQNO'],runno=1,periodid=int(p['PERIODID']),intervention=0,interval_datetime=target,interval_start=iso(parse(p['DATETIME'])-timedelta(minutes=30)),report_generated_at=generated,rrp=float(p['RRP']),price_lastchanged=iso(parse(p['LASTCHANGED'])),source_archive=archive_name,source_report=name)
    for field,col in [('total_demand','TOTALDEMAND'),('available_generation','AVAILABLEGENERATION'),('available_load','AVAILABLELOAD'),('net_interchange','NETINTERCHANGE'),('ss_solar_uigf','SS_SOLAR_UIGF'),('ss_wind_uigf','SS_WIND_UIGF')]:
     row[field]=float(s[col]) if s[col]!='' else None
     if row[field] is not None and not math.isfinite(row[field]):raise ValueError('Nonfinite forecast input')
    if not math.isfinite(row['rrp']):raise ValueError('Invalid price')
    assert row['interval_start']>=origin_text
    selected.append(row);forecast_rows.append(row)
   if selected[0]['predispatchseqno']!=selected[1]['predispatchseqno']:raise ValueError('Mixed vintages')
   f=dict(region=region,forecast_origin=origin_text,target_hour_start=origin_text,target_hour_end=iso(origin+timedelta(hours=1)),report_generated_at=generated,forecast_age_minutes=age,predispatchseqno=selected[0]['predispatchseqno'],target_halfhour_periods=2,aemo_hour_price=(selected[0]['rrp']+selected[1]['rrp'])/2,source_archive=archive_name,source_report=name,availability_basis='generated_time_proxy_not_verified_publication')
   for field in ['total_demand','available_generation','available_load','net_interchange','ss_solar_uigf','ss_wind_uigf']:
    vals=[r[field] for r in selected];f['aemo_'+field+'_two_period_mean']=sum(vals)/2 if all(v is not None for v in vals) else None
   features.append(f)
  if (index+1)%168==0:print(f'Extracted {index+1}/{len(origins)} hourly origins',flush=True)
# Actual labels and lagged observations are kept separate from forecast feature columns.
with sqlite3.connect(ROOT/'data/nem_pulse.db') as conn:
 actual={(r,t):p for r,t,p in conn.execute("SELECT region,settlement_date,rrp FROM price_demand WHERE settlement_date>'2026-07-31 22:00:00' AND settlement_date<='2026-10-01 00:00:00'")}
 demand={(r,t):v for r,t,v in conn.execute("SELECT region,settlement_date,total_demand FROM price_demand WHERE settlement_date>'2026-07-31 22:00:00' AND settlement_date<='2026-10-01 00:00:00'")}
 for f in features:
  origin=datetime.strptime(f['forecast_origin'],'%Y-%m-%d %H:%M:%S');region=f['region']
  future=[actual.get((region,iso(origin+timedelta(minutes=5*k)))) for k in range(1,13)]
  lag=[actual.get((region,iso(origin-timedelta(minutes=5*k)))) for k in range(12)]
  lag_demand=[demand.get((region,iso(origin-timedelta(minutes=5*k)))) for k in range(12)]
  if any(v is None for v in future+lag+lag_demand):raise ValueError('Missing actual labels or lagged data')
  f['actual_hour_mean_label']=sum(future)/12
  f['previous_hour_price']=sum(lag)/12;f['previous_hour_demand_mw']=sum(lag_demand)/12
 # Preserve all previous vintages; upsert only these selected hourly rows.
 cols=list(forecast_rows[0])
 conn.executemany('INSERT OR REPLACE INTO predispatch_region_forecast ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',[tuple(r[c] for c in cols) for r in forecast_rows])
 cols=list(features[0]);text_cols={'region','forecast_origin','target_hour_start','target_hour_end','report_generated_at','predispatchseqno','source_archive','source_report','availability_basis'}
 definitions=[c+(' TEXT' if c in text_cols else ' REAL') for c in cols]
 conn.execute('CREATE TABLE IF NOT EXISTS predispatch_hourly_features ('+','.join(definitions)+',PRIMARY KEY(region,forecast_origin))')
 conn.executemany('INSERT OR REPLACE INTO predispatch_hourly_features ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',[tuple(r[c] for c in cols) for r in features])
 assert conn.execute('SELECT count(*) FROM price_demand').fetchone()[0]==210240
 assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
for filename,rows in [('predispatch_aug_sep_features.csv',features),('predispatch_aug_sep_selected_versions.csv',forecast_rows)]:
 with (OUT/filename).open('w',newline='') as file:
  w=csv.DictWriter(file,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
quality=dict(coverage_start=iso(START),coverage_end_exclusive=iso(END),days=61,archives=manifest,selected_reports=len(parsed_reports),forecast_version_rows=len(forecast_rows),hourly_feature_rows=len(features),rows_per_region={r:sum(f['region']==r for f in features) for r in REGIONS},null_features={c:sum(f[c] is None for f in features) for c in features[0]},max_report_age_minutes=max(f['forecast_age_minutes'] for f in features),stale_report_issues=issues,generated_time_is_only_proxy=True,model_retrained=False,source_actual_rows_preserved=210240,extracted_at_utc=datetime.now(timezone.utc).isoformat())
(REPORT/'predispatch_aug_sep_quality.json').write_text(json.dumps(quality,indent=2))
print(json.dumps({k:v for k,v in quality.items() if k not in ['archives','null_features']},indent=2))
