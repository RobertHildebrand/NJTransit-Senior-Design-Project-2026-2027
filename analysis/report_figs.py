import json, sys; from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent.parent; FIG=ROOT/"report"/"figures"; sys.path.insert(0,str(ROOT/"analysis"))
C={"NJT published":"#6b736e","Proposed tiers, 0 protect":"#eb6834","Proposed tiers, 1 protect":"#2a78d6","Proposed tiers, 2 protect":"#4a3aa7","Tiered flexible, 1 protect":"#eda100","Tiered clock-face, 1 protect":"#1baf7a"}
MUTED="#898781"; GRID="#e1e0d9"
plt.rcParams.update({"font.size":9.5,"axes.edgecolor":"#c3c2b7","xtick.color":MUTED,"ytick.color":MUTED,"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,"grid.color":GRID,"grid.linewidth":0.6,"savefig.bbox":"tight"})
d=json.load(open(ROOT/"results"/"js_eval.json"))
yr=d["year"]; seasons=["winter","spring","summer","fall"]
fig,ax=plt.subplots(figsize=(8.5,3.4)); w=0.16
for k,r in enumerate(yr):
    ax.bar(np.arange(4)+(k-2)*w,[r["bySeason"][s] for s in seasons],w,color=C[r["name"]],label=f'{r["name"]} ({r["cancel_pct"]:.1f}% year)')
ax.set_xticks(range(4)); ax.set_xticklabels([s.title() for s in seasons]); ax.set_ylabel("Trips cancelled (% of published)"); ax.legend(frameon=False,fontsize=7.5)
ax.set_title("Cancellations by season over a simulated year (10 runs)",loc="left",fontsize=10)
fig.savefig(FIG/"fig_js_year.pdf"); plt.close(fig)
pb=pd.DataFrame(d["playbook"]); s=pb[pb.season=="summer"]
fig,axs=plt.subplots(1,2,figsize=(10,3.5))
for name,g in s.groupby("policy"):
    g=g.sort_values("cars"); axs[0].plot(g.cars,g.cancel_pct,"-o",ms=3.5,lw=1.6,color=C[name],label=name)
    nj=s[s.policy=="NJT published"].set_index("cars").total
    axs[1].plot(g.cars,(g.set_index("cars").total-nj.reindex(g.cars).values)/1000,"-o",ms=3.5,lw=1.6,color=C[name])
axs[0].set_xlabel("Cars at the 6 am hold sheet"); axs[0].set_ylabel("Cancelled (% of published)"); axs[0].legend(frameon=False,fontsize=7.5)
axs[0].set_title("Cancellations by cars available (summer)",loc="left",fontsize=10)
axs[1].axhline(0,color="#c3c2b7"); axs[1].set_xlabel("Cars at the 6 am hold sheet"); axs[1].set_ylabel("$000/day vs NJT published")
axs[1].set_title("Operating + rider-time cost vs NJT published (below 0 is better)",loc="left",fontsize=10); axs[1].set_ylim(-60,20)
fig.savefig(FIG/"fig_js_playbook.pdf"); plt.close(fig)
# sensitivity
sd=pd.DataFrame(json.load(open(ROOT/"results"/"js_sensitivity.json")))
cases=["base","MDBF 2,500 mi","MDBF 8,000 mi","repair 6 days","repair 20 days","rescue speed 15 mph"]
fig,ax=plt.subplots(figsize=(7.5,3))
for k,name in enumerate(["NJT published","Proposed tiers, 1 protect","Tiered flexible, 1 protect"]):
    v=[sd[(sd.case==c)&(sd.name==name)].cancel_pct.iloc[0] for c in cases]
    ax.scatter(v,np.arange(len(cases))+(k-1)*0.18,color=C[name],s=40,label=name,zorder=3,edgecolor="white")
ax.set_yticks(range(len(cases))); ax.set_yticklabels(cases); ax.invert_yaxis(); ax.set_xlabel("Trips cancelled over a year (%)"); ax.legend(frameon=False,fontsize=7.5)
ax.set_title("Sensitivity of annual cancellations to uncertain parameters",loc="left",fontsize=10)
fig.savefig(FIG/"fig_js_sensitivity.pdf"); plt.close(fig)
# meets histogram and track calibration
from timetable_tools import Line2026
m=pd.read_csv(ROOT/"data_public"/"gtfs_2026_observed_meet_points.csv")
fig,ax=plt.subplots(figsize=(10,2.9))
ax.hist(m.pos,bins=np.arange(0,34,0.25),color="#2a78d6")
for yy,cal,lab in [(-6,False,"NJDOT as scaled"),(-12,True,"calibrated")]:
    L=Line2026(calibrated=cal)
    for s in L.single: ax.plot([s["a"],s["b"]],[yy,yy],color="#d6962c",lw=5,solid_capstyle="butt")
    ax.text(33.4,yy+2.6,lab,ha="right",va="center",fontsize=8,color=MUTED)
ax.set_ylim(-16,40); ax.set_xlim(0,33.6); ax.set_xlabel("Miles from Camden"); ax.set_ylabel("Scheduled meets per weekday")
ax.set_title("Where NJ TRANSIT's timetable schedules trains to pass (bars) vs single track (orange)",loc="left",fontsize=10)
fig.savefig(FIG/"fig_meets_calibration.pdf"); plt.close(fig)
print("ok")
