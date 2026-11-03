#!/usr/bin/env python3
"""Evaluate immutable pregame player-goal forecasts against completed NHL boxscores."""
import json
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path("site-data")
bins=[("0.00–0.19",0,.2),("0.20–0.29",.2,.3),("0.30–0.39",.3,.4),("0.40–0.49",.4,.5),("0.50–0.59",.5,.6),("0.60+",.6,float("inf")),("0.50+",.5,float("inf"))]
buckets=[{"label":label,"players":0,"scored":0,"expectedHits":0.0,"expectedGoals":0.0,"actualGoals":0} for label,_,_ in bins]
games_count=0
for schedule_file in sorted(ROOT.glob("????-??-??.json")):
 try: schedule=json.loads(schedule_file.read_text())
 except (ValueError,OSError): continue
 day=schedule_file.stem
 results_file=ROOT/("results-"+day+".json")
 if not results_file.exists():continue
 try: results=json.loads(results_file.read_text()).get("games",{})
 except (ValueError,OSError):continue
 for game in schedule.get("games",[]):
  if game.get("gameState") not in ("OFF","FINAL"):continue
  gid=str(game.get("id",""))
  result=results.get(gid)
  archive=ROOT/"forecasts"/(gid+".json")
  if not result or not archive.exists():continue
  try: forecast=json.loads(archive.read_text())
  except (ValueError,OSError):continue
  saved=forecast.get("saved_at","")
  start=game.get("startTimeUTC","")
  try:
   if datetime.fromisoformat(saved.replace("Z","+00:00"))>=datetime.fromisoformat(start.replace("Z","+00:00")):continue
  except (ValueError,TypeError):continue
  if not isinstance(result.get("scorers"),list):continue
  actual={str(p.get("playerId")):int(p.get("goals",0)) for p in result["scorers"]}
  players=forecast.get("players",[])
  if not players:continue
  games_count+=1
  for p in players:
   try: x=float(p["expected"]); prob=float(p["probability"])
   except (KeyError,ValueError,TypeError):continue
   if not (0<=x<10 and 0<=prob<=1):continue
   goals=actual.get(str(p.get("playerId")),0)
   for bucket,(_,lo,hi) in zip(buckets,bins):
    if lo<=x<hi:
     bucket["players"]+=1;bucket["scored"]+=int(goals>0)
     bucket["actualGoals"]+=goals;bucket["expectedHits"]+=prob;bucket["expectedGoals"]+=x
(ROOT/"scorer-hit-rates.json").write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(),"games":games_count,"bins":buckets},indent=2))
print("Scorer hit rates:",games_count,"verified pregame archived games")
