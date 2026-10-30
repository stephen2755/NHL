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
    # Current NHL roster is distinct from season-to-date player statistics.
    # Save IDs for strict roster membership checks in the browser.
    roster = get("/roster/" + team + "/current")
    if roster and any(isinstance(roster.get(k), list) for k in ("forwards", "defensemen", "goalies")):
        ids = [str(p["id"]) for group in ("forwards", "defensemen", "goalies")
               for p in roster.get(group, []) if p.get("id") is not None]
        (ROOT / ("roster-" + team + ".json")).write_text(json.dumps({
            "team": team, "playerIds": ids, "updated_at": datetime.now(timezone.utc).isoformat()
        }))
    else:
        # Avoid retaining an obsolete roster when the API is unavailable.
        (ROOT / ("roster-" + team + ".json")).write_text(json.dumps({
            "team": team, "playerIds": [], "unavailable": True
        }))
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

# Daily results: final scores and scorer identities, sourced from NHL boxscores.
# Forecasts are joined separately from immutable pregame snapshots when present.
for offset in range(-7, 1):
    day = (today + timedelta(days=offset)).isoformat()
    source = ROOT / (day + ".json")
    if not source.exists():
        continue
    data = json.loads(source.read_text())
    finished = [g for g in data.get("games", []) if g.get("gameState") in ("OFF", "FINAL")]
    results = {}
    for game in finished:
        game_id = str(game.get("id", ""))
        if not game_id:
            continue
        box = get("/gamecenter/" + game_id + "/boxscore")
        if not box or not box.get("playerByGameStats"):
            continue
        scorers = []
        for side in ("awayTeam", "homeTeam"):
            team = game.get(side, {}).get("abbrev", "")
            if isinstance(team, dict):
                team = team.get("default", "")
            for position in ("forwards", "defense"):
                for player in box["playerByGameStats"].get(side, {}).get(position, []):
                    goals = int(player.get("goals", 0) or 0)
                    if goals <= 0:
                        continue
                    name = player.get("name", {})
                    if isinstance(name, dict):
                        name = name.get("default", "")
                    if not name:
                        name = " ".join(str(player.get(k, "")) for k in ("firstName", "lastName")).strip()
                    scorers.append({"playerId": str(player.get("playerId", "")),
                                    "name": name, "team": team, "goals": goals})
        archive = ROOT / "forecasts" / (game_id + ".json")
        forecast = None
        if archive.exists():
            try:
                forecast = json.loads(archive.read_text())
            except (ValueError, OSError):
                pass
        results[game_id] = {"scorers": scorers, "forecast": forecast}
    (ROOT / ("results-" + day + ".json")).write_text(json.dumps({"date": day, "games": results}))
print("Updated daily scorer results")
