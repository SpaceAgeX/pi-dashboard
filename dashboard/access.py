from __future__ import annotations
import os, sqlite3, time
from pathlib import Path
DB_PATH=Path(os.environ.get("ARYEHLAB_AUTH_DB","/var/lib/aryehlab/auth.db")); PENDING_TTL=600
def connect():
 db=sqlite3.connect(DB_PATH,timeout=5);db.row_factory=sqlite3.Row;db.execute("PRAGMA journal_mode=WAL");db.executescript("CREATE TABLE IF NOT EXISTS pending_requests(id TEXT PRIMARY KEY,secret_hash TEXT NOT NULL,approval_code TEXT NOT NULL UNIQUE,user_agent TEXT NOT NULL,requested_at INTEGER NOT NULL,source_ip TEXT,status TEXT NOT NULL CHECK(status IN ('pending','approved','denied')),approved_at INTEGER);CREATE TABLE IF NOT EXISTS trusted_devices(id TEXT PRIMARY KEY,secret_hash TEXT NOT NULL,name TEXT NOT NULL,user_agent TEXT NOT NULL,approved_at INTEGER NOT NULL,last_seen_at INTEGER NOT NULL,last_ip TEXT);");return db
def list_pending():
 with connect() as db: db.execute("DELETE FROM pending_requests WHERE requested_at<?",(int(time.time())-PENDING_TTL,));return [dict(r) for r in db.execute("SELECT id,approval_code,user_agent,requested_at,source_ip,status FROM pending_requests ORDER BY requested_at DESC")]
def list_devices():
 with connect() as db:return [dict(r) for r in db.execute("SELECT id,name,user_agent,approved_at,last_seen_at,last_ip FROM trusted_devices ORDER BY approved_at DESC")]
def decide(request_id,status):
 if status not in {"approved","denied"}:raise ValueError("Invalid decision")
 with connect() as db:r=db.execute("UPDATE pending_requests SET status=?,approved_at=? WHERE id=? AND status='pending' AND requested_at>=?",(status,int(time.time()),request_id,int(time.time())-PENDING_TTL));return r.rowcount==1
def rename(device_id,name):
 if not name.strip():return False
 with connect() as db:r=db.execute("UPDATE trusted_devices SET name=? WHERE id=?",(name.strip()[:80],device_id));return r.rowcount==1
def revoke(device_id):
 with connect() as db:r=db.execute("DELETE FROM trusted_devices WHERE id=?",(device_id,));return r.rowcount==1
def revoke_all():
 with connect() as db:n=db.execute("SELECT COUNT(*) FROM trusted_devices").fetchone()[0];db.execute("DELETE FROM trusted_devices");return n
def delete_pending(request_id):
 with connect() as db:r=db.execute("DELETE FROM pending_requests WHERE id=?",(request_id,));return r.rowcount==1
