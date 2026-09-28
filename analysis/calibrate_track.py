"""Calibrate NJDOT single/double-track mileposts against where NJ TRANSIT's own timetable schedules meets."""
import sys, json; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_tools import *
from parse_public import gtfs2026_weekday
import numpy as np
trips=[dict(dir=r['direction'],times=[float(m) for m in r['times']]) for r in gtfs2026_weekday() if sum(m is not None for m in r['times'])==21]
out={}
for cal in [False, True]:
    line=Line2026(calibrated=cal)
    out["calibrated" if cal else "njdot_scaled"]={f"g={g}":len(conflicts(line,trips,g=g)) for g in [0.0,0.5,1.0]}
    out[("calibrated" if cal else "njdot_scaled")+"_single"]=[(round(s['a'],2),round(s['b'],2)) for s in line.single]
json.dump(out,open(ROOT/"report"/"track_calibration.json","w"),indent=1); print(json.dumps(out,indent=1))
