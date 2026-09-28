import sys, json, time; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_tools import *
line=Line2026(calibrated=True)
res={}
for K in [8,7,6,5,4,3]:
    for C in [144,146,148,150,152,156,160]:
        t=time.time(); r=pattern_mip(line,K,C,g=0.5,time_limit=(60 if K>=7 else 40))
        key=f"{K}_{C}"
        if r is None: res[key]=None; print(key,'infeasible',round(time.time()-t,1),flush=True); continue
        # verify
        trips=trips_from_pattern(line,r,6*60,6*60+3*C); r['conflicts']=len(conflicts(line,trips,g=0.5))
        res[key]=r; print(key,r['status'],[round(x) for x in r['gapsN']],[round(x) for x in r['gapsS']],round(r['waitN'],2),round(r['waitS'],2),'conf',r['conflicts'],round(time.time()-t,1),flush=True)
        json.dump(res,open(ROOT/"results"/"patterns.json","w"))
