"""Build full-day current and proposed timetables, compute metrics, write CSVs, figures and a LaTeX timetable book."""
import sys, json, math; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_tools import *
from parse_public import gtfs2026_weekday
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
OUT = ROOT/"timetables"; OUT.mkdir(exist_ok=True); FIG = ROOT/"report"/"figures"
C6 = ["#2a78d6","#eb6834","#1baf7a","#eda100","#e87ba4","#4a3aa7","#898781"]; MUTED="#898781"; GRID="#e1e0d9"
plt.rcParams.update({"font.size":9.5,"axes.edgecolor":"#c3c2b7","xtick.color":MUTED,"ytick.color":MUTED,"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.color":GRID,"grid.linewidth":0.6,"savefig.bbox":"tight"})
line = Line2026(calibrated=True)
PROFILE = {5:2,6:7,7:10,8:8,9:5,10:4,11:4,12:4,13:4,14:5,15:7,16:9,17:9,18:6,19:4,20:3,21:2}; _s=sum(PROFILE.values()); PROFILE={k:v/_s for k,v in PROFILE.items()}
WR = STOP_ORDER.index("Walter Rand TC")
FIRST, LAST = 5*60+40, 21*60+5      # first/last origin departure (last arrival ~22:12, like today's last trips)
WINDOWS = [("early",FIRST,6*60,"base"),("am",6*60,9*60,"peak"),("mid",9*60,15*60+30,"base"),("pm",15*60+30,19*60,"peak"),("eve",19*60,LAST+1,"base")]

def njt_current():
    trips=[]
    for r in gtfs2026_weekday():
        trips.append(dict(dir=r["direction"], times=[None if m is None else float(m) for m in r["times"]], block=r["block"]))
    return trips

PEAK_WINDOWS=[(FIRST,9*60),(14*60+15,18*60+30)]   # PM starts 14:15 so returning trains also cover the 16:00-18:30 trips to Camden
def best_subset(pat, k):
    """Trains of the peak pattern that keep running off-peak: the k-subset with the most even spacing."""
    import itertools
    K,C=pat["K"],pat["C"]
    if k>=K: return list(range(K))
    best=None
    for sub in itertools.combinations(range(K),k):
        a=sorted(pat["a"][i] for i in sub); b=sorted(pat["b"][i]%C for i in sub)
        ga=np.diff(a+[a[0]+C]); gb=np.diff(b+[b[0]+C]); sc=(ga**2).sum()+(gb**2).sum()
        if best is None or sc<best[0]: best=(sc,sub)
    return list(best[1])

def build_proposed(pat, k_off, keep=None, ln=None):
    """One conflict-free pattern all day. Off-peak, only the k_off best-spaced trains keep running; the others
    run only cycles whose Camden departure falls in a peak window (then return to Camden and lay up).
    keep: explicit set of all-day trains (from the joint peak/midday MIP); ln: line (scaled running times)."""
    line=ln or globals()["line"]
    keep=set(keep) if keep is not None else set(best_subset(pat,k_off)); C=pat["C"]; trips=[]
    for k in range(pat["K"]):
        for n in range(-1, int(24*60/C)+2):
            tN=pat["a"][k]+n*C; tS=pat["b"][k]+n*C
            allday = k in keep
            inpeak = any(a<=tN<b for a,b in PEAK_WINDOWS)
            if (allday or inpeak) and FIRST<=tN<=LAST:
                trips.append(dict(dir="NB",times=stop_times(line,"NB",tN,pat["wN"][k]),traj=trajectory(line,"NB",tN,pat["wN"][k]),train=k))
            prevN=tS-(pat["b"][k]-pat["a"][k])      # this SB trip returns the train that left Camden at prevN
            nextN=prevN+C                             # ... and precedes the Camden departure at nextN
            am_start = (PEAK_WINDOWS[0][0]<=nextN<PEAK_WINDOWS[0][1]) and not (PEAK_WINDOWS[0][0]<=prevN<PEAK_WINDOWS[0][1])
            if FIRST<=tS<=LAST and (allday or any(a<=prevN<b for a,b in PEAK_WINDOWS) or am_start):   # am_start: train stabled overnight at Trenton
                trips.append(dict(dir="SB",times=stop_times(line,"SB",tS,pat["wS"][k]),traj=trajectory(line,"SB",tS,pat["wS"][k]),train=k))
    return trips


# ---------------- periodic (uniform-headway) tiers from the headway ladder ----------------
from rl_data import load_line as _load_line
from timetable_mip import headway_table as _hwt
_pline=_load_line(); _TAB={r["T"]:r for r in _hwt(_pline, range(15,61)) if r["trainsets"]}
PER_BOUNDS=[(5*60+45,6*60,"b"),(6*60,9*60,"p"),(9*60,15*60,"b"),(15*60,19*60,"p"),(19*60,22*60,"b")]
def _ptimes(sol, direction, dep):
    secs=_pline.sections; out=[]
    for k,x in enumerate(_pline.stations.pos_mi):
        if direction=="NB":
            w=sum(v for d,v in sol["_sN"].items() if secs.end_mi[d]<=x+1e-9); out.append(dep+_pline.time_nb(x)+w)
        else:
            w=sum(v for d,v in sol["_sS"].items() if secs.start_mi[d]>=x-1e-9); out.append(dep+_pline.time_sb(x)+w)
    return out
def _wvec(wd):
    """map waits keyed by rl_data section index onto Line2026.double order"""
    secs=_pline.sections; out=[0.0]*len(line.double)
    for d,v in wd.items():
        for j,s2 in enumerate(line.double):
            if abs(s2["a"]-secs.start_mi[d])<1e-6: out[j]=v
    return out
def periodic_trips(Tp,Tb):
    trips=[]; DS=5*60+45
    for a,b,kind in PER_BOUNDS:
        T=Tp if kind=="p" else Tb; sol=_TAB[T]; n=sol["trainsets"]
        k0=math.ceil((a-DS)/T)-1; k=k0
        while True:
            t=DS+k*T
            if t>=b: break
            if t>=a and t<=LAST: trips.append(dict(dir="NB",times=_ptimes(sol,"NB",t),traj=trajectory(line,"NB",t,_wvec(sol["_sN"]))))
            ts=t+sol["phi"]
            if a<=ts<b and ts<=LAST: trips.append(dict(dir="SB",times=_ptimes(sol,"SB",ts),traj=trajectory(line,"SB",ts,_wvec(sol["_sS"]))))
            k+=1
    return trips

def metrics(trips, label):
    full=[t for t in trips if all(x is not None for x in t["times"])]
    def dep(t): v=[x for x in t["times"] if x is not None]; return v[0] if t["dir"]=="NB" else v[-1]
    if "train" in trips[0]:
        bl={}; [bl.setdefault(t["train"],[]).append(i) for i,t in enumerate(trips)]; blocks=list(bl.values())
    elif "block" not in trips[0] or trips[0].get("block") is None:
        blocks=fifo_blocks(trips)
    else:
        bl={}; [bl.setdefault(t["block"],[]).append(i) for i,t in enumerate(trips)]; blocks=list(bl.values())
    spans=[]
    for bk in blocks:
        ts=[x for i in bk for x in trips[i]["times"] if x is not None]; spans.append((min(ts),max(ts)))
    grid=np.arange(5*60,23*60)
    # a train counts as in service while on a trip or turning back (gap between its trips <= 40 min)
    busy=[]
    for bk in blocks:
        iv=sorted((min(x for x in trips[i]["times"] if x is not None), max(x for x in trips[i]["times"] if x is not None)) for i in bk)
        cur=list(iv[0])
        for a,b in iv[1:]:
            if a-cur[1]<=40: cur[1]=max(cur[1],b)
            else: busy.append(tuple(cur)); cur=[a,b]
        busy.append(tuple(cur))
    active=np.array([sum(a<=t<=b for a,b in busy) for t in grid])
    spans=busy
    miles=sum(abs(line.pos[max(k for k,x in enumerate(t["times"]) if x is not None)]-line.pos[min(k for k,x in enumerate(t["times"]) if x is not None)]) for t in trips)
    out=dict(label=label, trips=len(trips), full_trips=len(full), vehicles_peak=int(active.max()), vehicles_midday=int(active[(grid>=11*60+30)&(grid<=14*60)].max()),
             train_hours=round(sum(b-a for a,b in spans)/60,1), car_miles=round(miles,0),
             first=min(dep(t) for t in trips), last=max(dep(t) for t in trips))
    # headways at Walter Rand
    for d in ["NB","SB"]:
        ts=sorted(t["times"][WR] for t in trips if t["dir"]==d and t["times"][WR] is not None)
        for per,(a,b) in {"am":(6*60+30,9*60),"mid":(10*60,14*60+30),"pm":(16*60,18*60+45)}.items():
            h=np.diff([x for x in ts if a<=x<b])
            if len(h):
                out[f"{d}_{per}_mean"]=round(float(h.mean()),1); out[f"{d}_{per}_max"]=round(float(h.max()),1)
                out[f"{d}_{per}_wait"]=round(float((h**2).sum()/(2*h.sum())),2)
        # passenger-weighted daily wait (random arrivals, hourly profile) at Walter Rand
        W=P=0; prev=FIRST
        for t in ts+[23*60]:
            te=min(t,22*60)
            if te>prev:
                lam=PROFILE.get(int(prev//60),0); g=te-prev; W+=lam*g*(t-prev-g/2); P+=lam*g
            prev=max(prev,t)
        out[f"{d}_day_wait"]=round(W/P,2)
    out["day_wait"]=round((out["NB_day_wait"]+out["SB_day_wait"])/2,2)
    out["conflicts"]=len(conflicts(line,[t for t in trips if all(x is not None for x in t["times"])],g=0.5))
    return out, blocks

def write_csv(trips, name):
    rows=[]
    for i,t in enumerate(sorted(trips,key=lambda t:(t["dir"], [x for x in t["times"] if x is not None][0] if t["dir"]=="NB" else [x for x in t["times"] if x is not None][-1]))):
        rows.append(dict(direction="to Trenton" if t["dir"]=="NB" else "to Camden", **{STOP_ORDER[k]:(None if x is None else f"{int(round(x))//60:02d}:{int(round(x))%60:02d}") for k,x in enumerate(t["times"])}))
    pd.DataFrame(rows).to_csv(OUT/f"{name}.csv",index=False)

def hhmm(x):
    if x is None: return "--"
    x=int(round(x)); return f"{x//60}:{x%60:02d}"

def latex_tables(trips, title, name, per_page=13):
    ttl=title.replace("%","\\%"); parts=[f"\\section{{{ttl}}}\\label{{tt:{name}}}"]
    for d,lab in [("NB","To Trenton (read down)"),("SB","To Camden (read down)")]:
        ts=[t for t in trips if t["dir"]==d]
        ts.sort(key=lambda t:[x for x in t["times"] if x is not None][0] if d=="NB" else [x for x in t["times"] if x is not None][-1])
        order=list(range(21)) if d=="NB" else list(range(20,-1,-1))
        for c0 in range(0,len(ts),per_page):
            chunk=ts[c0:c0+per_page]
            parts.append(f"\\subsection*{{{lab} --- trips {c0+1}--{c0+len(chunk)} of {len(ts)}}}")
            parts.append("\\begin{center}\\footnotesize\\setlength{\\tabcolsep}{3pt}\\begin{tabular}{@{}l"+"r"*len(chunk)+"@{}}\\toprule")
            parts.append("Station & "+" & ".join(str(c0+i+1) for i in range(len(chunk)))+" \\\\\\midrule")
            for k in order:
                parts.append(STOP_ORDER[k].replace("&","\\&")+" & "+" & ".join(hhmm(t["times"][k]) for t in chunk)+" \\\\")
            parts.append("\\bottomrule\\end{tabular}\\end{center}")
    return "\n".join(parts)

def build_TT():
    pats=json.load(open(ROOT/"results"/"patterns.json"))
    def best(K):   # one common 150-min cycle (NJ TRANSIT's) so patterns can hand trains to each other
        return pats[f"{K}_150"]
    chosen={K:best(K) for K in [8,7,6,5,4,3]}
    json.dump({K:(None if v is None else dict(C=v["C"],gapsN=v["gapsN"],gapsS=v["gapsS"],waitN=v["waitN"],waitS=v["waitS"],siding_wait=sum(map(sum,v["wN"]))+sum(map(sum,v["wS"])))) for K,v in chosen.items()},open(ROOT/"results"/"patterns_chosen.json","w"),indent=1)
    base5=pats['5_150']   # clock-face 30-min base with 5 trains
    TT={"NJT current (Sept 2026)":("njt_current",njt_current())}
    OFF={8:6,7:6,6:5,5:5,4:4,3:3}
    for K,lab in [(8,"Proposed T8 (8 trains peak, 6 midday)"),(7,"Proposed T7 (7 peak, 6 midday)"),(6,"Proposed T6 (6 peak, 5 midday)"),(5,"Proposed T5 (5 all day)"),(4,"Proposed T4 (4 all day)"),(3,"Proposed T3 (3 all day)")]:
        TT[lab]=(f"proposed_T{K}", build_proposed(chosen[K],OFF[K]))
    # proposals (analysis/proposals_solve.py): joint peak/midday, recovery, holds, robust meets, summer
    from proposals_mip import scaled_line
    PP=json.load(open(ROOT/"results"/"proposal_patterns.json"))
    PLAB={"E5":"Proposal E5: 8 peak, 5 midday (frees a car)","E6":"Proposal E6: 8 peak, 6 midday, even midday",
          "G8":"Proposal G8: 8 trains, 2-min meet buffers","S8":"Proposal S8: 8 trains, slack held before single track",
          "R8":"Proposal R8: 8 trains, 160-min cycle, 8-min layovers","W7":"Proposal W7: summer (+6% run time), 7 trains","B8":"Proposal B8: 8 trains, 160-min cycle, 2.5-min meet buffers, 9-min layovers","B7":"Proposal B7: 7 trains, 160-min cycle, 2.5-min meet buffers, 9-min layovers"}
    for nm in ["B8","B7","E5","E6","G8","S8","R8","W7"]:
        if nm not in PP: continue
        p=PP[nm]; o=p.get("opts",{})
        ln=scaled_line(o["scale"]) if o.get("scale") else (scaled_line(1-0.06) if o.get("holds") else line)
        TT[PLAB[nm]]=(f"proposal_{nm}", build_proposed(p,p["kmid"],keep=p["sub"][0],ln=ln))
    for Tp,Tb in [(21,30),(23,30),(26,30),(29,30),(38,38)]:
        n=_TAB[Tp]["trainsets"]
        TT[f"Uniform U{n}: every {Tp} min peak, {Tb} off-peak"]=(f"uniform_U{n}", periodic_trips(Tp,Tb))
    return TT

if __name__=="__main__":
    TT=build_TT()
    rows=[]; allblocks={}
    for lab,(name,trips) in TT.items():
        m,blocks=metrics(trips,lab); rows.append(m); write_csv(trips,name); allblocks[name]=blocks
    M=pd.DataFrame(rows); M.to_csv(OUT/"timetable_metrics.csv",index=False); print(M.T.to_string())
    # JSON for dashboard
    dj={}
    for lab,(name,trips) in TT.items():
        blocks=allblocks[name]; bid={}
        nb=0
        for bk in blocks:   # split a train's day into separate duties at lay-ups longer than 40 min
            seq=sorted(bk,key=lambda i:min(x for x in trips[i]["times"] if x is not None)); prev_end=None
            for i in seq:
                st=min(x for x in trips[i]["times"] if x is not None); en=max(x for x in trips[i]["times"] if x is not None)
                if prev_end is None or st-prev_end>40: nb+=1
                bid[i]=nb; prev_end=en
        dj[name]=dict(label=lab,trips=[dict(d=t["dir"],b=int(bid[i]),t=[None if x is None else round(x,1) for x in t["times"]]) for i,t in enumerate(trips)])
    json.dump(dj,open(OUT/"timetables_dashboard.json","w"),separators=(",",":"))
    # LaTeX timetable book
    body=[latex_tables(trips,lab,name) for lab,(name,trips) in TT.items()]
    open(OUT/"timetable_book_body.tex","w").write("\n\\clearpage\n".join(body))
    # figures: Marey NJT vs T8
    fig,axs=plt.subplots(2,1,figsize=(10,6.2),sharex=True)
    for ax,(lab,key) in zip(axs,[("NJT current (Sept 2026)","NJT current (Sept 2026)"),("Proposed T8 (8 trains peak, 6 midday)","Proposed T8 (8 trains peak, 6 midday)")]):
        for s in line.single: ax.axhspan(s["a"],s["b"],color="#f2e3c9",lw=0)
        for t in TT[key][1]:
            pts=[(x,line.pos[k]) for k,x in enumerate(t["times"]) if x is not None]
            ax.plot([p[0]/60 for p in pts],[p[1] for p in pts],color=C6[0] if t["dir"]=="NB" else C6[1],lw=0.9)
        ax.set_xlim(5.5,12.5); ax.set_ylim(0,line.L); ax.set_ylabel("Miles from Camden"); ax.grid(False); ax.set_title(lab,loc="left",fontsize=10)
    axs[1].set_xlabel("Hour of day"); fig.savefig(FIG/"fig_tt_marey_compare.pdf"); fig.savefig(FIG/"fig_tt_marey_compare.png",dpi=150); plt.close(fig)
    # headway pattern AM peak at Walter Rand, NB
    fig,axs=plt.subplots(1,2,figsize=(10,3.2))
    for ax,d,ttl in [(axs[0],"NB","To Trenton"),(axs[1],"SB","To Camden")]:
        for k,(lab,(name,trips)) in enumerate([(l,v) for l,v in TT.items() if l.startswith("NJT") or "T8" in l]):
            ts=sorted(t["times"][WR] for t in trips if t["dir"]==d and t["times"][WR] is not None)
            ts=[x for x in ts if 6*60+30<=x<9*60+30]
            ax.step([x/60 for x in ts[1:]],np.diff(ts),where="pre",color=C6[k],lw=2,label=lab)
        ax.set_ylim(0,35); ax.set_xlabel("Hour"); ax.set_ylabel("Minutes since previous train"); ax.set_title(f"AM peak headways at Walter Rand, {ttl}",loc="left",fontsize=10)
    axs[0].legend(frameon=False,fontsize=8)
    fig.savefig(FIG/"fig_tt_headways.pdf"); fig.savefig(FIG/"fig_tt_headways.png",dpi=150); plt.close(fig)
    # tier comparison chart
    fig,axs=plt.subplots(1,3,figsize=(12,3.3))
    labs=[r["label"].split(" (")[0].split(":")[0].replace("Proposed ","").replace("Uniform ","").replace("Proposal ","").replace("NJT current","NJT") for r in rows]
    cols=[C6[6] if r["label"].startswith("NJT") else C6[0] if r["label"].startswith("Proposed") else C6[2] if r["label"].startswith("Proposal") else "#9ec5f4" for r in rows]
    axs[0].bar(labs,[r["vehicles_peak"] for r in rows],color=cols); axs[0].set_title("Trains needed at peak",loc="left",fontsize=10)
    axs[1].bar(labs,[r["train_hours"] for r in rows],color=cols); axs[1].set_title("Train-hours per weekday",loc="left",fontsize=10)
    axs[2].bar(labs,[r["day_wait"] for r in rows],color=cols); axs[2].set_title("Avg rider wait, Walter Rand (min)",loc="left",fontsize=10)
    for ax in axs: ax.tick_params(axis="x",rotation=45,labelsize=8); ax.grid(axis="x",visible=False)
    fig.savefig(FIG/"fig_tt_tiers.pdf"); fig.savefig(FIG/"fig_tt_tiers.png",dpi=150); plt.close(fig)
