"""Delay simulation under two calibrated regimes (writes results/delay_regimes.json).

  alstom_2024_25 : incident rate fitted so today's timetable is 83% on time (NJ TRANSIT reported 80-87% in 2023-25)
  njt_2026       : incident rate fitted so today's timetable is 93% on time (OLS: 'above 93 percent' since Feb 2026)

For each regime and timetable: mean on-time share on normal and hot days, and the distribution of daily on-time share
(used to test the model against OLS's reported worst days of 45% and 56%).
"""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_build import build_TT, ROOT
from delay_sim import prepare, simulate, PAR

DAYS = 300
TT = build_TT(); PREP = {n: prepare(tr) for _, (n, tr) in TT.items()}

def fit(target):
    lo, hi = 0.0, 0.5
    for _ in range(10):
        mid = (lo + hi) / 2; rng = np.random.default_rng(11)
        o = np.mean([simulate(PREP["njt_current"], rng, dict(PAR, p_inc=mid))["otp"] for _ in range(200)])
        lo, hi = (mid, hi) if o > target else (lo, mid)
    return round((lo + hi) / 2, 4)

out = {}
for regime, target in [("alstom_2024_25", 0.83), ("njt_2026", 0.93)]:
    p = fit(target); par = dict(PAR, p_inc=p); hot = dict(par, heat=1.06)
    res = {}
    for name, pr in PREP.items():
        r1 = np.random.default_rng(1); r2 = np.random.default_rng(2)
        a = np.array([simulate(pr, r1, par)["otp"] for _ in range(DAYS)]); b = np.array([simulate(pr, r2, hot)["otp"] for _ in range(DAYS)])
        res[name] = dict(normal=dict(otp=float(a.mean()), p5=float(np.percentile(a, 5)), min=float(a.min())),
                         hot=dict(otp=float(b.mean()), p5=float(np.percentile(b, 5)), min=float(b.min())))
    out[regime] = dict(p_inc=p, target=target, tt=res)
    print(regime, "p_inc", p, {k: round(v["normal"]["otp"], 3) for k, v in res.items() if k in ("njt_current", "proposed_T8", "proposal_B8", "proposal_W7")})
json.dump(out, open(ROOT / "results" / "delay_regimes.json", "w"), indent=1)
