"""Delay-propagation simulation for River LINE timetables.

Each trip is a sequence of nodes (stations + ends of single-track sections). A train
  * runs each segment in  tech * X  minutes, where tech = (1 - SUPP) * scheduled median running time of the 2026
    GTFS feed for that stretch (the rest is the schedule's running-time supplement) and X is random
    (trip-level factor x segment factor, both lognormal), plus occasional incidents (ramp deployment, grade
    crossing, door fault ...) that add an exponential delay at a random node;
  * never leaves a station or a scheduled hold point early;
  * may enter a single-track section only after the opposing train that was scheduled through it just before has
    left it (+ buffer): meet order is fixed by the timetable, as a dispatcher would normally keep it;
  * starts its next trip at the terminal no earlier than arrival + minimum turnaround.
Knock-on delay = minutes spent waiting at single-track entrances for late opposing trains.
On-time = arrives at its last stop less than 6 min late (NJ TRANSIT counts 0:00-5:59 as on time).
"""
import sys, math, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_tools import Line2026, fifo_blocks

BASE = Line2026(calibrated=True)
TOL = 3.0
PAR = dict(supp=0.10, sd_trip=0.035, sd_seg=0.12, p_inc=0.12, m_inc=6.0, turn=3.0, g=0.5, heat=1.0, otp_min=6.0)


def trip_nodes(t, line=BASE):
    """Node positions and planned (arr, dep) times for one trip, in travel order."""
    st = [(line.pos[k], x) for k, x in enumerate(t["times"]) if x is not None]
    lo = min(p for p, _ in st); hi = max(p for p, _ in st)
    edges = sorted({s["a"] for s in line.single} | {s["b"] for s in line.single})
    xs = sorted({p for p, _ in st} | {e for e in edges if lo + 1e-6 < e < hi - 1e-6})
    if t["dir"] == "SB": xs = xs[::-1]
    stations = {round(p, 6) for p, _ in st}
    tr = t.get("traj")
    if tr:
        P = np.array([p for p, _ in tr]); T = np.array([m for _, m in tr])
        def arrdep(x):
            idx = np.where(np.abs(P - x) < 1e-6)[0]
            if len(idx): return float(T[idx].min()), float(T[idx].max())
            pp, tt = (P, T) if t["dir"] == "NB" else (P[::-1], T[::-1])
            v = float(np.interp(x, pp, tt)); return v, v
    else:
        sp = np.array([p for p, _ in st]); stt = np.array([x for _, x in st])
        def arrdep(x):
            v = float(np.interp(x, sp, stt)); return v, v
    arr, dep = zip(*[arrdep(x) for x in xs])
    if tr:   # built from the 2026 median running times: technical time follows the medians
        base = [line.timeN(x) if t["dir"] == "NB" else line.timeS(x) for x in xs]
        run = [abs(base[i + 1] - base[i]) for i in range(len(xs) - 1)]
    else:    # published GTFS trip: its own scheduled station-to-station times
        run = [max(0.0, arr[i + 1] - dep[i]) for i in range(len(xs) - 1)]
    return dict(x=list(xs), arr=list(arr), dep=list(dep), run=run,
                hold=[(round(x, 6) in stations) or (d - a > 0.05) for x, a, d in zip(xs, arr, dep)])


def prepare(trips, blocks=None, line=BASE):
    """Precompute nodes, block sequences and single-track meet order for a timetable."""
    trips = [t for t in trips if sum(x is not None for x in t["times"]) >= 2]
    N = [trip_nodes(t, line) for t in trips]
    if blocks is None:
        key = "block" if trips and "block" in trips[0] and trips[0]["block"] is not None else ("train" if "train" in trips[0] else None)
        if key:
            bl = {}; [bl.setdefault(t[key], []).append(i) for i, t in enumerate(trips)]; blocks = list(bl.values())
        else:
            blocks = fifo_blocks(trips)
    blocks = [sorted(b, key=lambda i: N[i]["dep"][0]) for b in blocks]
    # single-track sections: entry/exit node index per trip, and the opposing trip that must clear first
    secs = []
    for si, s in enumerate(line.single):
        ent = []
        for i, t in enumerate(trips):
            xs = N[i]["x"]
            a_in = [k for k, x in enumerate(xs) if abs(x - (s["a"] if t["dir"] == "NB" else s["b"])) < 1e-6]
            a_out = [k for k, x in enumerate(xs) if abs(x - (s["b"] if t["dir"] == "NB" else s["a"])) < 1e-6]
            if a_in and a_out: ent.append((N[i]["dep"][a_in[0]], i, a_in[0], a_out[0]))
        ent.sort()
        secs.append(ent)
    need = {}      # (trip, entry node) -> (blocking trip, its exit node)
    for ent in secs:
        last = {"NB": None, "SB": None}
        for _, i, kin, kout in ent:
            d = trips[i]["dir"]; opp = "SB" if d == "NB" else "NB"
            if last[opp] is not None:
                j, ko = last[opp]
                # tolerance: a scheduled meet that is up to TOL min 'inside' the single track (minute rounding of
                # GTFS times, uncertainty in the siding limits) is taken as feasible as scheduled
                allow = max(0.0, N[j]["dep"][ko] + PAR["g"] - N[i]["dep"][kin])
                need[(i, kin)] = (j, ko, min(allow, TOL))
            last[d] = (i, kout)
    return dict(trips=trips, N=N, blocks=blocks, need=need)


def simulate(prep, rng, par=PAR, record=False):
    trips, N, blocks, need = prep["trips"], prep["N"], prep["blocks"], prep["need"]
    n = len(trips)
    act = [None] * n                          # actual departure time at each node
    arrv = [None] * n
    knock = np.zeros(n)
    Y = np.exp(rng.normal(-par["sd_trip"] ** 2 / 2, par["sd_trip"], n))
    inc_node = [None] * n
    for i in range(n):
        if rng.random() < par["p_inc"]: inc_node[i] = (int(rng.integers(0, len(N[i]["x"]) - 1)), rng.exponential(par["m_inc"]))
    seg = [np.exp(rng.normal(-par["sd_seg"] ** 2 / 2, par["sd_seg"], len(N[i]["run"]))) for i in range(n)]
    exit_t = {}                               # (trip, node) -> time left the node
    kev = []                                  # knock-on waits (trip, position, time, minutes)
    waiting = {}                              # (trip, node) blocker -> list of block ids
    pos = [[0, 0, None] for _ in blocks]       # per block: trip index in block, node index, current time (arrival at node)
    ready = [N[b[0]]["dep"][0] for b in blocks]
    stack = list(range(len(blocks)))

    def advance(bi):
        b = blocks[bi]
        while pos[bi][0] < len(b):
            ti = b[pos[bi][0]]; nd = N[ti]; k = pos[bi][1]
            if k == 0 and act[ti] is None:
                act[ti] = [None] * len(nd["x"]); arrv[ti] = [None] * len(nd["x"])
                arrv[ti][0] = ready[bi]
            t_arr = arrv[ti][k]
            t_dep = max(t_arr, nd["dep"][k]) if nd["hold"][k] or k == 0 else t_arr
            if (ti, k) in need:
                j, ko, allow = need[(ti, k)]; blk = (j, ko)
                if blk not in exit_t:
                    waiting.setdefault(blk, []).append(bi); return
                t2 = max(t_dep, exit_t[blk] + par["g"] - allow)
                knock[ti] += t2 - t_dep
                if record and t2 - t_dep > 0.3: kev.append((ti, nd["x"][k], t_dep, t2 - t_dep))
                t_dep = t2
            act[ti][k] = t_dep
            exit_t[(ti, k)] = t_dep
            for w in waiting.pop((ti, k), []): stack.append(w)
            if k == len(nd["x"]) - 1:
                ready[bi] = t_dep + par["turn"]
                pos[bi][0] += 1; pos[bi][1] = 0
                if pos[bi][0] < len(b):
                    nxt = b[pos[bi][0]]
                    ready[bi] = max(ready[bi], N[nxt]["dep"][0])
                continue
            dt = nd["run"][k] * (1 - par["supp"]) * par["heat"] * Y[ti] * seg[ti][k]
            if inc_node[ti] and inc_node[ti][0] == k: dt += inc_node[ti][1]
            arrv[ti][k + 1] = t_dep + dt
            pos[bi][1] = k + 1

    guard = 0
    while True:
        while stack:
            advance(stack.pop())
        pending = [bi for bi in range(len(blocks)) if pos[bi][0] < len(blocks[bi])]
        if not pending: break
        # deadlock (only possible with an inconsistent timetable): release the earliest waiting train
        guard += 1
        if guard > 500: break
        key, bl = min(waiting.items(), key=lambda kv: min(arrv[blocks[b][pos[b][0]]][pos[b][1]] for b in kv[1]))
        exit_t[key] = -1e9; stack.extend(waiting.pop(key))
    # results
    late_end = np.array([act[i][-1] - N[i]["arr"][-1] if act[i] and act[i][-1] is not None else np.nan for i in range(n)])
    st_delay = []
    for i in range(n):
        if act[i] is None: continue
        for k in range(len(N[i]["x"])):
            if N[i]["hold"][k] and act[i][k] is not None: st_delay.append(max(0.0, act[i][k] - N[i]["dep"][k]))
    out = dict(otp=float(np.nanmean(late_end < par["otp_min"])), mean_late=float(np.nanmean(np.maximum(late_end, 0))),
               p95_late=float(np.nanpercentile(late_end, 95)), st_delay=float(np.mean(st_delay)),
               knock=float(knock.sum()), knock_trips=int((knock > 0.5).sum()), n=n)
    if record: out["act"] = act; out["arrv"] = arrv; out["knock_by_trip"] = knock.tolist(); out["late_end"] = late_end.tolist(); out["kev"] = kev
    return out


def run_many(prep, days=300, seed=1, par=PAR):
    rng = np.random.default_rng(seed)
    R = [simulate(prep, rng, par) for _ in range(days)]
    agg = {k: float(np.mean([r[k] for r in R])) for k in ["otp", "mean_late", "p95_late", "st_delay", "knock", "knock_trips"]}
    agg["otp_p10"] = float(np.percentile([r["otp"] for r in R], 10))
    return agg
