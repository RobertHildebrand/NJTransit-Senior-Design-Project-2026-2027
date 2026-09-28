"""Monte Carlo evaluation of River Line service policies under uncertain fleet availability.

Each simulated weekday:
  1. 06:00 hold sheet: A cars available (fleet state carried day to day).
  2. The policy picks a service plan (peak/base headway, trains, reserve).
  3. Trains run; in-service failures arrive as a Poisson process in car-miles
     (rate 1/MDBF, seasonal). A failure (a) removes the car for a multi-day repair,
     (b) needs a rescue car: a spare if one is free, otherwise an in-service train is
     pulled (the "you lose two" effect), (c) blocks the line if it happens on single
     track, making trains in that window late.
  4. Metrics: trips published / operated / cancelled / late, and passenger wait
     (random arrivals: wait over a gap g is lambda*g^2/2, cf. Welding 1957; Osuna & Newell 1972).

ALL PARAMETERS in `Params` are placeholders calibrated only to public aggregates
(MDBF 4,192 mi in 2024, OTP ~84% in 2025, "8-car" and "6-car" schedules); the team
must re-estimate them from NJ Transit hold sheets and failure logs.
"""
from dataclasses import dataclass, field
import heapq
import math
import numpy as np

from rl_data import load_line, weekday_demand_profile

DAY_START, DAY_END = 5 * 60 + 45, 22 * 60          # freight window 22:00-05:45
PEAKS = [(6 * 60, 9 * 60), (15 * 60, 19 * 60)]


@dataclass
class Params:
    fleet: int = 20
    long_term_out: int = 3                 # cars in overhaul program at any time
    mdbf_mi: float = 4192.0                # 2024 miles between breakdowns (ROI-NJ)
    season_mdbf_mult: dict = field(default_factory=lambda: {"winter": 0.85, "spring": 1.25, "summer": 0.65, "fall": 1.0})
    season_late_p: dict = field(default_factory=lambda: {"winter": 0.06, "spring": 0.03, "summer": 0.05, "fall": 0.09})
    shop_defect_p: float = 0.01            # daily prob an idle/available car is found defective at inspection
    repair_mean_days: float = 12.0         # mean repair time (parts obsolescence)
    rescue_min: float = 60.0               # time a rescue car is tied up
    block_min: float = 35.0                # line blocked if failure on single track
    single_frac: float = 12.7 / 33.9       # share of route that is single track
    weekday_boardings: float = 5600.0      # 2024 station boardings (Wikipedia/NJT)
    unplanned_weight: float = 1.0          # extra weight on wait beyond the published plan


def season(doy):
    m = (doy // 30.5) % 12                 # 0=Jan
    return {11: "winter", 0: "winter", 1: "winter", 2: "spring", 3: "spring", 4: "spring",
            5: "summer", 6: "summer", 7: "summer"}.get(int(m), "fall")


# ---------------------------------------------------------------- plans ------
class PlanBook:
    """Headway -> trainsets needed, from the timetable MIP."""
    def __init__(self, table):
        self.n = {r["T"]: r["trainsets"] for r in table if r["trainsets"]}
        self.info = {r["T"]: r for r in table if r["trainsets"]}

    def best_headway(self, trains, menu, cap=15):
        feas = [T for T in menu if T >= cap and T in self.n and self.n[T] <= trains]
        return min(feas) if feas else None


def make_plan(book, T_peak, T_base):
    periods, t = [], DAY_START
    bounds = sorted({DAY_START, DAY_END, *[b for p in PEAKS for b in p]})
    for a, b in zip(bounds[:-1], bounds[1:]):
        T = T_peak if any(p0 <= a < p1 for p0, p1 in PEAKS) else T_base
        periods.append((a, b, T, book.n[T], book.info[T]))
    return periods


def choose_plan(policy, A, book):
    """Return (T_peak, T_base) for A available cars under a policy."""
    kind, reserve, menu = policy["kind"], policy.get("reserve", 0), policy.get("menu")
    if kind == "fixed":
        return policy["T_peak"], policy["T_base"]
    n = A - reserve
    Tp = book.best_headway(n, menu) or max(menu)
    Tb = max(Tp, policy.get("base_min", 30))
    if Tb not in book.n:
        Tb = min(T for T in menu if T >= Tb)
    return Tp, Tb


# ------------------------------------------------------------ one day -------
def trips_for_period(a, b, T, n, info):
    """Periodic departures in [a,b). Returns list of (dep_time, direction, slot)."""
    trips = []
    shift = int(round((info["nb_trip_min"] + info["layover_trenton"] - info["phi"]) / T))
    k0 = math.ceil((a - DAY_START) / T)
    t = DAY_START + k0 * T
    while t < b:
        k = int(round((t - DAY_START) / T))
        trips.append((t, "NB", k % n))
        ts = t + info["phi"]
        if ts < b:
            trips.append((ts, "SB", (k - shift) % n))
        t += T
    return trips


def simulate_day(plan, A, prm, rng, doy, line_len):
    s = season(doy)
    mdbf = prm.mdbf_mi * prm.season_mdbf_mult[s]
    healthy = A
    failures = 0
    published = operated = late = cancelled = 0
    deps = {"NB": [], "SB": []}
    pub_deps = {"NB": [], "SB": []}
    blocks = []
    for (a, b, T, n, info) in plan:
        trips = trips_for_period(a, b, T, n, info)
        for t, d, _ in trips:
            pub_deps[d].append(t)
        published += len(trips)
        # fill slots
        slots_filled = min(n, healthy)
        spares = healthy - slots_filled
        vac_from = {j: (a if j >= slots_filled else math.inf) for j in range(n)}
        busy = {j: [] for j in range(n)}          # (start,end) intervals slot cannot run
        # failure clock per filled slot
        rate = (2 * line_len / (n * T)) / mdbf   # failures per operating minute per train
        ev = []
        for j in range(slots_filled):
            tf = a + rng.exponential(1 / rate)
            if tf < b:
                heapq.heappush(ev, (tf, j))
        while ev:
            tf, j = heapq.heappop(ev)
            if vac_from[j] <= tf:
                continue
            failures += 1
            healthy -= 1
            if rng.random() < prm.single_frac:
                blocks.append((tf, tf + prm.block_min))
            if spares > 0:                        # spare rescues, then takes over the slot
                spares -= 1
                busy[j].append((tf, tf + prm.rescue_min))
                tn = tf + prm.rescue_min + rng.exponential(1 / rate)
                if tn < b:
                    heapq.heappush(ev, (tn, j))
            else:                                 # pull another train to rescue
                vac_from[j] = tf
                others = [k for k in range(n) if vac_from[k] > tf and k != j]
                if others:
                    k = others[rng.integers(len(others))]
                    busy[k].append((tf, tf + prm.rescue_min))
        for t, d, j in trips:
            if t >= vac_from[j] or any(s0 <= t < s1 for s0, s1 in busy[j]):
                cancelled += 1
                continue
            operated += 1
            deps[d].append(t)
            blocked = any(s0 - 20 <= t <= s1 for s0, s1 in blocks)
            if blocked or rng.random() < prm.season_late_p[s]:
                late += 1
    return dict(published=published, operated=operated, cancelled=cancelled, late=late,
                failures=failures, healthy_end=healthy,
                wait=avg_wait(deps, prm), wait_pub=avg_wait(pub_deps, prm))


_prof = weekday_demand_profile()


def avg_wait(deps, prm):
    """Mean passenger wait (min) with random arrivals at hourly rates."""
    tot_w = tot_p = 0.0
    for d, ts in deps.items():
        ts = sorted(ts) + [DAY_END + 60]
        prev = DAY_START
        for t in ts:
            t_end = min(t, DAY_END)
            if t_end > prev:
                h = int(prev // 60)
                lam = prm.weekday_boardings / 2 * _prof.get(h, 0.0) / 60.0
                g = t_end - prev
                # passengers arriving in the gap wait until t (or leave at day end)
                tot_w += lam * g * (t - prev - g / 2)
                tot_p += lam * g
            prev = max(prev, t)
    return tot_w / tot_p if tot_p else float("nan")


# ------------------------------------------------------------ many days -----
def run_policy(policy, book, prm=None, days=365, reps=20, warmup=60, seed=0):
    prm = prm or Params()
    line = load_line()
    out = []
    for r in range(reps):
        rng = np.random.default_rng(seed + r)
        pool = prm.fleet - prm.long_term_out
        repair = []                                # days remaining for cars in shop
        # start from ~50% availability
        for _ in range(pool // 2):
            repair.append(int(rng.geometric(1 / prm.repair_mean_days)))
        for day in range(warmup + days):
            doy = day % 365
            avail = pool - len(repair)
            # inspection defects
            nd = rng.binomial(avail, prm.shop_defect_p)
            repair += [int(rng.geometric(1 / prm.repair_mean_days)) for _ in range(nd)]
            A = pool - len(repair)
            Tp, Tb = choose_plan(policy, A, book)
            plan = make_plan(book, Tp, Tb)
            res = simulate_day(plan, A, prm, rng, doy, line.length_mi)
            repair += [int(rng.geometric(1 / prm.repair_mean_days)) for _ in range(res["failures"])]
            repair = [x - 1 for x in repair if x > 1]
            if day >= warmup:
                res.update(rep=r, doy=doy, season=season(doy), A=A, T_peak=Tp, T_base=Tb)
                out.append(res)
    return out
