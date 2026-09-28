// Day engine from the Team 22 dashboard (river_line_sim.html), unchanged: plans -> blocks -> one simulated day
// with random breakdowns, rescues (protect car or a train pulled from service), single-track blockages and cancellations.
function RLEngine(D, D2, D3){
"use strict";
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

return {simulateDay, tripPos, tripEnd, totals, posToLL, P, planLabel, planTrains, fmt, singles, DS, DE, L, nearestStation};
}
