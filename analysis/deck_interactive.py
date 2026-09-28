"""Data for the deck's interactive slides: planned trajectories, scheduled meets with slack, and where
knock-on delay builds up (by single-track section and by hour) under the two calibrated delay regimes.
Writes results/deck_interactive.json."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_build import build_TT, ROOT
from delay_sim import prepare, simulate, PAR, BASE

KEYS = ["njt_current", "proposal_B8", "proposed_T8", "proposal_B7"]
DAYS = 300
REG = json.load(open(ROOT / "results" / "delay_regimes.json"))
TT = build_TT(); byname = {n: tr for _, (n, tr) in TT.items()}
SEC = [(s["a"], s["b"]) for s in BASE.single]

def sec_of(x):
    for si, (a, b) in enumerate(SEC):
        if abs(x - a) < 1e-6 or abs(x - b) < 1e-6: return si
    return None

out = {"sections": [[round(a, 2), round(b, 2)] for a, b in SEC], "tt": {}}
for k in KEYS:
    P = prepare(byname[k]); N = P["N"]; trips = P["trips"]
    # planned trajectories (node positions incl. single-track ends, with arrival and departure)
    traj = []
    for i, t in enumerate(trips):
        pts = []
        for x, a, d in zip(N[i]["x"], N[i]["arr"], N[i]["dep"]):
            pts.append([round(x, 2), round(a, 1)])
            if d - a > 0.05: pts.append([round(x, 2), round(d, 1)])
        traj.append([t["dir"], pts])
    # scheduled meets: train i enters single section after opposing train j leaves it
    meets = []
    for (i, kin), (j, ko, allow) in P["need"].items():
        si = sec_of(N[i]["x"][kin]); slack = N[i]["dep"][kin] - N[j]["dep"][ko]
        meets.append([si, round(N[i]["x"][kin], 2), round(N[i]["dep"][kin], 1), round(slack, 1), i, j])
    meets.sort(key=lambda m: m[2])
    reg = {}
    for rname, rv in REG.items():
        par = dict(PAR, p_inc=rv["p_inc"]); rng = np.random.default_rng(7)
        bysec = np.zeros((len(SEC), 2)); byhour = np.zeros(24); otp = []; late = []
        for _ in range(DAYS):
            r = simulate(P, rng, par, record=True); otp.append(r["otp"]); late.append(r["mean_late"])
            for (ti, x, t0, dd) in r["kev"]:
                si = sec_of(x)
                if si is not None: bysec[si, 0 if trips[ti]["dir"] == "NB" else 1] += dd
                byhour[min(23, int(t0 // 60))] += dd
        reg[rname] = dict(otp=round(float(np.mean(otp)) * 100, 1), late=round(float(np.mean(late)), 2),
                          knock=round(float(bysec.sum() / DAYS), 1),
                          bysec=[[round(v / DAYS, 2) for v in row] for row in bysec],
                          byhour=[round(v / DAYS, 2) for v in byhour])
        print(k, rname, reg[rname]["otp"], reg[rname]["knock"], [round(sum(r), 1) for r in reg[rname]["bysec"]])
    out["tt"][k] = dict(traj=traj, meets=meets, reg=reg)
json.dump(out, open(ROOT / "results" / "deck_interactive.json", "w"), separators=(",", ":"))
print("size", len(json.dumps(out, separators=(",", ":"))) / 1e3, "kB")
