"""Extended cyclic pattern MIP for the proposed schedules.

Same model as timetable_tools.pattern_mip (K trains on a C-minute cycle, every opposing meet on double track),
with three additions used by the proposals:
  sub       : list of (train indices, weight) -- the gaps of this subset of trains (the trains that keep running
              midday) are added to the objective, so peak AND midday spacing are optimized together
  hold      : minimum scheduled hold (min) at the downstream end of each double-track section, per direction
              (used to move running-time supplement to the entrances of single track)
  lminT/lminC: minimum layover at Trenton / Camden
Running times come from the Line object, so a line with scaled running times gives a slower (summer) pattern.
"""
import sys, copy, itertools, json
from pathlib import Path
import numpy as np, pulp
sys.path.insert(0, str(Path(__file__).resolve().parent))
from timetable_tools import Line2026, ROOT


def scaled_line(factor, calibrated=True):
    """Line with all running times multiplied by factor (e.g. 1.06 for a heat speed restriction timetable)."""
    l = Line2026(calibrated=calibrated)
    l.tN = l.tN * factor; l.tS = l.tS * factor; l.runN = float(l.tN[-1]); l.runS = float(l.tS[0])
    return l


def pre_single_holds(line):
    """Indices of double sections whose downstream end is the entrance of a single-track section, per direction."""
    sa = {round(s["a"], 6) for s in line.single}; sb = {round(s["b"], 6) for s in line.single}
    N = [d for d, s in enumerate(line.double) if round(s["b"], 6) in sa]
    S = [d for d, s in enumerate(line.double) if round(s["a"], 6) in sb]
    return N, S


def pattern_mip2(line, K, C, g=0.5, lminT=5.0, lminC=5.0, mingap=6.0, wmax=8.0, sub=None, holdN=None, holdS=None,
                 time_limit=120, verbose=False):
    D = range(len(line.double)); S = line.single
    holdN = holdN or {}; holdS = holdS or {}
    m = pulp.LpProblem(f"pat2_K{K}_C{C}", pulp.LpMinimize)
    a = [pulp.LpVariable(f"a{k}", 0, C) for k in range(K)]
    wN = [[pulp.LpVariable(f"wN{k}_{d}", holdN.get(d, 0), max(wmax, holdN.get(d, 0) + wmax)) for d in D] for k in range(K)]
    wS = [[pulp.LpVariable(f"wS{k}_{d}", holdS.get(d, 0), max(wmax, holdS.get(d, 0) + wmax)) for d in D] for k in range(K)]
    lT = [pulp.LpVariable(f"lT{k}", lminT, C) for k in range(K)]
    m += a[0] == 0
    for k in range(K - 1): m += a[k + 1] - a[k] >= mingap
    m += C - a[K - 1] >= mingap
    WN = [pulp.lpSum(wN[k]) for k in range(K)]; WS = [pulp.lpSum(wS[k]) for k in range(K)]
    b = [a[k] + line.runN + WN[k] + lT[k] for k in range(K)]
    for k in range(K):
        m += a[k] + C - (b[k] + line.runS + WS[k]) >= lminC
    for k in range(K - 1): m += b[k + 1] - b[k] >= mingap
    m += b[0] + C - b[K - 1] >= mingap
    for s in S:
        oN = line.timeN(s["b"]) - line.timeN(s["a"]); oS = line.timeS(s["a"]) - line.timeS(s["b"])
        for i in range(K):
            p = a[i] + line.timeN(s["a"]) + pulp.lpSum(wN[i][d] for d in D if line.double[d]["b"] <= s["a"] + 1e-9)
            for j in range(K):
                q = b[j] + line.timeS(s["b"]) + pulp.lpSum(wS[j][d] for d in D if line.double[d]["a"] >= s["b"] - 1e-9)
                z = pulp.LpVariable(f"z_{i}_{j}_{int(s['a']*100)}", -4, 4, cat="Integer")
                e = q - p - oN - g + C * z
                m += e >= 0; m += e <= C - oN - oS - 2 * g
    def cyc_gaps(xs):
        return [xs[t + 1] - xs[t] for t in range(len(xs) - 1)] + [xs[0] + C - xs[-1]]
    terms = [(gg, 1.0) for gg in cyc_gaps(a) + cyc_gaps(b)]
    for idx, w in (sub or []):
        idx = sorted(idx)
        terms += [(gg, w) for gg in cyc_gaps([a[i] for i in idx]) + cyc_gaps([b[i] for i in idx])]
    u = [pulp.LpVariable(f"u{i}", 0) for i in range(len(terms))]
    for i, (gg, w) in enumerate(terms):
        for t in range(4, 100, 2): m += u[i] >= 2 * t * gg - t * t
    extra = pulp.lpSum(WN) + pulp.lpSum(WS) - sum(holdN.values()) * K - sum(holdS.values()) * K
    m += pulp.lpSum(w * u[i] for i, (_, w) in enumerate(terms)) + 0.2 * extra
    m.solve(pulp.HiGHS(msg=verbose, timeLimit=time_limit))
    st = pulp.LpStatus[m.status]
    if st == "Infeasible" or pulp.value(a[1]) is None: return None
    v = lambda x: float(pulp.value(x))
    A = [v(x) for x in a]; B = [v(x) for x in b]
    res = dict(K=K, C=C, status=st, obj=float(pulp.value(m.objective)), a=A, b=B,
               wN=[[v(x) for x in row] for row in wN], wS=[[v(x) for x in row] for row in wS], lT=[v(x) for x in lT],
               sub=[list(s) for s, _ in (sub or [])])
    gN = np.diff(A + [A[0] + C]); gS = np.diff(sorted(B) + [sorted(B)[0] + C])
    res["gapsN"] = gN.tolist(); res["gapsS"] = gS.tolist()
    return res


def subset_classes(K, k):
    """k-subsets of range(K) containing 0, one per rotation class."""
    seen = set(); out = []
    for c in itertools.combinations(range(K), k):
        rots = [tuple(sorted((x - r) % K for x in c)) for r in c]
        key = min(rots)
        if key not in seen: seen.add(key); out.append(list(key))
    return out
