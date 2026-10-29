/* Standalone historical skater analytics. No projection-model inputs. */
let analyticsRows=null,analyticsSort='ixg',analyticsDescending=true;
const analyticsEsc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function parseSkaterCsv(text){
 const lines=[];let row=[],field='',quoted=false;
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){row.push(field);field=''}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(Boolean))lines.push(row);row=[];field=''}else field+=c}
 if(field||row.length){row.push(field);lines.push(row)}
 const headers=lines.shift()||[];return lines.map(c=>Object.fromEntries(headers.map((h,i)=>[h,c[i]??''])));
}
function analyticsMetric(row){
 const n=k=>Number(row[k])||0,minutes=n('icetime')/60,rate=v=>minutes>0?v*60/minutes:0;
 return {id:row.playerId,name:row.name,team:row.team,position:row.position,situation:row.situation,gp:n('games_played'),minutes,ixg:rate(n('I_F_xGoals')),goals:rate(n('I_F_goals')),ppMinutes:minutes,ixgTotal:n('I_F_xGoals'),onxg:rate(n('OnIce_F_xGoals')),onxa:rate(n('OnIce_A_xGoals')),share:n('onIce_xGoalsPercentage')*100};
}
async function loadAnalytics(){
 if(analyticsRows)return analyticsRows;
 const r=await fetch('skaters.csv?ts='+Date.now());if(!r.ok)throw Error('Could not load skaters.csv from GitHub Pages');
 analyticsRows=parseSkaterCsv(await r.text()).filter(r=>['5on5','5on4','4on5','all'].includes(r.situation)).map(analyticsMetric);
 return analyticsRows;
}
async function renderAnalytics(){
 const root=document.querySelector('#content');
 root.innerHTML='<h2>Skater Analytics</h2><p class="analytics-intro">Explore 2026 player shot quality, 5-on-5 performance and power-play production. This is a historical CSV snapshot; these statistics do not change the daily projections.</p><div class="card">Loading skater statistics…</div>';
 try{await loadAnalytics()}catch(e){root.innerHTML='<h2>Skater Analytics</h2><div class="card error">'+analyticsEsc(e.message)+'</div>';return}
 root.innerHTML='<h2>Skater Analytics</h2><p class="analytics-intro">Explore individual expected goals and on-ice shot quality. The uploaded 2026 CSV is a snapshot, not a live feed. All rates are per 60 minutes of ice time. This page does not change the model predictions.</p><div class="card"><div class="analytics-controls"><input id="analytics-search" aria-label="Search player" placeholder="Search player…"><select id="analytics-team" aria-label="Team"><option value="">All teams</option>'+[...new Set(analyticsRows.map(x=>x.team))].sort().map(t=>'<option>'+analyticsEsc(t)+'</option>').join('')+'</select><select id="analytics-situation" aria-label="Situation"><option value="5on5">5-on-5</option><option value="5on4">Power play (5-on-4)</option><option value="4on5">Penalty kill (4-on-5)</option><option value="all">All situations</option></select><select id="analytics-min" aria-label="Minimum ice time"><option value="60">Minimum 60 minutes</option><option value="0">No minimum</option><option value="150">Minimum 150 minutes</option><option value="300">Minimum 300 minutes</option></select></div><div id="analytics-count" class="analytics-meta"></div><div class="analytics-table-wrap"><table class="analytics-table"><thead><tr><th data-sort="name">Player</th><th data-sort="team">Team</th><th data-sort="gp">GP</th><th data-sort="minutes">TOI</th><th data-sort="ixg">iXG/60</th><th data-sort="goals">Goals/60</th><th data-sort="onxg">On-ice xGF/60</th><th data-sort="onxa">On-ice xGA/60</th><th data-sort="share">On-ice xG%</th></tr></thead><tbody id="analytics-body"></tbody></table></div><p class="small">TOI is total minutes in the selected situation. Power-play statistics reflect individual 5-on-4 usage, not verified PP1/PP2 membership. Click a column heading to sort. Showing up to 150 players.</p></div>';
 const update=()=>{
 const term=document.querySelector('#analytics-search').value.trim().toLowerCase(),team=document.querySelector('#analytics-team').value,sit=document.querySelector('#analytics-situation').value,min=Number(document.querySelector('#analytics-min').value);
 const rows=analyticsRows.filter(r=>r.situation===sit&&(!team||r.team===team)&&r.minutes>=min&&r.name.toLowerCase().includes(term));
 rows.sort((a,b)=>{const x=a[analyticsSort],y=b[analyticsSort];return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(analyticsDescending?-1:1)});
 document.querySelector('#analytics-count').textContent=rows.length+' players found · '+(sit==='5on4'?'Power play':sit==='5on5'?'5-on-5':sit==='4on5'?'Penalty kill':'All situations');
 document.querySelector('#analytics-body').innerHTML=rows.slice(0,150).map(r=>'<tr><td class="player-label">'+analyticsEsc(r.name)+'</td><td>'+analyticsEsc(r.team)+'</td><td>'+r.gp+'</td><td>'+r.minutes.toFixed(0)+'</td><td>'+r.ixg.toFixed(2)+'</td><td>'+r.goals.toFixed(2)+'</td><td>'+r.onxg.toFixed(2)+'</td><td>'+r.onxa.toFixed(2)+'</td><td>'+r.share.toFixed(1)+'%</td></tr>').join('')||'<tr><td colspan="9">No matching players</td></tr>';
 };
 for(const id of ['analytics-search','analytics-team','analytics-situation','analytics-min'])document.querySelector('#'+id).addEventListener('input',update);
 document.querySelectorAll('[data-sort]').forEach(th=>th.addEventListener('click',()=>{const key=th.dataset.sort;analyticsDescending=analyticsSort===key?!analyticsDescending:!['name','team'].includes(key);analyticsSort=key;update()}));update();
}
