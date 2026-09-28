"""Run the full prototype: headway ladder (MIP), plan ladder, time-space diagram,
policy simulation, figures, and results/summary.md."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rl_data import load_line
from timetable_mip import headway_table
from simulate import PlanBook, run_policy, Params

OUT = Path(__file__).resolve().parent.parent / "results"
OUT.mkdir(exist_ok=True)
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]   # fixed categorical order
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})
CLOCK = [15, 20, 30, 60]
FLEX = list(range(15, 61))


# ------------------------------------------------------------------ helpers --
def trajectory(line, sol, direction):
    """(time, pos) breakpoints for one train of the periodic timetable, t=0 at its origin."""
    secs = line.sections
    pts = sorted(set(line.stations.pos_mi) | set(secs.start_mi) | set(secs.end_mi))
    if direction == "NB":
        w = sol["_sN"]; out, cum = [], 0.0
        for x in pts:
            out.append((line.time_nb(x) + cum, x))
            for d, s in w.items():
                if abs(secs.end_mi[d] - x) < 1e-9 and s > 1e-6:
                    cum += s; out.append((line.time_nb(x) + cum, x))
        return out
    w = sol["_sS"]; out, cum = [], 0.0
    for x in reversed(pts):
        out.append((line.time_sb(x) + cum, x))
        for d, s in w.items():
            if abs(secs.start_mi[d] - x) < 1e-9 and s > 1e-6:
                cum += s; out.append((line.time_sb(x) + cum, x))
    return out


def occupancy(traj, a, e, t0, direction):
    """Entry = last time at the entry boundary (after any siding wait), exit = first time at exit boundary."""
    ent, ext = (a, e) if direction == "NB" else (e, a)
    t_in = max(t for t, x in traj if abs(x - ent) < 1e-9)
    t_out = min(t for t, x in traj if abs(x - ext) < 1e-9)
    return t0 + t_in, t0 + t_out


def verify_timetable(line, sol, horizon=600, g=0.5):
    """Independent check: no opposing overlap on any single-track section."""
    T, phi = sol["T"], sol["phi"]
    nb, sb = trajectory(line, sol, "NB"), trajectory(line, sol, "SB")
    worst = np.inf
    for _, s in line.single_sections().iterrows():
        for i in range(-10, horizon // T + 10):
            n0, n1 = occupancy(nb, s.start_mi, s.end_mi, i * T, "NB")
            for j in range(-10, horizon // T + 10):
                s0, s1 = occupancy(sb, s.start_mi, s.end_mi, phi + j * T, "SB")
                sep = max(s0 - n1, n0 - s1)       # >0 means disjoint
                worst = min(worst, sep)
    return worst                                   # should be >= g


# ------------------------------------------------------------------- main ----
def main(reps=30):
    line = load_line()
    table = headway_table(line, range(12, 61))
    book = PlanBook(table)
    hw = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in table])
    hw.to_csv(OUT / "headway_vs_trainsets.csv", index=False)

    # verification of every feasible timetable
    checks = {r["T"]: verify_timetable(line, r) for r in table if r["trainsets"]}
    bad = {T: v for T, v in checks.items() if v < 0.5 - 1e-6}
    print("min single-track separation (should be >= 0.5 min):", round(min(checks.values()), 3), "violations:", bad)

    # ---- fig 1: headway ladder
    fig, ax = plt.subplots(figsize=(7, 3.8))
    f = hw.dropna(subset=["trainsets"])
    ax.step(f["T"], f["trainsets"], where="post", color=C[0], lw=2)
    for T in CLOCK:
        n = book.n[T]
        ax.plot(T, n, "o", ms=8, color=C[1], mec="#fcfcfb", mew=2, zorder=3)
        ax.annotate(f"{T} min → {n} trains", (T, n), xytext=(6, 6), textcoords="offset points", color=INK, fontsize=9)
    ax.set_xlabel("Headway (min)"); ax.set_ylabel("Trainsets needed")
    ax.set_title("Trainsets needed per headway (single-track timetable MIP)", loc="left", color=INK)
    fig.tight_layout(); fig.savefig(OUT / "fig_headway_ladder.png", dpi=160); plt.close(fig)

    # ---- fig 2: time-space diagram for T=20
    sol = book.info[20]
    nb, sb = trajectory(line, sol, "NB"), trajectory(line, sol, "SB")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    for _, s in line.single_sections().iterrows():
        ax.axhspan(s.start_mi, s.end_mi, color="#f2e3c9", lw=0)
    for i in range(-6, 10):
        t0 = i * 20
        ax.plot([t0 + t for t, _ in nb], [x for _, x in nb], color=C[0], lw=1.6)
        ax.plot([sol["phi"] + t0 + t for t, _ in sb], [x for _, x in sb], color=C[1], lw=1.6)
    ax.set_xlim(0, 180); ax.set_ylim(0, line.length_mi)
    keep = [0, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 18, 20]
    ax.set_yticks(line.stations.pos_mi[keep]); ax.set_yticklabels(line.stations.name[keep].str.title(), fontsize=7)
    ax.set_xlabel("Minutes into the cycle"); ax.grid(False)
    ax.set_title("20-min periodic timetable (8 trainsets). Shaded = single track. Blue NB, orange SB", loc="left", color=INK, fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "fig_time_space_T20.png", dpi=160); plt.close(fig)

    # ---- plan ladder
    ladder = []
    for A in range(3, 15):
        row = {"cars_available": A}
        for name, menu, r in [("clockface_r0", CLOCK, 0), ("clockface_r1", CLOCK, 1), ("flex_r1", FLEX, 1)]:
            T = book.best_headway(A - r, menu)
            row[name] = f"{T} min ({book.n[T]} trains)" if T else "bus bridge"
        ladder.append(row)
    ladder = pd.DataFrame(ladder); ladder.to_csv(OUT / "plan_ladder.csv", index=False)

    # ---- policy simulation
    pols = {
        "Fixed 8-car (20/30)": dict(kind="fixed", T_peak=20, T_base=30),
        "Tiered clockface, no spare": dict(kind="tiered", reserve=0, menu=CLOCK),
        "Tiered clockface, 1 spare": dict(kind="tiered", reserve=1, menu=CLOCK),
        "Tiered flexible, 1 spare": dict(kind="tiered", reserve=1, menu=FLEX),
        "Tiered flexible, 2 spares": dict(kind="tiered", reserve=2, menu=FLEX),
    }
    rows, allday = [], []
    for name, p in pols.items():
        df = pd.DataFrame(run_policy(p, book, reps=reps)); df["policy"] = name; allday.append(df)
        prm = Params()
        rows.append({
            "policy": name,
            "mean cars available": df.A.mean(),
            "published trips/day": df.published.mean(),
            "cancelled % of published": 100 * df.cancelled.sum() / df.published.sum(),
            "on-time % of published": 100 * (df.operated - df.late).sum() / df.published.sum(),
            "in-service failures/day": df.failures.mean(),
            "avg wait (min)": df.wait.mean(),
            "avg wait vs published (min)": (df.wait - df.wait_pub).mean(),
            "impact score": (df.wait + prm.unplanned_weight * (df.wait - df.wait_pub)).mean(),
        })
    res = pd.DataFrame(rows); res.to_csv(OUT / "policy_comparison.csv", index=False)
    days = pd.concat(allday); days.to_csv(OUT / "simulated_days.csv", index=False)
    by_season = days.groupby(["policy", "season"]).apply(
        lambda d: pd.Series({"cancel %": 100 * d.cancelled.sum() / d.published.sum(),
                             "on-time % pub": 100 * (d.operated - d.late).sum() / d.published.sum(),
                             "avg wait": d.wait.mean(), "cars avail": d.A.mean()}), include_groups=False).round(1)
    by_season.to_csv(OUT / "policy_by_season.csv")

    # ---- fig 3: policy comparison (two panels, one axis each)
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
    names = res.policy.str.replace(", ", ",\n")
    for ax, col, title in [(axs[0], "cancelled % of published", "Unplanned cancellations (% of published trips)"),
                           (axs[1], "impact score", "Passenger impact score (min)")]:
        bars = ax.barh(names, res[col], color=C[0], height=0.6)
        bars[0].set_color(C[1])
        for b, v in zip(bars, res[col]):
            ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f" {v:.1f}", va="center", color=INK, fontsize=9)
        ax.invert_yaxis(); ax.set_title(title, loc="left", color=INK, fontsize=10); ax.grid(axis="y", visible=False)
    fig.tight_layout(); fig.savefig(OUT / "fig_policy_comparison.png", dpi=160); plt.close(fig)

    # ---- fig 4: availability distribution by season (fixed policy)
    d0 = days[days.policy == "Fixed 8-car (20/30)"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    seasons = ["winter", "spring", "summer", "fall"]
    for k, s in enumerate(seasons):
        v = d0[d0.season == s].A.value_counts(normalize=True).sort_index()
        ax.plot(v.index, 100 * v.values, "-o", color=C[k], lw=2, ms=5, label=s)
    ax.axvline(8, color=MUTED, lw=1, ls="--"); ax.text(8.1, ax.get_ylim()[1] * 0.92, "8 needed", color=MUTED, fontsize=9)
    ax.set_xlabel("Cars available at 6 am hold sheet"); ax.set_ylabel("% of days")
    ax.legend(frameon=False, ncol=4, loc="upper left")
    ax.set_title("Simulated availability by season (placeholder parameters)", loc="left", color=INK, fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "fig_availability.png", dpi=160); plt.close(fig)

    # ---- summary
    with open(OUT / "summary.md", "w") as fh:
        fh.write("# Prototype results\n\n")
        fh.write(f"Timetable verification: min opposing separation on single track = {min(checks.values()):.2f} min (>= 0.5 required); violations: {bad or 'none'}\n\n")
        fh.write("## Headway ladder (clock-face headways)\n\n")
        fh.write(hw[hw["T"].isin(CLOCK + [16, 24, 26])][["T", "trainsets", "cycle_min", "nb_trip_min", "sb_trip_min", "layover_trenton", "layover_camden", "added_wait_min"]].round(1).to_markdown(index=False))
        fh.write("\n\n## Plan ladder: cars at 6 am -> plan\n\n" + ladder.to_markdown(index=False))
        fh.write("\n\n## Policy comparison (%d reps x 365 weekdays)\n\n" % reps + res.round(2).to_markdown(index=False))
        fh.write("\n\n## By season\n\n" + by_season.to_markdown())
    print(res.round(2).to_string())
    print(ladder.to_string())


if __name__ == "__main__":
    main()
