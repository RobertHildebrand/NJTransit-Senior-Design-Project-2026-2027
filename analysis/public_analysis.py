"""Analyses of the freely available data -> figures + key numbers for the report and dashboard."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parent.parent/"src"))
from parse_public import trip_table, gtfs2026_weekday, STOP_ORDER, PUB, ROOT
FIG = ROOT/"report"/"figures"; FIG.mkdir(parents=True, exist_ok=True)
C = ["#2a78d6","#eb6834","#1baf7a","#eda100","#e87ba4","#4a3aa7"]; INK="#0b0b0b"; MUTED="#898781"; GRID="#e1e0d9"
plt.rcParams.update({"font.size":9.5,"axes.edgecolor":"#c3c2b7","xtick.color":MUTED,"ytick.color":MUTED,"axes.spines.top":False,
  "axes.spines.right":False,"axes.grid":True,"grid.color":GRID,"grid.linewidth":0.6,"savefig.bbox":"tight"})
K = {}

# ---------------- 1. current timetable (GTFS Sept 2026) ----------------
tt = trip_table()
K["gtfs_weekday_trips"] = int(len(tt)); K["gtfs_full_trips"] = int(tt.full.sum())
K["gtfs_run_time_median"] = float(tt[tt.full].run.median())
rows = gtfs2026_weekday()
spans = {}
for r in rows:
    ts=[m for m in r["times"] if m is not None]; a,b=min(ts),max(ts)
    s=spans.setdefault(r["block"],[1e9,0]); s[0]=min(s[0],a); s[1]=max(s[1],b)
grid=np.arange(5*60,22*60+30)
active=np.array([sum(a<=t<=b for a,b in spans.values()) for t in grid])
K["gtfs_max_trains"]=int(active.max()); K["gtfs_midday_trains"]=int(active[(grid>=10*60)&(grid<=14*60)].max())
# departures from Walter Rand NB and headways
wr = STOP_ORDER.index("Walter Rand TC")
nbdep = sorted(r["times"][wr] for r in rows if r["direction"]=="NB" and r["times"][wr] is not None)
sbdep = sorted(r["times"][wr] for r in rows if r["direction"]=="SB" and r["times"][wr] is not None)
def headway_stats(deps,a,b):
    d=[x for x in deps if a<=x<b]; h=np.diff(d)
    if len(h)<2: return None
    m=h.mean(); cv=h.std()/m; return dict(n=len(d),mean=float(m),cv=float(cv),wait_random=float(m/2*(1+cv**2)),wait_even=float(m/2),gaps=[int(x) for x in h])
K["nb_walter_rand_am"]=headway_stats(nbdep,6*60+30,9*60)
K["nb_walter_rand_pm"]=headway_stats(nbdep,16*60,19*60)
K["nb_walter_rand_mid"]=headway_stats(nbdep,9*60+30,15*60)
# peak cycle: 8 trains -> departures every ? ; cycle = sum of 8 consecutive gaps
fig,axs=plt.subplots(1,2,figsize=(10,3.2),gridspec_kw={"width_ratios":[1.3,1]})
ax=axs[0]; ax.step(grid/60,active,where="post",color=C[0],lw=2); ax.set_xlabel("Hour of day"); ax.set_ylabel("Trains in service")
ax.set_title("Trains in service, Sept 2026 weekday timetable",loc="left",fontsize=10); ax.set_xlim(5,22.5); ax.set_yticks(range(0,11,2))
ax=axs[1]
for d,col,lab in [(nbdep,C[0],"To Trenton"),(sbdep,C[1],"To Camden")]:
    hrs=np.array(d)//60; cnt=[int((hrs==h).sum()) for h in range(5,23)]
    ax.bar(np.arange(5,23)+(0 if col==C[0] else 0.4),cnt,width=0.38,color=col,label=lab)
ax.set_xlabel("Hour of day"); ax.set_ylabel("Departures at Walter Rand"); ax.legend(frameon=False,fontsize=8)
ax.set_title("Departures per hour",loc="left",fontsize=10)
fig.savefig(FIG/"fig_gtfs_service_profile.pdf"); fig.savefig(FIG/"fig_gtfs_service_profile.png",dpi=150); plt.close(fig)

# time-distance of the actual timetable
from rl_data import load_line
line=load_line(); pos=list(line.stations.pos_mi)
fig,ax=plt.subplots(figsize=(10,3.6))
from rl_data import DATA
secs=pd.read_csv(DATA/"river_line_track_segments.csv"); scale=line.length_mi/secs.to_mp.max()
for _,s in line.single_sections().iterrows(): ax.axhspan(s.start_mi,s.end_mi,color="#f2e3c9",lw=0)
for r in rows:
    pts=[(m,pos[k]) for k,m in enumerate(r["times"]) if m is not None]
    ax.plot([p[0]/60 for p in pts],[p[1] for p in pts],color=C[0] if r["direction"]=="NB" else C[1],lw=1)
ax.set_xlim(5.3,22.6); ax.set_ylim(0,line.length_mi); ax.set_xlabel("Hour of day"); ax.set_ylabel("Miles from Camden"); ax.grid(False)
ax.set_title("NJ TRANSIT River LINE weekday timetable (GTFS, Sept 2026); shaded = single track (NJDOT, calibrated)",loc="left",fontsize=10)
fig.savefig(FIG/"fig_gtfs_timespace.pdf"); fig.savefig(FIG/"fig_gtfs_timespace.png",dpi=150); plt.close(fig)

# ---------------- 2. OSM: single vs double, speed limits ----------------
S14=pd.read_csv(Path("/tmp/claude-0/-home-claude/2b445e9b-e2e6-5aa4-a09b-65db272a5048/scratchpad/gtfs2014/shapes.txt"))
sh=S14[S14.shape_id==1404].sort_values("shape_pt_sequence"); Lsh=sh.shape_dist_traveled.max(); sh=sh.assign(pos=Lsh-sh.shape_dist_traveled).sort_values("pos")
shp=sh[["shape_pt_lat","shape_pt_lon","pos"]].to_numpy()
pd.DataFrame(shp,columns=["lat","lon","pos_mi"]).round(6).to_csv(PUB/"gtfs_2014_river_line_shape_camden_to_trenton.csv",index=False)
def proj(lat,lon):
    d=(shp[:,0]-lat)**2+((shp[:,1]-lon)*np.cos(np.radians(40)))**2; return float(shp[np.argmin(d),2])
osm=pd.read_csv(PUB/"osm_river_line_route_ways.csv"); osm=osm[osm.railway.isin(["rail","light_rail"])].copy()
osm["p0"]=[proj(a,b) for a,b in zip(osm.start_lat,osm.start_lon)]; osm["p1"]=[proj(a,b) for a,b in zip(osm.end_lat,osm.end_lon)]
osm["a"]=osm[["p0","p1"]].min(axis=1); osm["b"]=osm[["p0","p1"]].max(axis=1)
osm["mph"]=osm.maxspeed.str.extract(r"(\d+)").astype(float)
xs=np.round(np.arange(0,Lsh,0.01),2); single=np.zeros_like(xs,bool); nb_speed=np.full_like(xs,np.nan)
for _,w in osm.iterrows():
    m=(xs>=w.a)&(xs<=w.b)
    if w.in_route_dir=="NS": single|=m
    if "N" in w.in_route_dir and not np.isnan(w.mph): nb_speed[m]=np.fmin(np.nan_to_num(nb_speed[m],nan=999),w.mph)
nb_speed[nb_speed==999]=np.nan
# contiguous single intervals
iv=[]; cur=None
for x,s in zip(xs,single):
    if s and cur is None: cur=x
    if not s and cur is not None: iv.append((cur,x)); cur=None
if cur is not None: iv.append((cur,xs[-1]))
iv=[(a,b) for a,b in iv if b-a>0.15]
K["osm_single_intervals"]=[(round(a,2),round(b,2)) for a,b in iv]; K["osm_single_miles"]=round(sum(b-a for a,b in iv),1)
pd.DataFrame(iv,columns=["start_mi","end_mi"]).round(2).to_csv(PUB/"osm_derived_single_track_intervals.csv",index=False)
# technical minimum run time at posted speed (no dwell/accel)
v=pd.Series(nb_speed).ffill().bfill().to_numpy()
K["osm_min_runtime_at_limit_min"]=round(float(np.sum(0.01/v*60)),1)
fig,ax=plt.subplots(figsize=(10,3.2))
for a,b in iv: ax.axvspan(a,b,color="#f2e3c9",lw=0)
for _,s in secs[secs.track=="Single"].iterrows(): ax.plot([s.from_mp*scale,s.to_mp*scale],[68,68],color="#d6962c",lw=5,solid_capstyle="butt")
ax.plot(xs,v,color=C[0],lw=1.8,drawstyle="steps-post",label="Posted speed toward Trenton (OSM)")
for s in line.stations.itertuples(): ax.axvline(s.pos_mi,color=GRID,lw=0.6,zorder=0)
ax.set_ylim(0,72); ax.set_xlim(0,Lsh); ax.set_xlabel("Miles from Camden"); ax.set_ylabel("mph")
ax.text(0.2,69.5,"NJDOT single track",fontsize=8,color="#a86f12"); ax.text(0.2,3,"shaded: single track per OSM route membership",fontsize=8,color=MUTED)
ax.set_title("Speed limits and single-track sections",loc="left",fontsize=10); ax.grid(axis="x",visible=False)
fig.savefig(FIG/"fig_osm_speed_track.pdf"); fig.savefig(FIG/"fig_osm_speed_track.png",dpi=150); plt.close(fig)

# ---------------- 3. weather ----------------
wm=pd.read_csv(PUB/"noaa_trenton_monthly_2015_2026.csv"); wm["mo"]=wm.month.str[5:].astype(int); wm["yr"]=wm.month.str[:4].astype(int)
clim=wm[wm.yr<2026].groupby("mo")[["days_tmax_ge90","days_tmax_ge95","days_tmin_le32","days_snow_ge1","days_precip_ge0.5"]].mean()
K["hot_days_jul_mean"]=round(float(clim.loc[7,"days_tmax_ge90"]),1); K["freeze_days_jan_mean"]=round(float(clim.loc[1,"days_tmin_le32"]),1)
K["hot_days_2024_JJA"]=int(wm[(wm.yr==2024)&wm.mo.between(6,8)].days_tmax_ge90.sum())
K["hot_days_mean_JJA"]=round(float(wm[(wm.yr<2026)&wm.mo.between(6,8)].groupby("yr").days_tmax_ge90.sum().mean()),1)
fig,ax=plt.subplots(figsize=(8,3.2)); mo=np.arange(1,13); w=0.28
ax.bar(mo-w,clim.days_tmax_ge90,w,color=C[1],label="Days ≥ 90°F"); ax.bar(mo,clim.days_tmin_le32,w,color=C[0],label="Days ≤ 32°F (min)")
ax.bar(mo+w,clim["days_precip_ge0.5"],w,color=C[2],label="Days ≥ 0.5 in rain")
ax.set_xticks(mo); ax.set_xticklabels("JFMAMJJASOND"); ax.set_ylabel("Days per month (2015–2025 mean)"); ax.legend(frameon=False,fontsize=8,ncol=3)
ax.set_title("Trenton-Mercer Airport weather seasonality (NOAA GHCN-Daily)",loc="left",fontsize=10)
fig.savefig(FIG/"fig_weather_seasonality.pdf"); fig.savefig(FIG/"fig_weather_seasonality.png",dpi=150); plt.close(fig)

# ---------------- 4. NTD ----------------
nm=pd.read_csv(PUB/"ntd_njt_lightrail_monthly_2015_2026.csv")
fig,ax=plt.subplots(figsize=(8,3))
for tos,col,lab in [("PT",C[0],"Purchased transportation (HBLR + River LINE)"),("DO",C[1],"Directly operated (Newark LR)")]:
    d=nm[nm.type_of_service==tos]; ax.plot(pd.to_datetime(d.month),d.unlinked_passenger_trips/1e6,color=col,lw=1.6,label=lab)
ax.set_ylabel("Monthly trips (millions)"); ax.legend(frameon=False,fontsize=8); ax.set_title("NJ TRANSIT light rail monthly ridership (NTD)",loc="left",fontsize=10)
fig.savefig(FIG/"fig_ntd_ridership.pdf"); fig.savefig(FIG/"fig_ntd_ridership.png",dpi=150); plt.close(fig)
met=pd.read_csv(PUB/"ntd_njt_all_modes_metrics_2024.csv")
K["ntd_cost_per_vrh_LR_PT_2024"]=float(met[(met["mode"]=="LR")&(met.type_of_service=="PT")].cost_per_vehicle_revenue_hour.iloc[0])
K["ntd_cost_per_vrh_LR_DO_2024"]=float(met[(met["mode"]=="LR")&(met.type_of_service=="DO")].cost_per_vehicle_revenue_hour.iloc[0])
K["ntd_cost_per_vrh_MB_PT_2024"]=float(met[(met["mode"]=="MB")&(met.type_of_service=="PT")].cost_per_vehicle_revenue_hour.iloc[0])
K["ntd_cost_per_vrh_MB_DO_2024"]=float(met[(met["mode"]=="MB")&(met.type_of_service=="DO")].cost_per_vehicle_revenue_hour.iloc[0])
bd=pd.read_csv(PUB/"ntd_njt_lightrail_breakdowns_2022_2024.csv")
bd["mi_per_major"]=bd.vehicle_passenger_car_miles/bd.major_mechanical_failures
K["ntd_LR_PT_miles_per_major_failure"]={int(r.report_year):int(r.mi_per_major) for r in bd[bd.type_of_service=="PT"].itertuples()}
json.dump(K,open(ROOT/"report"/"key_numbers.json","w"),indent=1)
print(json.dumps(K,indent=1))
