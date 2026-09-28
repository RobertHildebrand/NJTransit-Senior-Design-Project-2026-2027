"""Periodic single-track timetable MIP (PESP-style) for the River Line.

For a headway T (minutes), find a periodic timetable in which
  * NB trains leave Camden at 0, T, 2T, ... and SB trains leave Trenton at
    phi, phi+T, ...
  * opposing trains never occupy the same single-track section at the same time
    (with a clearance buffer g), i.e. every meet happens on double track;
  * trains may wait extra time only inside double-track sections (passing sidings);
  * each train turns at Trenton and Camden with at least `lmin` minutes of layover,
    and the vehicle cycle closes: round trip = m_C * T.
The number of trainsets needed is m_C. Objective: min trainsets, then min added wait.

Single-track section s with NB occupancy oN and SB occupancy oS yields the PESP
constraint  (q_s - p_s - oN - g) mod T  in  [0, T - oN - oS - 2g],
where p_s is NB entry and q_s is SB entry time; modelled with integer z_s.
"""
import math
import pulp
from rl_data import load_line


def solve_headway(line, T, g=0.5, lmin=5.0, max_wait=6.0, verbose=False):
    secs = line.sections.reset_index(drop=True)
    single = [i for i in secs.index if secs.track[i] == "Single"]
    double = [i for i in secs.index if secs.track[i] == "Double"]

    # quick necessary condition
    occ = {}
    for i in single:
        a, e = secs.start_mi[i], secs.end_mi[i]
        oN = line.time_nb(e) - line.time_nb(a)
        oS = line.time_sb(a) - line.time_sb(e)
        occ[i] = (oN, oS)
        if T - oN - oS - 2 * g < 0:
            return None

    m = pulp.LpProblem(f"RL_T{T}", pulp.LpMinimize)
    sN = {d: pulp.LpVariable(f"sN_{d}", 0, max_wait) for d in double}
    sS = {d: pulp.LpVariable(f"sS_{d}", 0, max_wait) for d in double}
    phi = pulp.LpVariable("phi", 0, T - 1e-6)
    z = {i: pulp.LpVariable(f"z_{i}", -20, 20, cat="Integer") for i in single}
    mT = pulp.LpVariable("mT", 0, 40, cat="Integer")
    mC = pulp.LpVariable("mC", 1, 40, cat="Integer")

    def nb_time(x):   # NB clock at position x (waits taken at the north end of a double section)
        return line.time_nb(x) + pulp.lpSum(sN[d] for d in double if secs.end_mi[d] <= x + 1e-9)

    def sb_time(x):   # SB clock at position x, measured from Camden-dep-of-NB=0 frame
        return phi + line.time_sb(x) + pulp.lpSum(sS[d] for d in double if secs.start_mi[d] >= x - 1e-9)

    for i in single:
        a, e = secs.start_mi[i], secs.end_mi[i]
        oN, oS = occ[i]
        p = nb_time(a)            # NB enters at south end
        q = sb_time(e)            # SB enters at north end
        expr = q - p - oN - g + T * z[i]
        m += expr >= 0
        m += expr <= T - oN - oS - 2 * g

    arrN = line.run_nb + pulp.lpSum(sN.values())
    lT = phi + T * mT - arrN
    m += lT >= lmin
    m += lT <= lmin + T
    arrS = phi + T * mT + line.run_sb + pulp.lpSum(sS.values())
    lC = T * mC - arrS
    m += lC >= lmin

    m += 1000 * mC + pulp.lpSum(sN.values()) + pulp.lpSum(sS.values())
    m.solve(pulp.HiGHS(msg=verbose))
    if pulp.LpStatus[m.status] != "Optimal":
        return None
    v = lambda x: float(pulp.value(x))
    return {
        "T": T,
        "trainsets": int(round(v(mC))),
        "cycle_min": v(mC) * T,
        "phi": v(phi),
        "nb_trip_min": v(arrN),
        "sb_trip_min": line.run_sb + sum(v(x) for x in sS.values()),
        "layover_trenton": v(lT),
        "layover_camden": v(lC),
        "added_wait_min": sum(v(x) for x in sN.values()) + sum(v(x) for x in sS.values()),
        "waits_nb": {secs.siding[d] or f"dbl@{secs.end_mi[d]:.1f}mi": round(v(sN[d]), 2) for d in double if v(sN[d]) > 1e-6},
        "waits_sb": {secs.siding[d] or f"dbl@{secs.start_mi[d]:.1f}mi": round(v(sS[d]), 2) for d in double if v(sS[d]) > 1e-6},
        "_sN": {d: v(sN[d]) for d in double},
        "_sS": {d: v(sS[d]) for d in double},
    }


def headway_table(line, Ts=range(10, 61), **kw):
    rows = []
    for T in Ts:
        r = solve_headway(line, T, **kw)
        rows.append(r if r else {"T": T, "trainsets": None})
    return rows


if __name__ == "__main__":
    line = load_line()
    for r in headway_table(line, [10, 12, 15, 20, 30]):
        print({k: v for k, v in r.items() if not k.startswith("_")})
