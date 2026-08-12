from __future__ import annotations
import asyncio,hashlib,sqlite3,time
import httpx
from app import app
from dashboard import access

def call(method,path,**kwargs):
 async def run():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:return await client.request(method,path,**kwargs)
 return asyncio.run(run())

def test_access_admin_and_same_origin_header(tmp_path):
 access.DB_PATH=tmp_path/"auth.db";access.connect().close()
 with access.connect() as db:db.execute("INSERT INTO pending_requests VALUES (?,?,?,?,?,?,?,NULL)",("request",hashlib.sha256(b"secret").hexdigest(),"123-456","Browser",int(time.time()),"127.0.0.1","pending"))
 assert call("POST","/api/access/pending/request/approve").status_code==403
 assert call("POST","/api/access/pending/request/approve",headers={"X-PI-Dashboard":"same-origin"}).json()=={"success":True}
 assert call("GET","/api/access").json()["pending"][0]["status"]=="approved"
