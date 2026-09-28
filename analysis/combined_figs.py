"""Figures and LaTeX tables for the combined evaluation (revision 4)."""
import json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R = Path(__file__).resolve().parent.parent; FIG = R / "report" / "figures"; REP = R / "report"
C = ["#898781", "#eb6834", "#2a78d6", "#1f8a4c", "#eda100", "#7cc49a"]; MUTED = "#898781"; GRID = "#e1e0d9"
plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "savefig.bbox": "tight"})
d = json.load(open(R / "results" / "combined_eval.json"))
COST = 547.0
SC = ["S1 Alstom 2024-25", "S2 NJ TRANSIT 2026", "S3 Renewed fleet"]
SHORT = ["Today's timetable", "B8 every day", "Tiers T8--T3 (+1 protect)", "Robust tiers (+1 protect)", "Robust tiers + summer W7", "Robust tiers (no protect)"]
pols = [x["name"] for x in d[SC[0]]["policies"]]

# figure: headline metric by scenario and policy
fig, ax = plt.subplots(figsize=(10, 3.8)); w = 0.8 / len(pols); x = np.arange(len(SC))
for j, p in enumerate(pols):
    v = [d[s]["policies"][j] for s in SC]
    ax.bar(x + (j - (len(pols) - 1) / 2) * w, [q["rtd"] for q in v], w, color=C[j], label=SHORT[j].replace("--", "–"),
           yerr=[[q["rtd"] - q["rtd_min"] for q in v], [q["rtd_max"] - q["rtd"] for q in v]], capsize=2, error_kw=dict(lw=0.8, ecolor="#555"))
ax.set_xticks(x, ["S1: Alstom era 2024–25", "S2: NJ TRANSIT 2026", "S3: renewed fleet"]); ax.set_ylim(50, 100)
ax.set_ylabel("Reliable trip-miles delivered (%)"); ax.grid(axis="x", visible=False)
ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
ax.set_title("Headline metric: on-time trip-miles delivered as % of today's timetable (bars: range over 10 simulated years)", loc="left", fontsize=10)
fig.savefig(FIG / "fig_rtd.pdf"); fig.savefig(FIG / "fig_rtd.png", dpi=150); plt.close(fig)

# figure: decomposition delivered vs on-time share, S1 and S2
fig, axs = plt.subplots(1, 2, figsize=(10, 3.2), sharey=True)
for ax, s in zip(axs, SC[:2]):
    v = d[s]["policies"]; y = np.arange(len(v))
    ax.barh(y, [q["delivered"] for q in v], color="#d9d7cf", label="trip-miles run")
    ax.barh(y, [q["rtd"] for q in v], color=[C[j] for j in range(len(v))], label="of which on time")
    for i, q in enumerate(v): ax.text(q["delivered"] + 0.6, i, f"{q['rtd']:.1f}% on time of {q['delivered']:.1f}% run", va="center", fontsize=7.5)
    ax.set_yticks(y, [t.replace("--", "–") for t in SHORT]); ax.invert_yaxis(); ax.set_xlim(0, 125); ax.set_title(s.replace("S1 ", "S1: ").replace("S2 ", "S2: "), loc="left", fontsize=10)
    ax.grid(axis="y", visible=False); ax.set_xlabel("% of today's promised trip-miles")
fig.savefig(FIG / "fig_rtd_decomp.pdf"); fig.savefig(FIG / "fig_rtd_decomp.png", dpi=150); plt.close(fig)

# table: headline results
rows = []
for j, p in enumerate(pols):
    cells = []
    for s in SC:
        q = d[s]["policies"][j]
        cells.append(f"{q['rtd']:.1f} ({q['rtd_min']:.0f}--{q['rtd_max']:.0f})")
    q1, q2 = d[SC[0]]["policies"][j], d[SC[1]]["policies"][j]
    rows.append(f"{SHORT[j]} & " + " & ".join(cells) + f" & {q1['cancel_pct']:.1f} / {q2['cancel_pct']:.1f} & {q1['onTimeShare']:.0f} / {q2['onTimeShare']:.0f} & {q2['th']*COST/1000:.1f} \\\\")
open(REP / "tab_rtd_rows.tex", "w").write("\n".join(rows) + "\n")

# sensitivity table (RTD of today vs robust tiers)
sens = ["S1, repairs 8 days", "S1 Alstom 2024-25", "S1, repairs 12 days", "S2, repairs 3 days", "S2 NJ TRANSIT 2026", "S2, repairs 8 days", "S2, MDBF 2,500"]
srows = []
for s in sens:
    v = d[s]["policies"]
    lab = s.replace("S1 Alstom 2024-25", "S1 (repairs 10 days)").replace("S2 NJ TRANSIT 2026", "S2 (repairs 5 days, MDBF 3,568)")
    srows.append(f"{lab} & {v[0]['A']:.1f} & " + " & ".join(f"{v[j]['rtd']:.1f}" for j in range(len(v))) + " \\\\")
open(REP / "tab_rtd_sens_rows.tex", "w").write("\n".join(srows) + "\n")
print(open(REP / "tab_rtd_rows.tex").read()); print(open(REP / "tab_rtd_sens_rows.tex").read())
