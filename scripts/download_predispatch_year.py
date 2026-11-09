"""Download official weekly archives from a saved official-directory manifest.
Raw ZIPs remain local. Existing valid downloads are reused; no arbitrary extraction.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/predispatch';RAW.mkdir(parents=True,exist_ok=True)
plan=json.loads((ROOT/'data/predispatch_year_download_plan.json').read_text())
def fetch(row):
 name=row['file'];dest=RAW/name
 if not (dest.exists() and dest.stat().st_size==row['bytes'] and zipfile.is_zipfile(dest)):
  temp=dest.with_suffix('.download')
  subprocess.run(['curl','--http1.1','-fsSL','--retry','4','--connect-timeout','30','--max-time','600',row['source_url'],'-o',str(temp)],check=True)
  if temp.stat().st_size!=row['bytes'] or not zipfile.is_zipfile(temp):raise ValueError('Invalid download '+name)
  temp.replace(dest)
 digest=hashlib.sha256()
 with dest.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):digest.update(chunk)
 return {**row,'sha256':digest.hexdigest()}
results=[];errors=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 jobs={pool.submit(fetch,row):row for row in plan}
 for job in as_completed(jobs):
  try:r=job.result()
  except Exception as e:
   errors.append({'file':jobs[job]['file'],'error':str(e)});print('DOWNLOAD FAILED',errors[-1],flush=True);continue
  results.append(r)
  print(f"Verified {len(results)}/{len(plan)}: {r['file']}",flush=True)
  (ROOT/'data/predispatch_year_download_manifest.partial.json').write_text(json.dumps(sorted(results,key=lambda x:x['file']),indent=2))
if errors:
 (ROOT/'reports/predispatch_year_download_errors.json').write_text(json.dumps(errors,indent=2))
 raise RuntimeError('Some archives failed; rerun downloader to reuse completed files')
(ROOT/'data/predispatch_year_download_manifest.json').write_text(json.dumps(sorted(results,key=lambda x:x['file']),indent=2))
print('All archives verified',flush=True)
