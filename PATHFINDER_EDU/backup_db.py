"""Manual, consistent SQLite backup for Render persistent disk (no public endpoint).
Run from Render Shell: python backup_db.py
Backup is placed under PF_DATA_DIR/backups. Download and retain a separate encrypted copy.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
root = Path(os.environ.get('PF_DATA_DIR', Path(__file__).resolve().parent/'data'))
source = root/'pathfinder.sqlite3'
if not source.is_file():raise SystemExit('데이터베이스가 존재하지 않습니다: '+str(source))
backup_dir = root/'backups'; backup_dir.mkdir(parents=True, exist_ok=True)
target = backup_dir / ('pathfinder_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'.sqlite3')
with sqlite3.connect(source) as src, sqlite3.connect(target) as dest:
    src.backup(dest)
os.chmod(target,0o600)
print('백업 완료:',target,'('+str(target.stat().st_size)+' bytes)')
print('주의: 같은 영구 디스크에만 있는 백업은 재난 복구 대책이 아닙니다. 별도의 안전한 위치로 복사하세요.')
