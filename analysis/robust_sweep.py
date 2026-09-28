"""Sweep of robust 8-train patterns: cycle C, meet buffer g, minimum layover. Writes results/robust_sweep.json."""
import json, sys
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from proposals_mip import *
CFG = [(150, 1.5, 7), (150, 2.0, 6.5), (155, 1.5, 8), (155, 2.0, 8), (160, 2.0, 8), (160, 1.5, 10), (165, 2.0, 10), (160, 2.5, 9)]
SUBS = [[0, 1, 2, 3, 4, 6], [0, 1, 2, 3, 5, 6]]
def job(a):
    (C, g, lm), sub = a
    r = pattern_mip2(Line2026(), 8, C, g=g, lminT=lm, lminC=lm, sub=[(sub, 1.0)], time_limit=200)
    if r: r.update(name=f"C{C}_g{g}_l{lm}", kmid=6, opts=dict(g=g, lmin=lm))
    return r
if __name__ == "__main__":
    with Pool(2) as p: res = p.map(job, [(c, s) for c in CFG for s in SUBS])
    best = {}
    for r in res:
        if r is None or min(r["gapsN"]) < 5.9: continue
        if r["name"] not in best or r["obj"] < best[r["name"]]["obj"]: best[r["name"]] = r
    for k, r in best.items(): print(k, r["status"], round(r["obj"]), [round(x, 1) for x in r["gapsN"]])
    json.dump(best, open(ROOT / "results" / "robust_sweep.json", "w"), indent=1)
