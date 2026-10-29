#!/usr/bin/env python3
"""Fetch public NHL injury statuses from ESPN; do not infer health from missing data."""
import json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
URL="https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 NHL-model-research","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=30) as response:
    raw=json.load(response)
teams={}
def normalize(x):
    return " ".join(str(x or "").lower().replace("’","'").split())
def collect(entry,team):
    athlete=entry.get("athlete") or {}
    name=athlete.get("displayName") or athlete.get("fullName") or entry.get("name")
    status=entry.get("status") or entry.get("type") or ""
    if isinstance(status,dict):
        status=status.get("description") or status.get("name") or status.get("abbreviation") or ""
    if not name:
        return
    key=normalize(name)
    teams.setdefault(team,{})[key]={"name":name,"status":str(status),"detail":str(entry.get("shortComment") or "")[:160]}
def process(group):
    teamobj=group.get("team") or {}
    code=teamobj.get("abbreviation") or teamobj.get("abbrev") or group.get("abbreviation")
    if not code:
        return
    code=str(code).upper()
    if code=="LA":code="LAK"
    if code=="TB":code="TBL"
    if code=="NJ":code="NJD"
    if code=="SJ":code="SJS"
    if code=="VEG" or code=="LV":code="VGK"
    for item in group.get("injuries",[]):
        collect(item,code)
if isinstance(raw,list):
    for group in raw:process(group)
elif isinstance(raw,dict):
    for group in raw.get("injuries",[]):process(group)
    for group in raw.get("teams",[]):process(group)
if not teams:
    raise SystemExit("No ESPN injuries parsed; refusing to publish an empty healthy-looking report")
out=Path("site-data/injuries.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({"source":"ESPN injury report","fetched_at":datetime.now(timezone.utc).isoformat(),"teams":teams}))
print("Published injury reports for",len(teams),"teams;",sum(map(len,teams.values())),"players")
