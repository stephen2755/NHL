#!/usr/bin/env python3
"""Best-effort Daily Faceoff starting-goalie snapshot, no invented confirmations."""
import json, re, urllib.request
from datetime import date, datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

OUT = Path("site-data")
OUT.mkdir(exist_ok=True)
# DFO lists the games in date order; we pair its game headings with the
# schedule's home/away team names rather than guessing from player identity.
class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens=[]
        self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript"):
            self.skip+=1
    def handle_endtag(self, tag):
        if tag in ("script","style","noscript") and self.skip:
            self.skip-=1
    def handle_data(self, data):
        if not self.skip:
            t=" ".join(data.split())
            if t:
                self.tokens.append(t)

STATUS = {"Confirmed", "Likely", "Unconfirmed", "Projected"}
# NHL API game schedule includes team names. Pair DFO matchup headings by
# their official display names; never label a projected goalie confirmed.
def label(team):
    x=team.get("name", "")
    return x.get("default","") if isinstance(x,dict) else x

def collect(day):
    schedule=OUT/(day+".json")
    if not schedule.exists():
        return
    games=json.loads(schedule.read_text()).get("games",[])
    url="https://www.dailyfaceoff.com/starting-goalies/"+date.fromisoformat(day).strftime("%m-%d-%Y")
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; NHL research dashboard)","Accept":"text/html"})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            html=r.read().decode("utf-8","replace")
    except Exception as e:
        message="Daily Faceoff fetch failed: "+str(e)
        (OUT/("goalies-status-"+day+".json")).write_text(json.dumps({"ok":False,"error":message,"checked_at":datetime.now(timezone.utc).isoformat(),"source_url":url}))
        print(message,day,flush=True)
        return
    p=TextParser()
    p.feed(html)
    tokens=p.tokens
    # Match each team's full matchup heading using normalized text. Some
    # HTML renderers split the heading into several adjacent text nodes.
    flat="\n".join(tokens)
    names={"ANA":"Anaheim Ducks","BOS":"Boston Bruins","BUF":"Buffalo Sabres","CAR":"Carolina Hurricanes","CBJ":"Columbus Blue Jackets","CGY":"Calgary Flames","CHI":"Chicago Blackhawks","COL":"Colorado Avalanche","DAL":"Dallas Stars","DET":"Detroit Red Wings","EDM":"Edmonton Oilers","FLA":"Florida Panthers","LAK":"Los Angeles Kings","MIN":"Minnesota Wild","MTL":"Montreal Canadiens","NJD":"New Jersey Devils","NSH":"Nashville Predators","NYI":"New York Islanders","NYR":"New York Rangers","OTT":"Ottawa Senators","PHI":"Philadelphia Flyers","PIT":"Pittsburgh Penguins","SEA":"Seattle Kraken","SJS":"San Jose Sharks","STL":"St Louis Blues","TBL":"Tampa Bay Lightning","TOR":"Toronto Maple Leafs","UTA":"Utah Mammoth","VAN":"Vancouver Canucks","VGK":"Vegas Golden Knights","WPG":"Winnipeg Jets","WSH":"Washington Capitals"}
    found={}
    for game in games:
        away=game.get("awayTeam",{})
        home=game.get("homeTeam",{})
        aa=away.get("abbrev","");hh=home.get("abbrev","")
        if isinstance(aa,dict):aa=aa.get("default","")
        if isinstance(hh,dict):hh=hh.get("default","")
        heading=names.get(aa,label(away))+" at "+names.get(hh,label(home))
        # DFO separates the team names and "at" into distinct HTML text nodes.
        pattern=re.escape(names.get(aa,label(away)))+r"\s+at\s+"+re.escape(names.get(hh,label(home)))
        match=re.search(pattern,flat,re.I)
        if not match:
            print("DFO matchup not found:",heading)
            continue
        next_heading=re.search(r"\n[A-Za-z .'-]+\nat\n[A-Za-z .'-]+\n",flat[match.end():])
        chunk=flat[match.end():match.end()+(next_heading.start() if next_heading else 12000)]
        # Validate the reported name against each team's NHL goalie roster.
        def roster(code):
            p=OUT/("goalie-stats-"+code+".json")
            if not p.exists():return {}
            try:
                data=json.loads(p.read_text())
                return {" ".join([x.get(k,{}).get("default","") if isinstance(x.get(k),dict) else x.get(k,"") for k in ("firstName","lastName")]).strip().casefold():x for x in data}
            except Exception:return {}
        pairs=re.findall(r"(?m)^([^\n]{4,55})[ \t]*\n[ \t]*(Confirmed|Likely|Unconfirmed|Projected)[ \t]*(?:\n|$)",chunk)
        picks={}
        for side,code in (("away",aa),("home",hh)):
            known=roster(code)
            for name,status in pairs:
                if name.strip().casefold() in known:
                    picks[side]={"name":name.strip(),"status":status,"source":"Daily Faceoff"}
                    break
        if picks:
            found[str(game.get("id"))]=picks
        else:
            print("DFO goalie cards not roster-matched:",heading,"pairs:",pairs[:5])
    if not found:
        message="Daily Faceoff HTML loaded but no matchups parsed; first tokens: "+repr(tokens[:35])
        (OUT/("goalies-status-"+day+".json")).write_text(json.dumps({"ok":False,"error":message,"checked_at":datetime.now(timezone.utc).isoformat(),"source_url":url}))
        print(message,flush=True)
        return
    (OUT/("goalies-"+day+".json")).write_text(json.dumps({"source":"Daily Faceoff","source_url":url,"fetched_at":datetime.now(timezone.utc).isoformat(),"games":found}))
    (OUT/("goalies-status-"+day+".json")).write_text(json.dumps({"ok":True,"matched":len(found),"scheduled":len(games),"checked_at":datetime.now(timezone.utc).isoformat(),"source_url":url}))
    print("Daily Faceoff",day,len(found),"of",len(games),"matchups parsed")

for delta in (0,1):
    collect((date.today()+timedelta(days=delta)).isoformat())
