"""Download the 24 official input files and verify their recorded SHA-256 hashes."""
from pathlib import Path
import csv, hashlib, urllib.request
ROOT = Path(__file__).resolve().parents[1]
raw = ROOT / 'data/raw'
raw.mkdir(parents=True, exist_ok=True)
with (ROOT / 'data/download_manifest.csv').open() as f:
    manifest = list(csv.DictReader(f))
for row in manifest:
    target = raw / row['file']
    if target.exists():
        content = target.read_bytes()
        if hashlib.sha256(content).hexdigest() == row['sha256']:
            print('Verified existing:', target.name)
            continue
        raise ValueError(f'{target.name}: existing file differs; review before replacing')
    with urllib.request.urlopen(row['source_url'], timeout=60) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != row['sha256']:
        raise ValueError(f'{target.name}: official version changed; review the manifest before importing')
    target.write_bytes(content)
    print('Downloaded and verified:', target.name)
