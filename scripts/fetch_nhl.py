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
        if isinstance(stats.get("goalies"), list):
            (ROOT / ("goalie-stats-" + team + ".json")).write_text(json.dumps(stats["goalies"]))
print("Updated skater totals for", len(team_stats), "of", len(teams), "teams")

# Recent goals are descriptive NHL boxscore statistics, not model inputs.
# Restrict requests to teams on today's slate; count each team's last 5
# completed regular-season games, excluding future games and today's live game.
recent = {}
today_file = ROOT / (today.isoformat() + ".json")
today_games = json.loads(today_file.read_text()).get("games", []) if today_file.exists() else []
today_teams = set()
for game in today_games:
    for side in ("awayTeam","homeTeam"):
        code = game.get(side,{}).get("abbrev","")
        if isinstance(code,dict): code=code.get("default","")
        if code: today_teams.add(code)
season = str(today.year if today.month >= 9 else today.year-1) + str(today.year+1 if today.month >= 9 else today.year)
for team in sorted(today_teams):
    schedule = get("/club-schedule-season/" + team + "/" + season)
    if not schedule: continue
    completed = [g for g in schedule.get("games",[]) if g.get("gameType")==2 and g.get("gameState") in ("OFF","FINAL") and g.get("gameDate","") < today.isoformat()]
    completed.sort(key=lambda g:g.get("gameDate",""),reverse=True)
    totals = {}
    for game in completed[:5]:
        box = get("/gamecenter/" + str(game["id"]) + "/boxscore")
        if not box: continue
        stats = box.get("playerByGameStats",{})
        side = "awayTeam" if (game.get("awayTeam",{}).get("abbrev") == team) else "homeTeam"
        for position in ("forwards","defense"):
            for player in stats.get(side,{}).get(position,[]):
                pid = str(player.get("playerId",""))
                if pid:
                    totals[pid] = totals.get(pid,0) + int(player.get("goals",0) or 0)
    recent[team] = {"games":min(5,len(completed)),"goals":totals}
(ROOT / "recent-goals.json").write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"teams":recent}))
print("Recent five-game goal totals:",len(recent),"teams")
