"""Evaluate the robust sweep patterns (schedule quality + delay simulation). Writes results/robust_eval.csv."""
import sys, json; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
from timetable_build import build_proposed, metrics, ROOT, build_TT
from delay_sim import prepare, run_many, PAR
de = json.load(open(ROOT / "results" / "delay_eval.json")); PAR.update(de["par"])
SW = json.load(open(ROOT / "results" / "robust_sweep.json")); PP = json.load(open(ROOT / "results" / "proposal_patterns.json"))
rows = []
cands = {k: v for k, v in SW.items()}
for k in ["E6", "G8", "R8", "E5"]: cands["prop_" + k] = PP[k]
for name, p in cands.items():
    tr = build_proposed(p, p["kmid"], keep=p["sub"][0])
    m, _ = metrics(tr, name); pr = prepare(tr)
    a = run_many(pr, 300, 1, PAR); b = run_many(pr, 300, 2, dict(PAR, heat=1.06))
    rows.append(dict(name=name, C=p["C"], g=p.get("opts", {}).get("g", 0.5), lmin=p.get("opts", {}).get("lmin", 5), trains=m["vehicles_peak"], mid=m["vehicles_midday"],
                     train_h=m["train_hours"], am_max=max(m["NB_am_max"], m["SB_am_max"]), wait=m["day_wait"], otp=a["otp"], hot=b["otp"], late=a["mean_late"],
                     wl=m["day_wait"] + a["mean_late"], conflicts=m["conflicts"]))
    print(rows[-1])
nj = run_many(prepare(build_TT()["NJT current (Sept 2026)"][1]), 300, 1, PAR)
print("NJT", nj["otp"], nj["mean_late"])
pd.DataFrame(rows).to_csv(ROOT / "results" / "robust_eval.csv", index=False)
