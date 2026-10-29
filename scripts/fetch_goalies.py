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
    url="https://www.dailyfaceoff.com/starting-goalies/"+day
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; NHL research dashboard)","Accept":"text/html"})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            html=r.read().decode("utf-8","replace")
    except Exception as e:
        print("Daily Faceoff unavailable",day,str(e))
        return
    p=TextParser()
    p.feed(html)
    tokens=p.tokens
    found={}
    for game in games:
        away=game.get("awayTeam",{})
        home=game.get("homeTeam",{})
        a=label(away);h=label(home)
        # The score endpoint may not include full team names; use a local
        # canonical NHL team-name lookup for matching.
        names={"ANA":"Anaheim Ducks","BOS":"Boston Bruins","BUF":"Buffalo Sabres","CAR":"Carolina Hurricanes","CBJ":"Columbus Blue Jackets","CGY":"Calgary Flames","CHI":"Chicago Blackhawks","COL":"Colorado Avalanche","DAL":"Dallas Stars","DET":"Detroit Red Wings","EDM":"Edmonton Oilers","FLA":"Florida Panthers","LAK":"Los Angeles Kings","MIN":"Minnesota Wild","MTL":"Montreal Canadiens","NJD":"New Jersey Devils","NSH":"Nashville Predators","NYI":"New York Islanders","NYR":"New York Rangers","OTT":"Ottawa Senators","PHI":"Philadelphia Flyers","PIT":"Pittsburgh Penguins","SEA":"Seattle Kraken","SJS":"San Jose Sharks","STL":"St Louis Blues","TBL":"Tampa Bay Lightning","TOR":"Toronto Maple Leafs","UTA":"Utah Mammoth","VAN":"Vancouver Canucks","VGK":"Vegas Golden Knights","WPG":"Winnipeg Jets","WSH":"Washington Capitals"}
        aa=away.get("abbrev","");hh=home.get("abbrev","")
        if isinstance(aa,dict):aa=aa.get("default","")
        if isinstance(hh,dict):hh=hh.get("default","")
        heading=names.get(aa,a)+" at "+names.get(hh,h)
        try:
            i=tokens.index(heading)
        except ValueError:
            continue
        # Only read up to the next matchup, and capture first two status
        # pairs. We require the player name immediately before the status.
        chunk=tokens[i+1:i+110]
        picks=[]
        for j,t in enumerate(chunk):
            if t in STATUS and j>0:
                name=chunk[j-1]
                if re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.'’ -]{3,55}",name) and len(name.split())>=2:
                    if not picks or picks[-1]["name"]!=name:
                        picks.append({"name":name,"status":t})
            if len(picks)>=2:
                break
        if len(picks)==2:
            found[str(game.get("id"))]={"away":picks[0],"home":picks[1]}
    (OUT/("goalies-"+day+".json")).write_text(json.dumps({"source":"Daily Faceoff","source_url":url,"fetched_at":datetime.now(timezone.utc).isoformat(),"games":found}))
    print("Daily Faceoff",day,len(found),"of",len(games),"matchups parsed")

for delta in (0,1):
    collect((date.today()+timedelta(days=delta)).isoformat())
