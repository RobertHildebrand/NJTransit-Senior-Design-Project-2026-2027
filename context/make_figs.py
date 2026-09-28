"""Figures for the background (context) report. Data: NTD (saved in data_public/ntd_hybrid_rail), DVRPC 2013, news/OLS."""
from pathlib import Path
import pandas as pd, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import matplotlib.dates as mdates
R = Path(__file__).resolve().parent.parent; F = R / "context" / "figures"; D = R / "data_public" / "ntd_hybrid_rail"
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7", "#898781"]; MUTED = "#898781"; GRID = "#e1e0d9"
plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": "#c3c2b7", "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "savefig.bbox": "tight"})
def save(fig, n): fig.savefig(F / f"{n}.pdf"); fig.savefig(F / f"{n}.png", dpi=150); plt.close(fig)

# 1 annual ridership
a = pd.read_csv(D / "ntd_riverline_YR_annual_calendar.csv"); a = a.groupby("y", as_index=False).upt.sum()
fig, ax = plt.subplots(figsize=(9, 3.3))
cols = [C[0] if y < 2020 else (C[1] if y < 2026 else C[2]) for y in a.y]
ax.bar(a.y, a.upt / 1e6, color=cols)
ax.axhline(a[a.y == 2019].upt.iloc[0] / 1e6, color=MUTED, ls=":", lw=1)
for y, v in zip(a.y, a.upt):
    ax.text(y, v / 1e6 + 0.04, f"{v/1e6:.2f}", ha="center", fontsize=7.5, color="#333")
ax.set_ylabel("Unlinked trips (millions)"); ax.set_xticks(a.y); ax.grid(axis="x", visible=False)
ax.text(2026, 0.2, "Jan–Jul\nonly", ha="center", fontsize=7.5, color="white")
ax.set_title("River LINE annual ridership, 2012–2026 (NTD, Hybrid Rail)", loc="left", fontsize=10)
save(fig, "fig_ctx_ridership_annual")

# 2 monthly with events
m = pd.read_csv(D / "ntd_riverline_YR_monthly_2023_2026.csv"); m["date"] = pd.to_datetime(m.date)
mm = m.groupby("date", as_index=False).agg(upt=("upt", "sum"), voms=("voms", "max"))
fig, ax = plt.subplots(figsize=(9, 3.4))
ax.plot(mm.date, mm.upt / 1000, color=C[0], lw=2, marker="o", ms=3)
for d, lab, yy in [("2024-08-12", " interim 30-min\n schedule + buses", 60), ("2024-10-14", " fatal tree\n strike", 30), ("2025-09-03", " takeover\n announced", 60), ("2026-02-14", " NJ TRANSIT\n operates", 30)]:
    ax.axvline(pd.Timestamp(d), color=C[1], lw=0.9, ls="--"); ax.text(pd.Timestamp(d), yy, lab, fontsize=7.5, ha="left", va="top", color=C[1])
ax.set_ylim(0, 195); ax.set_ylabel("Trips per month (thousands)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y")); ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax.set_title("Monthly ridership, Jan 2023–Jul 2026 (NTD). Feb 2026 is split between the two operators.", loc="left", fontsize=10)
save(fig, "fig_ctx_ridership_monthly")

# 3 DVRPC satisfaction + access
att = [("Fares", 40), ("Boarding station", 39), ("Travel time", 38), ("Frequency", 36), ("On-time performance", 36), ("Information", 31), ("Overall", 31),
       ("Ticket machines", 30), ("Parking", 27), ("Personal security", 24), ("Connections", 24), ("Customer communication", 21)]
acc = [("Drive & park", 35), ("Walk", 34), ("Carpool", 7), ("NJT bus", 7), ("PATCO", 5), ("Bike", 4), ("NJT train", 2)]
fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.3, 1]})
ax = axs[0]; y = np.arange(len(att))
ax.barh(y, [v for _, v in att], color=[C[1] if n in ("Customer communication", "Personal security", "Connections") else C[0] for n, _ in att])
ax.set_yticks(y, [n for n, _ in att]); ax.invert_yaxis(); ax.set_xlabel("% of riders rating 10 out of 10"); ax.grid(axis="y", visible=False)
ax.set_title("Satisfaction by attribute (DVRPC survey, Nov 2010)", loc="left", fontsize=10)
ax = axs[1]; y = np.arange(len(acc))
ax.barh(y, [v for _, v in acc], color=C[2]); ax.set_yticks(y, [n for n, _ in acc]); ax.invert_yaxis(); ax.set_xlabel("% of riders"); ax.grid(axis="y", visible=False)
ax.set_title("How riders reach the station", loc="left", fontsize=10)
save(fig, "fig_ctx_dvrpc")

# 4 NTD costs
k = pd.read_csv(D / "ntd_riverline_YR_metrics_2022_2024.csv").sort_values("report_year")
fig, axs = plt.subplots(1, 3, figsize=(10, 2.9))
for ax, col, ttl, fmt in [(axs[0], "cost_per_hour", "Operating cost per revenue hour ($)", "{:.0f}"), (axs[1], "cost_per_trip", "Operating cost per trip ($)", "{:.2f}"), (axs[2], "fare_per_trip", "Fare revenue per trip ($)", "{:.2f}")]:
    ax.bar(k.report_year.astype(str), k[col], color=C[5]); ax.set_title(ttl, loc="left", fontsize=9.5); ax.grid(axis="x", visible=False)
    for x, v in zip(k.report_year.astype(str), k[col]): ax.text(x, v, fmt.format(v), ha="center", va="bottom", fontsize=8)
axs[0].axhline(400, color=C[1], ls="--", lw=1); axs[0].text(-0.4, 420, "Team 22 model: $400", fontsize=7.5, color=C[1])
fig.suptitle("NTD report years (NJ TRANSIT fiscal years ending June 30)", x=0.01, ha="left", fontsize=8.5, color=MUTED, y=0.02)
save(fig, "fig_ctx_costs")

# 5 performance
pts = [("Aug 2023", 80.4, "Inquirer"), ("2024–25 avg", 87, "OLS FY27"), ("Jul 2025", 82.3, "News 12"), ("CY 2025", 84, "NJTOD"), ("Since Feb 2026", 93, "OLS FY27 (≥)")]
fig, axs = plt.subplots(1, 2, figsize=(10, 3.0), gridspec_kw={"width_ratios": [1.5, 1]})
ax = axs[0]; x = np.arange(len(pts))
ax.bar(x, [p[1] for p in pts], color=[C[1]] * 4 + [C[2]])
for i, p in enumerate(pts): ax.text(i, p[1] + 0.6, f"{p[1]:g}%" + ("+" if i == 4 else ""), ha="center", fontsize=8.5)
ax.axhline(97, color=MUTED, ls=":", lw=1); ax.text(-0.45, 97.6, "HBLR 2025: 97%", fontsize=7.5, color=MUTED)
ax.set_xticks(x, [f"{p[0]}\n({p[2]})" for p in pts], fontsize=7.8); ax.set_ylim(70, 102); ax.set_ylabel("% of trips on time"); ax.grid(axis="x", visible=False)
ax.set_title("River LINE on-time performance, as reported", loc="left", fontsize=10)
ax = axs[1]
ax.bar(["2022", "2024"], [22337, 4192], color=[C[0], C[1]]); ax.grid(axis="x", visible=False)
for xx, v in zip(["2022", "2024"], [22337, 4192]): ax.text(xx, v + 300, f"{v:,}", ha="center", fontsize=8.5)
ax.set_title("Mean miles between failures (ROI-NJ)", loc="left", fontsize=10)
save(fig, "fig_ctx_performance")
print("figures done")

# 6 MDBF by line (NJ TRANSIT performance data)
P = R / "data_public" / "njt_performance"
mb = pd.read_csv(P / "njt_lightrail_mdbf_by_line_monthly.csv", parse_dates=["date"])
fig, ax = plt.subplots(figsize=(9, 3.4))
for ln, c in [("River Line", C[1]), ("Newark Light Rail", C[4]), ("Hudson-Bergen Light Rail", C[5])]:
    q = mb[mb.line == ln]; ax.plot(q.date, q.mdbf / 1000, color=c, lw=2 if ln == "River Line" else 1.2, label=ln)
ax.axvline(pd.Timestamp("2026-02-14"), color=C[2], ls="--", lw=1); ax.text(pd.Timestamp("2026-02-14"), 30, " NJ TRANSIT\n operates", fontsize=7.5, color=C[2], va="top")
ax.set_ylim(0, 35); ax.set_ylabel("Miles between failures (thousands)"); ax.legend(frameon=False, fontsize=8, loc="upper left")
ax.set_title("Mean distance between failures by light rail line, Jan 2017–Aug 2026 (NJ TRANSIT)", loc="left", fontsize=10)
save(fig, "fig_ctx_mdbf")

# 7 satisfaction by wave
S = pd.read_csv(R / "data_public" / "njt_survey" / "njt_css_overall_by_light_rail_line.csv")
fig, ax = plt.subplots(figsize=(9, 3.2)); x = np.arange(len(S))
for col, lab, c in [("river_line", "River LINE", C[1]), ("hudson_bergen", "Hudson–Bergen", C[5]), ("newark_lr", "Newark Light Rail", C[4])]:
    ax.plot(x, S[col], marker="o", color=c, lw=2 if col == "river_line" else 1.2, label=lab)
for i, v in enumerate(S.river_line): ax.text(i, v - 0.18, f"{v:.1f}", ha="center", fontsize=8, color=C[1])
ax.axvspan(1.5, 1.5, color=MUTED); ax.text(1.55, 7.5, "no survey 2020–21", fontsize=7.5, color=MUTED)
ax.set_xticks(x, S.wave, fontsize=8); ax.set_ylim(5.4, 7.6); ax.set_ylabel("Overall satisfaction (0–10)"); ax.legend(frameon=False, fontsize=8, ncol=3, loc="lower left")
ax.set_title("NJ TRANSIT Customer Satisfaction Survey, overall score by light rail line", loc="left", fontsize=10)
save(fig, "fig_ctx_satisfaction")

# 8 TS2.1 cost history
T = pd.read_csv(D / "ntd_ts21_riverline_YR_2015_2024.csv")
fig, axs = plt.subplots(1, 2, figsize=(10, 3.2))
ax = axs[0]; bot = np.zeros(len(T))
for col, lab, c in [("OpExp VO", "Vehicle operations", C[0]), ("OpExp VM", "Vehicle maintenance", C[1]), ("OpExp NVM", "Non-vehicle maintenance", C[3]), ("OpExp GA", "General admin.", C[6])]:
    ax.bar(T.report_year, T[col] / 1e6, bottom=bot, color=c, label=lab); bot += T[col].values / 1e6
ax.set_ylabel("$ million"); ax.set_ylim(0, 48); ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper left"); ax.grid(axis="x", visible=False)
ax.set_title("Operating expense by function (NTD TS2.1)", loc="left", fontsize=10)
ax = axs[1]
ax.plot(T.report_year, T["OpExp Total"] / T.VRH, marker="o", color=C[5], label="Cost per revenue hour ($)")
ax2 = ax.twinx(); ax2.plot(T.report_year, 100 * T.Fares / T["OpExp Total"], marker="s", color=C[1], label="Farebox recovery (%)"); ax2.set_ylim(0, 10)
ax.set_ylim(0, 1000); ax.set_title("Cost per revenue hour and farebox recovery", loc="left", fontsize=10)
ax.legend(frameon=False, fontsize=7.5, loc="lower left"); ax2.legend(frameon=False, fontsize=7.5, loc="lower right"); ax2.spines["right"].set_visible(True)
save(fig, "fig_ctx_ts21")
print("extra figures done")
