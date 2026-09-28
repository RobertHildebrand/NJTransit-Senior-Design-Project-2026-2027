"""Run the delay-propagation simulation on every timetable (normal and hot days), sensitivity runs, meet-slack
analysis, and sample-day replays for the dashboard.  Writes results/delay_eval.json and timetables/delay_replays.json."""
import sys, json, copy
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_build import build_TT, ROOT, line as LINE
import delay_sim as DSM
from delay_sim import prepare, run_many, simulate, PAR

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 400
TT = build_TT()
PREP = {name: prepare(trips) for lab, (name, trips) in TT.items()}
LAB = {name: lab for lab, (name, trips) in TT.items()}

# ---- calibration: incident rate so that today's timetable gives ~83% on time (NJ TRANSIT reported 80-84%, 2023-25)
TARGET = 0.83
lo, hi = 0.02, 0.5
for _ in range(9):
    mid = (lo + hi) / 2
    o = run_many(PREP["njt_current"], 200, 11, dict(PAR, p_inc=mid))["otp"]
    lo, hi = (mid, hi) if o > TARGET else (lo, mid)
PAR["p_inc"] = round((lo + hi) / 2, 3)
print("calibrated p_inc", PAR["p_inc"])
HOT = dict(PAR, heat=1.06)

res = {"par": dict(PAR), "target_otp": TARGET, "tt": {}}
for name, p in PREP.items():
    a = run_many(p, DAYS, 1, PAR); b = run_many(p, DAYS, 2, HOT)
    res["tt"][name] = dict(label=LAB[name], normal=a, hot=b)
    print(f"{name:14s} OTP {a['otp']:.3f} hot {b['otp']:.3f}  late {a['mean_late']:.2f}  knock {a['knock']:.0f}")

# ---- meet slack in the schedule (how much a late train can absorb before it delays the opposing train)
def meet_slack(p):
    N = p["N"]; out = []
    for (i, kin), (j, ko, allow) in p["need"].items():
        out.append(N[i]["dep"][kin] - (N[j]["dep"][ko] + PAR["g"] - allow))
    return np.array(out)
res["slack"] = {}
for name, p in PREP.items():
    s = meet_slack(p); s = s[s < 60]     # meets more than an hour apart are not really interacting
    res["slack"][name] = dict(n=int(len(s)), lt1=float((s < 1).mean()), lt3=float((s < 3).mean()), median=float(np.median(s)),
                              hist=np.histogram(np.clip(s, 0, 30), bins=range(0, 31))[0].tolist())

# ---- sensitivity (subset of timetables)
KEYS = ["njt_current", "proposed_T8"] + [k for k in PREP if k.startswith("proposal_")]
SENS = {"supp 6%": dict(PAR, supp=0.06), "supp 14%": dict(PAR, supp=0.14), "incidents x2": dict(PAR, p_inc=PAR["p_inc"] * 2),
        "incidents x0.5": dict(PAR, p_inc=PAR["p_inc"] / 2), "segment noise x2": dict(PAR, sd_seg=PAR["sd_seg"] * 2), "turnaround 6 min": dict(PAR, turn=6.0)}
res["sens"] = {s: {k: run_many(PREP[k], DAYS // 2, 3, par)["otp"] for k in KEYS} for s, par in SENS.items()}
json.dump(res, open(ROOT / "results" / "delay_eval.json", "w"), indent=1)

# ---- sample-day replays for the dashboard: a typical and a bad normal day, and a hot day, same random draws
REPLAY_KEYS = ["njt_current", "proposed_T8"] + [k for k in PREP if k.startswith("proposal_")] + ["uniform_U8"]
def replay(p, seed, par):
    r = simulate(p, np.random.default_rng(seed), par, record=True)
    trips = []
    for i, t in enumerate(p["trips"]):
        nd = p["N"][i]; act = r["act"][i]
        st = {}
        for k in range(21):
            if t["times"][k] is None: continue
            idx = [q for q, x in enumerate(nd["x"]) if abs(x - LINE.pos[k]) < 1e-6]
            if idx and act[idx[0]] is not None: st[k] = round(act[idx[0]], 1)
        trips.append(dict(d=t["dir"], p=[None if x is None else round(x, 1) for x in t["times"]], a=[st.get(k) for k in range(21)],
                          k=round(r["knock_by_trip"][i], 1), l=round(r["late_end"][i], 1),
                          w=[[round(x, 2), round(t0, 1), round(dd, 1)] for (ti, x, t0, dd) in r["kev"] if ti == i]))
    return dict(otp=r["otp"], mean_late=r["mean_late"], knock=r["knock"], trips=trips)
# choose seeds by NJT outcome so every timetable replays the same "kind" of day
scores = [(simulate(PREP["njt_current"], np.random.default_rng(s), PAR)["otp"], s) for s in range(1, 120)]
scores.sort()
seeds = {"typical": scores[len(scores) // 2][1], "bad": scores[len(scores) // 10][1]}
rep = {"seeds": seeds, "days": {}}
for kind, seed, par in [("typical", seeds["typical"], PAR), ("bad", seeds["bad"], PAR), ("hot", seeds["typical"], HOT)]:
    rep["days"][kind] = {k: replay(PREP[k], seed, par) for k in REPLAY_KEYS}
json.dump(rep, open(ROOT / "timetables" / "delay_replays.json", "w"), separators=(",", ":"))
print("seeds", seeds)
