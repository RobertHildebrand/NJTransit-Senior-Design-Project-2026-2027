"""Tools for building and checking River LINE timetables with 2026 running times.

- line2026():   stations, cumulative scheduled times (2026 GTFS medians), NJDOT track sections
- pattern_mip(): cyclic, NON-uniform timetable for K trains on cycle C minutes that places every
                opposing meet on double track and minimizes sum of squared headways (rider wait)
- full-day timetables from patterns, FIFO vehicle blocks, conflict checker, metrics
"""
import sys, math
from pathlib import Path
import numpy as np, pandas as pd, pulp
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"src")); sys.path.insert(0, str(ROOT/"analysis"))
from rl_data import DATA
from parse_public import segment_runtimes_2026, STOP_ORDER

CAL_DELTA, CAL_M0, CAL_SPAN = 1.5, 12.0, 2.0

class Line2026:
    def __init__(self, calibrated=True):
        st = pd.read_csv(DATA/"river_line_stops.csv").sort_values("seq_south_to_north")
        self.pos = st.dist_from_ent_center_mi_shape.to_numpy(float); self.L = float(self.pos[-1])
        self.names = STOP_ORDER
        sr = segment_runtimes_2026()
        nb = sr[sr.direction=="NB"].sort_values("seg").mins.to_numpy(float)
        sb = sr[sr.direction=="SB"].sort_values("seg").mins.to_numpy(float)   # seg k: between stop k and k+1
        self.tN = np.concatenate([[0], np.cumsum(nb)])                    # NB time at stop k from Camden
        tS_rev = np.concatenate([[0], np.cumsum(sb[::-1])])                  # from Trenton
        self.tS = tS_rev[::-1].copy()                                          # SB time at stop k measured from Trenton
        self.runN, self.runS = float(self.tN[-1]), float(self.tS[0])
        sec = pd.read_csv(DATA/"river_line_track_segments.csv"); sc = self.L/sec.to_mp.max()
        # Calibration: NJDOT mileposts rescaled to GTFS shape distance, plus a +1.5 mi shift north of MP 12
        # (ramped over 2 mi). Fitted so that every meet in NJ TRANSIT's Sept 2026 timetable falls on
        # double track (1 residual conflict at the Pennsauken siding end). See analysis/calibrate_track.py.
        self.calibrated = calibrated
        f = (lambda mp: mp*sc + CAL_DELTA*np.clip((mp-CAL_M0)/CAL_SPAN, 0, 1)) if calibrated else (lambda mp: mp*sc)
        self.sections = [dict(track=r.track, a=f(r.from_mp), b=min(f(r.to_mp), self.L), siding=str(r.siding_name).replace(" (spelled 'Roehling' in source)","") if isinstance(r.siding_name,str) else "") for r in sec.itertuples()]
        self.single = [s for s in self.sections if s["track"]=="Single"]
        self.double = [s for s in self.sections if s["track"]=="Double"]
    def timeN(self, x): return float(np.interp(x, self.pos, self.tN))
    def timeS(self, x): return float(np.interp(x, self.pos, self.tS))

def pattern_mip(line, K, C, g=1.0, lmin=5.0, mingap=6.0, wmax=6.0, time_limit=60, verbose=False):
    D = range(len(line.double)); S = line.single
    m = pulp.LpProblem(f"pat_K{K}_C{C}", pulp.LpMinimize)
    a = [pulp.LpVariable(f"a{k}", 0, C) for k in range(K)]
    wN = [[pulp.LpVariable(f"wN{k}_{d}", 0, wmax) for d in D] for k in range(K)]
    wS = [[pulp.LpVariable(f"wS{k}_{d}", 0, wmax) for d in D] for k in range(K)]
    lT = [pulp.LpVariable(f"lT{k}", lmin, C) for k in range(K)]
    m += a[0] == 0
    for k in range(K-1): m += a[k+1] - a[k] >= mingap
    m += C - a[K-1] >= mingap
    WN = [pulp.lpSum(wN[k]) for k in range(K)]; WS = [pulp.lpSum(wS[k]) for k in range(K)]
    b = [a[k] + line.runN + WN[k] + lT[k] for k in range(K)]           # SB departure from Trenton
    for k in range(K):
        m += a[k] + C - (b[k] + line.runS + WS[k]) >= lmin              # Camden turnback closes the cycle
    for k in range(K-1): m += b[k+1] - b[k] >= mingap
    m += b[0] + C - b[K-1] >= mingap
    # single-track: NB train i vs SB train j, periodic in C
    for s in S:
        oN = line.timeN(s["b"]) - line.timeN(s["a"]); oS = line.timeS(s["a"]) - line.timeS(s["b"])
        for i in range(K):
            p = a[i] + line.timeN(s["a"]) + pulp.lpSum(wN[i][d] for d in D if line.double[d]["b"] <= s["a"]+1e-9)
            for j in range(K):
                q = b[j] + line.timeS(s["b"]) + pulp.lpSum(wS[j][d] for d in D if line.double[d]["a"] >= s["b"]-1e-9)
                z = pulp.LpVariable(f"z_{i}_{j}_{int(s['a']*100)}", -4, 4, cat="Integer")
                e = q - p - oN - g + C*z
                m += e >= 0; m += e <= C - oN - oS - 2*g
    # objective: sum of squared gaps (NB and SB), tangent-line linearization of g^2
    gaps = [a[k+1]-a[k] for k in range(K-1)] + [C - a[K-1]] + [b[k+1]-b[k] for k in range(K-1)] + [b[0]+C-b[K-1]]
    u = [pulp.LpVariable(f"u{i}", 0) for i in range(len(gaps))]
    for i, gg in enumerate(gaps):
        for t in range(4, 80, 2): m += u[i] >= 2*t*gg - t*t
    m += pulp.lpSum(u) + 0.2*pulp.lpSum(WN) + 0.2*pulp.lpSum(WS)
    m.solve(pulp.HiGHS(msg=verbose, timeLimit=time_limit))
    if pulp.LpStatus[m.status] not in ("Optimal",) and pulp.value(a[1]) is None: return None
    if pulp.LpStatus[m.status] == "Infeasible": return None
    v = lambda x: float(pulp.value(x))
    A = [v(x) for x in a]; B = [v(x) for x in b]
    res = dict(K=K, C=C, status=pulp.LpStatus[m.status], a=A, b=B,
               wN=[[v(x) for x in row] for row in wN], wS=[[v(x) for x in row] for row in wS], lT=[v(x) for x in lT])
    gN = np.diff(A + [A[0]+C]); gS = np.diff(sorted(B) + [sorted(B)[0]+C])
    res["gapsN"] = gN.tolist(); res["gapsS"] = gS.tolist()
    res["waitN"] = float((gN**2).sum()/(2*C)); res["waitS"] = float((gS**2).sum()/(2*C))
    return res

def stop_times(line, direction, dep, waits):
    """Times at each of 21 stops for one trip given siding waits (list over double sections)."""
    out = []
    for k, x in enumerate(line.pos):
        if direction == "NB":
            w = sum(waits[d] for d, s in enumerate(line.double) if s["b"] <= x + 1e-9)
            out.append(dep + line.tN[k] + w)
        else:
            w = sum(waits[d] for d, s in enumerate(line.double) if s["a"] >= x - 1e-9)
            out.append(dep + line.tS[k] + w)
    return out

def trajectory(line, direction, dep, waits):
    """Exact (pos, time) breakpoints: running time interpolated between stations; siding waits taken at the
    downstream end of each double-track section (NB: end b; SB: start a)."""
    pts = sorted(set(list(line.pos) + [s["a"] for s in line.sections] + [s["b"] for s in line.sections]))
    out = []; cum = 0.0
    seq = pts if direction == "NB" else pts[::-1]
    for x in seq:
        base = line.timeN(x) if direction == "NB" else line.timeS(x)
        out.append((x, dep + base + cum))
        for d, s in enumerate(line.double):
            edge = s["b"] if direction == "NB" else s["a"]
            if abs(edge - x) < 1e-9 and waits[d] > 1e-6:
                cum += waits[d]; out.append((x, dep + base + cum))
    return out

def trips_from_pattern(line, pat, start, end):
    """Instantiate a pattern: NB departures a_k + nC and SB b_k + nC whose origin departure lies in [start, end)."""
    trips = []; C = pat["C"]
    base = start - (start % C) - C
    for n in range(-2, int((end-start)/C) + 3):
        for k in range(pat["K"]):
            t = base + n*C + pat["a"][k]
            if start <= t < end: trips.append(dict(dir="NB", times=stop_times(line, "NB", t, pat["wN"][k]), traj=trajectory(line, "NB", t, pat["wN"][k])))
            t2 = base + n*C + pat["b"][k]
            if start <= t2 < end: trips.append(dict(dir="SB", times=stop_times(line, "SB", t2, pat["wS"][k]), traj=trajectory(line, "SB", t2, pat["wS"][k])))
    return trips

def fifo_blocks(trips, lmin=5.0):
    """Chain trips into vehicle blocks: a train arriving at a terminal takes the next departure there >= arrival + lmin."""
    ev = sorted(range(len(trips)), key=lambda i: (trips[i]["times"][0] if trips[i]["dir"]=="NB" else trips[i]["times"][-1]))
    dep = lambda t: t["times"][0] if t["dir"]=="NB" else t["times"][-1]
    arr = lambda t: t["times"][-1] if t["dir"]=="NB" else t["times"][0]
    waiting = {"C": [], "T": []}   # (ready_time, block)
    blocks = []
    for i in ev:
        t = trips[i]; term = "C" if t["dir"]=="NB" else "T"; d = dep(t)
        cand = [w for w in waiting[term] if w[0] <= d]
        if cand:
            w = min(cand, key=lambda w: w[0]); waiting[term].remove(w); blk = w[1]
        else:
            blk = len(blocks); blocks.append([])
        blocks[blk].append(i); t["block"] = blk
        waiting["T" if term=="C" else "C"].append((arr(t) + lmin, blk))
    return blocks

def conflicts(line, trips, g=1.0):
    """Count NB/SB pairs occupying the same single-track section at the same time (with buffer g)."""
    bad = []
    occ = []
    for i, t in enumerate(trips):
        tt = t["times"]; tr = t.get("traj")
        def at(x, first):
            if tr is None: return float(np.interp(x, line.pos, tt))
            ts = [tm for (p, tm) in tr if abs(p - x) < 1e-9]
            if ts: return max(ts) if first else min(ts)
            ps = [p for p, _ in tr]; tms = [tm for _, tm in tr]
            if t["dir"] == "SB": ps, tms = ps[::-1], tms[::-1]
            return float(np.interp(x, ps, tms))
        for s in line.single:
            if t["dir"] == "NB":
                t_in = at(s["a"], True); t_out = at(s["b"], False)
            else:
                t_in = at(s["b"], True); t_out = at(s["a"], False)
            occ.append((round(s["a"], 2), t["dir"], t_in, t_out, i))
    df = pd.DataFrame(occ, columns=["sec", "dir", "tin", "tout", "trip"])
    for sec, grp in df.groupby("sec"):
        N = grp[grp.dir=="NB"].to_numpy(); Sx = grp[grp.dir=="SB"].to_numpy()
        for n in N:
            for s in Sx:
                if not (s[2] >= n[3] + g - 1e-6 or n[2] >= s[3] + g - 1e-6):
                    bad.append((sec, n[4], s[4]))
    return bad
