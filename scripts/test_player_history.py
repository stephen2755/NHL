#!/usr/bin/env python3
"""Evaluate prior-season MoneyPuck scoring rates against later season totals.
Retrospective rate test: actual test-season games played is used for scaling.
Not a game-level forecast or a test of live predictions.
"""
import collections
import json
import math
from pathlib import Path

DATA = Path("historical-skaters-2021-2024.json")
OUT = Path("site-data/player-history-test.json")
players = json.loads(DATA.read_text())["players"]
by_id = collections.defaultdict(list)
for p in players:
    if p["gp"] > 0:
        by_id[str(p["id"])].append(p)
for rows in by_id.values():
    rows.sort(key=lambda r: r["season"])

report = {"source": "MoneyPuck", "method": "Prior seasons only; actual test-season games played used to evaluate scoring rates, not a true preseason or game-level forecast.", "seasons": []}
for season in (2022, 2023, 2024):
    cases = []
    for rows in by_id.values():
        hist = [r for r in rows if r["season"] < season]
        test = next((r for r in rows if r["season"] == season), None)
        if not hist or not test or test["gp"] < 10:
            continue
        weights = [(.7 ** (season - 1 - r["season"])) * min(r["gp"], 82) for r in hist]
        denom = sum(weights)
        goals = sum(w * r["goals"] / r["gp"] for w, r in zip(weights, hist)) / denom
        xg = sum(w * r["xg"] / r["gp"] for w, r in zip(weights, hist)) / denom
        cases.append((test, goals, xg))
    metrics = {}
    for label, mix in (("goals_only", 0), ("xg_only", 1), ("xg_goals_blend", .75)):
        errors, deviances = [], []
        for test, goals, xg in cases:
            expected = max(.01, ((1 - mix) * goals + mix * xg) * test["gp"])
            actual = test["goals"]
            errors.append(abs(expected - actual))
            deviances.append(2 * (expected - actual + (actual * math.log(actual / expected) if actual else 0)))
        metrics[label] = {"mae": round(sum(errors) / len(errors), 3),
                          "poisson_deviance": round(sum(deviances) / len(deviances), 3)}
    report["seasons"].append({"season_start": season, "players": len(cases), "models": metrics})
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
