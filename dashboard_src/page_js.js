(function(){
"use strict";
const D = window.RL_DATA, D2 = window.RL_DATA2, D3 = window.RL_DATA3;
const L = D.L, DS = 345, DE = 1320;
const PEAKS = [[360,540],[900,1140]];
const CLOCK = [15,20,30,60];
const FLEX = []; for (let T=15; T<=60; T++) if (D.plans[T]) FLEX.push(T);
const PROFILE = (()=>{const w={5:2,6:7,7:10,8:8,9:5,10:4,11:4,12:4,13:4,14:5,15:7,16:9,17:9,18:6,19:4,20:3,21:2};
  const s=Object.values(w).reduce((a,b)=>a+b,0); const o={}; for(const k in w) o[k]=w[k]/s; return o;})();
const singles = D.sections.filter(s=>s.track==="Single");
const SEASONS=["winter","spring","summer","fall"];
const seasonOfDay = d => { const m=Math.floor(d/30.5)%12; return m===11||m<=1?"winter":m<=4?"spring":m<=7?"summer":"fall"; };
const STAGES = {camden:[1.2], burl:[16.85], trenton:[L-0.3], split:[1.2, L-0.3]};
const STAGE_NAME = p => p<3?"Camden shop":p>30?"Trenton":"Burlington yard";

// model parameters (Policy lab edits these)
const P = { mdbf:3568, seasonMult:{winter:.85,spring:1.25,summer:.65,fall:1}, lateP:{winter:.06,spring:.03,summer:.05,fall:.09},
  hotShare:0.23, delayRegime:"njt_2026", dispatch:10, rescueMph:25, towMph:15, couple:10, blockMin:35, boardings:5600, repairDays:5, longOut:3, fleet:20,
  trainHour:547, vtts:13.6, waitMult:2, unplannedMult:1, busHour:170 };

// live-day state
const S = { cars:8, policy:"gtfs", reserve:1, season:"summer", stage:"burl", seed:7, rand:true, manual:[], t:410, playing:true, speed:3 };
let DAY=null;

// ---------- utils ----------
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const fmt = m => { m=Math.max(0,m); const h=Math.floor(m/60), mm=Math.floor(m%60); return String(h).padStart(2,"0")+":"+String(mm).padStart(2,"0"); };
const money = v => "$"+(Math.abs(v)>=1000? (v/1000).toFixed(v>=100000?0:1)+"k" : Math.round(v));
function interpTraj(tr,tau){ if(tau<=tr[0][0]) return tr[0][1];
  for(let i=1;i<tr.length;i++){ if(tau<=tr[i][0]){ const [t0,p0]=tr[i-1],[t1,p1]=tr[i]; return t1===t0?p1:p0+(p1-p0)*(tau-t0)/(t1-t0);} } return tr[tr.length-1][1]; }
function tauAt(tr,x){ for(let i=1;i<tr.length;i++){ const [t0,p0]=tr[i-1],[t1,p1]=tr[i];
  if((p0<=x&&x<=p1)||(p1<=x&&x<=p0)) return p1===p0?t0:t0+(t1-t0)*(x-p0)/(p1-p0);} return null; }
function posToLL(p){ const tk=D.track; let lo=0,hi=tk.length-1;
  if(p<=tk[0][2]) return [tk[0][0],tk[0][1]]; if(p>=tk[hi][2]) return [tk[hi][0],tk[hi][1]];
  while(hi-lo>1){const m=(lo+hi)>>1; if(tk[m][2]<=p) lo=m; else hi=m;}
  const a=tk[lo],b=tk[hi],f=(p-a[2])/(b[2]-a[2]||1); return [a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f]; }
const nearestStation = p => D.stations.reduce((b,s)=>Math.abs(s.pos-p)<Math.abs(b.pos-p)?s:b, D.stations[0]);
const inSingle = p => singles.find(s=>p>s.a+0.02&&p<s.b-0.02);

// ---------- plans -> blocks ----------
function choosePlan(cfg){
  if (cfg.policy==="fixed") return {kind:"periodic",Tp:20,Tb:30};
  if (cfg.policy==="gtfs") return {kind:"tt",key:"njt_current"};
  if (cfg.policy==="fixedKey") return {kind:"tt",key:cfg.key};
  if (cfg.policy==="prop"){ const K=Math.min(8,cfg.cars-cfg.reserve); if(K<3) return null;
    if(cfg.summerKey && cfg.season==="summer" && K>=7 && D3.tt[cfg.summerKey]) return {kind:"tt",key:cfg.summerKey};
    if(cfg.tiers && cfg.tiers[K] && D3.tt[cfg.tiers[K]]) return {kind:"tt",key:cfg.tiers[K]};
    return {kind:"tt",key:"proposed_T"+K}; }
  const menu = cfg.policy==="clock"?CLOCK:FLEX, n=cfg.cars-cfg.reserve;
  const feas = menu.filter(T=>D.plans[T]&&D.plans[T].n<=n);
  if (!feas.length) return null;
  const Tp=Math.min(...feas); let Tb=Math.max(Tp,30); if(!menu.includes(Tb)) Tb=Math.min(...menu.filter(T=>T>=Tb));
  return {kind:"periodic",Tp,Tb};
}
function periodsOf(plan){ const b=[...new Set([DS,DE,...PEAKS.flat()])].sort((x,y)=>x-y), out=[];
  for(let i=0;i<b.length-1;i++){ const a=b[i]; const pk=PEAKS.some(([x,y])=>a>=x&&a<y); out.push({a,b:b[i+1],T:pk?plan.Tp:plan.Tb,peak:pk}); } return out; }
const TTB={};
function ttBlocks(key){ if(TTB[key]) return TTB[key];
  const pos=D2.gtfs.stationPos, by={};
  D3.tt[key].trips.forEach(r=>{ const pts=r.t.map((m,k)=>m==null?null:[m,pos[k]]).filter(Boolean); pts.sort((x,y)=>x[0]-y[0]);
    const dep=pts[0][0]; const tr=pts.map(([m,p])=>[m-dep,p]); (by[r.b]=by[r.b]||[]).push({dir:r.d,dep,dur:tr[tr.length-1][0],tr}); });
  const isNJT=key==="njt_current";
  TTB[key]=Object.entries(by).map(([b,trips])=>{ trips.sort((x,y)=>x.dep-y.dep); const start=trips[0].dep, end=Math.max(...trips.map(t=>t.dep+t.dur)); return {label:(isNJT?"Block ":"Train ")+(isNJT?b:(+b+1)),start,end,trips}; }).sort((a,b)=>a.start-b.start);
  return TTB[key]; }
function gtfsBlocks(){ return ttBlocks("njt_current"); }
function blocksFor(plan){
  if (plan.kind==="tt") return ttBlocks(plan.key).map((b,i)=>({...b, idx:i, trips:b.trips.map(t=>({...t}))}));
  const out=[];
  periodsOf(plan).forEach(per=>{ const pl=D.plans[per.T], n=pl.n, T=per.T; const nbDur=pl.nb[pl.nb.length-1][0], sbDur=pl.sb[pl.sb.length-1][0];
    const slots=[]; for(let j=0;j<n;j++) slots.push({label:`Train ${j+1}`,start:per.a,end:per.b,trips:[],peak:per.peak});
    const k0=Math.ceil((per.a-DS)/T)-1;
    for(let k=k0;;k++){ const t=DS+k*T; if(t>=per.b) break;
      if(t>=per.a) slots[((k%n)+n)%n].trips.push({dir:"NB",dep:t,dur:nbDur,tr:pl.nb});
      const ts=t+pl.phi; if(ts>=per.a&&ts<per.b) slots[(((k-pl.shift)%n)+n)%n].trips.push({dir:"SB",dep:ts,dur:sbDur,tr:pl.sb}); }
    slots.forEach(s=>{ s.trips.sort((a,b)=>a.dep-b.dep); s.end=per.b; s.handover=true; out.push(s); });
  });
  out.forEach((b,i)=>b.idx=i); return out;
}
function planLabel(plan){ if(!plan) return "Bus bridge"; if(plan.kind==="tt") return D3.tt[plan.key].label;
  return `Peak every ${plan.Tp} min · base every ${plan.Tb} min`; }
function planTrains(plan){ if(!plan) return [0,0]; if(plan.kind==="tt"){ const m=D3.metrics[plan.key]; return [m.vehicles_peak,m.vehicles_midday]; } return [D.plans[plan.Tp].n, D.plans[plan.Tb].n]; }

// ---------- one simulated day ----------
function simulateDay(cfg){
  const rng=mulberry32(cfg.seed*9973+17);
  const plan=choosePlan(cfg);
  const ev=[], blocks=[], rescues=[]; const log=(t,cls,msg)=>ev.push({t,cls,msg});
  const day={plan,trips:[],blocks,rescues,ev,trainHours:0};
  if(!plan){ log(360,"f",`Only ${cfg.cars} cars with ${cfg.reserve} held as protect: not enough for any rail timetable. Bus bridge all day.`); day.totals=totals(day,Infinity); return day; }
  const season=cfg.season, mdbf=P.mdbf*P.seasonMult[season];
  const B=blocksFor(plan); day.B=B;
  B.forEach(b=>b.trips.forEach(t=>{ t.block=b.idx; t.status="ok"; t.holds=[]; t.delay=0; t.bg= rng()<P.lateP[season] ? 6.5+rng()*6 : 0; t.label=b.label; }));
  const stagePos=STAGES[cfg.stage||"burl"];
  const V=[]; for(let i=1;i<=cfg.cars;i++) V.push({id:i,failed:false,busyUntil:0,block:null,home:stagePos[i%stagePos.length]});
  const [np]=planTrains(plan);
  log(DS,"p",`Hold sheet: ${cfg.cars} cars. ${planLabel(plan)} (${np} trains at peak).`);
  const rate=(2*L/150)/mdbf; // failures per operating minute per train (~150-min round trip)
  // event queue
  const Q=[]; B.forEach(b=>Q.push({t:b.start,type:"start",b:b.idx}));
  (cfg.manual||[]).forEach(m=>Q.push({t:m.t,type:"fail",b:m.block,manual:true}));
  const pop=()=>{ let k=0; for(let i=1;i<Q.length;i++){ if(Q[i].t<Q[k].t || (Q[i].t===Q[k].t && Q[i].type==="fail" && Q[k].type!=="fail")) k=i; } return Q.splice(k,1)[0]; };
  const isFree=(v,t)=>!v.failed && v.busyUntil<=t && (!v.block || B[v.block.idx].end<=t || B[v.block.idx].vac<=t);
  B.forEach(b=>{ b.veh=null; b.vac=Infinity; b.busy=[]; });
  const activeTrip=(b,t)=>b.trips.find(x=>t>=x.dep&&t<x.dep+x.dur);
  const blockPos=(b,t)=>{ const a=activeTrip(b,t); if(a) return interpTraj(a.tr,t-a.dep); const prev=b.trips.filter(x=>x.dep+x.dur<=t).pop(); if(prev) return prev.dir==="NB"?L:0; const nx=b.trips.find(x=>x.dep>t); return nx?(nx.dir==="NB"?0:L):0; };
  const isBusy=(b,t)=>b.busy.some(([x,y])=>t>=x&&t<y);
  let shortLogged={};
  while(Q.length){
    const e=pop(); const b=B[e.b]; if(!b) continue;
    if(e.type==="start"){
      const free=V.filter(v=>isFree(v,e.t)); free.sort((x,y)=>(x.block?0:1)-(y.block?0:1)); // prefer cars coming off another block
      const v=free[0];
      if(v){ v.block=b; b.veh=v; if(cfg.rand && b.trips.length){ const tf=e.t-Math.log(1-rng())/rate; if(tf<b.end) Q.push({t:tf,type:"fail",b:b.idx}); } }
      else { b.vac=b.start; const key=Math.floor(b.start/30); if(b.trips.length && !shortLogged[key]){ shortLogged[key]=1; log(b.start,"f",`${fmt(b.start)}: no car free for ${b.label.toLowerCase()} — its ${b.trips.length} trip(s) are cancelled.`);} }
      continue;
    }
    // failure
    const tf=e.t; if(!b.veh || b.vac<=tf || isBusy(b,tf) || tf<b.start || tf>=b.end) continue;
    const veh=b.veh; veh.failed=true;
    const trip=activeTrip(b,tf); const pos=blockPos(b,tf);
    if(trip){ trip.status="failed"; trip.failAt=tf; }
    const where = trip?`near ${nearestStation(pos).name}`:`at ${pos>L/2?"Trenton":"Camden"} (layover)`;
    const sec=trip?inSingle(pos):null;
    log(tf,"f",`${e.manual?"You broke down":"Breakdown:"} car ${veh.id}, ${b.label.toLowerCase()}${trip?" ("+(trip.dir==="NB"?"to Trenton":"to Camden")+")":""} ${where}.${sec?" Single track: line blocked both ways for "+P.blockMin+" min.":""}`);
    if(sec) blocks.push({a:sec.a,b:sec.b,t0:tf,t1:tf+P.blockMin});
    const yard=D.yards.reduce((x,y)=>Math.abs(y.pos-pos)<Math.abs(x.pos-pos)?y:x, D.yards[0]);
    const spares=V.filter(v=>isFree(v,tf) && !v.block);  // cars never used today = protect cars
    const spares2=spares.length?spares:V.filter(v=>isFree(v,tf)); // or cars laid up after the peak
    let r;
    if(spares2.length){
      spares2.sort((x,y)=>Math.abs(x.home-pos)-Math.abs(y.home-pos)); const sp=spares2[0];
      const from=sp.block? (pos>L/2?L:0) : sp.home;
      const tDep=tf+P.dispatch, tArr=tDep+Math.abs(pos-from)/P.rescueMph*60, tC=tArr+P.couple, tEnd=tC+Math.abs(pos-yard.pos)/P.towMph*60;
      r={from,pos,yard:yard.pos,tf,tDep,tArr,tC,tEnd,spare:true,veh:sp.id};
      sp.busyUntil=tEnd+5; sp.block=b; b.veh=sp; b.busy.push([tf,tEnd+5]);
      log(tDep,"r",`Protect car ${sp.id} leaves ${sp.block&&from!==sp.home?"the terminal":STAGE_NAME(from)}; reaches the failed car at ${fmt(tArr)}, tows it to ${yard.name} by ${fmt(tEnd)}, then takes over.`);
      if(cfg.rand){ const nt=tEnd+5-Math.log(1-rng())/rate; if(nt<b.end) Q.push({t:nt,type:"fail",b:b.idx}); }
    } else {
      b.vac=tf;
      const cands=B.filter(k=>k!==b && k.veh && !k.veh.failed && k.vac>tf && k.start<=tf && k.end>tf && !isBusy(k,tf));
      if(cands.length){
        cands.sort((x,y)=>Math.abs(blockPos(x,tf)-pos)-Math.abs(blockPos(y,tf)-pos)); const k=cands[0];
        const from=blockPos(k,tf); const ct=activeTrip(k,tf); if(ct){ ct.status="curtailed"; ct.failAt=tf; }
        const tDep=tf+P.dispatch, tArr=tDep+Math.abs(pos-from)/P.rescueMph*60, tC=tArr+P.couple, tEnd=tC+Math.abs(pos-yard.pos)/P.towMph*60;
        r={from,pos,yard:yard.pos,tf,tDep,tArr,tC,tEnd,spare:false,veh:k.veh.id};
        k.busy.push([tf,tEnd+5]); k.veh.busyUntil=tEnd+5;
        log(tDep,"r",`No protect car free. ${k.label} is pulled from service to rescue; its trips until ${fmt(tEnd+5)} are cancelled, and ${b.label.toLowerCase()} is cancelled for the rest of its run.`);
      } else {
        const tDep=tf+30; r={from:yard.pos,pos,yard:yard.pos,tf,tDep,tArr:tDep+Math.abs(pos-yard.pos)/P.rescueMph*60,spare:false,veh:null};
        r.tC=r.tArr+P.couple; r.tEnd=r.tC+Math.abs(pos-yard.pos)/P.towMph*60; log(tDep,"r","No car available to rescue; shop crew recovers the failed car.");
      }
    }
    r.failedCar=veh.id; rescues.push(r);
  }
  // trip statuses, delays
  const trips=[]; B.forEach(b=>b.trips.forEach(t=>{ if(t.status==="ok" && (t.dep>=b.vac || isBusy(b,t.dep) || !b.veh&&b.vac===Infinity)) t.status="cancelled"; if(!b.veh && t.status==="ok") t.status="cancelled"; trips.push(t); }));
  const bl=blocks.slice().sort((x,y)=>x.t0-y.t0);
  trips.forEach(tr=>{ if(tr.status==="cancelled") return; let delay=tr.bg;
    for(const k of bl){ const ep=tr.dir==="NB"?k.a:k.b; const tau=tauAt(tr.tr,ep); if(tau==null) continue; const entry=tr.dep+delay+tau;
      if(tr.failAt!=null && entry>=tr.failAt) continue; if(entry>=k.t0-1 && entry<k.t1){ const d=k.t1-entry; tr.holds.push({tau,pos:ep,dur:d}); delay+=d; } }
    tr.delay=delay; if(tr.status==="ok" && delay>6) tr.status="late"; });
  trips.sort((a,b)=>a.dep-b.dep); trips.forEach((t,i)=>t.id=i);
  day.trips=trips;
  day.trainHours = B.reduce((s,b)=>s+(b.veh? (Math.min(b.end,b.vac)-b.start)/60:0),0);
  const nC=trips.filter(x=>x.status==="cancelled").length; if(nC) log(DE,"f",`End of day: ${nC} of ${trips.length} published trips cancelled.`);
  ev.sort((a,b)=>a.t-b.t); day.totals=totals(day,Infinity); return day;
}
function tripPos(tr,t){ const dep=tr.dep+tr.bg; let tau=t-dep; if(tau<0) return null;
  for(const h of tr.holds){ if(tau<=h.tau) break; if(tau<=h.tau+h.dur) return h.pos; tau-=h.dur; }
  if(tau>tr.dur) return null; return interpTraj(tr.tr,tau); }
function tripEnd(tr){ return tr.dep+tr.bg+tr.dur+tr.holds.reduce((a,h)=>a+h.dur,0); }
function avgWait(deps){ let W=0,Pn=0;
  for(const d of ["NB","SB"]){ const ts=deps[d].slice().sort((a,b)=>a-b); ts.push(DE+60); let prev=DS;
    for(const t of ts){ const te=Math.min(t,DE); if(te>prev){ const h=Math.floor(prev/60); const lam=P.boardings/2*(PROFILE[h]||0)/60; const g=te-prev; W+=lam*g*(t-prev-g/2); Pn+=lam*g; } prev=Math.max(prev,t);} }
  return Pn?W/Pn:NaN; }
function totals(day,t){
  const tr=day.trips.filter(x=>x.dep<=t);
  const pub=tr.length, canc=tr.filter(x=>x.status==="cancelled"||x.status==="curtailed").length, fail=tr.filter(x=>x.status==="failed").length;
  const late=tr.filter(x=>x.status==="late").length, ok=tr.filter(x=>x.status==="ok").length;
  const o={pub,canc,fail,late,ok,run:pub-canc,otp:pub?100*ok/pub:NaN};
  if(t===Infinity){ if(day.trips.length){ const dep={NB:[],SB:[]},pdp={NB:[],SB:[]};
      day.trips.forEach(x=>{ pdp[x.dir].push(x.dep); if(x.status!=="cancelled") dep[x.dir].push(x.dep+x.bg); });
      o.wait=avgWait(dep); o.waitPub=avgWait(pdp); } else { o.wait=NaN; o.waitPub=NaN; }
    o.trainHours=day.trainHours||0; o.opCost=o.trainHours*P.trainHour;
    o.busCost= day.plan? 0 : 16*2*3*P.busHour; // bus bridge: ~3 buses x 2 directions x 16 h
    o.riderCost= isNaN(o.wait)? P.boardings*(25*P.waitMult)/60*P.vtts : P.boardings*(o.wait*P.waitMult + Math.max(0,o.wait-o.waitPub)*P.unplannedMult)/60*P.vtts;
    o.total=o.opCost+o.busCost+o.riderCost;
    const mi=x=>Math.abs(x.tr[x.tr.length-1][1]-x.tr[0][1]);
    o.milesPub=day.trips.reduce((a,x)=>a+mi(x),0); o.milesOk=day.trips.filter(x=>x.status==="ok").reduce((a,x)=>a+mi(x),0);
    o.milesRun=day.trips.filter(x=>x.status==="ok"||x.status==="late").reduce((a,x)=>a+mi(x),0); }
  return o;
}

// ---------- headline metric: on-time trip-miles delivered / trip-miles promised by the normal timetable ----------
let BASE_MILES=null;
function baseMiles(){ if(BASE_MILES==null) BASE_MILES=ttBlocks("njt_current").reduce((a,b)=>a+b.trips.reduce((s,x)=>s+Math.abs(x.tr[x.tr.length-1][1]-x.tr[0][1]),0),0); return BASE_MILES; }
function otpFor(key,season){ const reg=(D3.delayRegimes||{})[P.delayRegime]; const d=reg?reg.tt:((D3.delay||{}).tt||{}); if(key==="bus") return 0; const r=d[key]; if(!r) return NaN;
  return season==="summer"? (1-P.hotShare)*r.normal.otp+P.hotShare*r.hot.otp : r.normal.otp; }
// ---------- year simulation (Policy lab) ----------
function simulateYear(policyCfg, runs, seed0){
  const res=[];
  for(let r=0;r<runs;r++){
    const rng=mulberry32(seed0+r*101); const pool=P.fleet-P.longOut; let repair=[];
    const geo=()=>Math.max(1,Math.ceil(Math.log(1-rng())/Math.log(1-1/P.repairDays)));
    for(let i=0;i<Math.floor(pool/2);i++) repair.push(geo());
    for(let day=0; day<365+60; day++){
      const avail=pool-repair.length; let nd=0; for(let i=0;i<avail;i++) if(rng()<0.01) nd++; for(let i=0;i<nd;i++) repair.push(geo());
      const A=Math.max(0,pool-repair.length); const season=seasonOfDay(day%365);
      const d=simulateDay({...policyCfg, cars:A, season, seed:Math.floor(rng()*1e9), rand:true, manual:[]});
      for(let i=0;i<d.rescues.length;i++) repair.push(geo());
      repair=repair.map(x=>x-1).filter(x=>x>0);
      if(day>=60){ const T=d.totals; const key=d.plan?(d.plan.kind==="tt"?d.plan.key:"periodic"):"bus"; const ot=otpFor(key,season);
        res.push({run:r,A,season,key,pub:T.pub,canc:T.canc+T.fail,ok:T.ok,wait:T.wait,waitPub:T.waitPub,op:T.opCost+T.busCost,rider:T.riderCost,fails:d.rescues.length,
          th:T.trainHours||0,milesPub:T.milesPub||0,milesOk:T.milesOk||0,milesOnTime:Math.min(baseMiles(),(T.milesOk||0))*ot}); }
    }
  }
  return res;
}

// ---------- map ----------
const svg=d3.select("#mapsvg"), mapEl=document.getElementById("map"), tip=document.getElementById("tip");
const gRoot=svg.append("g"), gBase=gRoot.append("g"), gTrack=gRoot.append("g"), gBlocks=gRoot.append("g"), gStations=gRoot.append("g"), gLabels=gRoot.append("g"), gTrains=gRoot.append("g");
let proj,path,zoomK=1,W0=0,H0=0;
const trackFeature={type:"LineString",coordinates:D.track.map(p=>[p[0],p[1]])};
const segLine=(a,b)=>{ const c=D.track.filter(p=>p[2]>a&&p[2]<b).map(p=>[p[0],p[1]]); return {type:"LineString",coordinates:[posToLL(a),...c,posToLL(b)]}; };
const PRIORITY=new Set(["Entertainment Center","Walter Rand Transportation Ctr","Pennsauken Transit Center","Palmyra","Riverside","Burlington Towne Ctr","Florence","Roebling","Bordentown","Trenton Transit Center","Beverly/Edgewater Park","Cass Street"]);
const prettyName=n=>n.replace("36Th","36th").replace("Walter Rand Transportation Ctr","Walter Rand TC").replace("Trenton Transit Center","Trenton TC").replace("Pennsauken Transit Center","Pennsauken TC");
function drawMap(){
  const r=mapEl.getBoundingClientRect(); if(!r.width) return; W0=r.width; H0=r.height; svg.attr("viewBox",`0 0 ${W0} ${H0}`);
  proj=d3.geoMercator().fitExtent([[30,56],[W0-120,H0-24]],trackFeature); path=d3.geoPath(proj);
  [gBase,gTrack,gStations,gLabels,gBlocks].forEach(g=>g.selectAll("*").remove());
  gBase.append("path").attr("d",path({type:"MultiLineString",coordinates:D.counties})).attr("fill","none").attr("stroke","var(--county)").attr("stroke-width",1).attr("stroke-dasharray","4 3").attr("vector-effect","non-scaling-stroke");
  D.river.forEach(l=>gBase.append("path").attr("d",path({type:"LineString",coordinates:l})).attr("fill","none").attr("stroke","var(--water)").attr("stroke-width",6).attr("stroke-linecap","round").attr("stroke-linejoin","round").attr("vector-effect","non-scaling-stroke"));
  const rl=proj([-74.93,40.08]); gBase.append("text").attr("class","sc").attr("x",rl[0]-4).attr("y",rl[1]-16).attr("transform",`rotate(-22 ${rl[0]} ${rl[1]})`).attr("fill","var(--water-ink)").attr("font-family","var(--display)").attr("font-style","italic").attr("font-size",15).attr("letter-spacing",".12em").text("DELAWARE RIVER");
  [["PENNSYLVANIA",-75.05,40.17],["NEW JERSEY",-74.86,39.99],["PHILADELPHIA",-75.2,39.965]].forEach(([t,x,y])=>{ const p=proj([x,y]); gBase.append("text").attr("class","sc").attr("x",p[0]).attr("y",p[1]).attr("text-anchor","middle").attr("fill","var(--muted)").attr("font-family","var(--display)").attr("font-weight",600).attr("font-size",14).attr("letter-spacing",".22em").attr("opacity",.7).text(t); });
  gTrack.append("path").attr("d",path(trackFeature)).attr("fill","none").attr("stroke","var(--surface)").attr("stroke-width",8).attr("vector-effect","non-scaling-stroke").attr("stroke-linecap","round");
  singles.forEach(s=>gTrack.append("path").attr("d",path(segLine(s.a,s.b))).attr("fill","none").attr("stroke","var(--single)").attr("stroke-width",7).attr("vector-effect","non-scaling-stroke"));
  gTrack.append("path").attr("d",path(trackFeature)).attr("fill","none").attr("stroke","var(--track)").attr("stroke-width",2.2).attr("vector-effect","non-scaling-stroke");
  D.sections.filter(s=>s.siding).forEach(s=>{ const p=proj(posToLL((s.a+s.b)/2)); gLabels.append("text").attr("class","sc lbl sid").attr("x",p[0]).attr("y",p[1]).attr("text-anchor","end").attr("fill","var(--single)").attr("font-weight",600).text(s.siding); });
  D.yards.forEach(y=>{ const p=proj(posToLL(y.pos)); gStations.append("rect").attr("class","yard").attr("data-cx",p[0]).attr("data-cy",p[1]).attr("fill","var(--surface)").attr("stroke","var(--ink)").attr("transform",`rotate(45 ${p[0]} ${p[1]})`).append("title").text(y.name); });
  const rs=d3.scaleSqrt().domain([0,1100]).range([3,8.5]);
  D.stations.forEach(s=>{ const p=proj([s.lon,s.lat]);
    gStations.append("circle").attr("class","stn").attr("cx",p[0]).attr("cy",p[1]).attr("data-r",rs(s.board||60)).attr("fill","var(--surface)").attr("stroke","var(--ink)").attr("stroke-width",1.6).attr("vector-effect","non-scaling-stroke")
      .on("mouseenter",ev=>showTip(ev,`<b>${prettyName(s.name)}</b><br>${s.board!=null?s.board.toLocaleString()+" weekday boardings (2024)":"Boardings not reported"}<br>Mile ${s.pos.toFixed(1)} from Camden`)).on("mouseleave",hideTip);
    gLabels.append("text").attr("class","sc lbl"+(PRIORITY.has(s.name)?" pri":"")).attr("x",p[0]).attr("y",p[1]).attr("fill","var(--ink-2)").attr("font-weight",500).text(prettyName(s.name)); });
  applyZoom(); render();
}
const zoom=d3.zoom().scaleExtent([1,9]).on("zoom",ev=>{ gRoot.attr("transform",ev.transform); zoomK=ev.transform.k; applyZoom(); render(); });
svg.call(zoom);
document.getElementById("zin").onclick=()=>svg.transition().duration(250).call(zoom.scaleBy,1.6);
document.getElementById("zout").onclick=()=>svg.transition().duration(250).call(zoom.scaleBy,1/1.6);
document.getElementById("zreset").onclick=()=>svg.transition().duration(300).call(zoom.transform,d3.zoomIdentity);
function applyZoom(){ const k=zoomK, small=W0<600, CORE=new Set(["Trenton TC","Walter Rand TC","Burlington Towne Ctr","Bordentown","Riverside","Pennsauken TC"]);
  gLabels.selectAll("text").each(function(){ const el=d3.select(this), sid=el.classed("sid"); el.attr("font-size",(sid?11:12)/k).attr("dx",(sid?-10:10)/k).attr("dy",(sid?-10:(this.textContent==="Entertainment Center"?27:12))/k); });
  gLabels.selectAll("text.lbl:not(.sid)").attr("display",function(){ const pri=this.classList.contains("pri"); if(k>=2.2) return null; if(!pri) return "none"; return (!small||CORE.has(this.textContent))?null:"none"; });
  gLabels.selectAll("text.sid").attr("display",small&&k<2?"none":null);
  gStations.selectAll("circle.stn").attr("r",function(){return +this.dataset.r/k;});
  gStations.selectAll("rect.yard").each(function(){ const x=+this.dataset.cx,y=+this.dataset.cy,s=10/k; d3.select(this).attr("x",x-s/2).attr("y",y-s/2).attr("width",s).attr("height",s).attr("stroke-width",1.5/k); });
  gBase.selectAll("text.sc").attr("font-size",function(){ return (this.textContent==="DELAWARE RIVER"?15:14)/k; }); }
function showTip(ev,html){ tip.innerHTML=html; tip.hidden=false; const r=mapEl.getBoundingClientRect(); let x=ev.clientX-r.left+12,y=ev.clientY-r.top+12; if(x>r.width-250) x-=260; tip.style.left=x+"px"; tip.style.top=y+"px"; }
function hideTip(){ tip.hidden=true; }
function trainsAt(t){ const out=[]; if(!DAY) return out;
  for(const tr of DAY.trips){ if(tr.status==="cancelled") continue; if(tr.failAt!=null&&t>=tr.failAt) continue; const p=tripPos(tr,t); if(p==null) continue; out.push({key:"t"+tr.id,pos:p,kind:tr.dir,tr}); }
  DAY.rescues.forEach((r,i)=>{ if(t<r.tf||t>r.tEnd) return; let fp=r.pos,rp=null;
    if(t>=r.tC){ const f=(t-r.tC)/Math.max(1,r.tEnd-r.tC); fp=r.pos+(r.yard-r.pos)*f; rp=fp; }
    else if(t>=r.tDep){ const f=Math.min(1,(t-r.tDep)/Math.max(1,r.tArr-r.tDep)); rp=r.from+(r.pos-r.from)*f; }
    else if(!r.spare&&r.veh) rp=r.from;
    out.push({key:"f"+i,pos:fp,kind:"fail",r}); if(rp!=null&&r.veh) out.push({key:"r"+i,pos:rp,kind:"rescue",r,off:t>=r.tC}); });
  return out; }
const reduceMotion=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function render(){ if(!proj) return; const t=S.t,k=zoomK;
  const bl=DAY?DAY.blocks.filter(b=>t>=b.t0&&t<b.t1):[];
  const bsel=gBlocks.selectAll("path").data(bl,d=>d.a+"_"+d.t0); bsel.exit().remove();
  bsel.enter().append("path").attr("fill","none").attr("stroke","var(--fail)").attr("stroke-width",11).attr("stroke-opacity",.55).attr("vector-effect","non-scaling-stroke").attr("stroke-linecap","round").attr("d",d=>path(segLine(d.a,d.b)));
  const data=trainsAt(t); const sel=gTrains.selectAll("g.train").data(data,d=>d.key); sel.exit().remove();
  const en=sel.enter().append("g").attr("class","train").style("cursor",d=>d.kind==="NB"||d.kind==="SB"?"pointer":"default");
  en.append("circle").attr("class","halo"); en.append("circle").attr("class","body");
  en.on("mouseenter",(ev,d)=>showTip(ev,tipFor(d))).on("mouseleave",hideTip).on("click",(ev,d)=>{ if(d.kind!=="NB"&&d.kind!=="SB") return; ev.stopPropagation(); S.manual.push({t:S.t+0.01,block:d.tr.block}); rebuild(); });
  const all=en.merge(sel);
  all.attr("transform",d=>{ const p=proj(posToLL(d.pos)); const o=d.kind==="rescue"&&d.off?7/k:0; return `translate(${p[0]+o},${p[1]-o})`; });
  all.select("circle.body").attr("r",d=>(d.kind==="rescue"?5.5:6.5)/k).attr("fill",d=>({NB:"var(--nb)",SB:"var(--sb)",fail:"var(--fail)",rescue:"var(--rescue)"}[d.kind])).attr("stroke","var(--surface)").attr("stroke-width",2/k);
  all.select("circle.halo").attr("r",d=>(d.kind==="fail"?7:(d.tr&&d.tr.status==="late"?10:0))/k).attr("fill","none").attr("stroke",d=>d.kind==="fail"?"var(--fail)":"var(--warn)").attr("stroke-width",d=>(d.kind==="fail"?2:2.2)/k).attr("stroke-dasharray",d=>d.kind==="fail"?null:`${3/k} ${2/k}`).classed("pulse",d=>d.kind==="fail"&&!reduceMotion); }
function tipFor(d){ if(d.kind==="fail") return `<b>Failed car ${d.r.failedCar}</b><br>Waiting for rescue since ${fmt(d.r.tf)}${S.t>=d.r.tC?"<br>Being towed to the yard":""}`;
  if(d.kind==="rescue") return `<b>Rescue: car ${d.r.veh}</b><br>${d.r.spare?"Protect car":"Pulled from passenger service"}<br>Clear by ${fmt(d.r.tEnd)}`;
  const tr=d.tr; return `<b>${tr.label} · ${tr.dir==="NB"?"to Trenton":"to Camden"}</b><br>Scheduled ${fmt(tr.dep)} from ${tr.dir==="NB"?"Camden":"Trenton"}<br>${tr.delay>0.5?`Running ${Math.round(tr.delay)} min late`:"On time"}<br><span style="opacity:.8">Click to break this train down</span>`; }

// ---------- marey ----------
const msvg=d3.select("#marey"); let mx,my;
function drawMarey(){ const el=document.getElementById("marey"); const r=el.getBoundingClientRect(); if(!r.width) return; const W=r.width,H=300,m={l:118,r:12,t:10,b:26};
  msvg.attr("viewBox",`0 0 ${W} ${H}`); msvg.selectAll("*").remove();
  mx=d3.scaleLinear().domain([DS,DE]).range([m.l,W-m.r]); my=d3.scaleLinear().domain([0,L]).range([H-m.b,m.t]);
  singles.forEach(s=>msvg.append("rect").attr("x",m.l).attr("width",W-m.l-m.r).attr("y",my(s.b)).attr("height",my(s.a)-my(s.b)).attr("fill","var(--single-soft)"));
  PEAKS.forEach(([a,b])=>msvg.append("rect").attr("x",mx(a)).attr("width",mx(b)-mx(a)).attr("y",m.t).attr("height",H-m.b-m.t).attr("fill","var(--ink)").attr("opacity",.035));
  const xa=msvg.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(mx).tickValues(d3.range(360,1321,60)).tickFormat(v=>fmt(v)).tickSize(4));
  xa.selectAll("text").attr("fill","var(--muted)").attr("font-size",11); xa.selectAll("line,path").attr("stroke","var(--rule)");
  D.stations.filter(s=>PRIORITY.has(s.name)&&s.name!=="Cass Street"&&s.name!=="Florence").forEach(s=>{ msvg.append("line").attr("x1",m.l).attr("x2",W-m.r).attr("y1",my(s.pos)).attr("y2",my(s.pos)).attr("stroke","var(--rule)").attr("stroke-width",.6);
    msvg.append("text").attr("x",m.l-6).attr("y",my(s.pos)+3.5).attr("text-anchor","end").attr("font-size",10.5).attr("fill","var(--muted)").text(prettyName(s.name)); });
  if(!DAY) return;
  DAY.blocks.forEach(b=>msvg.append("rect").attr("x",mx(b.t0)).attr("width",mx(b.t1)-mx(b.t0)).attr("y",my(b.b)).attr("height",my(b.a)-my(b.b)).attr("fill","var(--fail)").attr("opacity",.45));
  const line=d3.line().x(d=>mx(d[0])).y(d=>my(d[1]));
  DAY.trips.forEach(tr=>{ const pts=[]; const end=tr.failAt!=null?tr.failAt:tripEnd(tr);
    if(tr.status==="cancelled") for(const [tau,p] of tr.tr) pts.push([tr.dep+tau,p]);
    else for(let t=tr.dep+tr.bg;t<=end+0.01;t+=1){ const p=tripPos(tr,Math.min(t,end)); if(p!=null) pts.push([Math.min(t,end),p]); }
    if(pts.length<2) return;
    msvg.append("path").attr("d",line(pts)).attr("fill","none").attr("stroke",tr.status==="cancelled"?"var(--muted)":tr.dir==="NB"?"var(--nb)":"var(--sb)").attr("stroke-width",tr.status==="cancelled"?1:1.4).attr("stroke-dasharray",tr.status==="cancelled"?"3 3":null).attr("opacity",tr.status==="cancelled"?.5:.9);
    if(tr.status==="failed"){ const p=pts[pts.length-1]; msvg.append("path").attr("d",d3.symbol(d3.symbolCross,70)()).attr("transform",`translate(${mx(p[0])},${my(p[1])}) rotate(45)`).attr("fill","var(--fail)"); } });
  DAY.rescues.forEach(r=>{ if(!r.veh) return; msvg.append("path").attr("d",line([[r.tDep,r.from],[r.tArr,r.pos],[r.tC,r.pos],[r.tEnd,r.yard]])).attr("fill","none").attr("stroke","var(--rescue)").attr("stroke-width",2).attr("stroke-dasharray","5 2"); });
  msvg.append("line").attr("id","mcur").attr("y1",m.t).attr("y2",H-m.b).attr("stroke","var(--ink)").attr("stroke-width",1.5); moveCursor(); }
function moveCursor(){ if(mx) msvg.select("#mcur").attr("x1",mx(S.t)).attr("x2",mx(S.t)); }
msvg.on("click",ev=>{ const [x]=d3.pointer(ev); setT(Math.round(Math.max(DS,Math.min(DE,mx.invert(x))))); });

// ---------- live panels ----------
function recommendation(cars,season){ const s=season==="summer"||season==="winter"?"summer":"spring";
  const rows=D2.playbook.filter(r=>r.cars===Math.min(14,Math.max(3,cars))&&r.season===s); if(!rows.length) return null; return bestRow(rows); }
function kpi(v,k,cls){ return `<div class="kpi ${cls||""}"><div class="v">${v}</div><div class="k">${k}</div></div>`; }
function updatePanels(){
  const pl=DAY.plan; const [np,nb]=planTrains(pl);
  document.getElementById("planbox").innerHTML = !pl? `<span class="lab">Plan</span><div class="big">Bus bridge</div><div class="sub">Not enough cars for any rail timetable after holding ${S.reserve} protect car(s).</div>`
   : `<span class="lab">${S.policy==="fixed"||S.policy==="gtfs"?"Published plan (fixed)":"Plan chosen from the hold sheet"}</span><div class="big">${planLabel(pl)}</div>
      <div class="sub">${np} trains at peak, ${nb} midday · ${Math.max(0,S.cars-np)} car(s) spare at peak${S.cars<np?` · <b style="color:var(--fail)">${np-S.cars} train(s) short</b>`:""}</div>`;
  const rec=recommendation(S.cars,S.season);
  document.getElementById("advice").innerHTML = rec? `<b>Playbook for ${S.cars} cars (${S.season==="summer"||S.season==="winter"?"high":"low"}-failure season):</b> ${rec.policy} — ${rec.plan}. Expected ${rec.cancel_pct.toFixed(1)}% of trips cancelled.` : "";
  const now=pl?totals(DAY,S.t):null, tot=DAY.totals;
  const onLine=trainsAt(S.t).filter(d=>d.kind==="NB"||d.kind==="SB").length, failedNow=DAY.rescues.filter(r=>r.tf<=S.t).length, blockedNow=DAY.blocks.some(b=>S.t>=b.t0&&S.t<b.t1);
  const kn=document.getElementById("kpisNow"), kd=document.getElementById("kpisDay"), st=document.getElementById("status");
  if(!now){ kn.innerHTML=kpi("0","trains on the line")+kpi("—","trips run")+kpi("—","on time"); kd.innerHTML=kpi("100%","trips replaced by bus","bad")+kpi(money(tot.busCost),"bus bridge cost")+kpi(money(tot.riderCost),"rider time cost"); st.className="pill bad"; st.textContent="Bus bridge"; return; }
  kn.innerHTML=kpi(onLine,"trains on the line")+kpi(`${now.run}<small style="font-size:13px;color:var(--muted)">/${now.pub}</small>`,"trips run / scheduled")+kpi(now.canc,"cancelled",now.canc?"bad":"")+kpi(failedNow,"breakdowns",failedNow?"bad":"")+kpi(now.late,"late (>6 min)",now.late?"bad":"")+kpi(isNaN(now.otp)?"—":Math.round(now.otp)+"%","on time");
  kd.innerHTML=kpi((100*(tot.canc+tot.fail)/Math.max(1,tot.pub)).toFixed(1)+"%","trips lost",tot.canc+tot.fail?"bad":"good")+kpi(Math.round(tot.otp)+"%","on time (of scheduled)",tot.otp>=90?"good":"bad")+kpi(tot.wait.toFixed(1)+"<small style='font-size:12px;color:var(--muted)'> min</small>",`avg wait (plan ${tot.waitPub.toFixed(1)})`)
    +kpi(Math.round(tot.trainHours),"train-hours")+kpi(money(tot.opCost),"operating cost")+kpi(money(tot.riderCost),"rider time cost");
  if(blockedNow){ st.className="pill bad"; st.textContent="Line blocked"; } else if(DAY.rescues.some(r=>S.t>=r.tf&&S.t<=r.tEnd)){ st.className="pill warn"; st.textContent="Rescue in progress"; }
  else if(now.canc||failedNow){ st.className="pill warn"; st.textContent="Reduced service"; } else { st.className="pill good"; st.textContent="Normal service"; }
}
let lastLogN=-1;
function updateLog(){ const items=DAY.ev.filter(e=>e.t<=S.t); if(items.length===lastLogN) return; lastLogN=items.length;
  document.getElementById("log").innerHTML=items.slice().reverse().map(e=>`<div><time>${fmt(e.t)}</time><span class="${e.cls}">${e.msg}</span></div>`).join("")||`<div><time>—</time><span>Service starts 05:45.</span></div>`; }
const periodLabel=t=>t<360?"Early":t<540?"AM peak":t<900?"Midday":t<1140?"PM peak":"Evening";

// ---------- small chart helpers ----------
function axesChart(sel, xs, series, opt){ const el=document.querySelector(sel); const r=el.getBoundingClientRect(); if(!r.width) return; const W=r.width,H=r.height||230,m={l:44,r:12,t:series.length>1&&!opt.noLegend?26:10,b:28};
  const s=d3.select(el); s.attr("viewBox",`0 0 ${W} ${H}`); s.selectAll("*").remove();
  const x=(opt.xScale||d3.scaleLinear)().domain(opt.xDomain||d3.extent(xs)).range([m.l,W-m.r]);
  const ymax=opt.yMax||d3.max(series.flatMap(sr=>sr.y.filter(v=>v!=null)))*1.1; const y=d3.scaleLinear().domain([0,ymax]).nice().range([H-m.b,m.t]);
  s.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(opt.xTicks||6).tickFormat(opt.xFmt||null).tickSize(3)).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
  s.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W-m.l-m.r))).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.select(".domain").remove();g.selectAll("line").attr("stroke","var(--rule)").attr("stroke-opacity",.6);});
  series.forEach(sr=>{ if(opt.bars){ const bw=(x(xs[1])-x(xs[0]))/(series.length+1); const k=series.indexOf(sr);
      s.append("g").selectAll("rect").data(sr.y).join("rect").attr("x",(d,i)=>x(xs[i])-bw*series.length/2+k*bw).attr("width",bw-1).attr("y",d=>y(d)).attr("height",d=>y(0)-y(d)).attr("fill",sr.color).attr("rx",2).append("title").text((d,i)=>`${sr.name}: ${d}`);
    } else { s.append("path").attr("d",d3.line().defined(d=>d[1]!=null).x(d=>x(d[0])).y(d=>y(d[1])).curve(opt.step?d3.curveStepAfter:d3.curveLinear)(xs.map((v,i)=>[v,sr.y[i]]))).attr("fill","none").attr("stroke",sr.color).attr("stroke-width",2);
      if(opt.dots) s.append("g").selectAll("circle").data(xs.map((v,i)=>[v,sr.y[i]]).filter(d=>d[1]!=null)).join("circle").attr("cx",d=>x(d[0])).attr("cy",d=>y(d[1])).attr("r",3.5).attr("fill",sr.color).attr("stroke","var(--surface)").attr("stroke-width",1.5).append("title").text(d=>`${sr.name}: ${opt.xFmt?opt.xFmt(d[0]):d[0]} → ${(+d[1]).toFixed(1)}`); } });
  if(series.length>1&&!opt.noLegend){ let lx=m.l+6; const lg=s.append("g"); series.forEach(sr=>{ const g=lg.append("g").attr("transform",`translate(${lx},${m.t+4})`); g.append("rect").attr("width",10).attr("height",10).attr("rx",2).attr("fill",sr.color); const tx=g.append("text").attr("x",14).attr("y",9).attr("font-size",11).attr("fill","var(--ink-2)").text(sr.name); lx+=tx.node().getComputedTextLength()+30; }); }
  return {x,y,s}; }
const COLORS=["#2a78d6","#eb6834","#1baf7a","#eda100","#e87ba4","#4a3aa7","#6b736e"];

// ---------- playbook tab ----------
const POLS=[...new Set(D2.playbook.map(r=>r.policy))];
const CANCEL_CAP=5; // operating guardrail: do not recommend a plan that cancels more than 5% of its own trips unexpectedly
function bestRow(rows){ let rs=rows.filter(r=>r.rtd!=null&&!isNaN(r.rtd)); if(!rs.length) return rows[0];
  const okc=rs.filter(r=>r.cancel_pct<=CANCEL_CAP+0.05); if(okc.length) rs=okc; else return rs.reduce((b,r)=>r.cancel_pct<b.cancel_pct?r:b,rs[0]);
  return rs.reduce((b,r)=>(r.rtd>b.rtd+0.3||(Math.abs(r.rtd-b.rtd)<=0.3&&r.total<b.total))?r:b,rs[0]); }  // recommend only timetables that are conflict-free all day
function drawPlaybook(){ const season=document.getElementById("pbSeason").value; const rows=D2.playbook.filter(r=>r.season===season);
  const cars=[...new Set(rows.map(r=>r.cars))].sort((a,b)=>a-b);
  let html=`<thead><tr><th>Cars at 6 am</th><th>Recommended</th><th style="text-align:right">Trains (peak)</th><th style="text-align:right">Cancelled</th><th style="text-align:right">Reliable trip-miles</th><th style="text-align:right">Avg wait</th><th style="text-align:right">$/day vs today</th></tr></thead><tbody>`;
  const best={};
  cars.forEach(c=>{ const rs=rows.filter(r=>r.cars===c); const bst=bestRow(rs); best[c]=bst; const nj=rs.find(r=>r.policy==="Today's timetable")||bst; const d=bst.total-nj.total;
    html+=`<tr class="${c===S.cars?"cur":""}"><td class="num" style="text-align:left">${c}</td><td class="rec">${bst.policy}<div class="small">${bst.plan}</div></td><td class="num">${bst.trains_peak}</td><td class="num">${bst.cancel_pct.toFixed(1)}%<div class="small">NJT: ${nj.cancel_pct.toFixed(1)}%</div></td><td class="num"><b>${bst.rtd.toFixed(0)}%</b><div class="small">today: ${nj.rtd.toFixed(0)}%</div></td><td class="num">${bst.wait_total.toFixed(1)}</td><td class="num" style="color:${d<-50?"var(--good)":"var(--muted)"}">${d<-50?"−"+money(-d):"≈ same"}</td></tr>`; });
  document.getElementById("pbTable").innerHTML=html+"</tbody>";
  // rules: group consecutive car counts with the same recommended policy
  const groups=[]; cars.forEach(c=>{ const p=best[c].policy; const g=groups[groups.length-1]; if(g&&g.p===p) g.to=c; else groups.push({p,from:c,to:c}); });
  document.getElementById("pbRules").innerHTML=groups.map(g=>{ const r0=best[g.from], r1=best[g.to]; const nj0=rows.find(r=>r.cars===g.from&&r.policy==="Today's timetable"), nj1=rows.find(r=>r.cars===g.to&&r.policy==="Today's timetable");
    const rng=g.from===g.to?`${g.from} cars`:`${g.from}–${g.to} cars`;
    return `<div><b>${rng}:</b> ${g.p}. Reliable trip-miles ${Math.min(r0.rtd,r1.rtd).toFixed(0)}–${Math.max(r0.rtd,r1.rtd).toFixed(0)}% (today's timetable run with the same cars: ${Math.min(nj0.rtd,nj1.rtd).toFixed(0)}–${Math.max(nj0.rtd,nj1.rtd).toFixed(0)}%); cancels ${Math.min(r0.cancel_pct,r1.cancel_pct).toFixed(1)}–${Math.max(r0.cancel_pct,r1.cancel_pct).toFixed(1)}% of trips (today: ${Math.min(nj0.cancel_pct,nj1.cancel_pct).toFixed(1)}–${Math.max(nj0.cancel_pct,nj1.cancel_pct).toFixed(1)}%).</div>`; }).join("");
  const s1=POLS.map((p,k)=>({name:p,color:COLORS[k],y:cars.map(c=>{const r=rows.find(q=>q.cars===c&&q.policy===p);return r?r.cancel_pct:null;})}));
  const s2=POLS.map((p,k)=>({name:p,color:COLORS[k],y:cars.map(c=>{const r=rows.find(q=>q.cars===c&&q.policy===p);return r?r.rtd:null;})}));
  axesChart("#pbChart1",cars,s1,{dots:true,xTicks:cars.length,noLegend:true}); axesChart("#pbChart2",cars,s2,{dots:true,xTicks:cars.length,noLegend:true});
  document.getElementById("pbLegend").innerHTML=POLS.map((p,k)=>`<span><i class="dot" style="background:${COLORS[k]}"></i>${p}</span>`).join(""); }
document.getElementById("pbSeason").onchange=drawPlaybook;

// ---------- policy lab ----------
const LAB=[["lMdbf","oMdbf","mdbf",v=>(+v).toLocaleString()],["lRepair","oRepair","repairDays",v=>v],["lOut","oOut","longOut",v=>v],["lBlock","oBlock","blockMin",v=>v],["lCost","oCost","trainHour",v=>"$"+v],["lVtts","oVtts","vtts",v=>"$"+(+v).toFixed(2)],["lRuns","oRuns",null,v=>v]];
LAB.forEach(([id,out,key,f])=>{ const el=document.getElementById(id); const u=()=>{ document.getElementById(out).textContent=f(el.value); if(key) P[key]=+el.value; if(key==="trainHour"||key==="vtts"){ if(DAY){ DAY.totals=totals(DAY,Infinity); updatePanels(); drawCosts(); } } }; el.addEventListener("input",u); u(); });
const RT={8:"proposal_B8",7:"proposal_B7"};
const LABPOLS=[["Today's timetable",{policy:"gtfs",reserve:0}],["B8 every day",{policy:"fixedKey",key:"proposal_B8",reserve:0}],["Tiers T8–T3, 1 protect",{policy:"prop",reserve:1}],["Robust tiers, 1 protect",{policy:"prop",reserve:1,tiers:RT}],["Robust tiers + summer W7",{policy:"prop",reserve:1,tiers:RT,summerKey:"proposal_W7"}],["Robust tiers, no protect",{policy:"prop",reserve:0,tiers:RT}]];
const SCEN={S1:{mdbf:3661,repairDays:10,longOut:3,delayRegime:"alstom_2024_25"},S2:{mdbf:3568,repairDays:5,longOut:3,delayRegime:"njt_2026"},S3:{mdbf:10000,repairDays:5,longOut:3,delayRegime:"njt_2026"}};
document.getElementById("lScen").onchange=e=>{ const sc=SCEN[e.target.value]; Object.assign(P,sc); document.getElementById("lMdbf").value=Math.min(15000,sc.mdbf); document.getElementById("lRepair").value=sc.repairDays; document.getElementById("lOut").value=sc.longOut;
  ["lMdbf","lRepair","lOut"].forEach(id=>document.getElementById(id).dispatchEvent(new Event("input"))); };
let labResults=null;
document.getElementById("runLab").onclick=async ()=>{
  const btn=document.getElementById("runLab"), st=document.getElementById("labStatus"); btn.disabled=true; const runs=+document.getElementById("lRuns").value; const stage=document.getElementById("lStage").value;
  const out=[]; for(const [name,cfg] of LABPOLS){ st.textContent=`Simulating ${name}…`; await new Promise(r=>setTimeout(r,20)); const t0=performance.now();
    const res=simulateYear({...cfg,stage},runs,4242); out.push({name,res}); }
  labResults=out; st.textContent=`Done: ${runs} × 365 weekdays per policy.`; btn.disabled=false; drawLab(); };
function drawLab(){ if(!labResults) return;
  const agg=labResults.map(({name,res})=>{ const pub=d3.sum(res,r=>r.pub)||1; const BM=baseMiles(); return {name,rtd:100*d3.sum(res,r=>r.milesOnTime)/(res.length*BM),A:d3.mean(res,r=>r.A),canc:100*d3.sum(res,r=>r.canc)/pub,ot:100*d3.sum(res,r=>r.ok)/pub,wait:d3.mean(res.filter(r=>!isNaN(r.wait)),r=>r.wait),op:d3.mean(res,r=>r.op),rider:d3.mean(res,r=>r.rider),fails:d3.mean(res,r=>r.fails),bySeason:SEASONS.map(s=>{const q=res.filter(r=>r.season===s);return 100*d3.sum(q,r=>r.canc)/Math.max(1,d3.sum(q,r=>r.pub));})}; });
  const best=agg.reduce((b,r)=>r.rtd>b.rtd+0.3||(Math.abs(r.rtd-b.rtd)<=0.3&&r.op+r.rider<b.op+b.rider)?r:b,agg[0]);
  document.getElementById("labTable").innerHTML=`<thead><tr><th>Policy</th><th style="text-align:right">Reliable trip-miles</th><th style="text-align:right">Cars avail.</th><th style="text-align:right">Cancelled</th><th style="text-align:right">Avg wait</th><th style="text-align:right">Breakdowns/day</th><th style="text-align:right">Operating $/day</th><th style="text-align:right">Rider time $/day</th><th style="text-align:right">Total $/day</th></tr></thead><tbody>`+
    agg.map(r=>`<tr class="${r===best?"cur":""}"><td>${r.name}${r===best?' <span class="chip m">best</span>':""}</td><td class="num"><b>${r.rtd.toFixed(1)}%</b></td><td class="num">${r.A.toFixed(1)}</td><td class="num">${r.canc.toFixed(1)}%</td><td class="num">${r.wait.toFixed(1)}</td><td class="num">${r.fails.toFixed(2)}</td><td class="num">${money(r.op)}</td><td class="num">${money(r.rider)}</td><td class="num">${money(r.op+r.rider)}</td></tr>`).join("")+"</tbody>";
  // scatter
  const el=document.getElementById("labChart"); const R=el.getBoundingClientRect(); const W=R.width,H=R.height||230,m={l:52,r:12,t:12,b:34}; const s=d3.select(el); s.attr("viewBox",`0 0 ${W} ${H}`); s.selectAll("*").remove();
  const x=d3.scaleLinear().domain(d3.extent(agg,r=>r.op)).nice().range([m.l,W-m.r]), y=d3.scaleLinear().domain(d3.extent(agg,r=>r.rider)).nice().range([H-m.b,m.t]);
  if(x.domain()[0]===x.domain()[1]) x.domain([x.domain()[0]-1000,x.domain()[1]+1000]);
  s.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(5).tickFormat(v=>money(v))).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
  s.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(v=>money(v))).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
  s.append("text").attr("x",W-m.r).attr("y",H-4).attr("text-anchor","end").attr("font-size",11).attr("fill","var(--muted)").text("operating cost per weekday →");
  s.append("text").attr("x",m.l+4).attr("y",m.t+8).attr("font-size",11).attr("fill","var(--muted)").text("↑ rider waiting cost");
  agg.forEach((r,k)=>{ s.append("circle").attr("cx",x(r.op)).attr("cy",y(r.rider)).attr("r",7).attr("fill",COLORS[k]).attr("stroke","var(--surface)").attr("stroke-width",2).append("title").text(`${r.name}: ${money(r.op)} + ${money(r.rider)}`);
    const right=x(r.op)>W*0.62; s.append("text").attr("x",x(r.op)+(right?-10:10)).attr("y",y(r.rider)+4).attr("text-anchor",right?"end":"start").attr("font-size",11).attr("fill","var(--ink-2)").text(r.name); });
  axesChart("#labChart2",[0,1,2,3],agg.map((r,k)=>({name:r.name,color:COLORS[k],y:r.bySeason})),{bars:true,xTicks:4,xFmt:i=>SEASONS[i]||"",xDomain:[-0.6,3.6],noLegend:true});
}

// ---------- costs tab ----------
const EFFECTS=[
 ["Train operating cost (crew, energy, wear)","m","Train-hours × $/train-hour. Rate is an assumption bracketed by NTD 2024 light rail cost per revenue hour ($560 DO, $809 PT). Get NJT's marginal cost."],
 ["Rider waiting time","m","Random-arrival wait over actual gaps, valued at 2 × USDOT local personal VTTS ($13.60/h, 2015 $)."],
 ["Unplanned cancellations (unreliability)","m","Extra weight on wait beyond the published schedule; published plans avoid most of it."],
 ["Rescue moves (second car tied up)","m","Protect car or pulled train, travel from staging, coupling, tow to yard."],
 ["Single-track blockage delays","p","Fixed blockage time; no delay propagation or knock-on meets."],
 ["Crowding and comfort","p","Not in the cost. Capacity 184/car (90 seated); cancellations double the next train's load."],
 ["Bus bridge / supplemental buses","p","Only when no rail plan is feasible; bus cost at ~$170/bus-hour (NTD 2024 NJT bus $126 PT to $214 DO)."],
 ["Ridership loss from poor reliability","n","Not modeled. Frequency elasticities in TCRP Report 95 Ch. 9 suggest lost riders and fare revenue."],
 ["Extra breakdowns from extra car-miles","p","Failures scale with train-miles run, so a 9th train also raises failure risk; repair capacity is not modeled."],
 ["Maintenance shop capacity and repair order","n","Repairs are random with a mean; which car to fix first is a decision not yet modeled."],
 ["Operator (crew) availability","n","NJT now employs operators; crew shortages can bind before cars do."],
 ["Transfers at Trenton and Walter Rand","n","Missed NJT/SEPTA/PATCO connections when trips are cancelled are not counted."],
 ["Rider communication","n","Assumes riders know the published plan by 6 am; needs app/GTFS-realtime updates."],
 ["Freight window and night maintenance","n","Service limited to 5:45 am–10 pm; extensions for events not modeled."],
 ["Safety, equity and access","n","Grade-crossing exposure, ADA, and service to Camden and Trenton communities are not scored."]];
function drawCosts(){ if(!DAY) return; const T=DAY.totals;
  document.getElementById("costKpis").innerHTML=kpi(Math.round(T.trainHours||0),"train-hours today")+kpi(money(T.opCost+T.busCost),"operating + bus")+kpi(money(T.riderCost),"rider waiting time")+kpi(money(T.total),"total per weekday");
  const el=document.getElementById("costChart"); const R=el.getBoundingClientRect(); if(!R.width) return; const W=R.width,H=120; const s=d3.select(el); s.attr("viewBox",`0 0 ${W} ${H}`); s.selectAll("*").remove();
  const parts=[["Operating",T.opCost,COLORS[0]],["Bus bridge",T.busCost,COLORS[3]],["Rider waiting (planned)",P.boardings*(Math.min(T.wait,T.waitPub||T.wait)||25)*P.waitMult/60*P.vtts,COLORS[1]],["Unplanned extra",Math.max(0,T.riderCost-P.boardings*(Math.min(T.wait,T.waitPub||T.wait)||25)*P.waitMult/60*P.vtts),"var(--fail)"]].filter(p=>p[1]>1);
  const tot=d3.sum(parts,p=>p[1]); const x=d3.scaleLinear().domain([0,tot]).range([0,W-4]); let acc=0;
  parts.forEach(([n,v,c])=>{ s.append("rect").attr("x",x(acc)+2).attr("y",20).attr("width",Math.max(1,x(v)-2)).attr("height",34).attr("rx",3).attr("fill",c); if(x(v)>90) s.append("text").attr("x",x(acc)+8).attr("y",78).attr("font-size",12).attr("fill","var(--ink-2)").text(`${n}: ${money(v)}`); acc+=v; });
  document.getElementById("effectsTable").innerHTML=`<thead><tr><th>Cost or effect</th><th>In the model?</th><th>How / what is missing</th></tr></thead><tbody>`+EFFECTS.map(([a,k,c])=>`<tr><td>${a}</td><td><span class="chip ${k}">${k==="m"?"Modeled":k==="p"?"Partly":"Not yet"}</span></td><td>${c}</td></tr>`).join("")+"</tbody>"; }

// ---------- data tab ----------
function drawData(){ const K=D2.keys;
  document.getElementById("dataKpis").innerHTML=kpi(K.gtfs_weekday_trips,"weekday trips (Sept 2026)")+kpi(K.gtfs_max_trains+" / "+K.gtfs_midday_trains,"trains peak / midday")+kpi(K.gtfs_run_time_median+" min","scheduled end-to-end")+kpi(K.osm_min_runtime_at_limit_min+" min","run at posted speeds, no stops")
   +kpi(K.nb_walter_rand_am.gaps.join("/"),"AM peak gaps (min)")+kpi(K.nb_walter_rand_am.wait_random.toFixed(1)+" min","avg wait AM (even: "+K.nb_walter_rand_am.wait_even.toFixed(1)+")")+kpi(K.hot_days_mean_JJA,"days ≥ 90°F per summer")+kpi("$"+Math.round(K.ntd_cost_per_vrh_LR_DO_2024)+"–"+Math.round(K.ntd_cost_per_vrh_LR_PT_2024),"LR cost per revenue hour (NTD 2024)");
  // trains in service from GTFS blocks
  const B=gtfsBlocks(); const xs=d3.range(300,1350,5); const y=xs.map(t=>B.filter(b=>b.start<=t&&t<=b.end).length);
  axesChart("#dChart1",xs,[{name:"Trains",color:COLORS[0],y}],{step:true,xFmt:v=>fmt(v),xTicks:8,yMax:10});
  const w=D2.weather; axesChart("#dChart2",w.months,[{name:"Days ≥ 90°F",color:COLORS[1],y:w.hot},{name:"Days ≤ 32°F",color:COLORS[0],y:w.freeze},{name:"Days ≥ 0.5 in rain",color:COLORS[2],y:w.rain}],{bars:true,xTicks:12,xFmt:m=>"JFMAMJJASOND"[m-1]||"",xDomain:[0.4,12.6]});
  const pt=D2.ntd.PT, dd=D2.ntd.DO; const dates=pt.map(r=>new Date(r[0]+"-15"));
  axesChart("#dChart3",dates,[{name:"HBLR + River LINE (PT)",color:COLORS[0],y:pt.map(r=>r[1]/1e6)},{name:"Newark LR (DO)",color:COLORS[1],y:dd.map(r=>r[1]/1e6)}],{xScale:d3.scaleTime,xFmt:d3.timeFormat("%Y"),xTicks:6});
  const el=document.getElementById("dChart4"); const R=el.getBoundingClientRect(); if(R.width){ const W=R.width,H=150,m={l:70,r:12}; const s=d3.select(el); s.attr("viewBox",`0 0 ${W} ${H}`); s.selectAll("*").remove();
    const x=d3.scaleLinear().domain([0,L]).range([m.l,W-m.r]);
    [["NJDOT",34,singles.map(q=>[q.a,q.b])],["OSM",84,D2.osmSingle]].forEach(([lab,yy,iv])=>{ s.append("text").attr("x",m.l-8).attr("y",yy+14).attr("text-anchor","end").attr("font-size",12).attr("fill","var(--ink-2)").text(lab);
      s.append("rect").attr("x",m.l).attr("y",yy+6).attr("width",W-m.l-m.r).attr("height",12).attr("fill","var(--surface-2)").attr("stroke","var(--rule)");
      iv.forEach(([a,b])=>s.append("rect").attr("x",x(a)).attr("y",yy).attr("width",Math.max(1,x(b)-x(a))).attr("height",24).attr("rx",3).attr("fill","var(--single)").append("title").text(`${lab} single track ${a.toFixed(1)}–${b.toFixed(1)} mi`)); });
    s.append("g").attr("transform",`translate(0,${H-24})`).call(d3.axisBottom(x).ticks(8).tickFormat(v=>v+" mi")).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");}); } }


// ---------- timetables tab ----------
const TT_KEYS=Object.keys(D3.tt);
const ttSel=document.getElementById("ttSel");
ttSel.innerHTML=TT_KEYS.map(k=>`<option value="${k}">${D3.tt[k].label}</option>`).join("");
let TTS={key:"proposed_T8",dir:"NB",per:"am"}; ttSel.value=TTS.key;
ttSel.onchange=()=>{ TTS.key=ttSel.value; drawTT(); };
document.querySelectorAll("#ttDir button").forEach(b=>b.onclick=()=>{ TTS.dir=b.dataset.dir; document.querySelectorAll("#ttDir button").forEach(x=>x.setAttribute("aria-pressed",x===b)); drawTT(); });
document.querySelectorAll("#ttPer button").forEach(b=>b.onclick=()=>{ TTS.per=b.dataset.per; document.querySelectorAll("#ttPer button").forEach(x=>x.setAttribute("aria-pressed",x===b)); drawTT(); });
const PERW={am:[330,555],mid:[540,930],pm:[900,1155],eve:[1140,1340],all:[0,1500]};
const STN=["Entertainment Center","Aquarium","Cooper St/Rutgers","Walter Rand TC","36th Street","Pennsauken TC","Route 73/Pennsauken","Palmyra","Riverton","Cinnaminson","Riverside","Delanco","Beverly/Edgewater Park","Burlington South","Burlington Towne Ctr","Florence","Roebling","Bordentown","Cass Street","Hamilton Avenue","Trenton TC"];
const hm=x=>{ if(x==null) return "—"; const r=Math.round(x); return `${Math.floor(r/60)}:${String(r%60).padStart(2,"0")}`; };
function drawTT(){ const key=TTS.key, m=D3.metrics[key], T=D3.tt[key];
  document.getElementById("ttKpis").innerHTML=kpi(m.vehicles_peak+" / "+m.vehicles_midday,"trains peak / midday")+kpi(m.trips,"weekday trips")+kpi(Math.round(m.train_hours),"train-hours")+kpi(m.day_wait.toFixed(1)+" min","avg wait, Walter Rand")
    +kpi((m.NB_am_mean||0).toFixed(1)+" / "+(m.NB_am_max||0).toFixed(0),"AM mean / max gap →Trenton")+kpi((m.SB_am_mean||0).toFixed(1)+" / "+(m.SB_am_max||0).toFixed(0),"AM mean / max gap →Camden")+kpi((m.NB_mid_mean||0).toFixed(1),"midday gap (min)")+kpi(m.conflicts,"single-track conflicts",m.conflicts?"bad":"good");
  // comparison table
  const rows=TT_KEYS.map(k=>({k,...D3.metrics[k]}));
  document.getElementById("ttCompare").innerHTML=`<thead><tr><th>Timetable</th><th style="text-align:right">Trains peak/mid</th><th style="text-align:right">Trips</th><th style="text-align:right">Train-h</th><th style="text-align:right">AM gaps →Trenton (mean/max)</th><th style="text-align:right">Midday gap</th><th style="text-align:right">Avg wait</th><th style="text-align:right">Meet conflicts</th><th style="text-align:right">Cars incl. 1 protect</th></tr></thead><tbody>`+
    rows.map(r=>`<tr class="${r.k===key?"cur":""}" style="cursor:pointer" data-k="${r.k}"><td>${D3.tt[r.k].label}</td><td class="num">${r.vehicles_peak}/${r.vehicles_midday}</td><td class="num">${r.trips}</td><td class="num">${Math.round(r.train_hours)}</td><td class="num">${(r.NB_am_mean||0).toFixed(1)} / ${(r.NB_am_max||0).toFixed(0)}</td><td class="num">${(r.NB_mid_mean||0).toFixed(1)}</td><td class="num">${r.day_wait.toFixed(1)}</td><td class="num" style="color:${r.conflicts>1?"var(--fail)":"inherit"}">${r.conflicts}</td><td class="num">${r.vehicles_peak+1} cars</td></tr>`).join("")+"</tbody>";
  document.querySelectorAll("#ttCompare tr[data-k]").forEach(tr=>tr.onclick=()=>{ TTS.key=tr.dataset.k; ttSel.value=TTS.key; drawTT(); });
  // marey
  const el=document.getElementById("ttMarey"); const R=el.getBoundingClientRect(); if(R.width){ const W=R.width,H=280,mg={l:110,r:10,t:8,b:24}; const sv=d3.select(el); sv.attr("viewBox",`0 0 ${W} ${H}`); sv.selectAll("*").remove();
    const [w0,w1]=TTS.per==="all"?[330,1340]:PERW[TTS.per]; const x=d3.scaleLinear().domain([w0,w1]).range([mg.l,W-mg.r]), y=d3.scaleLinear().domain([0,L]).range([H-mg.b,mg.t]);
    singles.forEach(q=>sv.append("rect").attr("x",mg.l).attr("width",W-mg.l-mg.r).attr("y",y(q.b)).attr("height",y(q.a)-y(q.b)).attr("fill","var(--single-soft)"));
    sv.append("g").attr("transform",`translate(0,${H-mg.b})`).call(d3.axisBottom(x).ticks(8).tickFormat(v=>fmt(v))).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
    [0,3,5,10,14,15,17,20].forEach(k=>sv.append("text").attr("x",mg.l-6).attr("y",y(D2.gtfs.stationPos[k])+3.5).attr("text-anchor","end").attr("font-size",10.5).attr("fill","var(--muted)").text(STN[k]));
    const pos=D2.gtfs.stationPos; const ln=d3.line().x(d=>x(d[0])).y(d=>y(d[1]));
    sv.append("clipPath").attr("id","ttclip").append("rect").attr("x",mg.l).attr("y",0).attr("width",W-mg.l-mg.r).attr("height",H);
    const g=sv.append("g").attr("clip-path","url(#ttclip)");
    T.trips.forEach(r=>{ const pts=r.t.map((m,k)=>m==null?null:[m,pos[k]]).filter(Boolean); g.append("path").attr("d",ln(pts)).attr("fill","none").attr("stroke",r.d==="NB"?"var(--nb)":"var(--sb)").attr("stroke-width",1.4); }); }
  // grid
  const [w0,w1]=PERW[TTS.per]; const trips=T.trips.filter(r=>r.d===TTS.dir).map(r=>({...r,dep:r.d==="NB"?r.t.find(v=>v!=null):[...r.t].reverse().find(v=>v!=null)})).filter(r=>r.dep>=w0&&r.dep<w1).sort((a,b)=>a.dep-b.dep);
  const order=TTS.dir==="NB"?[...Array(21).keys()]:[...Array(21).keys()].reverse();
  document.getElementById("ttGrid").innerHTML=`<thead><tr><th>Station</th>${trips.map((r,i)=>`<th style="text-align:right">${i+1}</th>`).join("")}</tr></thead><tbody>`+order.map(k=>`<tr><td style="white-space:nowrap">${STN[k]}</td>${trips.map(r=>`<td class="num">${hm(r.t[k])}</td>`).join("")}</tr>`).join("")+"</tbody>";
}

// ---------- proposals ----------
const DL=D3.delay||{tt:{},slack:{}}, RP=D3.replay||{days:{}}, PROPS=D3.props||[];
const shortName=k=>{ const l=(D3.tt[k]||{}).label||k; return l.startsWith("NJT")?"NJT today":l.replace(/^Proposal /,"").replace(/^Proposed /,"").replace(/^Uniform /,"").split(/[:(]/)[0].trim(); };
const RPS={A:"njt_current",B:PROPS.find(p=>p.rec)?.key||"proposed_T8",day:"typical",per:"am"};
const pct=v=>(100*v).toFixed(0)+"%";
function drawProps(){
  const keys=PROPS.map(p=>p.key).filter(k=>DL.tt[k]&&D3.metrics[k]); const nj=DL.tt.njt_current, mj=D3.metrics.njt_current;
  const rec=PROPS.find(p=>p.rec); const r=rec&&DL.tt[rec.key], mr=rec&&D3.metrics[rec.key];
  document.getElementById("prKpis").innerHTML= rec? kpi(shortName(rec.key),"recommended weekday timetable")+kpi(`${pct(nj.normal.otp)} → ${pct(r.normal.otp)}`,"on time, today → recommended",r.normal.otp>=nj.normal.otp?"good":"bad")
    +kpi(`${pct(nj.hot.otp)} → ${pct(r.hot.otp)}`,"on time on a hot day",r.hot.otp>=nj.hot.otp?"good":"bad")+(()=>{ const a=mj.day_wait+nj.normal.mean_late, b=mr.day_wait+r.normal.mean_late; return kpi(`${a.toFixed(1)} → ${b.toFixed(1)}`,"wait + lateness per rider (min)",b<a-0.1?"good":b>a+0.1?"bad":""); })() : "";
  const cmp=(v,base,better)=>{ const d=v-base; if(Math.abs(d)<1e-9) return ""; const good=better==="hi"?d>0:d<0; return `style="color:${good?"var(--good)":"var(--fail)"}"`; };
  document.getElementById("prTable").innerHTML=`<thead><tr><th>Schedule</th><th>What changes</th><th style="text-align:right">Trains peak/mid</th><th style="text-align:right">Train-h</th><th style="text-align:right">Longest AM gap</th><th style="text-align:right">Avg wait</th><th style="text-align:right">On time</th><th style="text-align:right">Hot day</th><th style="text-align:right">Avg lateness</th><th style="text-align:right">Wait + lateness</th><th style="text-align:right">Held-for-meet min/day</th></tr></thead><tbody>`+
    keys.map(k=>{ const m=D3.metrics[k], d=DL.tt[k], p=PROPS.find(x=>x.key===k); const wl=m.day_wait+d.normal.mean_late, wl0=mj.day_wait+nj.normal.mean_late;
      return `<tr data-k="${k}" style="cursor:pointer" class="${k===RPS.B?"cur":""}"><td><b>${shortName(k)}</b>${p.rec?' <span class="pill good">recommended</span>':""}</td><td style="min-width:220px">${p.what}</td><td class="num">${m.vehicles_peak}/${m.vehicles_midday}</td><td class="num" ${cmp(m.train_hours,mj.train_hours,"lo")}>${Math.round(m.train_hours)}</td><td class="num" ${cmp(Math.max(m.NB_am_max,m.SB_am_max),Math.max(mj.NB_am_max,mj.SB_am_max),"lo")}>${Math.max(m.NB_am_max,m.SB_am_max).toFixed(0)}</td><td class="num" ${cmp(m.day_wait,mj.day_wait,"lo")}>${m.day_wait.toFixed(1)}</td><td class="num" ${cmp(d.normal.otp,nj.normal.otp,"hi")}>${pct(d.normal.otp)}</td><td class="num" ${cmp(d.hot.otp,nj.hot.otp,"hi")}>${pct(d.hot.otp)}</td><td class="num" ${cmp(d.normal.mean_late,nj.normal.mean_late,"lo")}>${d.normal.mean_late.toFixed(1)}</td><td class="num" ${cmp(wl,wl0,"lo")}><b>${wl.toFixed(1)}</b></td><td class="num" ${cmp(d.normal.knock,nj.normal.knock,"lo")}>${Math.round(d.normal.knock)}</td></tr>`; }).join("")+"</tbody>";
  document.querySelectorAll("#prTable tr[data-k]").forEach(tr=>tr.onclick=()=>{ if(RP.days.typical&&RP.days.typical[tr.dataset.k]){ RPS.B=tr.dataset.k; document.getElementById("rpB").value=RPS.B; } drawProps(); });
  // scatter
  { const el=document.getElementById("prScatter"), R=el.getBoundingClientRect(); if(R.width){ const W=R.width,H=300,m={l:44,r:14,t:10,b:34}; const sv=d3.select(el); sv.attr("viewBox",`0 0 ${W} ${H}`); sv.selectAll("*").remove();
    const pts=keys.map(k=>({k,x:D3.metrics[k].day_wait,y:100*DL.tt[k].normal.otp}));
    const x=d3.scaleLinear().domain([d3.min(pts,p=>p.x)-0.4,d3.max(pts,p=>p.x)+0.4]).range([m.l,W-m.r]), y=d3.scaleLinear().domain([Math.min(60,d3.min(pts,p=>p.y)-3),100]).range([H-m.b,m.t]);
    const ax=g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");};
    sv.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(6)).call(ax); sv.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5)).call(ax);
    sv.append("text").attr("x",W-m.r).attr("y",H-4).attr("text-anchor","end").attr("font-size",11).attr("fill","var(--muted)").text("scheduled average wait, min");
    const nj0=pts.find(p=>p.k==="njt_current"); if(nj0){ sv.append("line").attr("x1",x(nj0.x)).attr("x2",x(nj0.x)).attr("y1",m.t).attr("y2",H-m.b).attr("stroke","var(--rule)").attr("stroke-dasharray","3 3"); sv.append("line").attr("x1",m.l).attr("x2",W-m.r).attr("y1",y(nj0.y)).attr("y2",y(nj0.y)).attr("stroke","var(--rule)").attr("stroke-dasharray","3 3"); }
    pts.forEach(p=>{ const pr=PROPS.find(q=>q.key===p.k); const c=p.k==="njt_current"?"var(--muted)":pr.rec?"var(--good)":p.k.startsWith("uniform")?"var(--warn)":"var(--nb)";
      sv.append("circle").attr("cx",x(p.x)).attr("cy",y(p.y)).attr("r",p.k===RPS.B||p.k===RPS.A?6.5:4.5).attr("fill",c).attr("stroke","var(--surface)").attr("stroke-width",1.5).style("cursor","pointer").on("click",()=>{ RPS.B=p.k; document.getElementById("rpB").value=p.k; drawProps(); })
        .append("title").text(`${shortName(p.k)}: wait ${p.x.toFixed(1)} min, ${p.y.toFixed(0)}% on time`);
      sv.append("text").attr("x",x(p.x)+7).attr("y",y(p.y)+4).attr("font-size",11).attr("fill","var(--ink)").text(shortName(p.k)); }); } }
  // hot bars
  { const el=document.getElementById("prHot"), R=el.getBoundingClientRect(); if(R.width){ const W=R.width,H=300,m={l:78,r:14,t:18,b:24}; const sv=d3.select(el); sv.attr("viewBox",`0 0 ${W} ${H}`); sv.selectAll("*").remove();
    const y=d3.scaleBand().domain(keys).range([m.t,H-m.b]).padding(0.25), x=d3.scaleLinear().domain([0,100]).range([m.l,W-m.r]);
    sv.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x).ticks(5).tickFormat(v=>v+"%")).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
    keys.forEach(k=>{ const d=DL.tt[k]; const h=y.bandwidth()/2;
      sv.append("text").attr("x",m.l-6).attr("y",y(k)+y.bandwidth()/2+4).attr("text-anchor","end").attr("font-size",11).attr("fill","var(--ink)").text(shortName(k));
      sv.append("rect").attr("x",m.l).attr("y",y(k)).attr("height",h-1).attr("width",x(100*d.normal.otp)-m.l).attr("fill","var(--nb)");
      sv.append("rect").attr("x",m.l).attr("y",y(k)+h).attr("height",h-1).attr("width",x(100*d.hot.otp)-m.l).attr("fill","var(--sb)"); });
    [["normal day","var(--nb)"],["hot day","var(--sb)"]].forEach(([t,c],i)=>{ sv.append("rect").attr("x",m.l+i*100).attr("y",2).attr("width",10).attr("height",10).attr("fill",c); sv.append("text").attr("x",m.l+14+i*100).attr("y",11).attr("font-size",11).attr("fill","var(--muted)").text(t); }); } }
  document.getElementById("prRules").innerHTML=(D3.propRules||[]).map(t=>`<p>${t}</p>`).join("");
  drawReplay(); drawSlack(); drawYearTable();
}
function drawReplay(){ const day=RP.days[RPS.day]; if(!day) return;
  [["A","rpMA","rpKA","rpLabA"],["B","rpMB","rpKB","rpLabB"]].forEach(([w,sid,kid,lid])=>{ const k=RPS[w], R=day[k]; if(!R) return;
    const late=R.trips.map(t=>t.l).filter(v=>v!=null&&!isNaN(v));
    document.getElementById(lid).innerHTML=`<b>${w}: ${(D3.tt[k]||{}).label||k}</b>`;
    document.getElementById(kid).innerHTML=kpi(pct(R.otp),"on time this day",R.otp>=0.83?"good":R.otp<0.7?"bad":"")+kpi(R.mean_late.toFixed(1)+" min","average lateness at the end of the trip")+kpi(Math.max(...late).toFixed(0)+" min","latest arrival")+kpi(Math.round(R.knock)+" min","held for late opposing trains");
    const el=document.getElementById(sid), BB=el.getBoundingClientRect(); if(!BB.width) return; const W=BB.width,H=260,mg={l:110,r:10,t:8,b:24}; const sv=d3.select(el); sv.attr("viewBox",`0 0 ${W} ${H}`); sv.selectAll("*").remove();
    const [w0,w1]=RPS.per==="all"?[330,1340]:PERW[RPS.per]; const x=d3.scaleLinear().domain([w0,w1]).range([mg.l,W-mg.r]), y=d3.scaleLinear().domain([0,L]).range([H-mg.b,mg.t]);
    singles.forEach(q=>sv.append("rect").attr("x",mg.l).attr("width",W-mg.l-mg.r).attr("y",y(q.b)).attr("height",y(q.a)-y(q.b)).attr("fill","var(--single-soft)"));
    sv.append("g").attr("transform",`translate(0,${H-mg.b})`).call(d3.axisBottom(x).ticks(8).tickFormat(v=>fmt(v))).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
    const pos=D2.gtfs.stationPos; [0,3,5,10,14,15,17,20].forEach(q=>sv.append("text").attr("x",mg.l-6).attr("y",y(pos[q])+3.5).attr("text-anchor","end").attr("font-size",10.5).attr("fill","var(--muted)").text(STN[q]));
    const cid="rpclip"+w; sv.append("clipPath").attr("id",cid).append("rect").attr("x",mg.l).attr("y",0).attr("width",W-mg.l-mg.r).attr("height",H);
    const g=sv.append("g").attr("clip-path",`url(#${cid})`); const ln=d3.line().x(d=>x(d[0])).y(d=>y(d[1]));
    R.trips.forEach(t=>{ const c=t.d==="NB"?"var(--nb)":"var(--sb)";
      const pp=t.p.map((m,q)=>m==null?null:[m,pos[q]]).filter(Boolean), aa=t.a.map((m,q)=>m==null?null:[m,pos[q]]).filter(Boolean);
      g.append("path").attr("d",ln(pp)).attr("fill","none").attr("stroke",c).attr("stroke-width",1).attr("opacity",0.28);
      g.append("path").attr("d",ln(aa)).attr("fill","none").attr("stroke",c).attr("stroke-width",1.6).append("title").text(`${t.d==="NB"?"To Trenton":"To Camden"}, planned ${hm(pp[0][0])}: arrives ${t.l>0?t.l.toFixed(1)+" min late":"on time"}`);
      (t.w||[]).forEach(e=>g.append("circle").attr("cx",x(e[1])).attr("cy",y(e[0])).attr("r",2.5+Math.sqrt(e[2])*1.6).attr("fill","var(--fail)").attr("opacity",0.75).append("title").text(`Held ${e[2].toFixed(1)} min at ${fmt(e[1])} for a late opposing train`)); });
  }); }
function drawSlack(){ const el=document.getElementById("prSlack"), R=el.getBoundingClientRect(); if(!R.width) return; const W=R.width,H=240,m={l:40,r:10,t:22,b:30}; const sv=d3.select(el); sv.attr("viewBox",`0 0 ${W} ${H}`); sv.selectAll("*").remove();
  const bins=[[0,1,"<1"],[1,2,"1–2"],[2,3,"2–3"],[3,5,"3–5"],[5,10,"5–10"],[10,30,"10+"]];
  const share=k=>{ const h=DL.slack[k].hist, n=h.reduce((a,b)=>a+b,0); return bins.map(([a,b])=>h.slice(a,b).reduce((s,v)=>s+v,0)/n); };
  const A=share(RPS.A), B=share(RPS.B); const x=d3.scaleBand().domain(bins.map(b=>b[2])).range([m.l,W-m.r]).padding(0.2), y=d3.scaleLinear().domain([0,Math.max(...A,...B)*1.1]).range([H-m.b,m.t]);
  sv.append("g").attr("transform",`translate(0,${H-m.b})`).call(d3.axisBottom(x)).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
  sv.append("g").attr("transform",`translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(v=>Math.round(100*v)+"%")).call(g=>{g.selectAll("text").attr("fill","var(--muted)");g.selectAll("line,path").attr("stroke","var(--rule)");});
  bins.forEach((b,i)=>{ const bw=x.bandwidth()/2; sv.append("rect").attr("x",x(b[2])).attr("width",bw-1).attr("y",y(A[i])).attr("height",y(0)-y(A[i])).attr("fill","var(--muted)"); sv.append("rect").attr("x",x(b[2])+bw).attr("width",bw-1).attr("y",y(B[i])).attr("height",y(0)-y(B[i])).attr("fill","var(--good)"); });
  sv.append("text").attr("x",W-m.r).attr("y",H-2).attr("text-anchor","end").attr("font-size",11).attr("fill","var(--muted)").text("minutes of slack at the meet");
  [["A: "+shortName(RPS.A),"var(--muted)"],["B: "+shortName(RPS.B),"var(--good)"]].forEach(([t,c],i)=>{ sv.append("rect").attr("x",m.l+i*150).attr("y",4).attr("width",10).attr("height",10).attr("fill",c); sv.append("text").attr("x",m.l+14+i*150).attr("y",13).attr("font-size",11).attr("fill","var(--muted)").text(t); }); }
function drawYearTable(){ const Y=D3.year||[]; document.getElementById("prYear").innerHTML=`<thead><tr><th>Plan</th><th style="text-align:right">Reliable trip-miles</th><th style="text-align:right">Cancelled</th><th style="text-align:right">Summer</th></tr></thead><tbody>`+Y.map(r=>`<tr><td>${r.name}</td><td class="num"><b>${r.rtd!=null?r.rtd.toFixed(1)+"%":"—"}</b></td><td class="num">${r.cancel_pct.toFixed(1)}%</td><td class="num">${r.bySeason.summer.toFixed(1)}%</td></tr>`).join("")+"</tbody>"; }
(function(){ const opts=Object.keys(RP.days.typical||{}).map(k=>`<option value="${k}">${shortName(k)}</option>`).join("");
  const a=document.getElementById("rpA"), b=document.getElementById("rpB"); a.innerHTML=opts; b.innerHTML=opts; a.value=RPS.A; b.value=RPS.B;
  a.onchange=()=>{ RPS.A=a.value; drawProps(); }; b.onchange=()=>{ RPS.B=b.value; drawProps(); };
  document.querySelectorAll("#rpDay button").forEach(x=>x.onclick=()=>{ RPS.day=x.dataset.day; document.querySelectorAll("#rpDay button").forEach(y=>y.setAttribute("aria-pressed",y===x)); drawReplay(); });
  document.querySelectorAll("#rpPer button").forEach(x=>x.onclick=()=>{ RPS.per=x.dataset.per; document.querySelectorAll("#rpPer button").forEach(y=>y.setAttribute("aria-pressed",y===x)); drawReplay(); }); })();

// ---------- headless evaluation (used to produce the report's tables) ----------
window.RL_EVAL={
  setP(o){ Object.assign(P,o); return P; },
  playbook(days=300){ const out=[]; const RT2={8:"proposal_B8",7:"proposal_B7"}; const BM=baseMiles();
    const pols=[["Today's timetable",{policy:"gtfs",reserve:0}],["B8 every day",{policy:"fixedKey",key:"proposal_B8",reserve:0}],["Robust tiers, 0 protect",{policy:"prop",reserve:0,tiers:RT2}],["Robust tiers, 1 protect",{policy:"prop",reserve:1,tiers:RT2}],["Robust tiers, 2 protect",{policy:"prop",reserve:2,tiers:RT2}],["Tiers T8–T3, 1 protect",{policy:"prop",reserve:1}]];
    for(const season of ["summer","spring"]) for(let A=3;A<=14;A++) for(const [name,cfg] of pols){ const plan=choosePlan({...cfg,cars:A,season}); if(!plan) continue;
      let pub=0,canc=0,ok=0,w=0,wp=0,op=0,rid=0,n=0,fails=0,mot=0,mrun=0; const rng=mulberry32(A*1000+(season==="summer"?1:2));
      for(let d=0;d<days;d++){ const day=simulateDay({...cfg,cars:A,season,stage:"burl",seed:Math.floor(rng()*1e9),rand:true,manual:[]}); const T=day.totals;
        const key=day.plan?(day.plan.kind==="tt"?day.plan.key:"periodic"):"bus"; const ot=otpFor(key,season);
        pub+=T.pub; canc+=T.canc+T.fail; ok+=T.ok; w+=T.wait; wp+=Math.max(0,T.wait-T.waitPub); op+=T.opCost; rid+=T.riderCost; n++; fails+=day.rescues.length; mot+=Math.min(BM,T.milesOk||0)*ot; mrun+=Math.min(BM,T.milesOk||0); }
      const [np]=planTrains(plan); out.push({season,cars:A,policy:name,plan:planLabel(plan),trains_peak:np,cancel_pct:100*canc/pub,ontime_pct:100*mot/Math.max(1,mrun),rtd:100*mot/(n*BM),wait:w/n,excess:wp/n,wait_total:(w+wp)/n,op_cost:op/n,rider_cost:rid/n,total:(op+rid)/n,fails:fails/n}); }
    return out; },
  year(runs=5, stage="burl"){ return LABPOLS.map(([name,cfg])=>{ const res=simulateYear({...cfg,stage},runs,4242); const pub=res.reduce((a,r)=>a+r.pub,0);
      const bySeason={}; SEASONS.forEach(s=>{ const q=res.filter(r=>r.season===s); bySeason[s]=100*q.reduce((a,r)=>a+r.canc,0)/Math.max(1,q.reduce((a,r)=>a+r.pub,0)); });
      return {name,A:res.reduce((a,r)=>a+r.A,0)/res.length,cancel_pct:100*res.reduce((a,r)=>a+r.canc,0)/pub,ontime_pct:100*res.reduce((a,r)=>a+r.ok,0)/pub,wait:res.filter(r=>!isNaN(r.wait)).reduce((a,r)=>a+r.wait,0)/res.filter(r=>!isNaN(r.wait)).length,op:res.reduce((a,r)=>a+r.op,0)/res.length,rider:res.reduce((a,r)=>a+r.rider,0)/res.length,fails:res.reduce((a,r)=>a+r.fails,0)/res.length,bySeason}; }); },
  yearP(list, runs=5){ return list.map(([name,cfg])=>{ const res=simulateYear({...cfg,stage:"burl"},runs,4242); const pub=res.reduce((a,r)=>a+r.pub,0);
      const bySeason={}; SEASONS.forEach(s=>{ const q=res.filter(r=>r.season===s); bySeason[s]=100*q.reduce((a,r)=>a+r.canc,0)/Math.max(1,q.reduce((a,r)=>a+r.pub,0)); });
      const BM=baseMiles(), runsIdx=[...new Set(res.map(x=>x.run))];
      const rtdRun=runsIdx.map(k=>{ const q=res.filter(x=>x.run===k); return 100*q.reduce((a,x)=>a+x.milesOnTime,0)/(q.length*BM); }).sort((a,b)=>a-b);
      const rtdSeason={}; SEASONS.forEach(s=>{ const q=res.filter(r=>r.season===s); rtdSeason[s]=100*q.reduce((a,x)=>a+x.milesOnTime,0)/Math.max(1,q.length*BM); });
      const keyShare={}; res.forEach(x=>keyShare[x.key]=(keyShare[x.key]||0)+1/res.length);
      return {name,rtd:100*res.reduce((a,x)=>a+x.milesOnTime,0)/(res.length*BM),rtd_min:rtdRun[0],rtd_max:rtdRun[rtdRun.length-1],rtdSeason,
        delivered:100*res.reduce((a,x)=>a+Math.min(BM,x.milesOk),0)/(res.length*BM),onTimeShare:100*res.reduce((a,x)=>a+x.milesOnTime,0)/Math.max(1,res.reduce((a,x)=>a+Math.min(BM,x.milesOk),0)),A:res.reduce((a,x)=>a+x.A,0)/res.length,
        Aq:[0.05,0.5,0.95].map(p=>{ const v=res.map(x=>x.A).sort((a,b)=>a-b); return v[Math.floor(p*(v.length-1))]; }),
        Aseason:Object.fromEntries(SEASONS.map(s=>{ const q=res.filter(x=>x.season===s).map(x=>x.A); return [s,{mean:q.reduce((a,b)=>a+b,0)/Math.max(1,q.length),pLt8:q.filter(v=>v<8).length/Math.max(1,q.length),pGe12:q.filter(v=>v>=12).length/Math.max(1,q.length)}]; })),
        th:res.reduce((a,x)=>a+x.th,0)/res.length,fails_per_day:res.reduce((a,x)=>a+x.fails,0)/res.length,keyShare,
        cancel_pct:100*res.reduce((a,r)=>a+r.canc,0)/pub,pub_per_day:pub/res.length,wait:res.filter(r=>!isNaN(r.wait)).reduce((a,r)=>a+r.wait,0)/res.filter(r=>!isNaN(r.wait)).length,op:res.reduce((a,r)=>a+r.op,0)/res.length,bySeason}; }); },
  staging(runs=5){ return ["camden","burl","trenton","split"].map(st=>{ const res=simulateYear({policy:"prop",reserve:1,stage:st},runs,777); const pub=res.reduce((a,r)=>a+r.pub,0); return {stage:st,cancel_pct:100*res.reduce((a,r)=>a+r.canc,0)/pub,ontime_pct:100*res.reduce((a,r)=>a+r.ok,0)/pub}; }); }
};

// ---------- tabs ----------
const TABS=["live","tt","prop","play","lab","cost","data","about"];
function showTab(k){ TABS.forEach(t=>{ const on=t===k; document.getElementById("tab-"+t).setAttribute("aria-selected",on); document.getElementById("pg-"+t).hidden=!on; });
  try{ localStorage.setItem("rl-tab",k); }catch(e){}
  requestAnimationFrame(()=>{ if(k==="live"){ drawMap(); drawMarey(); } if(k==="play") drawPlaybook(); if(k==="lab") drawLab(); if(k==="cost") drawCosts(); if(k==="data") drawData(); if(k==="tt") drawTT(); if(k==="prop") drawProps(); }); }
TABS.forEach(t=>document.getElementById("tab-"+t).onclick=()=>showTab(t));

// ---------- controls ----------
function setT(t){ S.t=t; document.getElementById("tslider").value=Math.round(t); tick(true); }
function rebuild(){ DAY=simulateDay(S); lastLogN=-1; drawMarey(); updatePanels(); updateLog(); render(); drawCosts(); }
document.getElementById("cars").addEventListener("input",e=>{ S.cars=+e.target.value; document.getElementById("carsOut").textContent=S.cars; S.manual=[]; rebuild(); });
document.querySelectorAll("#policySeg button").forEach(b=>b.onclick=()=>{ S.policy=b.dataset.pol; document.querySelectorAll("#policySeg button").forEach(x=>x.setAttribute("aria-pressed",x===b)); syncRes(); S.manual=[]; rebuild(); });
document.querySelectorAll("#resSeg button").forEach(b=>b.onclick=()=>{ S.reserve=+b.dataset.res; document.querySelectorAll("#resSeg button").forEach(x=>x.setAttribute("aria-pressed",x===b)); S.manual=[]; rebuild(); });
function syncRes(){ document.querySelectorAll("#resSeg button").forEach(x=>x.disabled=S.policy==="gtfs"); }
document.getElementById("season").onchange=e=>{ S.season=e.target.value; rebuild(); };
document.getElementById("stage").onchange=e=>{ S.stage=e.target.value; rebuild(); };
document.getElementById("randFail").onchange=e=>{ S.rand=e.target.checked; rebuild(); };
document.getElementById("newDay").onclick=()=>{ S.seed=Math.floor(Math.random()*1e6); S.manual=[]; rebuild(); };
document.getElementById("clearManual").onclick=()=>{ S.manual=[]; rebuild(); };
document.getElementById("tslider").addEventListener("input",e=>{ S.t=+e.target.value; tick(true); });
document.querySelectorAll("[data-jump]").forEach(b=>b.onclick=()=>setT(+b.dataset.jump));
document.querySelectorAll("[data-speed]").forEach(b=>b.onclick=()=>{ S.speed=+b.dataset.speed; document.querySelectorAll("[data-speed]").forEach(x=>x.setAttribute("aria-pressed",x===b)); });
const playBtn=document.getElementById("playBtn");
function setPlaying(p){ S.playing=p; playBtn.textContent=p?"Pause":"Play"; }
playBtn.onclick=()=>{ if(!S.playing&&S.t>=DE) S.t=DS; setPlaying(!S.playing); };
document.addEventListener("keydown",e=>{ if(e.code==="Space"&&!["INPUT","SELECT","BUTTON"].includes(document.activeElement.tagName)&&!document.getElementById("pg-live").hidden){ e.preventDefault(); playBtn.click(); } });
let lastPanel=0;
function tick(force){ document.getElementById("clock").textContent=fmt(S.t); document.getElementById("periodLabel").textContent=periodLabel(S.t); render(); moveCursor();
  const now=performance.now(); if(force||now-lastPanel>250){ lastPanel=now; updatePanels(); updateLog(); document.getElementById("tslider").value=Math.round(S.t); } }
let lastFrame=performance.now();
function loop(ts){ const dt=(ts-lastFrame)/1000; lastFrame=ts; if(S.playing&&!document.getElementById("pg-live").hidden){ S.t=Math.min(DE,S.t+dt*S.speed); if(S.t>=DE) setPlaying(false); tick(false); } requestAnimationFrame(loop); }
(function pickSeed(){ for(let s=1;s<200;s++){ S.seed=s; const d=simulateDay(S); if(d.rescues.some(r=>r.tf>400&&r.tf<520)) return; } S.seed=7; })();
if(reduceMotion) setPlaying(false);
syncRes();
let rz; window.addEventListener("resize",()=>{ clearTimeout(rz); rz=setTimeout(()=>{ const k=TABS.find(t=>!document.getElementById("pg-"+t).hidden); showTab(k); },150); });
DAY=simulateDay(S);
let startTab="live"; try{ const v=localStorage.getItem("rl-tab"); if(TABS.includes(v)) startTab=v; }catch(e){}
if(/^#(live|tt|prop|play|lab|cost|data|about)$/.test(location.hash)) startTab=location.hash.slice(1);
showTab(startTab); updatePanels(); updateLog(); tick(true);
requestAnimationFrame(loop);
})();
