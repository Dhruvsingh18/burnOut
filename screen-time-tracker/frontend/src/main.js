
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const COLORS={'VS Code':'#7C6FFF','Cursor':'#6366F1','Chrome':'#F59E0B','Firefox':'#F97316','Edge':'#0EA5E9','Safari':'#06B6D4','Brave':'#FB7185','Terminal':'#00D4A0','PowerShell':'#6366F1','Slack':'#8B5CF6','Discord':'#7C3AED','Teams':'#3B82F6','Zoom':'#2563EB','Figma':'#EC4899','Photoshop':'#38BDF8','Illustrator':'#F59E0B','Spotify':'#1DB954','YouTube':'#FF5C5C','Netflix':'#DC2626','Twitch':'#9146FF','Reddit':'#FF6314','Twitter':'#1DA1F2','Notion':'#AAAAAA','Obsidian':'#7C3AED','PyCharm':'#00D4A0','IntelliJ':'#FF5C5C','Excel':'#21A366','Word':'#2B579A'};
const col=n=>COLORS[n]||'#8B90A7';
const ini=n=>n.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
const fmt=m=>m>=60?`${Math.floor(m/60)}h ${String(m%60).padStart(2,'0')}m`:`${m}m`;
let D={today:null,week:null,hist:[],lims:{}},C={},curApp=null,filt='all',focus=['deep work'];
let rules=[
  {icon:'&#128276;',bg:'rgba(77,166,255,.12)',t:'Daily total alert',d:'Notify when over daily limit',on:true},
  {icon:'&#127769;',bg:'rgba(139,92,246,.12)',t:'Late night warning',d:'Alert after your cutoff time',on:true},
  {icon:'&#128293;',bg:'rgba(255,92,92,.12)',t:'Distraction spike',d:'Warn when distracting apps exceed 45 min',on:true},
  {icon:'&#9749;',bg:'rgba(255,176,32,.12)',t:'Break reminder',d:'Nudge after long sessions',on:true},
  {icon:'&#128140;',bg:'rgba(77,166,255,.12)',t:'Weekly digest',d:'Email summary every Monday',on:false},
];
function tick(){document.getElementById('clk').textContent=new Date().toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'});}
tick();setInterval(tick,1000);
async function loadAll(){
  try{
    const [t,w,h,l]=await Promise.all([fetch(`${API}/api/today`).then(r=>r.json()),fetch(`${API}/api/week`).then(r=>r.json()),fetch(`${API}/api/history?days=30`).then(r=>r.json()),fetch(`${API}/api/limits`).then(r=>r.json())]);
    D={today:t,week:w,hist:h,lims:Object.fromEntries(l.map(x=>[x.app_name,x.limit_minutes]))};
    setConn(true);renderAll();doAlerts();
  }catch{setConn(false);offline();}
}
function setConn(ok){
  document.getElementById('adot').style.cssText=ok?'background:var(--gr);box-shadow:0 0 0 3px rgba(0,212,160,.15)':'background:var(--rd);box-shadow:0 0 0 3px rgba(255,92,92,.15)';
  document.getElementById('albl').textContent=ok?'Agent connected':'Agent offline';
  document.getElementById('synclbl').textContent=ok?'Last sync: just now':'Check backend';
}
function offline(){['td-c','wk-c','ap-c','cm-c'].forEach(id=>{const el=document.getElementById(id);if(el)el.innerHTML=`<div class="es"><div class="es-icon">&#128268;</div><div class="es-title">Backend not running</div><div class="es-sub">Start the backend server, then refresh.</div><div class="es-code">python -m uvicorn backend.main:app --reload</div></div>`;});}
function renderAll(){renderToday();renderWeek();renderApps();renderCmp();}
function renderToday(){
  const d=D.today,el=document.getElementById('td-c');
  if(!d||d.total_minutes===0){el.innerHTML=`<div class="es"><div class="es-icon">&#9201;</div><div class="es-title">No data yet today</div><div class="es-sub">Agent is running. Data appears within 5 minutes.</div></div>`;return;}
  const avg=d.avg_daily_minutes||0,diff=d.total_minutes-avg,lim=7*60,pct=Math.min(100,Math.round(d.total_minutes/lim*100));
  const arc=276,off=arc-(pct/100)*arc,rc=pct>=90?'var(--rd)':pct>=70?'var(--am)':'var(--vi)';
  el.innerHTML=`<div class="ph"><div><div class="bnum">${fmt(d.total_minutes)}</div><div class="blbl">Today, ${new Date().toLocaleDateString('en-US',{weekday:'long'})}</div></div><div><div class="dlt" style="color:${diff>0?'var(--rd)':'var(--gr)'}">${diff>0?'&uarr;':'&darr;'} ${fmt(Math.abs(diff))}</div><div class="dls">vs your daily avg</div></div></div>
  <div class="ovr"><div class="rw"><svg viewBox="0 0 108 108" width="108" height="108"><circle cx="54" cy="54" r="44" fill="none" stroke="rgba(255,255,255,.06)" stroke-width="9"/><circle cx="54" cy="54" r="44" fill="none" stroke="${rc}" stroke-width="9" stroke-dasharray="${arc}" stroke-dashoffset="${Math.round(off)}" stroke-linecap="round" transform="rotate(-90 54 54)" style="transition:stroke-dashoffset .8s;filter:drop-shadow(0 0 6px ${rc})"/></svg><div class="rc"><div class="rp" style="color:${rc}">${pct}%</div><div class="rl">of limit</div></div></div>
  <div class="s3" style="margin-bottom:0"><div class="sc"><div class="sca" style="background:var(--vi)"></div><div class="sv" style="color:var(--vi2);font-size:${(d.first_app||'').length>7?'14px':'24px'}">${d.first_app||'&mdash;'}</div><div class="sl">Top app</div></div><div class="sc"><div class="sca" style="background:var(--gr)"></div><div class="sv" style="color:var(--gr)">${d.productive_pct}%</div><div class="sl">Productive</div></div><div class="sc"><div class="sca" style="background:var(--am)"></div><div class="sv" style="color:var(--am)">${d.switch_count}</div><div class="sl">Switches</div></div></div></div>
  <div class="sg" id="sg"></div><div class="cf" id="cf"></div>
  <div class="sh">App usage &mdash; click any row for detail</div><div id="al"></div>
  <div class="dv"></div><div class="sh">Hourly breakdown</div>
  <div style="position:relative;height:120px"><canvas id="hch"></canvas></div>`;
  const sg=document.getElementById('sg');
  d.apps.forEach(a=>{const s=document.createElement('span');s.style.cssText=`flex:${a.minutes};background:${col(a.app_name)}`;s.title=`${a.app_name}: ${fmt(a.minutes)}`;sg.appendChild(s);});
  const cf=document.getElementById('cf');
  ['all','productive','comms','distract','other'].forEach(c=>{const b=document.createElement('button');b.className='cb'+(filt===c?' on':'');b.textContent=c==='distract'?'Distraction':c.charAt(0).toUpperCase()+c.slice(1);b.onclick=()=>{filt=c;document.querySelectorAll('.cb').forEach(x=>x.classList.remove('on'));b.classList.add('on');appList('al',d.apps,filt);};cf.appendChild(b);});
  appList('al',d.apps,filt);
  killC('hch');
  const HL=Array.from({length:24},(_,i)=>i%6===0?(i<12?`${i||12}am`:`${i===12?12:i-12}pm`):'');
  C['hch']=new Chart(document.getElementById('hch'),{type:'bar',data:{labels:HL,datasets:[{data:d.hourly,backgroundColor:d.hourly.map((_,i)=>i>=22||i<6?'rgba(255,92,92,.6)':'rgba(124,111,255,.6)'),borderRadius:4,barThickness:18}]},options:{...bc(),scales:{x:{...bc().scales.x},y:{...bc().scales.y,display:false}}}});
}
function appList(id,apps,f){
  const el=document.getElementById(id);if(!el)return;
  const list=f==='all'?apps:apps.filter(a=>a.category===f);
  if(!list.length){el.innerHTML=`<div style="font-size:13px;color:var(--tx2);padding:16px 0">No apps in this category.</div>`;return;}
  const mx=Math.max(...list.map(a=>a.minutes),1);
  el.innerHTML=list.map(a=>{const badge=a.limit_minutes?`<span class="ltag ${a.over_limit?'ov':'un'}">${a.over_limit?'Over limit':'Limit '+fmt(a.limit_minutes)}</span>`:'';return `<div class="ar" onclick="openModal('${a.app_name}')"><div class="ai" style="background:${col(a.app_name)}">${ini(a.app_name)}</div><div class="am2"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px"><span class="an">${a.app_name}</span>${badge}</div><div class="bt"><div class="bf" style="width:${Math.round(a.minutes/mx*100)}%;background:${col(a.app_name)}"></div></div></div><span class="at" style="color:${col(a.app_name)}">${fmt(a.minutes)}</span></div>`;}).join('');
}
function renderWeek(){
  const w=D.week,el=document.getElementById('wk-c');
  if(!w||w.total_minutes===0){el.innerHTML=`<div class="es"><div class="es-icon">&#128197;</div><div class="es-title">No weekly data yet</div><div class="es-sub">Keep the agent running and data will build up.</div></div>`;return;}
  const wm=Math.max(...w.days.map(d=>d.total_minutes),1);
  el.innerHTML=`<div class="ph"><div><div class="bnum" style="background:linear-gradient(135deg,var(--bl),var(--tl));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">${fmt(w.total_minutes)}</div><div class="blbl">This week</div></div></div>
  <div class="s3"><div class="sc"><div class="sca" style="background:var(--gr)"></div><div class="sv" style="color:var(--gr)">${fmt(w.avg_minutes)}</div><div class="sl">Daily avg</div></div><div class="sc"><div class="sca" style="background:var(--am)"></div><div class="sv" style="color:var(--am)">${w.longest_day||'&mdash;'}</div><div class="sl">Longest day</div></div><div class="sc"><div class="sca" style="background:var(--vi)"></div><div class="sv" style="color:var(--vi2)">${w.days.filter(d=>d.total_minutes>0).length}/7</div><div class="sl">Active days</div></div></div>
  <div class="card"><div class="card-lbl">Daily totals</div><div class="wcs" id="wcs"></div><div style="display:flex;justify-content:space-between;font-size:11px;font-weight:600;color:var(--tx3)">${w.days.map(d=>`<span>${d.day}</span>`).join('')}</div></div>
  <div class="card"><div class="card-lbl">30-day history</div><div class="hrw" id="hrw"></div><div style="display:flex;justify-content:space-between;font-size:11px;color:var(--tx3);margin-top:5px"><span>30 days ago</span><span>Today</span></div></div>`;
  const wcs=document.getElementById('wcs');
  w.days.forEach(d=>{wcs.innerHTML+=`<div class="wc${d.today?' tod':''}"><div class="wv">${d.total_minutes?fmt(d.total_minutes):''}</div><div class="wb" style="height:${Math.round((d.total_minutes/wm)*155)}px" title="${d.day}: ${fmt(d.total_minutes)}"></div></div>`;});
  const hm=Math.max(...D.hist.map(h=>h.total_minutes),1),hr=document.getElementById('hrw');
  D.hist.forEach(h=>{hr.innerHTML+=`<div class="hb${h.today?' cur':''}" style="height:${Math.max(4,Math.round((h.total_minutes/hm)*50))}px" title="${h.date}: ${fmt(h.total_minutes)}"></div>`;});
}
function renderApps(){
  const d=D.today,el=document.getElementById('ap-c');
  if(!d||!d.apps?.length){el.innerHTML=`<div class="es"><div class="es-icon">&#128187;</div><div class="es-title">No app data yet</div><div class="es-sub">Apps appear once the agent has been running a few minutes.</div></div>`;return;}
  const cats={productive:0,comms:0,distract:0,other:0};
  d.apps.forEach(a=>{cats[a.category]=(cats[a.category]||0)+a.minutes;});
  el.innerHTML=`<div class="ph" style="margin-bottom:20px"><div><div style="font-size:32px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(135deg,var(--vi2),var(--bl));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">All Apps</div><div class="blbl">Today &mdash; click for detail</div></div></div><div id="all-al"></div><div class="dv"></div><div class="sh">Category split</div><div style="position:relative;height:200px"><canvas id="cch"></canvas></div>`;
  appList('all-al',d.apps,'all');
  killC('cch');
  const ks=Object.keys(cats).filter(c=>cats[c]>0);
  C['cch']=new Chart(document.getElementById('cch'),{type:'doughnut',data:{labels:ks.map(c=>c==='distract'?'Distraction':c.charAt(0).toUpperCase()+c.slice(1)),datasets:[{data:ks.map(c=>cats[c]),backgroundColor:['#7C6FFF','#8B5CF6','#FF5C5C','#4A4F66'],borderWidth:0,hoverOffset:8}]},options:{responsive:true,maintainAspectRatio:false,cutout:'68%',plugins:{legend:{display:true,position:'right',labels:{color:'#8B90A7',font:{family:'Inter',size:12},boxWidth:12,padding:14}}}}});
}
function renderCmp(){
  const el=document.getElementById('cm-c'),today=D.today,hist=D.hist;
  if(!today||today.total_minutes===0||hist.length<2){el.innerHTML=`<div class="es"><div class="es-icon">&#128202;</div><div class="es-title">Not enough history yet</div><div class="es-sub">Come back after 2+ days of tracking.</div></div>`;return;}
  const yd=hist[hist.length-2],diff=today.total_minutes-(yd?.total_minutes||0);
  el.innerHTML=`<div class="ph" style="margin-bottom:20px"><div><div style="font-size:32px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(135deg,var(--vi2),var(--bl));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Compare</div><div class="blbl">Today vs yesterday</div></div></div>
  <div class="cg"><div class="cc now"><div class="ccl" style="color:var(--vi2)">Today</div><div class="ccn" style="color:var(--vi2)">${fmt(today.total_minutes)}</div><div class="ccs">${today.productive_pct}% productive &middot; ${today.switch_count} switches</div></div><div class="cc"><div class="ccl" style="color:var(--tx3)">Yesterday</div><div class="ccn" style="color:var(--tx2)">${fmt(yd?.total_minutes||0)}</div><div class="ccs">&nbsp;</div></div></div>
  <div style="display:inline-flex;align-items:center;gap:8px;padding:10px 18px;border-radius:22px;background:${diff>0?'rgba(255,92,92,.1)':'rgba(0,212,160,.1)'};color:${diff>0?'var(--rd)':'var(--gr)'};font-weight:700;font-size:14px;margin-bottom:24px">${diff>0?'&uarr;':'&darr;'} ${fmt(Math.abs(diff))} ${diff>0?'more':'less'} than yesterday</div>
  <div class="card"><div class="card-lbl">Hourly comparison</div><div style="position:relative;height:160px"><canvas id="cmpch"></canvas></div><div style="display:flex;gap:20px;margin-top:12px;font-size:12px;font-weight:600"><span style="display:flex;align-items:center;gap:6px"><span style="width:12px;height:4px;background:var(--vi);border-radius:2px;display:inline-block"></span>Today</span><span style="display:flex;align-items:center;gap:6px"><span style="width:12px;height:4px;background:rgba(255,255,255,.15);border-radius:2px;display:inline-block"></span>Yesterday</span></div></div>`;
  killC('cmpch');
  const HL=Array.from({length:24},(_,i)=>i%6===0?(i<12?`${i||12}am`:`${i===12?12:i-12}pm`):'');
  C['cmpch']=new Chart(document.getElementById('cmpch'),{type:'bar',data:{labels:HL,datasets:[{label:'Today',data:today.hourly,backgroundColor:'rgba(124,111,255,.7)',borderRadius:3,barThickness:12},{label:'Yesterday',data:Array(24).fill(0),backgroundColor:'rgba(255,255,255,.12)',borderRadius:3,barThickness:12}]},options:bc()});
}
function renderFocus(){document.getElementById('fchips').innerHTML=['deep work','wind down','break time','focus block','no social'].map(f=>`<button class="fc${focus.includes(f)?' on':''}" onclick="tFocus('${f}')">${f}</button>`).join('');}
function tFocus(f){focus=focus.includes(f)?focus.filter(x=>x!==f):[...focus,f];renderFocus();}
renderFocus();
function renderRules(){document.getElementById('rlist').innerHTML=rules.map((r,i)=>`<div class="rr"><div class="ric" style="background:${r.bg}">${r.icon}</div><div class="rif"><div class="rt">${r.t}</div><div class="rd">${r.d}</div></div><label class="tg"><input type="checkbox" ${r.on?'checked':''} onchange="rules[${i}].on=this.checked"><span class="kn"></span></label></div>`).join('');}
renderRules();
function doAlerts(){
  if(!D.today)return;
  const ns=[];
  D.today.apps.forEach(a=>{if(a.over_limit)ns.push({c:col(a.app_name),m:`${a.app_name} exceeded ${fmt(a.limit_minutes)} limit`,t:'now'});});
  if(D.today.total_minutes>7*60)ns.push({c:'var(--am)',m:'Daily screen time exceeded 7 hours',t:'today'});
  if(ns.length){document.getElementById('nb').textContent=ns.length;document.getElementById('nb').style.display='';document.getElementById('nlist').innerHTML=ns.map(n=>`<div style="padding:12px 0;border-bottom:1px solid var(--border)"><div style="display:flex;align-items:center;gap:8px;margin-bottom:3px"><div style="width:7px;height:7px;border-radius:50%;background:${n.c};flex-shrink:0"></div><span style="font-size:13px;font-weight:500">${n.m}</span></div><div style="font-size:11px;color:var(--tx2);padding-left:15px">${n.t}</div></div>`).join('');}
}
function openModal(name){
  curApp=name;const a=D.today?.apps.find(x=>x.app_name===name);if(!a)return;
  document.getElementById('mt').textContent=a.app_name;document.getElementById('mt').style.color=col(a.app_name);
  document.getElementById('ms').textContent=`${fmt(a.minutes)} today  \u00b7  ${a.category}${a.over_limit?' \u26a0 over limit':''}`;
  document.getElementById('msr').innerHTML=[{v:fmt(a.minutes),l:'Today'},{v:fmt(a.minutes*7),l:'Est. week'},{v:a.limit_minutes?fmt(a.limit_minutes):'None',l:'Daily limit'}].map(s=>`<div class="mst"><div class="msv" style="color:${col(a.app_name)}">${s.v}</div><div class="msl">${s.l}</div></div>`).join('');
  document.getElementById('lsl').value=a.limit_minutes||0;document.getElementById('lvl').textContent=a.limit_minutes?fmt(a.limit_minutes):'None';
  killC('mchart');
  const lbls=Array.from({length:24},(_,i)=>i%6===0?(i<12?`${i||12}am`:`${i===12?12:i-12}pm`):'');
  C['mchart']=new Chart(document.getElementById('mchart'),{type:'bar',data:{labels:lbls,datasets:[{data:a.hourly||Array(24).fill(0),backgroundColor:col(a.app_name)+'bb',borderRadius:3,barThickness:14}]},options:{...bc(),scales:{x:{...bc().scales.x},y:{display:false}}}});
  document.getElementById('mbg').classList.add('open');
  const BROWSERS=['Chrome','Firefox','Edge','Safari','Brave','Opera'];
  const cpanel=document.getElementById('chrome-panel');
  if(cpanel){if(BROWSERS.includes(name)){cpanel.style.display='block';loadChromeAnalysis();}else{cpanel.style.display='none';}}
}
function closeModal(){document.getElementById('mbg').classList.remove('open');killC('mchart');}
async function saveLimit(){
  if(!curApp)return;const v=parseInt(document.getElementById('lsl').value)||0;
  try{if(v>0)await fetch(`${API}/api/limits`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app_name:curApp,limit_minutes:v})});else await fetch(`${API}/api/limits/${encodeURIComponent(curApp)}`,{method:'DELETE'});closeModal();await loadAll();toast(`Limit ${v?'saved':'cleared'} for ${curApp}`);}catch{toast('Failed - is the backend running?');}
}
const si=document.getElementById('search'),sr=document.getElementById('sres');
si.addEventListener('input',()=>{const q=si.value.trim().toLowerCase();if(!q){sr.classList.remove('open');return;}const hits=(D.today?.apps||[]).filter(a=>a.app_name.toLowerCase().includes(q));sr.innerHTML=hits.length?hits.map(a=>`<div class="sri" onclick="openModal('${a.app_name}')"><div class="srd" style="background:${col(a.app_name)}"></div><span class="srn">${a.app_name}</span><span class="srt">${fmt(a.minutes)}</span></div>`).join(''):`<div style="padding:10px 14px;font-size:13px;color:var(--tx2)">No apps found</div>`;sr.classList.add('open');});
si.addEventListener('keydown',e=>{if(e.key==='Escape'){si.value='';sr.classList.remove('open');si.blur();}});
document.addEventListener('click',e=>{if(!si.contains(e.target)&&!sr.contains(e.target))sr.classList.remove('open');});
const nb=[...document.querySelectorAll('.ni')];
document.addEventListener('keydown',e=>{if(e.target===si)return;const m={'1':0,'2':1,'3':2,'4':3,'5':4,'6':5};if(m[e.key]!==undefined){nb[m[e.key]]?.click();return;}if(e.key==='/')  {e.preventDefault();si.focus();}if(e.key==='Escape'){closeModal();document.getElementById('npanel').classList.remove('open');document.getElementById('spanel').classList.remove('open');document.getElementById('kh').classList.remove('show');}if(e.key==='?')toggleKbd();});
function go(n,b){document.querySelectorAll('.pg').forEach(p=>p.classList.remove('active'));document.getElementById('p-'+n).classList.add('active');document.querySelectorAll('.ni').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(n==='chrome')loadChromeFullPage();}
function toggleNotif(){document.getElementById('npanel').classList.toggle('open');document.getElementById('spanel').classList.remove('open');}
function toggleSettings(){document.getElementById('spanel').classList.toggle('open');document.getElementById('npanel').classList.remove('open');}
function toggleKbd(){document.getElementById('kh').classList.toggle('show');}
function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600);}
function exportReport(){const apps=D.today?.apps||[];if(!apps.length){toast('No data to export yet');return;}const rows=[['App','Minutes','Category','Over Limit','Daily Limit'],...apps.map(a=>[a.app_name,a.minutes,a.category,a.over_limit?'Yes':'No',a.limit_minutes||''])];const b=new Blob([rows.map(r=>r.join(',')).join('\n')],{type:'text/csv'});const u=URL.createObjectURL(b);const el=document.createElement('a');el.href=u;el.download=`burnout-${new Date().toISOString().slice(0,10)}.csv`;el.click();URL.revokeObjectURL(u);toast('Exported to CSV');}
function clearData(){if(confirm('Clear all data? Cannot be undone.'))toast('Data cleared');}
function killC(id){if(C[id]){C[id].destroy();delete C[id];}}
const GC='rgba(255,255,255,0.05)',TC='rgba(255,255,255,0.25)',MF={family:'Inter',size:10};
function bc(){return{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false},ticks:{color:TC,font:MF},border:{display:false}},y:{grid:{color:GC},ticks:{color:TC,font:MF},border:{display:false}}}};}

// ── Chrome analysis ────────────────────────────────────────────────────────
async function loadChromeAnalysis(){
  try{const r=await fetch(`${API}/api/chrome-analysis`);const data=await r.json();renderChromePanel(data);}
  catch(e){console.warn('Chrome analysis unavailable');}
}
function renderChromePanel(data){
  const el=document.getElementById('chrome-panel');if(!el)return;
  const s=data.summary,total=s.total_minutes||0,prodPct=s.productive_pct||0;
  const unprodPct=total>0?Math.round(s.unproductive_minutes/total*100):0,neutPct=Math.max(0,100-prodPct-unprodPct);
  const catColor=c=>c==='productive'?'#00D4A0':c==='unproductive'?'#FF5C5C':c==='neutral'?'#FFB020':'#8B90A7';
  const sites=data.title_analysis.slice(0,8),maxMins=Math.max(...sites.map(s=>s.minutes),1);
  el.innerHTML=`<div style="border-top:1px solid rgba(255,255,255,0.07);margin-top:16px;padding-top:16px">
    <div style="font-size:10px;font-weight:700;color:#4A4F66;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Chrome Tab Analysis
      ${data.extension_installed?'<span style="background:rgba(0,212,160,.15);color:#00D4A0;padding:2px 8px;border-radius:10px;margin-left:8px;font-size:9px">EXTENSION ACTIVE</span>':'<span style="background:rgba(255,255,255,.06);color:#8B90A7;padding:2px 8px;border-radius:10px;margin-left:8px;font-size:9px">TITLE ANALYSIS ONLY</span>'}
    </div>
    ${total>0?`<div style="display:flex;gap:10px;margin-bottom:14px">
      <div style="flex:1;background:rgba(0,212,160,.08);border:1px solid rgba(0,212,160,.2);border-radius:10px;padding:12px;text-align:center"><div style="font-size:20px;font-weight:700;color:#00D4A0">${prodPct}%</div><div style="font-size:10px;color:#8B90A7;margin-top:2px">Productive</div></div>
      <div style="flex:1;background:rgba(255,92,92,.08);border:1px solid rgba(255,92,92,.2);border-radius:10px;padding:12px;text-align:center"><div style="font-size:20px;font-weight:700;color:#FF5C5C">${unprodPct}%</div><div style="font-size:10px;color:#8B90A7;margin-top:2px">Unproductive</div></div>
      <div style="flex:1;background:rgba(255,176,32,.08);border:1px solid rgba(255,176,32,.2);border-radius:10px;padding:12px;text-align:center"><div style="font-size:20px;font-weight:700;color:#FFB020">${neutPct}%</div><div style="font-size:10px;color:#8B90A7;margin-top:2px">Neutral</div></div>
    </div>`:'<div style="font-size:13px;color:#8B90A7;margin-bottom:12px">No Chrome data yet today.</div>'}
    ${sites.length>0?`<div style="font-size:10px;font-weight:700;color:#4A4F66;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">Sites visited today</div>
    ${sites.map(s=>`<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04)">
      <div style="width:8px;height:8px;border-radius:50%;background:${catColor(s.category)};flex-shrink:0"></div>
      <span style="font-size:12px;flex:1;color:#F1F3F9;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.site}</span>
      <div style="flex:1;height:3px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden"><div style="height:100%;width:${Math.round(s.minutes/maxMins*100)}%;background:${catColor(s.category)};border-radius:3px"></div></div>
      <span style="font-size:11px;font-weight:600;color:${catColor(s.category)};min-width:36px;text-align:right">${s.minutes}m</span>
    </div>`).join('')}`:''}
    ${!data.extension_installed?`<div style="margin-top:14px;padding:12px;background:rgba(124,111,255,.08);border:1px solid rgba(124,111,255,.2);border-radius:10px">
      <div style="font-size:12px;font-weight:600;color:#9F93FF;margin-bottom:4px">Install the Chrome extension for full tab tracking</div>
      <div style="font-size:11px;color:#8B90A7;line-height:1.5">Install from the <code style="color:#9F93FF">chrome-extension/</code> folder to track all open tabs.</div>
    </div>`:''}
  </div>`;
}
function renderChromeFullPanel(data){
  const el=document.getElementById('chrome-full-panel');if(!el)return;
  const s=data.summary,total=s.total_minutes||0,prodPct=s.productive_pct||0;
  const unprodPct=total>0?Math.round(s.unproductive_minutes/total*100):0,neutPct=Math.max(0,100-prodPct-unprodPct);
  const catColor=c=>c==='productive'?'#00D4A0':c==='unproductive'?'#FF5C5C':c==='neutral'?'#FFB020':'#8B90A7';
  const catLabel=c=>c==='productive'?'Productive':c==='unproductive'?'Unproductive':c==='neutral'?'Neutral':'Other';
  const sites=data.title_analysis.slice(0,12),maxMins=Math.max(...sites.map(s=>s.minutes),1);
  const extBadge=data.extension_installed?'<span style="background:rgba(0,212,160,.15);color:#00D4A0;padding:3px 10px;border-radius:10px;font-size:11px;font-weight:600">Extension active</span>':'<span style="background:rgba(255,255,255,.06);color:#8B90A7;padding:3px 10px;border-radius:10px;font-size:11px;font-weight:600">Title analysis only</span>';
  el.innerHTML=`<div style="display:flex;align-items:center;gap:10px;margin-bottom:20px">${extBadge}${!data.extension_installed?'<span style="font-size:12px;color:var(--tx2)">Install from <code style="color:var(--vi2)">chrome-extension/</code> for full tab tracking</span>':''}</div>
  ${total>0?`<div class="s3" style="margin-bottom:20px">
    <div class="sc"><div class="sca" style="background:#00D4A0"></div><div class="sv" style="color:#00D4A0">${prodPct}%</div><div class="sl">Productive</div><div style="font-size:12px;color:var(--tx2);margin-top:6px">${s.productive_minutes}m</div></div>
    <div class="sc"><div class="sca" style="background:#FF5C5C"></div><div class="sv" style="color:#FF5C5C">${unprodPct}%</div><div class="sl">Unproductive</div><div style="font-size:12px;color:var(--tx2);margin-top:6px">${s.unproductive_minutes}m</div></div>
    <div class="sc"><div class="sca" style="background:#FFB020"></div><div class="sv" style="color:#FFB020">${neutPct}%</div><div class="sl">Neutral</div><div style="font-size:12px;color:var(--tx2);margin-top:6px">${s.neutral_minutes}m</div></div>
  </div>
  <div style="height:8px;background:rgba(255,255,255,.06);border-radius:8px;overflow:hidden;display:flex;margin-bottom:24px">
    <div style="width:${prodPct}%;background:#00D4A0;transition:width .8s ease"></div>
    <div style="width:${unprodPct}%;background:#FF5C5C;transition:width .8s ease"></div>
    <div style="width:${neutPct}%;background:#FFB020;transition:width .8s ease"></div>
  </div>`:`<div style="font-size:13px;color:var(--tx2);margin-bottom:20px;padding:20px;background:var(--card);border-radius:12px;border:1px solid var(--border)">No Chrome data yet today. Make sure the agent is running and Chrome is open.</div>`}
  <div class="sh" style="margin-bottom:14px">Sites visited today</div>
  ${sites.length>0?`<div style="background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden">
    ${sites.map((s,i)=>`<div style="display:flex;align-items:center;gap:14px;padding:12px 16px;border-bottom:${i<sites.length-1?'1px solid rgba(255,255,255,.04)':'none'}">
      <div style="width:10px;height:10px;border-radius:50%;background:${catColor(s.category)};flex-shrink:0;box-shadow:0 0 0 3px ${catColor(s.category)}22"></div>
      <span style="font-size:13px;font-weight:600;flex:1;color:var(--tx);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.site}</span>
      <span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:8px;background:${catColor(s.category)}18;color:${catColor(s.category)};white-space:nowrap">${catLabel(s.category)}</span>
      <div style="width:100px;height:4px;background:rgba(255,255,255,.06);border-radius:4px;overflow:hidden;flex-shrink:0"><div style="height:100%;width:${Math.round(s.minutes/maxMins*100)}%;background:${catColor(s.category)};border-radius:4px"></div></div>
      <span style="font-size:12px;font-weight:700;color:${catColor(s.category)};min-width:36px;text-align:right">${s.minutes}m</span>
    </div>`).join('')}
  </div>`:'<div style="font-size:13px;color:var(--tx2)">No sites identified yet.</div>'}`;
}
async function loadChromeFullPage(){
  try{const r=await fetch(`${API}/api/chrome-analysis`);const data=await r.json();renderChromeFullPanel(data);renderChromePanel(data);}
  catch(e){const el=document.getElementById('chrome-full-panel');if(el)el.innerHTML='<div class="es"><div class="es-title">Chrome analysis unavailable</div><div class="es-sub">Make sure the backend has the latest main.py deployed.</div></div>';}
}

loadAll();setInterval(loadAll,60000);loadChromeAnalysis();setInterval(loadChromeAnalysis,60000);

// expose to global scope for onclick handlers
window.go=go;window.toggleNotif=toggleNotif;window.toggleSettings=toggleSettings;
window.toggleKbd=toggleKbd;window.exportReport=exportReport;window.clearData=clearData;
window.openModal=openModal;window.closeModal=closeModal;window.saveLimit=saveLimit;
window.tFocus=tFocus;window.renderRules=renderRules;window.filterCat=filterCat;
window.loadChromeFullPage=loadChromeFullPage;
