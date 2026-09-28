// ================= interactive slides (from the dashboard) =================
const TTN={njt_current:"Today",proposal_B8:"B8",proposal_B7:"B7",proposed_T8:"T8 (even)"};
const TTLONG={njt_current:"Today's timetable",proposal_B8:"B8 (proposed)",proposal_B7:"B7 (7 trains)",proposed_T8:"T8 (evenly spaced)"};
const SECN=["36th Street","Route 73 – Palmyra","Cinnaminson – Riverside","Beverly – Burlington S.","Burlington – Florence","Roebling","Bordentown – Cass St."];
const SHORT=["36th St.","Rt 73 – Palmyra","Riverside","Beverly","Burl. – Florence","Roebling","Cass St."];
const SECWHY=["1.5 miles with the 36th Street stop on the single track.","1.7 miles with two stops (Route 73 and Palmyra) on the single track: about 4.5 minutes to cross, the slowest section.","1.3 miles, no stops.","The shortest section: 1 mile, no stops.","2.1 miles, no stops.","The longest section: 3.1 miles, with the Roebling stop on it.","2 miles, no stops."];
const hm=t=>{t=Math.round(t);return `${Math.floor(t/60)}:${String(((t%60)+60)%60).padStart(2,"0")}`;};
const IX=D.ix, SEC=IX.sections, POS=stations.map(q=>q[1]);
function seg(id,opts,val,on){ const box=document.getElementById(id); box.innerHTML="";
  opts.forEach(([k,lab])=>{ const b=document.createElement("button"); b.type="button"; b.textContent=lab; b.setAttribute("aria-pressed",k===val); b.onclick=()=>{ [...box.children].forEach(c=>c.setAttribute("aria-pressed","false")); b.setAttribute("aria-pressed","true"); on(k); }; box.appendChild(b); }); }
function sel(id,opts,val,on){ const s=document.getElementById(id); s.innerHTML=opts.map(([k,l])=>`<option value="${k}"${k===val?" selected":""}>${l}</option>`).join(""); s.onchange=()=>on(s.value); }
const clear=n=>{while(n.firstChild)n.removeChild(n.firstChild);};
const WINS=[["am","6–9:30 am",360,570],["mid","Midday",570,900],["pm","3–7 pm",900,1140],["eve","Evening",1140,1350],["day","All day",320,1350]];
const secOf=x=>SEC.findIndex(([a,b])=>Math.abs(x-a)<.02||Math.abs(x-b)<.02);
// position (miles) of a trajectory at time t, or null
function posAt(pts,t){ for(let i=1;i<pts.length;i++){ const [x0,t0]=pts[i-1],[x1,t1]=pts[i]; if(t>=t0&&t<=t1) return t1>t0?x0+(x1-x0)*(t-t0)/(t1-t0):x1; } return null; }
function termDeps(k,atX){ return IX.tt[k].traj.filter(([d,p])=>Math.abs(p[0][0]-atX)<.05).map(([d,p])=>p[0][1]).sort((a,b)=>a-b); }
function maxGap(ts,t0,t1){ const v=ts.filter(t=>t>=t0-40&&t<=t1); let g=0; for(let i=1;i<v.length;i++) if(v[i]>=t0) g=Math.max(g,v[i]-v[i-1]); return g; }

// ---------- explorer ----------
(function(){
  const st={tt:"njt_current",cmp:"",win:"am"}; const svg=document.getElementById("exSvg"); const W=760,H=380,m={l:92,r:10,t:8,b:24};
  const NOTES={
    njt_current:"<b>Today.</b> Peak trains leave every 15, 15 and 30 minutes, which fits 8 trains into the 150-minute round trip. The red dots cluster at <b>Route 73 – Palmyra</b>: 32 times a day a train is due to enter just as the opposing train leaves, with less than a minute to spare.",
    proposal_B8:"<b>B8.</b> The same 8 trains on a 160-minute cycle. Meets are moved so every one has at least 2.5 minutes to spare (no red or amber dots), and layovers are at least 9 minutes. The price: gaps stay uneven, up to about 31 minutes, as today.",
    proposed_T8:"<b>T8, evenly spaced.</b> Trains every ~20 minutes, but the meets land wherever the spacing puts them. Tight meets appear all along the line, especially at Roebling and Burlington – Florence.",
    proposal_B7:"<b>B7.</b> One train fewer, for days with 8 working cars (7 in service + 1 spare). Longer gaps, but the most slack of any plan."};
  function draw(){ clear(svg); const w=WINS.find(q=>q[0]===st.win); const t0=w[2],t1=w[3];
    const X=t=>m.l+(W-m.l-m.r)*(t-t0)/(t1-t0), Y=mi=>H-m.b-(H-m.t-m.b)*mi/L;
    SEC.forEach(([a,b],i)=>{ const r=el("rect",{x:m.l,y:Y(b),width:W-m.l-m.r,height:Y(a)-Y(b),fill:"var(--single)",opacity:.75},svg); hoverable(r,`<b>${SECN[i]}</b> single track<br>${SECWHY[i]}`); });
    [["Camden",0],["Pennsauken",5.34],["Riverside",12.29],["Burlington",18.29],["Bordentown",27.61],["Trenton",L]].forEach(([n,p])=>{ el("text",{x:m.l-6,y:Y(p)+4,"text-anchor":"end","font-size":11.5,class:"lab"},svg,n); el("line",{x1:m.l,x2:W-m.r,y1:Y(p),y2:Y(p),stroke:"var(--rule)","stroke-width":.6},svg); });
    const step=(t1-t0)>600?120:(t1-t0)>300?60:30; for(let t=Math.ceil(t0/step)*step;t<=t1;t+=step) el("text",{x:X(t),y:H-6,"text-anchor":"middle","font-size":11.5},svg,hm(t));
    el("clipPath",{id:"exclip"},svg).appendChild(el("rect",{x:m.l,y:0,width:W-m.l-m.r,height:H}));
    const g=el("g",{"clip-path":"url(#exclip)"},svg);
    const lw=st.win==="day"?1:1.6;
    if(st.cmp) IX.tt[st.cmp].traj.forEach(([d,p])=>{ if(p[p.length-1][1]<t0||p[0][1]>t1) return; el("path",{d:p.map(([x,t],j)=>(j?"L":"M")+X(t).toFixed(1)+","+Y(x).toFixed(1)).join(""),fill:"none",stroke:"var(--ink-2)","stroke-width":1,"stroke-dasharray":"4 3",opacity:.7},g); });
    IX.tt[st.tt].traj.forEach(([d,p])=>{ if(p[p.length-1][1]<t0||p[0][1]>t1) return; const col=d==="NB"?"var(--s1)":"var(--s2)"; const dd=p.map(([x,t],j)=>(j?"L":"M")+X(t).toFixed(1)+","+Y(x).toFixed(1)).join("");
      el("path",{d:dd,fill:"none",stroke:col,"stroke-width":lw},g); const hit=el("path",{d:dd,fill:"none",stroke:"transparent","stroke-width":8},g);
      const a=p[0],b=p[p.length-1]; hoverable(hit,`<b>${d==="NB"?"To Trenton":"To Camden"}</b><br>leaves ${hm(a[1])} (mile ${a[0].toFixed(1)}), arrives ${hm(b[1])} (mile ${b[0].toFixed(1)})<br>${Math.round(b[1]-a[1])} min`); });
    IX.tt[st.tt].meets.forEach(([si,x,t,sl])=>{ if(sl>=2.5||t<t0||t>t1) return; const c=el("circle",{cx:X(t),cy:Y(x),r:sl<1?4.5:3.8,fill:sl<1?"var(--bad)":"var(--signal)",stroke:"var(--panel)","stroke-width":1.2},g);
      hoverable(c,`<b>${SECN[si]}</b> · ${hm(t)}<br>${sl<0?"scheduled to overlap by "+(-sl).toFixed(1)+" min":sl.toFixed(1)+" min"} between the opposing train leaving the single track and this one entering`); });
    // table
    const keys=[st.tt].concat(st.cmp?[st.cmp]:[]);
    const rows=[["Trips starting",k=>IX.tt[k].traj.filter(([d,p])=>p[0][1]>=t0&&p[0][1]<t1).length],
      ["Longest wait, Camden (min)",k=>Math.round(maxGap(termDeps(k,0),t0,t1))],
      ["Longest wait, Trenton (min)",k=>Math.round(maxGap(termDeps(k,L),t0,t1))],
      ["Meets &lt;1 min spare",k=>IX.tt[k].meets.filter(q=>q[3]<1&&q[2]>=t0&&q[2]<t1).length],
      ["Meets 1–2.5 min spare",k=>IX.tt[k].meets.filter(q=>q[3]>=1&&q[3]<2.5&&q[2]>=t0&&q[2]<t1).length],
      ["Held at sidings, min/day (2024–25)",k=>{const h=IX.tt[k].reg.alstom_2024_25.byhour; let s=0; for(let i=0;i<24;i++) if(i*60>=t0-30&&i*60<t1) s+=h[i]; return Math.round(s);}],
      ["Held at sidings, min/day (2026)",k=>{const h=IX.tt[k].reg.njt_2026.byhour; let s=0; for(let i=0;i<24;i++) if(i*60>=t0-30&&i*60<t1) s+=h[i]; return Math.round(s);}]];
    document.getElementById("exTab").innerHTML=`<thead><tr><th>${w[1]}</th>${keys.map(k=>`<th class="r">${TTN[k]}</th>`).join("")}</tr></thead><tbody>`+rows.map(([n,f])=>`<tr><td>${n}</td>${keys.map(k=>`<td class="r">${f(k)}</td>`).join("")}</tr>`).join("")+"</tbody>";
    document.getElementById("exNote").innerHTML=NOTES[st.tt];
    document.getElementById("exCmpLeg").hidden=!st.cmp; document.getElementById("exCmpName").textContent=st.cmp?TTN[st.cmp]+" (dashed)":"";
  }
  seg("exTT",Object.entries(TTN),st.tt,k=>{st.tt=k; if(st.cmp===k){st.cmp="";document.getElementById("exCmp").value="";} draw();});
  sel("exCmp",[["","nothing"]].concat(Object.entries(TTN)),st.cmp,k=>{st.cmp=k===st.tt?"":k; draw();});
  seg("exWin",WINS.map(q=>[q[0],q[1]]),st.win,k=>{st.win=k;draw();});
  draw();
})();

// ---------- replay ----------
(function(){
  const st={day:"typical",win:"am",A:"njt_current",B:"proposal_B8",t:0,play:false}; const svg=document.getElementById("rpSvg"); const W=700,H=400;
  const RW=[["am","Morning",330,580],["mid","Midday",570,900],["pm","Afternoon",880,1170]];
  const DAYS=[["typical","Typical"],["bad","Bad (1 in 10)"],["hot","Hot"]];
  const m={l:66,r:10}; const PH=128, TOPS=[16,214]; let dyn=[], X, Yf;
  // actual trajectory of a replay trip, in travel order: [[mile,t]...]
  const traj=(tr,which)=>{ const a=tr[which]; const idx=[...a.keys()].filter(i=>a[i]!=null); if(tr[0]==="SB") idx.reverse(); return idx.map(i=>[POS[i],a[i]]); };
  function build(){ clear(svg); const w=RW.find(q=>q[0]===st.win); const t0=w[2],t1=w[3];
    X=t=>m.l+(W-m.l-m.r)*(t-t0)/(t1-t0); dyn=[];
    [st.A,st.B].forEach((k,pi)=>{ const top=TOPS[pi]; const Y=mi=>top+PH-PH*mi/L; const R=D.rp[st.day][k];
      el("text",{x:m.l,y:top-4,"font-size":13,class:"strong"},svg,TTLONG[k]);
      SEC.forEach(([a,b])=>el("rect",{x:m.l,y:Y(b),width:W-m.l-m.r,height:Y(a)-Y(b),fill:"var(--single)",opacity:.7},svg));
      el("text",{x:m.l-6,y:Y(0)+4,"text-anchor":"end","font-size":11},svg,"Camden"); el("text",{x:m.l-6,y:Y(L)+8,"text-anchor":"end","font-size":11},svg,"Trenton");
      const cid="rpc"+pi; el("clipPath",{id:cid},svg).appendChild(el("rect",{x:m.l,y:top-2,width:W-m.l-m.r,height:PH+4}));
      const g=el("g",{"clip-path":`url(#${cid})`},svg);
      const trips=R.trips.map(tr=>({d:tr[0],p:traj(tr,1),a:traj(tr,2),k:tr[3],l:tr[4],w:tr[5]})).filter(q=>q.a.length>1&&q.a[q.a.length-1][1]>=t0-5&&q.a[0][1]<=t1+5);
      trips.forEach(q=>{ const col=q.d==="NB"?"var(--s1)":"var(--s2)"; el("path",{d:q.p.map(([x,t],j)=>(j?"L":"M")+X(t).toFixed(1)+","+Y(x).toFixed(1)).join(""),fill:"none",stroke:col,"stroke-width":1,opacity:.25},g);
        q.path=el("path",{fill:"none",stroke:col,"stroke-width":1.7},g); q.col=col;
        q.wc=q.w.map(([mi,t,dd])=>{ const c=el("circle",{cx:X(t),cy:Y(mi),r:2.5+Math.sqrt(dd)*1.5,fill:"var(--bad)",opacity:.85},g); c.style.display="none"; hoverable(c,`Held ${dd.toFixed(1)} min at ${SECN[Math.max(0,secOf(mi))]} for a late opposing train`); return [t,c,dd]; }); });
      // live strip under the panel
      const sy=top+PH+30, sx=mi=>m.l+(W-m.l-m.r)*mi/L;
      SEC.forEach(([a,b])=>el("rect",{x:sx(a),y:sy-8,width:sx(b)-sx(a),height:16,fill:"var(--single)"},svg));
      el("line",{x1:sx(0),x2:sx(L),y1:sy,y2:sy,stroke:"var(--muted)","stroke-width":1.5},svg);
      el("text",{x:m.l-6,y:sy+4,"text-anchor":"end","font-size":11},svg,"now");
      const dots=el("g",{},svg);
      dyn.push({k,R,trips,Y,dots,sx,sy});
    });
    const cur=el("line",{y1:8,y2:TOPS[1]+PH+4,stroke:"var(--ink)","stroke-width":1,"stroke-dasharray":"2 3"},svg); dyn.cur=cur;
    const r=document.getElementById("rpT"); r.min=t0; r.max=t1; if(st.t<t0||st.t>t1) st.t=t0; r.value=st.t;
    for(let t=Math.ceil(t0/60)*60;t<=t1;t+=60) el("text",{x:X(t),y:H-4,"text-anchor":"middle","font-size":11.5},svg,hm(t));
    frame();
  }
  function frame(){ const t=st.t; dyn.cur.setAttribute("x1",X(t)); dyn.cur.setAttribute("x2",X(t)); document.getElementById("rpClock").textContent=hm(t);
    const stats=[];
    dyn.forEach(P=>{ clear(P.dots); let held=0,done=0,ok=0,lateNow=0;
      P.trips.forEach(q=>{ const pts=q.a.filter(p=>p[1]<=t); const x=posAt(q.a,t); if(x!=null) pts.push([x,t]);
        q.path.setAttribute("d",pts.length>1?pts.map(([x,tt],j)=>(j?"L":"M")+X(tt).toFixed(1)+","+P.Y(x).toFixed(1)).join(""):"");
        q.wc.forEach(([tw,c,dd])=>{ const on=tw<=t; c.style.display=on?"":"none"; if(on) held+=dd; });
        if(q.a[q.a.length-1][1]<=t){ done++; if(q.l<6) ok++; }
        if(x!=null){ const pl=posAt(q.p,t); // lateness: planned time at this mile vs now
          let late=0; for(let i=1;i<q.p.length;i++){ const [x0,t0]=q.p[i-1],[x1,t1]=q.p[i]; if((x-x0)*(x-x1)<=0&&x1!==x0){ late=t-(t0+(t1-t0)*(x-x0)/(x1-x0)); break; } }
          if(late>=6) lateNow++;
          const c=el("circle",{cx:P.sx(x),cy:P.sy+(q.d==="NB"?-4:4),r:5,fill:late>=6?"var(--bad)":q.col,stroke:"var(--panel)","stroke-width":1.5},P.dots);
          hoverable(c,`${q.d==="NB"?"To Trenton":"To Camden"} · mile ${x.toFixed(1)}<br>${late>0.5?late.toFixed(1)+" min late":"on schedule"}`); } });
      stats.push({held,done,ok,lateNow,R:P.R});
    });
    const [a,b]=stats; const row=(n,f)=>`<tr><td>${n}</td><td class="r">${f(a)}</td><td class="r">${f(b)}</td></tr>`;
    document.getElementById("rpTab").innerHTML=`<thead><tr><th>So far</th><th class="r">${TTN[st.A]}</th><th class="r">${TTN[st.B]}</th></tr></thead><tbody>`+
      row("Trips arrived",s=>s.done)+row("…of which on time",s=>s.done?Math.round(100*s.ok/s.done)+"%":"–")+row("Trains ≥6 min late now",s=>s.lateNow)+row("Minutes held at sidings",s=>Math.round(s.held))+
      `<tr><td colspan="3" class="small" style="padding-top:.5em">Whole day: ${TTN[st.A]} ${Math.round(a.R.otp)}% on time, ${a.R.knock} min held · ${TTN[st.B]} ${Math.round(b.R.otp)}% on time, ${b.R.knock} min held</td></tr></tbody>`;
  }
  let last=null; function tick(ts){ if(!st.play){last=null;return;} if(last!=null){ st.t+=(ts-last)/1000*8; const mx=+document.getElementById("rpT").max; if(st.t>=mx){st.t=mx;st.play=false;btn();} document.getElementById("rpT").value=st.t; frame(); } last=ts; requestAnimationFrame(tick); }
  const btn=()=>document.getElementById("rpPlay").textContent=st.play?"❚❚ Pause":"▶ Play";
  document.getElementById("rpPlay").onclick=()=>{ const r=document.getElementById("rpT"); if(!st.play&&st.t>=+r.max) st.t=+r.min; st.play=!st.play; btn(); if(st.play) requestAnimationFrame(tick); };
  document.getElementById("rpT").oninput=e=>{ st.t=+e.target.value; frame(); };
  seg("rpDay",DAYS,st.day,k=>{st.day=k;build();}); seg("rpWin",RW.map(q=>[q[0],q[1]]),st.win,k=>{st.win=k;st.t=0;build();});
  const opts=Object.entries(TTN); sel("rpA",opts,st.A,k=>{st.A=k;build();}); sel("rpB",opts,st.B,k=>{st.B=k;build();});
  st.t=420; build();
  window.__rpStop=()=>{st.play=false;btn();};
})();

// ---------- bottlenecks ----------
(function(){
  const st={tt:"njt_current",reg:"alstom_2024_25"}; const sv=document.getElementById("bnSec"), hv=document.getElementById("bnHour");
  const FIX={
    njt_current:k=>`<p class="callout"><b>Fix 1 · timetable.</b> Re-time the meets so no train is due to enter single track within 2.5 minutes of the opposing train leaving. B8 does this: tight meets go from ${k.tight} a day to 0 and siding holds fall from ${k.tot} to ${k.b8} min/day.</p><p class="callout cool"><b>Next, to test:</b> a dispatching rule to swap the meet order when the first train is several minutes late (not yet modeled); shorter dwell at Route 73 and Palmyra; and, if a siding is ever funded, this section first.</p>`,
    proposal_B8:k=>`<p class="callout cool"><b>What's left is not a timetable problem.</b> No meet has less than 2.5 minutes, so holds are spread out. Route 73 – Palmyra still leads because it is slow to cross. The next gains come from dispatching rules, dwell time there, and fewer incidents (door faults, ramps, crossings).</p>`,
    proposed_T8:k=>`<p class="callout"><b>Why we don't recommend even spacing on its own.</b> Evenly spaced trains force meets into tight spots all along the line (${k.tight} a day under 1 minute), and holds at sidings rise to ${k.tot} min/day, ${Math.round(k.tot/k.today*10)/10}× today's.</p>`,
    proposal_B7:k=>`<p class="callout cool"><b>The short-day plan.</b> One train fewer leaves the most slack: ${k.tot} min/day held, the least of any plan. Use it when only 8 cars pass inspection (7 in service, 1 spare).</p>`};
  function draw(){ clear(sv); clear(hv); const T=IX.tt[st.tt], R=T.reg[st.reg]; const W=700;
    const tot=R.bysec.reduce((s,r)=>s+r[0]+r[1],0); const mx=Math.max(90,...Object.values(IX.tt).map(t=>Math.max(...t.reg[st.reg].bysec.map(r=>r[0]+r[1]))));
    const x=mi=>20+(W-40)*mi/L, base=160, Hh=120, Yv=v=>base-Hh*v/mx;
    // track
    SEC.forEach(([a,b])=>el("rect",{x:x(a),y:base+6,width:x(b)-x(a),height:14,fill:"var(--single)"},sv));
    el("line",{x1:x(0),x2:x(L),y1:base+13,y2:base+13,stroke:"var(--muted)","stroke-width":1.5},sv);
    [["Camden",0,"start"],["Trenton",L,"end"]].forEach(([n,p,an])=>el("text",{x:x(p),y:base+34,"text-anchor":an,"font-size":11.5},sv,n));
    const tightBy=SEC.map((_,i)=>T.meets.filter(q=>q[0]===i&&q[3]<1).length);
    let top=0; R.bysec.forEach((r,i)=>{ if(r[0]+r[1]>R.bysec[top][0]+R.bysec[top][1]) top=i; });
    R.bysec.forEach(([nb,sb],i)=>{ const [a,b]=SEC[i]; const cx=(x(a)+x(b))/2, bw=Math.max(26,x(b)-x(a));
      const r1=el("rect",{x:cx-bw/2,y:Yv(nb),width:bw,height:base-Yv(nb),fill:"var(--s1)",rx:2},sv);
      const r2=el("rect",{x:cx-bw/2,y:Yv(nb+sb),width:bw,height:Math.max(0,Yv(nb)-Yv(nb+sb)-2),fill:"var(--s2)",rx:2},sv);
      const html=`<b>${SECN[i]}</b><br>${SECWHY[i]}<br>held here: ${(nb+sb).toFixed(0)} min/day (to Trenton ${nb.toFixed(0)}, to Camden ${sb.toFixed(0)})<br>meets with &lt;1 min spare: ${tightBy[i]} a day`;
      hoverable(r1,html); hoverable(r2,html);
      el("text",{x:cx,y:Yv(nb+sb)-5,"text-anchor":"middle","font-size":12,class:"strong"},sv,Math.round(nb+sb));
      el("text",{x:cx,y:base+34+(i%2)*15,"text-anchor":"middle","font-size":11,class:i===top?"strong":"lab"},sv,SHORT[i]);
      if(tightBy[i]) el("text",{x:cx,y:Yv(nb+sb)-19,"text-anchor":"middle","font-size":10.5,fill:"var(--bad)"},sv,`${tightBy[i]} tight`);
    });
    el("rect",{x:W-190,y:5,width:10,height:10,fill:"var(--s1)",rx:2},sv); el("text",{x:W-176,y:14,"font-size":11.5,class:"lab"},sv,"to Trenton");
    el("rect",{x:W-100,y:5,width:10,height:10,fill:"var(--s2)",rx:2},sv); el("text",{x:W-86,y:14,"font-size":11.5,class:"lab"},sv,"to Camden");
    // hours
    const H=120,m={l:30,r:8,t:8,b:20}; const hs=[]; for(let h=5;h<=22;h++) hs.push(h); const hmax=Math.max(20,...Object.values(IX.tt).map(t=>Math.max(...t.reg[st.reg].byhour)));
    const Xh=h=>m.l+(W-m.l-m.r)*(h-5)/18, Yh=v=>H-m.b-(H-m.t-m.b)*v/hmax, bw=(Xh(6)-Xh(5))*.72;
    [[6,9.5],[15,19]].forEach(([a,b])=>el("rect",{x:Xh(a),y:m.t,width:Xh(b)-Xh(a),height:H-m.t-m.b,fill:"var(--river-soft)"},hv));
    el("line",{x1:m.l,x2:W-m.r,y1:H-m.b,y2:H-m.b,stroke:"var(--muted)"},hv);
    hs.forEach(h=>{ const v=R.byhour[h]||0; const b=el("rect",{x:Xh(h)+1,y:Yh(v),width:bw,height:H-m.b-Yh(v),fill:"var(--signal)",rx:2},hv); hoverable(b,`${hm(h*60)}–${hm(h*60+60)}: ${v.toFixed(1)} min held per day`);
      if(h%2===0) el("text",{x:Xh(h)+1+bw/2,y:H-5,"text-anchor":"middle","font-size":11},hv,h<=12?h+(h===12?"pm":"am"):(h-12)+"pm"); });
    el("text",{x:Xh(6)+4,y:m.t+12,"font-size":11,class:"lab"},hv,"peaks");
    // notes
    const peak=[6,7,8,9,15,16,17,18].reduce((s,h)=>s+R.byhour[h],0), all=R.byhour.reduce((s,v)=>s+v,0);
    const regName=st.reg==="alstom_2024_25"?"2024–25 conditions":"2026 conditions";
    const k={tight:T.meets.filter(q=>q[3]<1).length,tot:Math.round(tot),b8:Math.round(IX.tt.proposal_B8.reg[st.reg].knock),today:IX.tt.njt_current.reg[st.reg].knock};
    const tt=R.bysec[top][0]+R.bysec[top][1];
    document.getElementById("bnNote").innerHTML=`<table class="mtab"><tbody><tr><td>On time (${regName})</td><td class="r">${R.otp.toFixed(0)}%</td></tr><tr><td>Held at sidings, all day</td><td class="r">${Math.round(tot)} min</td></tr></tbody></table>
      <p><b>Where:</b> ${SECN[top]}, ${Math.round(tt)} min/day (${Math.round(100*tt/tot)}% of all holds). ${SECWHY[top]}</p>
      <p><b>When:</b> ${Math.round(100*peak/all)}% of it in the two peaks, when all trains are out.</p>`+FIX[st.tt](k);
  }
  seg("bnTT",Object.entries(TTN),st.tt,k=>{st.tt=k;draw();});
  seg("bnReg",[["alstom_2024_25","2024–25 (Alstom)"],["njt_2026","2026 (NJ TRANSIT)"]],st.reg,k=>{st.reg=k;draw();});
  draw();
})();

