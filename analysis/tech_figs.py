"""Figures for the technical report: where knock-on delay builds up (by single-track section and by hour)."""
import json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R = Path(__file__).resolve().parent.parent; OUT = R / "techreport" / "figures"; OUT.mkdir(parents=True, exist_ok=True)
MUTED = "#898781"; GRID = "#e1e0d9"
plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "savefig.bbox": "tight"})
d = json.load(open(R / "results" / "deck_interactive.json"))
SEC = ["36th St.", "Rt 73–Palmyra", "Cinnaminson–\nRiverside", "Beverly–\nBurl. South", "Burlington–\nFlorence", "Roebling", "Bordentown–\nCass St."]
TT = [("njt_current", "Today", "#2a78d6"), ("proposal_B8", "B8", "#1baf7a"), ("proposed_T8", "T8 (even)", "#eb6834"), ("proposal_B7", "B7", "#7a5bd6")]
fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.4), sharey=True)
for ax, reg, title in zip(axs, ["alstom_2024_25", "njt_2026"], ["2024–25 delay regime (today 82% on time)", "2026 delay regime (today 92% on time)"]):
    x = np.arange(7); w = 0.2
    for j, (k, lab, c) in enumerate(TT):
        v = [sum(r) for r in d["tt"][k]["reg"][reg]["bysec"]]
        ax.bar(x + (j - 1.5) * w, v, w * 0.92, color=c, label=f"{lab} ({d['tt'][k]['reg'][reg]['knock']:.0f} min/day)")
    ax.set_xticks(x, SEC, fontsize=7.6); ax.grid(axis="x", visible=False); ax.set_title(title, loc="left", fontsize=9.5)
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
axs[0].set_ylabel("Minutes held per day at entrance")
fig.savefig(OUT / "fig_bottleneck_sections.pdf"); plt.close(fig)
fig, ax = plt.subplots(figsize=(10.5, 2.8)); hrs = np.arange(5, 23)
for k, lab, c in TT[:3]:
    ax.plot(hrs + 0.5, [d["tt"][k]["reg"]["alstom_2024_25"]["byhour"][h] for h in hrs], color=c, lw=2, marker="o", ms=3.5, label=lab)
for a, b in [(6, 9.5), (15, 19)]: ax.axvspan(a, b, color="#0d5f73", alpha=0.06, lw=0)
ax.set_xticks(range(5, 24, 2), [f"{h}:00" for h in range(5, 24, 2)]); ax.set_ylabel("Minutes held per day"); ax.legend(frameon=False, fontsize=8, ncol=3)
ax.set_title("Knock-on holding by hour of departure from the siding, 2024–25 regime (shaded: peaks)", loc="left", fontsize=9.5)
fig.savefig(OUT / "fig_bottleneck_hours.pdf"); plt.close(fig)
# meet slack distribution
fig, ax = plt.subplots(figsize=(10.5, 2.7)); bins = np.arange(-3, 12.5, 0.5)
for k, lab, c in TT[:3]:
    s = [m[3] for m in d["tt"][k]["meets"] if m[3] < 12]
    ax.hist(s, bins=bins, histtype="step", lw=2, color=c, label=f"{lab}: {sum(1 for q in s if q < 1)} meets < 1 min")
ax.axvline(1, color=MUTED, ls="--", lw=1); ax.axvline(2.5, color=MUTED, ls=":", lw=1)
ax.set_xlabel("Planned spare time at a single-track hand-off (min)"); ax.set_ylabel("Hand-offs per day"); ax.legend(frameon=False, fontsize=8)
fig.savefig(OUT / "fig_meet_slack.pdf"); plt.close(fig)
print("ok")
