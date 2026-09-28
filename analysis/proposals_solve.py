"""Solve the pattern MIPs behind the proposed schedules (writes results/proposal_patterns.json).

  E5  8 trains peak, 5 midday: peak and midday spacing optimized jointly (frees a 6th car midday)
  E6  8 trains peak, 6 midday: as T8 but with the midday subset optimized jointly
  R8  8 trains on a 160-min cycle with >= 8-min layovers at both ends (more recovery time)
  S8  8 trains on 150 min, 6% of running time moved into scheduled holds just before each single-track section
  G8  8 trains on 150 min, 6 midday, 2-min buffer at every single-track meet (robust meets)
  W7  summer: running times +6% (heat speed restrictions), 7 trains on 160 min, 5 midday
"""
import json, sys
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from proposals_mip import *

HOLD_SHARE = 0.06


def job(spec):
    name, K, C, kmid, sub, opts = spec
    if opts.get("scale"): line = scaled_line(opts["scale"])
    else: line = Line2026()
    kw = dict(lminT=opts.get("lmin", 5.0), lminC=opts.get("lmin", 5.0), time_limit=opts.get("tl", 90), g=opts.get("g", 0.5))
    if opts.get("holds"):
        line = scaled_line(1 - HOLD_SHARE)
        N, S = pre_single_holds(line)
        h = 67.0 * HOLD_SHARE
        kw["holdN"] = {d: h / len(N) for d in N}; kw["holdS"] = {d: h / len(S) for d in S}
    r = pattern_mip2(line, K, C, sub=[(sub, 1.0)], **kw)
    if r: r.update(name=name, kmid=kmid, opts=opts, holdN=kw.get("holdN"), holdS=kw.get("holdS"))
    return r


if __name__ == "__main__":
    want = sys.argv[1:] or ["E5", "E6", "R8", "S8", "G8", "W7"]
    tl = 240
    specs = []
    if "E5" in want: specs += [("E5", 8, 150, 5, sub, {"tl": tl}) for sub in subset_classes(8, 5)]
    if "E6" in want: specs += [("E6", 8, 150, 6, sub, {"tl": tl}) for sub in subset_classes(8, 6)]
    if "R8" in want: specs += [("R8", 8, 160, 6, sub, {"lmin": 8.0, "tl": tl}) for sub in subset_classes(8, 6)]
    if "S8" in want: specs += [("S8", 8, 150, 6, sub, {"holds": True, "tl": tl}) for sub in subset_classes(8, 6)]
    if "G8" in want: specs += [("G8", 8, 150, 6, sub, {"g": 2.0, "tl": tl}) for sub in subset_classes(8, 6)]
    if "W7" in want: specs += [("W7", 7, 160, 5, sub, {"scale": 1.06, "tl": tl}) for sub in subset_classes(7, 5)]
    with Pool(2) as p: res = p.map(job, specs)
    f = ROOT / "results" / "proposal_patterns.json"
    best = json.load(open(f)) if f.exists() else {}
    best = {k: v for k, v in best.items() if k not in want}
    for r in res:
        if r is None or min(r["gapsN"]) < 5.9: continue      # time limit hit without an incumbent
        if r["name"] not in best or r["obj"] < best[r["name"]]["obj"]: best[r["name"]] = r
    for k, r in best.items():
        print(k, r["status"], round(r["obj"]), r["sub"], [round(x, 1) for x in r["gapsN"]])
    json.dump(best, open(f, "w"), indent=1)
