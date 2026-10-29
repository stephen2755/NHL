#!/usr/bin/env python3
"""Fetch public NHL data during GitHub Actions deployment, not in visitors' browsers."""
import json, os, time, urllib.request
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

BASE = "https://api-web.nhle.com/v1"
ROOT = Path("site-data")
ROOT.mkdir(exist_ok=True)

def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0 NHL-Daily-Card/0.1", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except Exception as exc:
            print("NHL API error", path, attempt + 1, repr(exc), flush=True)
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    return None

today = date.today()
standings = get("/standings/now")
if standings is not None:
    (ROOT / "standings.json").write_text(json.dumps(standings))
else:
    print("WARNING: standings not available")
count = 0
for offset in range(-7, 15):
    day = (today + timedelta(days=offset)).isoformat()
    data = get("/score/" + day)
    if data is not None:
        (ROOT / (day + ".json")).write_text(json.dumps(data))
        count += 1
print("Fetched", count, "score dates; standings:", standings is not None)
if not count:
    raise SystemExit("NHL schedule unavailable; deployment stopped to preserve previous site")
(ROOT / "status.json").write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "dates": count, "standings": standings is not None}))
