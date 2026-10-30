#!/usr/bin/env python3
"""Leakage-free walk-forward NHL baseline backtest. Uses completed regular-season games only."""
import json
import math
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api-web.nhle.com/v1"
TEAMS = "ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH".split()
OUT = Path("site-data")
OUT.mkdir(exist_ok=True)
SEASON = "20252026"
LEAGUE = 3.05

def fetch(team):
    url = f"{BASE}/club-schedule-season/{team}/{SEASON}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 NHL-model-backtest", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response).get("games", [])
        except Exception as exc:
            print("Schedule error", team, attempt + 1, str(exc), flush=True)
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    return None

def abbrev(obj):
    value = (obj or {}).get("abbrev", "")
    return value.get("default", "") if isinstance(value, dict) else value

def probs(away, home):
    def pmf(k, lam):
        return math.exp(-lam) * lam ** k / math.factorial(k)
    pa = [pmf(i, away) for i in range(17)]
    ph = [pmf(i, home) for i in range(17)]
    aw = sum(pa[i] * ph[j] for i in range(17) for j in range(i))
    tie = sum(pa[i] * ph[i] for i in range(17))
    return min(.999, max(.001, aw + tie / 2))

def predict(a, h, hist, shrink=.65, home_ice=.13):
    def rate(team):
        rows = hist[team]
        n = len(rows)
        # 10-game pseudo-count toward league average to stabilize early-season estimates.
        return ((sum(x[0] for x in rows) + 10 * LEAGUE) / (n + 10),
                (sum(x[1] for x in rows) + 10 * LEAGUE) / (n + 10))
    agf, aga = rate(a)
    hgf, hga = rate(h)
    x = max(.5, LEAGUE + shrink * ((agf - LEAGUE) + (hga - LEAGUE)) / 2 - home_ice)
    y = max(.5, LEAGUE + shrink * ((hgf - LEAGUE) + (aga - LEAGUE)) / 2 + home_ice)
    return x, y, probs(x, y)

def summarize(rows):
    if not rows:
        return None
    n = len(rows)
    return {
        "games": n,
        "team_goal_mae": round(sum((abs(r["actual_away"] - r["pred_away"]) + abs(r["actual_home"] - r["pred_home"])) / 2 for r in rows) / n, 3),
        "total_goal_mae": round(sum(abs((r["actual_away"] + r["actual_home"]) - (r["pred_away"] + r["pred_home"])) for r in rows) / n, 3),
        "winner_accuracy": round(sum((r["away_win_prob"] > .5) == (r["actual_away"] > r["actual_home"]) for r in rows) / n, 4),
        "brier_score": round(sum((r["away_win_prob"] - int(r["actual_away"] > r["actual_home"])) ** 2 for r in rows) / n, 4),
        "log_loss": round(-sum(int(r["actual_away"] > r["actual_home"]) * math.log(max(.001, r["away_win_prob"])) + int(r["actual_away"] < r["actual_home"]) * math.log(max(.001, 1 - r["away_win_prob"])) for r in rows) / n, 4)
    }

all_games = {}
failed = []
for team in TEAMS:
    schedule = fetch(team)
    if schedule is None:
        failed.append(team)
        continue
    for g in schedule:
        if g.get("gameType") != 2 or g.get("gameState") not in ("OFF", "FINAL"):
            continue
        a, h = abbrev(g.get("awayTeam")), abbrev(g.get("homeTeam"))
        av, hv = g.get("awayTeam", {}).get("score"), g.get("homeTeam", {}).get("score")
        if not a or not h or not isinstance(av, int) or not isinstance(hv, int) or av == hv:
            continue
        key = str(g.get("id", a + h + str(g.get("gameDate"))))
        all_games[key] = {"id": key, "date": g.get("gameDate", ""), "away": a, "home": h, "actual_away": av, "actual_home": hv}

if failed:
    print("Failed team schedules:", ", ".join(failed))
if len(all_games) < 900 or failed:
    raise SystemExit(f"Incomplete 2025-26 regular-season dataset ({len(all_games)} games); refusing to publish misleading metrics")

games = sorted(all_games.values(), key=lambda g: (g["date"], g["id"]))
history = defaultdict(list)
tested = []
baseline = []
for day in sorted({g["date"] for g in games}):
    todays = [g for g in games if g["date"] == day]
    for g in todays:
        a, h = g["away"], g["home"]
        # Same-date results are never used to predict one another.
        if min(len(history[a]), len(history[h])) >= 10:
            x, y, p = predict(a, h, history)
            tested.append({**g, "pred_away": round(x, 4), "pred_home": round(y, 4), "away_win_prob": round(p, 5)})
            bx, by = LEAGUE - .13, LEAGUE + .13
            baseline.append({**g, "pred_away": bx, "pred_home": by, "away_win_prob": probs(bx, by)})
    for g in todays:
        history[g["away"]].append((g["actual_away"], g["actual_home"]))
        history[g["home"]].append((g["actual_home"], g["actual_away"]))

def calibration(rows):
    bins = []
    for low in range(0, 100, 10):
        group = [r for r in rows if low <= 100 * r["away_win_prob"] < low + 10]
        if not group:
            continue
        bins.append({"range": f"{low}-{low + 10}%", "games": len(group),
                     "predicted": round(sum(r["away_win_prob"] for r in group) / len(group), 4),
                     "actual": round(sum(r["actual_away"] > r["actual_home"] for r in group) / len(group), 4)})
    return bins

report = {
    "season": SEASON, "generated_at": datetime.now(timezone.utc).isoformat(),
    "method": "Walk-forward, game-date grouped; each team needs 10 prior games; no same-day or future results.",
    "model": "Goals-for/against shrinkage with 10-game league-average prior and home ice",
    "games_found": len(games), "games_tested": len(tested),
    "model_metrics": summarize(tested), "baseline_metrics": summarize(baseline),
    "last_10": tested[-10:], "calibration": calibration(tested),
    "monthly": [{"month": month, "metrics": summarize([r for r in tested if r["date"].startswith(month)])} for month in sorted({r["date"][:7] for r in tested})],
}
(OUT / "backtest.json").write_text(json.dumps(report, separators=(",", ":")))
print("Backtest report:", json.dumps({"games": len(games), "tested": len(tested), "model": report["model_metrics"], "baseline": report["baseline_metrics"]}))
