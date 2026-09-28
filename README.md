# River Line schedule optimization — starter package (Team 22)

**Start with `report/report.pdf`** and the background report `context/context_report.pdf` (riders, community effects, history, budget, problems, plans; with `context/documents_to_download.pdf`) (findings, models, dashboard, future work). Also: `timetables/timetable_book.pdf` (current NJT timetable vs proposed T8–T3 and uniform tiers, every trip), `report/data_requests.pdf` (what to ask NJ TRANSIT for), `lit_review/data_sources.pdf` (provenance of every number), `river_line_sim.html` (the dashboard, offline copy).

Contents:

- `lit_review/` — the literature review in LaTeX (`lit_review.tex`, `refs.bib`, compiled `lit_review.pdf`).
- `data/` — first public data pull (2014 GTFS, NJDOT track). `data/README_data.md` lists the sources.
- `docs_downloaded/` — documents the team downloaded by hand (survey reports, NJT performance files, board agendas, NTD time series, SSO appendix), sorted by the IDs in `context/documents_to_download.pdf`.
- `data_public/njt_performance/`, `data_public/njt_survey/` — data extracted from those downloads (River LINE failures by month 2017–2026; satisfaction by wave).
- `context/` — background report (LaTeX, figures, `ctx_refs.bib`) and the list of documents still to download.
- `data_public/ntd_hybrid_rail/` — NTD River LINE data (Hybrid Rail, mode YR): monthly ridership 2023–26, annual 2012–26, costs and failures 2022–24.
- `data_public/` — second pull (Sept 28, 2026): current GTFS timetable, NOAA weather, NTD, OpenStreetMap, DVRPC survey summary.
- `analysis/` — scripts that turn the public data into report figures, the playbook and the dashboard data.
- `report/` — LaTeX report, data request, figures.
- `timetables/` — timetables as CSV (`njt_current`, `proposed_T8`…`T3`, `uniform_U8`…`U4`), `timetable_metrics.csv` (trains, train-hours, headways, waits, meet conflicts) and the printable `timetable_book.pdf`. Built by `analysis/timetable_build.py` from the pattern MIP in `analysis/timetable_tools.py` (`analysis/run_patterns.py`); track calibrated to NJT meet points by `analysis/calibrate_track.py`.
- **Proposed schedules (revision 3).** `analysis/proposals_mip.py` (extended pattern MIP), `proposals_solve.py`, `robust_sweep.py`, `robust_b7.py` (solves); `delay_sim.py` + `delay_eval.py` (delay-propagation simulation calibrated to 83% on time); `proposal_figs.py` (report figures). Results in `results/delay_eval.json`, `robust_eval.csv`, `js_year_proposals.json`; replays in `timetables/delay_replays.json`. Recommended: **B8** (8 trains, 160-min cycle, ≥2.5-min meet buffers, ≥9-min layovers), **B7** for 7-car days, **W7** summer timetable.
- `src/` + `results/` — a working prototype.


## Revision 4 (Sept 28, 2026): questions, one headline measure, calibrated scenarios, validation
- **Headline measure:** reliable trip-miles delivered (RTD), i.e. trip-miles that run and arrive <6 min late, as % of today's timetable.
- **Calibrated scenarios:**
  - S1 Alstom 2024–25: MDBF 3,661, repairs 10 days.
  - S2 NJ TRANSIT 2026: MDBF 3,568, repairs 5 days.
  - S3 renewed fleet: MDBF 10,000.
  - Cost is $547 per train-hour (NTD vehicle operations + maintenance).
- **Results (RTD):**

  | Policy | S1 | S2 | S3 |
  |---|---|---|---|
  | Today | 69% | 84% | 86% |
  | B8 | 73% | 87.5% | 89.5% |
  | Robust tiers | 74% | 87.5% | 89.5% |
  | T8–T3 tiers | 65% | 83% | 85% |

- **Validation:** see report Section 9, Table 6.
- **Scripts:** `analysis/delay_regimes.py`, `analysis/combined_eval.py`, `analysis/combined_figs.py`. Dashboard source and headless runner are in `dashboard_src/`; `python dashboard_src/build.py` builds `river_line_sim.html`.

## Prototype

```
pip install pulp highspy pandas matplotlib tabulate
cd src && python run_all.py        # about 30 s; writes everything in results/
```

| File | What it does |
|---|---|
| `rl_data.py` | Loads the stations and the scheduled running times between them (GTFS). Loads single/double track by milepost (NJDOT). Builds the time–distance trajectories. |
| `timetable_mip.py` | **Periodic single-track timetable MIP** (PESP-style). For a headway *T*, it finds the NB/SB offset and any siding waits so that opposing trains meet only on double track. It includes turnback layovers ≥ 5 min and returns the **minimum number of trainsets**. Solved with HiGHS; each headway solves in well under a second. |
| `simulate.py` | Monte Carlo over 365 weekdays. It simulates the fleet state (in-service failures at 1/MDBF per car-mile with seasonal factors, multi-day repairs), the 6 am hold sheet, the choice of plan, rescues (a spare, or else pull an in-service train), and line blockages on single track. It reports cancellations, OTP and passenger wait. |
| `run_all.py` | Builds the headway ladder and plan ladder, checks every timetable independently, runs the policy comparison, and writes the figures and `results/summary.md`. |

### What it shows so far

1. **The headway ladder reproduces NJT's practice.** A 20-min headway needs **8 trainsets** and a 30-min headway needs **6**. Those are the "8-car" and "6-car" schedules in the client notes. 15 min needs 11, which matches the 2014 peak of 11–12 blocks. The model got there from track layout and running times alone.
2. **Cars are worth something only in steps.** With clock-face headways, 7 cars run the same service as 6, and 9–10 run the same as 8. A **flexible** menu (24, 26, 31, 37 min, …) turns every extra car into more service.
3. **Policy comparison** (placeholder parameters, calibrated only to public numbers: MDBF 4,192 mi, OTP ≈ 84%).
   - Publishing a fixed 8-car schedule and cancelling whatever can't run gives about **7% unplanned cancellations**. That rises to 14% in summer.
   - A tiered plan chosen at the 6 am hold sheet with one protect car cuts cancellations to about **1%**. On the flexible menu it also gives the lowest passenger-impact score.
   - See `results/summary.md`.

### Limitations (the team's to-do list)

- **Parameters are placeholders.** These include the failure rates, repair times, seasonal factors, rescue and blockage times, and the demand profile. Re-estimate them from the hold sheets and failure logs.
- **The track chart is approximate.** Railroad mileposts are rescaled onto GTFS shape distance. Get the actual siding limits and speed restrictions.
- **Running times are the 2014 GTFS medians.** Update them from the current feed or from AVL data.
- **The timetable is strictly periodic within each period.** Transitions between peak and base aren't modelled. Short turns, limited-stop trips and 2-car consists aren't modelled either.
- **Plans are only re-chosen at the 6 am hold sheet.** The 6 pm hold sheet could trigger a re-plan in the evening.
- **OTP is proxied.** It uses background lateness plus blockages. There's no delay-propagation model.

### Natural extensions

- A two-stage stochastic model: choose the published tiers, then choose the recourse plan once availability is revealed.
- Joint maintenance scheduling, i.e. which cars to repair first.
- Modelling passenger demand at the level of individual trips.
- A timetable robustness objective, such as light robustness or recoverable robustness.

## Presentation deck (`deck/`)
- `river_line_deck.html`: self-contained 30-slide deck: a standalone HTML file that opens in any browser, no Claude needed (arrow keys to navigate; interactive slides work offline, fonts load from Google Fonts when online). Includes four interactive slides from the dashboard: the live line map (the dashboard's day engine in `deck/engine.js`, with breakdowns and rescues), timetable explorer, day replay, and bottleneck map.
- Rebuild: `python analysis/deck_interactive.py` (bottleneck data), then `python deck/make_deck_data.py` (inlines data, JS and images into `deck_src.html`).
- Photos in `deck/img/` are from Wikimedia Commons under CC/GFDL/public-domain licenses; see `deck/img/CREDITS.md`. The route map is © NJ TRANSIT (via NJDOT SSO Appendix F); get permission before public use.

## Technical report (`techreport/`)
`technical_report.pdf` (28 pp., LaTeX source alongside): data and processing, track calibration, the two timetable MIPs (uniform-headway PESP and cyclic pattern model with robustness parameters), timetable construction, delay-propagation and fleet simulations (with pseudocode), the combined measure (reliable trip-miles delivered), scenarios and policies, results, bottleneck analysis, validation, conclusions and reproducibility map. Figures: `analysis/tech_figs.py` plus figures from `report/`.
