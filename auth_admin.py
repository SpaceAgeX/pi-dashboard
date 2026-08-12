#!/usr/bin/env python3
import argparse,json
from dashboard.access import delete_pending,list_devices,list_pending,revoke,revoke_all
p=argparse.ArgumentParser();s=p.add_subparsers(dest="command",required=True);s.add_parser("list-devices");s.add_parser("list-pending")
for c in ("revoke","delete-pending"):s.add_parser(c).add_argument("id")
s.add_parser("revoke-all").add_argument("--yes",action="store_true");a=p.parse_args()
if a.command=="list-devices":print(json.dumps(list_devices(),indent=2))
elif a.command=="list-pending":print(json.dumps(list_pending(),indent=2))
elif a.command=="revoke":raise SystemExit(0 if revoke(a.id) else 1)
elif a.command=="delete-pending":raise SystemExit(0 if delete_pending(a.id) else 1)
elif a.command=="revoke-all":
 if not a.yes:p.error("revoke-all requires --yes")
 print(f"Revoked {revoke_all()} device(s)")
