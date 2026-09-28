"""Parse the public data pulled on 2026-09-28 into tidy tables used by the model and report."""
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "data_public"
STOP_ORDER = ["Entertainment Center","Aquarium","Cooper St/Rutgers","Walter Rand TC","36th Street","Pennsauken TC","Route 73/Pennsauken","Palmyra","Riverton","Cinnaminson","Riverside","Delanco","Beverly/Edgewater Park","Burlington South","Burlington Towne Ctr","Florence","Roebling","Bordentown","Cass Street","Hamilton Avenue","Trenton TC"]

def gtfs2026_weekday():
    rows=[]
    for i,line in enumerate(open(PUB/"gtfs_2026-09_weekday_timetable_raw.txt").read().strip().split("\n")):
        d,b,t=line.split(";"); ts=t.split(" ")
        mins=[None if x=="-" else int(x[:2])*60+int(x[2:]) for x in ts]
        rows.append(dict(trip=i,direction="NB" if d=="1" else "SB",block=int(b),times=mins))
    return rows

def trip_table():
    out=[]
    for r in gtfs2026_weekday():
        idx=[k for k,m in enumerate(r["times"]) if m is not None]
        first,last=(idx[0],idx[-1]) if r["direction"]=="NB" else (idx[-1],idx[0])
        dep=r["times"][first]; arr=r["times"][last]
        out.append(dict(trip=r["trip"],direction=r["direction"],block=r["block"],origin=STOP_ORDER[first],dest=STOP_ORDER[last],
                        dep=dep,arr=arr,run=arr-dep,n_stops=len(idx),full=(len(idx)==21)))
    return pd.DataFrame(out)

def segment_runtimes_2026():
    rows=[]
    for r in gtfs2026_weekday():
        if sum(m is not None for m in r["times"])<21: continue
        for k in range(20):
            a,b=(k,k+1) if r["direction"]=="NB" else (k+1,k)
            rows.append(dict(direction=r["direction"],seg=k,from_stop=STOP_ORDER[a],to_stop=STOP_ORDER[b],mins=r["times"][b]-r["times"][a]))
    df=pd.DataFrame(rows)
    return df.groupby(["direction","seg","from_stop","to_stop"]).mins.median().reset_index()

if __name__=="__main__":
    tt=trip_table(); print(tt.groupby(["direction","full"]).run.describe())
    print(segment_runtimes_2026().groupby("direction").mins.sum())
