"""Combined evaluation (revision 4): fleet simulation + delay simulation -> headline metric.

Headline metric (RTD, 'reliable trip-miles delivered'): on-time trip-miles actually run, as a share of the trip-miles in
NJ TRANSIT's normal published timetable. A cancelled trip counts as not delivered; a trip that runs is weighted by the
delay-simulation on-time probability for that day's timetable (normal day, or a summer mix with 23% hot days).

Scenarios are calibrated to observed data (see report Section 'Validation'):
  S1 Alstom 2024-25 : MDBF 3,661 (NJT monthly series mean 2024-25), repair 10 days, delay regime fitted to 83% on time
  S2 NJ TRANSIT 2026: MDBF 3,568 (mean Mar-Aug 2026), repair 5 days, delay regime fitted to 93% on time
  S3 Renewed fleet  : MDBF 10,000 (about 2017 level), repair 5 days, 2026 delay regime
Costs: $547 per train-hour = NTD FY2024 vehicle operations + vehicle maintenance / vehicle revenue hours (TS2.1).
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'dashboard_src'))
import jsrun
ROOT = Path(__file__).resolve().parent.parent
RUNS = 10
COST = 547.0
T = {"8": "proposal_B8", "7": "proposal_B7"}
POL = [
 ["Today: NJT timetable, cancel what cannot run", {"policy": "gtfs", "reserve": 0}],
 ["Publish B8 every day, cancel what cannot run", {"policy": "fixedKey", "key": "proposal_B8", "reserve": 0}],
 ["Tiers T8-T3 from 6 am count, 1 protect car", {"policy": "prop", "reserve": 1}],
 ["Robust tiers B8/B7/T6-T3, 1 protect car", {"policy": "prop", "reserve": 1, "tiers": T}],
 ["Robust tiers + summer W7, 1 protect car", {"policy": "prop", "reserve": 1, "tiers": T, "summerKey": "proposal_W7"}],
 ["Robust tiers B8/B7/T6-T3, no protect car", {"policy": "prop", "reserve": 0, "tiers": T}],
]
SCEN = {
 "S1 Alstom 2024-25": dict(mdbf=3661, repairDays=10, longOut=3, delayRegime="alstom_2024_25", trainHour=COST),
 "S2 NJ TRANSIT 2026": dict(mdbf=3568, repairDays=5, longOut=3, delayRegime="njt_2026", trainHour=COST),
 "S3 Renewed fleet": dict(mdbf=10000, repairDays=5, longOut=3, delayRegime="njt_2026", trainHour=COST),
}
SENS = {
 "S1, repairs 8 days": dict(SCEN["S1 Alstom 2024-25"], repairDays=8),
 "S1, repairs 12 days": dict(SCEN["S1 Alstom 2024-25"], repairDays=12),
 "S2, repairs 3 days": dict(SCEN["S2 NJ TRANSIT 2026"], repairDays=3),
 "S2, repairs 8 days": dict(SCEN["S2 NJ TRANSIT 2026"], repairDays=8),
 "S2, MDBF 2,500": dict(SCEN["S2 NJ TRANSIT 2026"], mdbf=2500),
}
if __name__ == "__main__":
    allsc = {**SCEN, **SENS}
    res = jsrun.run([(p, POL) for p in allsc.values()], RUNS)
    out = {name: dict(params=allsc[name], policies=r) for name, r in zip(allsc, res)}
    json.dump(out, open(ROOT / "results" / "combined_eval.json", "w"), indent=1)
    for name, v in out.items():
        print("==", name)
        for x in v["policies"]:
            print(f"  {x['name'][:48]:48s} RTD {x['rtd']:5.1f} [{x['rtd_min']:.1f}-{x['rtd_max']:.1f}]  delivered {x['delivered']:5.1f}  cancel {x['cancel_pct']:5.1f}  A {x['A']:.1f}  th {x['th']:.0f}")
