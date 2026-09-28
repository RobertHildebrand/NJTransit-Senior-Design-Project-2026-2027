"""Robust 7-train tier (B7): 160-min cycle, 2.5-min meet buffers, 9-min layovers; adds B7 to proposal_patterns.json."""
import json, sys
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from proposals_mip import *
def job(sub):
    r = pattern_mip2(Line2026(), 7, 160, g=2.5, lminT=9, lminC=9, sub=[(sub, 1.0)], time_limit=240)
    if r: r.update(name="B7", kmid=len(sub), opts=dict(g=2.5, lmin=9))
    return r
if __name__ == "__main__":
    subs = subset_classes(7, 6) + subset_classes(7, 5)
    with Pool(2) as p: res = [r for r in p.map(job, subs) if r and min(r["gapsN"]) >= 5.9]
    for r in res: print(r["sub"], round(r["obj"]), [round(x, 1) for x in r["gapsN"]])
    json.dump(res, open(ROOT / "results" / "robust_b7_candidates.json", "w"), indent=1)
