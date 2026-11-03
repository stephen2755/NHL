#!/usr/bin/env python3
"""Publish transparent coverage of immutable pregame forecasts and actual NHL results."""
import json
from pathlib import Path
from datetime import datetime,timezone
root=Path("site-data")
dates=set();games={}
for file in root.glob("????-??-??.json"):
 try: schedule=json.loads(file.read_text())
 except (OSError,ValueError):continue
 for game in schedule.get("games",[]):
  if game.get("gameState") in ("OFF","FINAL") and game.get("id"):
   games[str(game["id"])]={"date":file.stem,"start":game.get("startTimeUTC")}
results={}
for file in root.glob("results-????-??-??.json"):
 try: payload=json.loads(file.read_text()).get("games",{})
 except (OSError,ValueError):continue
 for gid,item in payload.items():
  if isinstance(item,dict) and isinstance(item.get("scorers"),list):
   results[str(gid)]=item
valid_goals=valid_shots=0;earliest=None;latest=None
for gid,game in games.items():
 result=results.get(gid);file=root/"forecasts"/(gid+".json")
 if not result or not file.exists():continue
 try:
  snapshot=json.loads(file.read_text())
  saved=datetime.fromisoformat(snapshot["saved_at"].replace("Z","+00:00"))
  start=datetime.fromisoformat(game["start"].replace("Z","+00:00"))
  if saved>=start:continue
 except (ValueError,TypeError,KeyError,AttributeError,OSError):continue
 if snapshot.get("players"):valid_goals+=1
 if snapshot.get("shots") and isinstance(result.get("shots"),list):valid_shots+=1
 earliest=min(earliest,game["date"]) if earliest else game["date"]
 latest=max(latest,game["date"]) if latest else game["date"]
report={"generated_at":datetime.now(timezone.utc).isoformat(),"completedGamesInSchedules":len(games),"completedGamesWithBoxscores":len(results),"verifiedPregameGoalForecastGames":valid_goals,"verifiedPregameSOGForecastGames":valid_shots,"earliestVerifiedDate":earliest,"latestVerifiedDate":latest,"note":"Historical results without an original pregame forecast are not treated as model predictions."}
(root/"history-coverage.json").write_text(json.dumps(report,indent=2))
print("Historical coverage:",report)
