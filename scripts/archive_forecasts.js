#!/usr/bin/env node
// Save immutable pregame forecasts by executing the site's actual JavaScript model.
// Never regenerate an archived game after puck drop.
const fs=require('fs'),path=require('path'),vm=require('vm');
const root=process.cwd(),out=path.join(root,'site-data','forecasts');
fs.mkdirSync(out,{recursive:true});
const elements={};
function el(selector){return elements[selector]??=( {value:'',textContent:'',innerHTML:'',className:'',addEventListener(){},classList:{toggle(){}}} );}
const context=vm.createContext({
 console,Date,Math,Number,String,JSON,Set,Map,Promise,Array,Object,
 document:{querySelector:el,querySelectorAll:()=>[]},
 fetch:async url=>{
   const file=path.join(root,String(url).split('?')[0]);
   if(!file.startsWith(root+path.sep)||!fs.existsSync(file))return {ok:false};
   return {ok:true,json:async()=>JSON.parse(fs.readFileSync(file,'utf8')),text:async()=>fs.readFileSync(file,'utf8')};
 }
});
vm.runInContext(fs.readFileSync('analytics.js','utf8'),context);
vm.runInContext(fs.readFileSync('app.js','utf8').replace(/load\(\);\s*$/, ''),context);
(async()=>{
 const now=Date.now();let count=0;
 const dates=[...new Set(fs.readdirSync('site-data').filter(x=>/^\d{4}-\d{2}-\d{2}\.json$/.test(x)).map(x=>x.slice(0,10)))].sort();
 for(const day of dates){
  const schedule=JSON.parse(fs.readFileSync(path.join(root,'site-data',day+'.json')));
  const pending=(schedule.games||[]).filter(g=>g.id&&g.startTimeUTC&&Date.parse(g.startTimeUTC)>now+60*1000&&!fs.existsSync(path.join(out,g.id+'.json')));
  if(!pending.length)continue;
  el('#date').value=day;
  await vm.runInContext('load()',context);
  if(el('#status').className==='error'){console.warn('Skipping forecasts for',day,el('#status').textContent);continue;}
  for(const g of pending){
   const filename=path.join(out,g.id+'.json');
   if(fs.existsSync(filename)||Date.parse(g.startTimeUTC)<=Date.now()+60*1000)continue;
   context.__game=g;
   const forecast=vm.runInContext(`(()=>{
     const m=model(__game);if(!m)return null;
     return {away:m.a,home:m.h,awayGoals:m.x,homeGoals:m.y,awayWinProbability:m.aw,
       players:[...playerRows(m.a,m.x,100).map(p=>({...p,team:m.a})),
                ...playerRows(m.h,m.y,100).map(p=>({...p,team:m.h}))].map(p=>({
         playerId:p.playerId,name:p.name,team:p.team,expected:p.expected,
         probability:1-Math.exp(-p.expected)}))}
   })()`,context);
   if(!forecast||!forecast.players.length)continue;
   forecast.gameId=String(g.id);forecast.gameDate=day;
   forecast.saved_at=new Date().toISOString();forecast.model='live-browser-v1';
   fs.writeFileSync(filename,JSON.stringify(forecast)+'\n',{flag:'wx'});
   count++;
  }
 }
 // Verify that every game still at least one minute from puck drop has an archive.
 let missing=[];
 for(const day of dates){
  const schedule=JSON.parse(fs.readFileSync(path.join(root,'site-data',day+'.json')));
  for(const g of schedule.games||[]){
   if(g.id&&g.startTimeUTC&&Date.parse(g.startTimeUTC)>Date.now()+60*1000&&!fs.existsSync(path.join(out,g.id+'.json')))
    missing.push(day+': '+g.id);
  }
 }
 console.log('Archived',count,'new pregame forecasts; missing future archives:',missing.length);
 if(missing.length){console.error('Missing pregame archives:',missing.slice(0,30).join(', '));process.exitCode=1;}
})().catch(e=>{console.error(e);process.exitCode=1});
