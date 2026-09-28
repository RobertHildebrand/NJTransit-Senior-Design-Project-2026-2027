import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(ROOT/"analysis")); sys.path.insert(0,str(ROOT/"src"))
from parse_public import gtfs2026_weekday, PUB
from rl_data import load_line
line=load_line(); pos=[round(x,3) for x in line.stations.pos_mi]
g=[dict(d=r["direction"],b=r["block"],t=r["times"]) for r in gtfs2026_weekday()]
wm=pd.read_csv(PUB/"noaa_trenton_monthly_2015_2026.csv"); wm["mo"]=wm.month.str[5:].astype(int); wm["yr"]=wm.month.str[:4].astype(int)
clim=wm[wm.yr<2026].groupby("mo")[["days_tmax_ge90","days_tmin_le32","days_precip_ge0.5","days_snow_ge1"]].mean().round(2)
nm=pd.read_csv(PUB/"ntd_njt_lightrail_monthly_2015_2026.csv")
ntd={tos:[[r.month,int(r.unlinked_passenger_trips)] for r in nm[nm.type_of_service==tos].itertuples()] for tos in ["PT","DO"]}
osm=pd.read_csv(PUB/"osm_derived_single_track_intervals.csv")
K=json.load(open(ROOT/"report"/"key_numbers.json"))
pb=pd.read_csv(ROOT/"results"/"playbook.csv")
out=dict(gtfs=dict(stationPos=pos,trips=g),
  weather=dict(months=list(range(1,13)),hot=clim.days_tmax_ge90.tolist(),freeze=clim.days_tmin_le32.tolist(),rain=clim["days_precip_ge0.5"].tolist(),snow=clim.days_snow_ge1.tolist()),
  ntd=ntd, osmSingle=osm.values.round(2).tolist(), keys=K,
  playbook=json.loads(pb.to_json(orient="records")))
json.dump(out,open(ROOT.parent/"rl_map"/"data2.json","w"),separators=(",",":"))
print(len(json.dumps(out)))
