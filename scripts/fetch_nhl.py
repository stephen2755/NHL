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

# Season skater totals for approximate player goal projections.
# Fetch only teams appearing on upcoming cards, and retain cached team files
# when a transient NHL API failure occurs.
teams = set()
for offset in range(0, 15):
    day = (today + timedelta(days=offset)).isoformat()
    p = ROOT / (day + ".json")
    if not p.exists():
        continue
    try:
        games = json.loads(p.read_text()).get("games", [])
        for game in games:
            for side in ("homeTeam", "awayTeam"):
                code = game.get(side, {}).get("abbrev", {})
                if isinstance(code, dict):
                    code = code.get("default")
                if isinstance(code, str) and len(code) == 3:
                    teams.add(code)
    except (ValueError, OSError):
        continue
team_stats = {}
for team in sorted(teams):
    stats = get("/club-stats/" + team + "/now")
    if stats and isinstance(stats.get("skaters"), list):
        team_stats[team] = stats["skaters"]
        (ROOT / ("skaters-" + team + ".json")).write_text(json.dumps(stats["skaters"]))
print("Updated skater totals for", len(team_stats), "of", len(teams), "teams")
