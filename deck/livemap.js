// ---------- live line map (the dashboard's Live day tab, compact) ----------
(function(){
  const LM=D.lm, E=RLEngine(LM.D,LM.D2,LM.D3), MD=LM.D;
  const svg=document.getElementById("lmSvg"); if(!svg) return;
  const W=640,H=470, pad=18;
  const RT={8:"proposal_B8",7:"proposal_B7"};
  const POLS=[["gtfs","Today's timetable",{policy:"gtfs",reserve:0}],["b8","B8 every day",{policy:"fixedKey",key:"proposal_B8",reserve:0}],["play","Playbook + 1 spare",{policy:"prop",reserve:1,tiers:RT}]];
  const S={cars:10,pol:"gtfs",season:"summer",seed:7,manual:[],t:420,play:false,stage:"burl"};
  // equirectangular projection fitted to the track (good enough at this latitude and scale)
  const lat0=40.1, kx=Math.cos(lat0*Math.PI/180);
  const pts=MD.track.map(p=>[p[0]*kx,-p[1]]);
  const xs=pts.map(p=>p[0]), ys=pts.map(p=>p[1]);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
  const sc=Math.min((W-2*pad-130)/(x1-x0),(H-2*pad-10)/(y1-y0));
  const ox=pad+40+((W-2*pad-130)-(x1-x0)*sc)/2, oy=pad+((H-2*pad)-(y1-y0)*sc)/2;
  const P=([lon,lat])=>[ox+(lon*kx-x0)*sc, oy+(-lat-y0)*sc];
  const line=cs=>cs.map((c,i)=>{const p=P(c);return (i?"L":"M")+p[0].toFixed(1)+","+p[1].toFixed(1);}).join("");
  const segLL=(a,b)=>[E.posToLL(a),...MD.track.filter(p=>p[2]>a&&p[2]<b).map(p=>[p[0],p[1]]),E.posToLL(b)];
  const pretty=n=>n.replace("36Th","36th").replace("Walter Rand Transportation Ctr","Walter Rand TC").replace("Trenton Transit Center","Trenton TC").replace("Pennsauken Transit Center","Pennsauken TC").replace("Entertainment Center","Camden (Ent. Center)");
  const KEYST=new Set(["Entertainment Center","Pennsauken Transit Center","Palmyra","Riverside","Burlington Towne Ctr","Florence","Roebling","Bordentown","Trenton Transit Center"]);
  // base layers
  el("rect",{x:0,y:0,width:W,height:H,fill:"var(--land)",rx:4},svg);
  const cl=el("clipPath",{id:"lmclip"},svg); el("rect",{x:0,y:0,width:W,height:H,rx:4},cl);
  const base=el("g",{"clip-path":"url(#lmclip)"},svg);
  el("path",{d:MD.counties.map(l=>line(l)).join(""),fill:"none",stroke:"var(--county)","stroke-width":1,"stroke-dasharray":"4 3"},base);
  MD.river.forEach(l=>el("path",{d:line(l),fill:"none",stroke:"var(--water)","stroke-width":9,"stroke-linecap":"round","stroke-linejoin":"round"},base));
  [["PENNSYLVANIA",-75.0,40.19],["NEW JERSEY",-74.83,40.0],["PHILADELPHIA",-75.13,39.985]].forEach(([t,lo,la])=>{ const p=P([lo,la]); el("text",{x:p[0],y:p[1],"text-anchor":"middle","font-size":12,"letter-spacing":"3","font-weight":600,opacity:.65},base,t); });
  { const p=P([-74.93,40.075]); el("text",{x:p[0],y:p[1],"font-size":12,"font-style":"italic","letter-spacing":"2",fill:"var(--water-ink)",transform:`rotate(-30 ${p[0]} ${p[1]})`},base,"DELAWARE RIVER"); }
  const allLL=MD.track.map(p=>[p[0],p[1]]);
  el("path",{d:line(allLL),fill:"none",stroke:"var(--panel)","stroke-width":8,"stroke-linecap":"round"},base);
  E.singles.forEach(s=>el("path",{d:line(segLL(s.a,s.b)),fill:"none",stroke:"var(--single)","stroke-width":8},base));
  el("path",{d:line(allLL),fill:"none",stroke:"var(--ink-2)","stroke-width":2.2},base);
  const gBlk=el("g",{},base);
  MD.stations.forEach(s=>{ const p=P([s.lon,s.lat]); const c=el("circle",{cx:p[0],cy:p[1],r:3.4,fill:"var(--panel)",stroke:"var(--ink)","stroke-width":1.3},base);
    hoverable(c,`<b>${pretty(s.name)}</b><br>mile ${s.pos.toFixed(1)} from Camden${s.board!=null?"<br>"+s.board.toLocaleString()+" weekday boardings (2024)":""}`);
    if(KEYST.has(s.name)) el("text",{x:p[0]+8,y:p[1]+4,"font-size":11.5,class:"lab"},base,pretty(s.name)); });
  MD.yards.forEach(y=>{ const p=P(E.posToLL(y.pos)); const r=el("rect",{x:p[0]-4,y:p[1]-4,width:8,height:8,fill:"var(--panel)",stroke:"var(--ink)","stroke-width":1.3,transform:`rotate(45 ${p[0]} ${p[1]})`},base); hoverable(r,y.name); });
  const gTr=el("g",{},base);
  // state
  let DAY=null;
  function cfg(){ return Object.assign({cars:S.cars,season:S.season,stage:S.stage,seed:S.seed,rand:true,manual:S.manual},POLS.find(p=>p[0]===S.pol)[2]); }
  function rebuild(){ DAY=E.simulateDay(cfg()); draw(); }
  function trainsAt(t){ const out=[]; if(!DAY) return out;
    for(const tr of DAY.trips){ if(tr.status==="cancelled") continue; if(tr.failAt!=null&&t>=tr.failAt) continue; const p=E.tripPos(tr,t); if(p==null) continue; out.push({pos:p,kind:tr.dir,tr}); }
    DAY.rescues.forEach(r=>{ if(t<r.tf||t>r.tEnd) return; let fp=r.pos,rp=null;
      if(t>=r.tC){ const f=(t-r.tC)/Math.max(1,r.tEnd-r.tC); fp=r.pos+(r.yard-r.pos)*f; rp=fp; }
      else if(t>=r.tDep){ const f=Math.min(1,(t-r.tDep)/Math.max(1,r.tArr-r.tDep)); rp=r.from+(r.pos-r.from)*f; }
      else if(!r.spare&&r.veh) rp=r.from;
      out.push({pos:fp,kind:"fail",r}); if(rp!=null&&r.veh) out.push({pos:rp,kind:"rescue",r,off:t>=r.tC}); });
    return out; }
  function draw(){ const t=S.t; clear(gBlk); clear(gTr);
    DAY.blocks.filter(b=>t>=b.t0&&t<b.t1).forEach(b=>el("path",{d:line(segLL(b.a,b.b)),fill:"none",stroke:"var(--bad)","stroke-width":12,"stroke-opacity":.5,"stroke-linecap":"round"},gBlk));
    trainsAt(t).forEach(d=>{ const p=P(E.posToLL(d.pos)); const o=d.kind==="rescue"&&d.off?6:0; const g=el("g",{transform:`translate(${p[0]+o},${p[1]-o})`},gTr);
      if(d.kind==="fail"){ el("circle",{r:9,fill:"none",stroke:"var(--bad)","stroke-width":2,class:"pulse"},g); }
      else if(d.tr&&d.tr.status==="late"){ el("circle",{r:10.5,fill:"none",stroke:"var(--signal)","stroke-width":2.2,"stroke-dasharray":"3 2"},g); }
      const c=el("circle",{r:d.kind==="rescue"?5.5:6.5,fill:{NB:"var(--s1)",SB:"var(--s2)",fail:"var(--bad)",rescue:"var(--rescue)"}[d.kind],stroke:"var(--panel)","stroke-width":2},g);
      const hit=el("circle",{r:12,fill:"transparent"},g);
      if(d.kind==="NB"||d.kind==="SB"){ const tr=d.tr; hit.style.cursor="pointer";
        hoverable(hit,`<b>${tr.label} · ${tr.dir==="NB"?"to Trenton":"to Camden"}</b><br>left ${tr.dir==="NB"?"Camden":"Trenton"} ${E.fmt(tr.dep)}<br>${tr.delay>0.5?"running "+Math.round(tr.delay)+" min late":"on time"}<br><i>click to break it down</i>`);
        hit.addEventListener("click",()=>{ S.manual.push({t:S.t+0.01,block:tr.block}); tip.hidden=true; rebuild(); }); }
      else if(d.kind==="fail") hoverable(hit,`<b>Broken-down car ${d.r.failedCar}</b><br>failed at ${E.fmt(d.r.tf)}${S.t>=d.r.tC?"<br>being towed to the yard":"<br>waiting for rescue"}`);
      else hoverable(hit,`<b>Rescue: car ${d.r.veh}</b><br>${d.r.spare?"spare (protect) car":"pulled from passenger service"}<br>clear by ${E.fmt(d.r.tEnd)}`); });
    // panel
    document.getElementById("lmClock").textContent=hm(t); document.getElementById("lmT").value=Math.round(t);
    const pl=DAY.plan, [np]=E.planTrains(pl);
    document.getElementById("lmPlan").innerHTML= pl?`<b>${E.planLabel(pl).replace(/:.*$/,"")}</b> · needs ${np} trains at the peaks${S.cars<np?` · <b style="color:var(--bad)">${np-S.cars} short</b>`:` · ${S.cars-np} spare`}`:"<b style='color:var(--bad)'>Bus bridge</b>: not enough cars for any timetable";
    const now=E.totals(DAY,t), tot=DAY.totals; const onLine=trainsAt(t).filter(d=>d.kind==="NB"||d.kind==="SB").length;
    const fails=DAY.rescues.filter(r=>r.tf<=t).length;
    const row=(k,a,b,bad)=>`<tr><td>${k}</td><td class="r"${bad?' style="color:var(--bad);font-weight:600"':""}>${a}</td><td class="r">${b}</td></tr>`;
    document.getElementById("lmTab").innerHTML=`<thead><tr><th></th><th class="r">so far</th><th class="r">whole day</th></tr></thead><tbody>`+
      row("Trains on the line",onLine,"")+row("Trips run / scheduled",`${now.run}/${now.pub}`,`${tot.run}/${tot.pub}`)+
      row("Cancelled or cut short",now.canc+now.fail,tot.canc+tot.fail,now.canc+now.fail>0)+row("Breakdowns",fails,DAY.rescues.length,fails>0)+
      row("On time",isNaN(now.otp)?"–":Math.round(now.otp)+"%",Math.round(tot.otp)+"%")+"</tbody>";
    const evs=DAY.ev.filter(e=>e.t<=t&&e.cls!=="p").slice(-3).reverse();
    document.getElementById("lmLog").innerHTML=(evs.length?evs:[{t:DAY.ev[0].t,cls:"p",msg:DAY.ev[0].msg}]).map(e=>`<div style="border-left:3px solid ${e.cls==="f"?"var(--bad)":e.cls==="r"?"var(--rescue)":"var(--river)"};padding-left:.5em"><span class="num muted">${hm(e.t)}</span> ${e.msg}</div>`).join("");
  }
  // controls
  const carsIn=document.getElementById("lmCars");
  carsIn.oninput=()=>{ S.cars=+carsIn.value; document.getElementById("lmCarsOut").textContent=S.cars; S.manual=[]; rebuild(); };
  seg("lmPol",POLS.map(p=>[p[0],p[1]]),S.pol,k=>{S.pol=k;S.manual=[];rebuild();});
  seg("lmSeason",[["spring","Spring"],["summer","Summer"],["fall","Fall"],["winter","Winter"]],S.season,k=>{S.season=k;rebuild();});
  document.getElementById("lmNew").onclick=()=>{ S.seed=Math.floor(Math.random()*1e6); S.manual=[]; rebuild(); };
  document.getElementById("lmT").oninput=e=>{ S.t=+e.target.value; draw(); };
  const btn=()=>document.getElementById("lmPlay").textContent=S.play?"❚❚ Pause":"▶ Play";
  let last=null; function tick(ts){ if(!S.play){last=null;return;} if(last!=null){ S.t=Math.min(E.DE,S.t+(ts-last)/1000*4); if(S.t>=E.DE){S.play=false;btn();} draw(); } last=ts; requestAnimationFrame(tick); }
  document.getElementById("lmPlay").onclick=()=>{ if(!S.play&&S.t>=E.DE) S.t=E.DS; S.play=!S.play; btn(); if(S.play) requestAnimationFrame(tick); };
  window.__lmStop=()=>{ S.play=false; btn(); };
  // open on a day with a morning-peak breakdown, like the dashboard
  for(let s=1;s<200;s++){ S.seed=s; const d=E.simulateDay(cfg()); if(d.rescues.some(r=>r.tf>400&&r.tf<500)){ S.t=Math.max(E.DS,Math.floor(d.rescues.find(r=>r.tf>400).tf)-12); break; } }
  rebuild();
})();
