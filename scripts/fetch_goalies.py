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
        print("Daily Faceoff unavailable",day,str(e))
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
        match=re.search(re.escape(heading),flat,re.I)
        if not match:
            print("DFO matchup not found:",heading)
            continue
        # The two goalie cards occur immediately after the matchup header,
        # each as a player name followed by its explicit status.
        next_heading=re.search(r"\n[A-Za-z .'-]+ at [A-Za-z .'-]+\n",flat[match.end():])
        chunk=flat[match.end():match.end()+(next_heading.start() if next_heading else 12000)]
        pairs=re.findall(r"(?m)^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.\u0027’ -]{3,55})[ \t]*\n[ \t]*(Confirmed|Likely|Unconfirmed|Projected)[ \t]*(?:\n|$)",chunk)
        picks=[{"name":name.strip(),"status":status} for name,status in pairs[:2]]
        if len(picks)==2:
            found[str(game.get("id"))]={"away":picks[0],"home":picks[1]}
        else:
            print("DFO goalie cards not parsed:",heading,"pairs:",len(picks))
    if not found:
        raise RuntimeError("Daily Faceoff returned zero parsed goalie matchups; inspect HTML structure")
    (OUT/("goalies-"+day+".json")).write_text(json.dumps({"source":"Daily Faceoff","source_url":url,"fetched_at":datetime.now(timezone.utc).isoformat(),"games":found}))
    print("Daily Faceoff",day,len(found),"of",len(games),"matchups parsed")

for delta in (0,1):
    collect((date.today()+timedelta(days=delta)).isoformat())
