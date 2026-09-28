"""Report figures and LaTeX tables for the proposed schedules (delay simulation + fleet simulation)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from timetable_build import build_TT, ROOT, line, C6, MUTED, GRID
from delay_sim import prepare
FIG = ROOT / "report" / "figures"; REP = ROOT / "report"
plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "savefig.bbox": "tight"})
de = json.load(open(ROOT / "results" / "delay_eval.json")); rp = json.load(open(ROOT / "timetables" / "delay_replays.json"))
cfg = json.load(open(ROOT / "results" / "proposals_dashboard.json")); yr = json.load(open(ROOT / "results" / "js_year_proposals.json"))
tt = json.load(open(ROOT / "timetables" / "timetables_dashboard.json")); lab2key = {v["label"]: k for k, v in tt.items()}
M = {lab2key[r["label"]]: r for r in pd.read_csv(ROOT / "timetables" / "timetable_metrics.csv").to_dict("records")}
KEYS = [p["key"] for p in cfg["props"]]
def short(k):
    l = tt[k]["label"]
    return "NJT today" if l.startswith("NJT") else l.replace("Proposal ", "").replace("Proposed ", "").replace("Uniform ", "").split(":")[0].split(" (")[0]
col = lambda k: C6[6] if k == "njt_current" else ("#1f8a4c" if k == "proposal_B8" else ("#eda100" if k.startswith("uniform") else C6[0]))
f = lambda k: de["tt"][k]["normal"]; h = lambda k: de["tt"][k]["hot"]

# 1 trade-off
fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
ax = axs[0]
for k in KEYS:
    x, y = M[k]["day_wait"], 100 * f(k)["otp"]
    ax.scatter(x, y, s=60 if k in ("njt_current", "proposal_B8") else 34, color=col(k), zorder=3, edgecolor="white")
    ax.annotate(short(k), (x, y), xytext=(5, 3), textcoords="offset points", fontsize=8.5)
ax.axhline(100 * f("njt_current")["otp"], color=MUTED, ls=":", lw=0.8); ax.axvline(M["njt_current"]["day_wait"], color=MUTED, ls=":", lw=0.8)
ax.set_xlabel("Scheduled average wait at Walter Rand (min)"); ax.set_ylabel("Trips on time (%)"); ax.set_title("Even spacing vs punctuality (up and left is better)", loc="left", fontsize=10)
ax = axs[1]; y = np.arange(len(KEYS))
ax.barh(y - 0.2, [100 * f(k)["otp"] for k in KEYS], 0.4, color=C6[0], label="normal day")
ax.barh(y + 0.2, [100 * h(k)["otp"] for k in KEYS], 0.4, color=C6[1], label="hot day (+6% running time)")
ax.set_yticks(y, [short(k) for k in KEYS]); ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel("Trips on time (%)"); ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
ax.grid(axis="y", visible=False)
fig.savefig(FIG / "fig_prop_tradeoff.pdf"); fig.savefig(FIG / "fig_prop_tradeoff.png", dpi=150); plt.close(fig)

# 2 replay NJT vs B8, typical day, morning
day = rp["days"]["typical"]
fig, axs = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True)
for ax, k in zip(axs, ["njt_current", "proposal_B8"]):
    for s in line.single: ax.axhspan(s["a"], s["b"], color="#f2e3c9", lw=0)
    R = day[k]
    for t in R["trips"]:
        c = C6[0] if t["d"] == "NB" else C6[1]
        pp = [(m, line.pos[q]) for q, m in enumerate(t["p"]) if m is not None]; aa = [(m, line.pos[q]) for q, m in enumerate(t["a"]) if m is not None]
        ax.plot([p[0] / 60 for p in pp], [p[1] for p in pp], color=c, lw=0.8, alpha=0.3)
        ax.plot([p[0] / 60 for p in aa], [p[1] for p in aa], color=c, lw=1.3)
        for x, t0, dd in t.get("w", []): ax.scatter(t0 / 60, x, s=12 + 10 * dd, color="#d03b3b", alpha=0.75, zorder=4, lw=0)
    ax.set_xlim(5.5, 9.6); ax.set_ylim(0, line.L); ax.grid(False); ax.set_ylabel("Miles from Camden")
    ax.set_title(f"{short(k)}: {100*R['otp']:.0f}% on time, average lateness {R['mean_late']:.1f} min, {R['knock']:.0f} min held for late opposing trains", loc="left", fontsize=10)
axs[1].set_xlabel("Hour of day")
fig.savefig(FIG / "fig_prop_replay.pdf"); fig.savefig(FIG / "fig_prop_replay.png", dpi=150); plt.close(fig)

# 3 why: meet slack and layovers
TT = build_TT(); byname = {n: tr for _, (n, tr) in TT.items()}
fig, axs = plt.subplots(1, 2, figsize=(11, 3.4))
bins = [(0, 1, "<1"), (1, 2, "1–2"), (2, 3, "2–3"), (3, 5, "3–5"), (5, 10, "5–10"), (10, 30, "10+")]
show = ["njt_current", "proposed_T8", "proposal_B8"]; cs = [C6[6], C6[0], "#1f8a4c"]
for j, (k, c) in enumerate(zip(show, cs)):
    hh = np.array(de["slack"][k]["hist"]); sh = [hh[a:b].sum() / hh.sum() for a, b, _ in bins]
    axs[0].bar(np.arange(len(bins)) + (j - 1) * 0.27, [100 * v for v in sh], 0.27, color=c, label=short(k))
axs[0].set_xticks(range(len(bins)), [b[2] for b in bins]); axs[0].set_xlabel("Minutes of slack at the meet"); axs[0].set_ylabel("% of scheduled meets")
axs[0].set_title("How late a train can be before it holds the opposing train", loc="left", fontsize=10); axs[0].legend(frameon=False, fontsize=8); axs[0].grid(axis="x", visible=False)
lay = {}
for k in show:
    p = prepare(byname[k]); N = p["N"]; L = []
    for b in p["blocks"]:
        for i, j in zip(b[:-1], b[1:]):
            v = N[j]["dep"][0] - N[i]["arr"][-1]
            if v < 40: L.append(v)
    lay[k] = np.array(L)
for k, c in zip(show, cs):
    v = np.sort(lay[k]); axs[1].step(v, np.arange(1, len(v) + 1) / len(v) * 100, where="post", color=c, lw=2, label=f"{short(k)} (median {np.median(v):.1f} min)")
axs[1].set_xlim(4, 30); axs[1].set_xlabel("Layover at the terminal (min)"); axs[1].set_ylabel("% of turnbacks at or below"); axs[1].legend(frameon=False, fontsize=8)
axs[1].set_title("Terminal layovers", loc="left", fontsize=10)
fig.savefig(FIG / "fig_prop_why.pdf"); fig.savefig(FIG / "fig_prop_why.png", dpi=150); plt.close(fig)
json.dump({k: dict(median=float(np.median(v)), lt8=float((v < 8).mean())) for k, v in lay.items()}, open(ROOT / "results" / "layovers.json", "w"), indent=1)

# 4 sensitivity
S = de["sens"]; sk = ["njt_current", "proposed_T8", "proposal_B8", "proposal_B7", "proposal_E5", "proposal_W7"]
cases = ["base"] + list(S.keys())
fig, ax = plt.subplots(figsize=(11, 3.4)); w = 0.8 / len(sk)
for j, k in enumerate(sk):
    vals = [100 * f(k)["otp"]] + [100 * S[c][k] for c in S]
    ax.bar(np.arange(len(cases)) + (j - (len(sk) - 1) / 2) * w, vals, w, color=[C6[6], C6[0], "#1f8a4c", "#7cc49a", C6[4], C6[3]][j], label=short(k))
ax.set_xticks(range(len(cases)), ["calibrated", "supplement 6%", "supplement 14%", "incidents ×2", "incidents ×½", "segment noise ×2", "turnaround 6 min"], fontsize=8.5)
ax.set_ylabel("Trips on time (%)"); ax.set_ylim(0, 100); ax.legend(frameon=False, fontsize=8, ncol=6, loc="upper center", bbox_to_anchor=(0.5, 1.12)); ax.grid(axis="x", visible=False)
fig.savefig(FIG / "fig_prop_sens.pdf"); fig.savefig(FIG / "fig_prop_sens.png", dpi=150); plt.close(fig)

# tables
rows = []
for k in KEYS:
    m = M[k]; a = f(k)
    gap = max(m["NB_am_max"], m["SB_am_max"])
    rows.append(f"{short(k)} & {int(m['vehicles_peak'])}/{int(m['vehicles_midday'])} & {m['train_hours']:.0f} & {gap:.0f} & {m['day_wait']:.1f} & {100*a['otp']:.0f} & {100*h(k)['otp']:.0f} & {a['mean_late']:.1f} & {m['day_wait']+a['mean_late']:.1f} & {a['knock']:.0f} \\\\")
    if k in ("njt_current", "proposed_T8"): rows.append("\\midrule")
open(REP / "tab_prop_rows.tex", "w").write("\n".join(rows) + "\n")
yrows = [f"{r['name'].replace('–','--')} & {r['cancel_pct']:.1f} & {r['bySeason']['summer']:.1f} & {r['bySeason']['winter']:.1f} & {r['wait']:.1f} & {r['op']/1000:.1f} \\\\" for r in yr]
open(REP / "tab_propyear_rows.tex", "w").write("\n".join(yrows) + "\n")
print("done"); print(open(REP / "tab_prop_rows.tex").read()); print(open(REP / "tab_propyear_rows.tex").read())
