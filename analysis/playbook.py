"""Plan playbook: for each number of cars at the 6 am hold sheet and each policy, expected
cancellations, on-time, passenger wait, train-hours and a simple cost account.
Also sensitivity of the policy ranking to key placeholder parameters."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(ROOT/"src"))
from rl_data import load_line
from timetable_mip import headway_table
from simulate import PlanBook, Params, choose_plan, make_plan, simulate_day
FIG=ROOT/"report"/"figures"; OUT=ROOT/"results"
C=["#2a78d6","#eb6834","#1baf7a","#eda100","#e87ba4","#4a3aa7"]; MUTED="#898781"; GRID="#e1e0d9"
plt.rcParams.update({"font.size":9.5,"axes.edgecolor":"#c3c2b7","xtick.color":MUTED,"ytick.color":MUTED,"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.color":GRID,"grid.linewidth":0.6,"savefig.bbox":"tight"})
COST=dict(train_hour=400.0,      # $/train-hour marginal (NTD 2024 LR average $560 DO / $809 PT incl. fixed; assumption)
          vtts=13.60, wait_mult=2.0, # USDOT 2016 guidance, local personal travel, 2015$; waiting valued 2x
          unplanned_mult=1.0)      # extra weight on wait beyond the published schedule (assumption)
CLOCK=[15,20,30,60]; FLEX=list(range(15,61))
POL={"Fixed 8-car (20/30)":dict(kind="fixed",T_peak=20,T_base=30),
     "Tiered clock-face, 0 protect":dict(kind="tiered",reserve=0,menu=CLOCK),
     "Tiered clock-face, 1 protect":dict(kind="tiered",reserve=1,menu=CLOCK),
     "Tiered flexible, 1 protect":dict(kind="tiered",reserve=1,menu=FLEX),
     "Tiered flexible, 2 protect":dict(kind="tiered",reserve=2,menu=FLEX)}
line=load_line(); book=PlanBook(headway_table(line,range(12,61)))
def train_hours(plan): return sum(n*(b-a)/60 for a,b,T,n,info in plan)
def eval_A(pol,A,prm,days=400,seed=1,season_doy=180):
    rng=np.random.default_rng(seed); Tp,Tb=choose_plan(pol,A,book)
    if Tp is None: return None
    plan=make_plan(book,Tp,Tb); th=train_hours(plan); R=[]
    for d in range(days):
        r=simulate_day(plan,A,prm,rng,season_doy,line.length_mi); R.append(r)
    df=pd.DataFrame(R); pub=df.published.sum()
    wait=df.wait.mean(); excess=(df.wait-df.wait_pub).mean()
    rider=prm.weekday_boardings*(wait*COST["wait_mult"]+excess*COST["unplanned_mult"])/60*COST["vtts"]
    op=th*COST["train_hour"]
    return dict(Tp=Tp,Tb=Tb,trains_peak=book.n[Tp],train_hours=th,cancel_pct=100*df.cancelled.sum()/pub,
                ontime_pct=100*(df.operated-df.late).sum()/pub,wait=wait,excess=excess,op_cost=op,rider_cost=rider,total=op+rider)
if __name__=="__main__":
    prm=Params(); rows=[]
    for A in range(4,15):
        for name,p in POL.items():
            for seas,doy in [("summer",180),("spring",100)]:
                r=eval_A(p,A,prm,season_doy=doy)
                if r: rows.append(dict(cars=A,policy=name,season=seas,**r))
    pb=pd.DataFrame(rows).round(2); pb.to_csv(OUT/"playbook.csv",index=False)
    # figure: rider cost vs operating cost by cars (summer), per policy
    fig,axs=plt.subplots(1,2,figsize=(10,3.6))
    s=pb[pb.season=="summer"]
    for k,(name,_) in enumerate(POL.items()):
        d=s[s.policy==name]; axs[0].plot(d.cars,d.cancel_pct,"-o",ms=4,color=C[k],lw=1.6,label=name)
        axs[1].plot(d.cars,d.wait+d.excess,"-o",ms=4,color=C[k],lw=1.6,label=name)
    axs[0].set_xlabel("Cars available at 6 am"); axs[0].set_ylabel("Cancelled (% of published)"); axs[0].set_title("Cancellations by fleet size (summer)",loc="left",fontsize=10)
    axs[1].set_xlabel("Cars available at 6 am"); axs[1].set_ylabel("Avg wait + unplanned excess (min)"); axs[1].set_title("Rider wait by fleet size (summer)",loc="left",fontsize=10)
    axs[1].legend(frameon=False,fontsize=7.5,loc="upper right")
    fig.savefig(FIG/"fig_playbook.pdf"); fig.savefig(FIG/"fig_playbook.png",dpi=150); plt.close(fig)
    # total daily cost relative to the fixed 8-car schedule, by cars (summer)
    fig,ax=plt.subplots(figsize=(8,3.4)); cars=[5,6,7,8,9,10]; w=0.16
    for k,name in enumerate(POL):
        vals=[]
        for A in cars:
            q=s[(s.cars==A)&(s.policy==name)]; f=s[(s.cars==A)&(s.policy=="Fixed 8-car (20/30)")]
            vals.append((q.total.iloc[0]-f.total.iloc[0])/1000 if len(q) else np.nan)
        ax.bar(np.arange(len(cars))+(k-2)*w,vals,w,color=C[k],label=name)
    ax.axhline(0,color="#c3c2b7",lw=1); ax.set_xticks(range(len(cars))); ax.set_xticklabels([f"{c} cars" for c in cars])
    ax.set_ylabel("Total cost vs fixed 8-car ($000/day)"); ax.legend(frameon=False,fontsize=7.5,ncol=2)
    ax.set_title("Operating + rider-time cost relative to the fixed schedule (summer); below 0 is better",loc="left",fontsize=10)
    fig.savefig(FIG/"fig_cost_frontier.pdf"); fig.savefig(FIG/"fig_cost_frontier.png",dpi=150); plt.close(fig)
    # sensitivity: MDBF and rescue time at A=8 summer
    sens=[]
    for label,kw in [("base",{}),("MDBF 8,000 mi",dict(mdbf_mi=8000.)),("MDBF 2,500 mi",dict(mdbf_mi=2500.)),("rescue 30 min",dict(rescue_min=30.)),("rescue 90 min",dict(rescue_min=90.)),("block 60 min",dict(block_min=60.))]:
        p2=Params(**kw)
        for name in ["Fixed 8-car (20/30)","Tiered flexible, 1 protect","Tiered clock-face, 1 protect"]:
            for A in [8,9]:
                r=eval_A(POL[name],A,p2,days=300)
                sens.append(dict(case=label,policy=name,cars=A,cancel_pct=r["cancel_pct"],wait_total=r["wait"]+r["excess"],total_cost=r["total"]))
    pd.DataFrame(sens).round(2).to_csv(OUT/"sensitivity.csv",index=False)
    print(pb[(pb.season=="summer")&(pb.cars.isin([6,7,8,9,10]))].to_string())
    print(pd.DataFrame(sens).round(1).to_string())
