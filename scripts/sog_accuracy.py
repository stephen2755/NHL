#!/usr/bin/env python3
"""Walk-forward evaluation of archived pregame player SOG against final NHL boxscores."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path("site-data")
BINS=[("0.0–0.9",0,1),("1.0–1.9",1,2),("2.0–2.9",2,3),("3.0–3.9",3,4),("4.0–4.9",4,5),("5.0+",5,float("inf"))]
bins=[{"label":label,"players":0,"projected":0.0,"actual":0,"absoluteError":0.0,"withinOne":0} for label,_,_ in BINS]
games=0;player_games=0;absolute_error=0.;signed_error=0.
for file in sorted(ROOT.glob("results-????-??-??.json")):
 try: results=json.loads(file.read_text()).get("games",{})
 except (ValueError,OSError):continue
 for gid,result in results.items():
  archive=ROOT/"forecasts"/(str(gid)+".json")
  if not archive.exists() or not isinstance(result.get("shots"),list):continue
  try: snapshot=json.loads(archive.read_text())
  except (ValueError,OSError):continue
  saved=snapshot.get("saved_at");start=None
  schedule=ROOT/(file.stem.replace("results-","")+".json")
  if schedule.exists():
   try:
    for g in json.loads(schedule.read_text()).get("games",[]):
     if str(g.get("id"))==str(gid):
      if g.get("gameState") not in ("OFF","FINAL"):break
      start=g.get("startTimeUTC");break
   except (ValueError,OSError):pass
  try:
   if not start or datetime.fromisoformat(saved.replace("Z","+00:00"))>=datetime.fromisoformat(start.replace("Z","+00:00")):continue
  except (AttributeError,ValueError,TypeError):continue
  predictions=snapshot.get("shots")
  if not isinstance(predictions,list) or not predictions:continue
  actual={str(p.get("playerId")):int(p.get("shots",0)) for p in result["shots"]}
  counted=False
  for p in predictions:
   pid=str(p.get("playerId",""))
   if pid not in actual:continue # DNP excluded, not treated as zero shots
   try:projected=float(p["projected"])
   except (KeyError,ValueError,TypeError):continue
   if not 0<=projected<30:continue
   observed=actual[pid];error=abs(observed-projected)
   player_games+=1;absolute_error+=error;signed_error+=observed-projected;counted=True
   for b,(_,lo,hi) in zip(bins,BINS):
    if lo<=projected<hi:
     b["players"]+=1;b["projected"]+=projected;b["actual"]+=observed
     b["absoluteError"]+=error;b["withinOne"]+=int(error<=1)
     break
  if counted:games+=1
(ROOT/"sog-accuracy.json").write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(),"games":games,"playerGames":player_games,"absoluteError":absolute_error,"signedError":signed_error,"bins":bins},indent=2))
print("SOG accuracy:",games,"games,",player_games,"player-games")
