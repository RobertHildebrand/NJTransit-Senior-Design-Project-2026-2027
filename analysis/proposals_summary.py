"""Proposal list + plain-language findings for the dashboard (results/proposals_dashboard.json)."""
import json, pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
de = json.load(open(R / "results" / "delay_eval.json"))["tt"]
M = pd.read_csv(R / "timetables" / "timetable_metrics.csv")
tt = json.load(open(R / "timetables" / "timetables_dashboard.json")); lab2key = {v["label"]: k for k, v in tt.items()}
m = {lab2key[r["label"]]: r for r in M.to_dict("records")}
WHAT = {
 "njt_current": ("Today's timetable: 150-min cycle, 15/15/30-min peak gaps, 12 vehicle blocks.", False),
 "proposed_T8": ("Same 8 trains, peak gaps evened out (17–21 min); meets packed with 0.5-min buffers.", False),
 "proposal_B8": ("8 trains on a 160-min cycle; every single-track meet has ≥2.5 min buffer; ≥9-min layovers.", True),
 "proposal_B7": ("7-train version of B8 for 7-car days (replaces T7).", False),
 "proposal_E5": ("8 trains at the peaks but only 5 midday (every 30 min): frees a car for maintenance or protect.", False),
 "proposal_E6": ("T8 with the midday service chosen jointly with the peak (midday gaps ≤30 min).", False),
 "proposal_G8": ("E6 with a 2-min buffer at every meet.", False),
 "proposal_S8": ("E6 with 6% of running time moved into holds just before each single-track section.", False),
 "proposal_R8": ("8 trains on a 160-min cycle with ≥8-min layovers (0.5-min meet buffers).", False),
 "proposal_W7": ("Summer timetable: running times +6% for heat restrictions, 7 trains on 160 min, 5 midday.", False),
 "uniform_U8": ("Clock-face every 21 min peak / 30 off-peak (needs retiming at 7 changeover meets).", False),
}
props = [dict(key=k, what=w, rec=r) for k, (w, r) in WHAT.items() if k in de]
f = lambda k: de[k]["normal"]; h = lambda k: de[k]["hot"]
wl = lambda k: m[k]["day_wait"] + f(k)["mean_late"]
rules = [
 f"<b>Evening out the gaps alone makes trains later.</b> T8 cuts the longest AM gap from {m['njt_current']['NB_am_max']:.0f} to {m['proposed_T8']['NB_am_max']:.0f} min, but its meets are packed tight and its layovers are short, so one late train holds the next: on time falls from {100*f('njt_current')['otp']:.0f}% to {100*f('proposed_T8')['otp']:.0f}%. Today's 30-minute gap is, in effect, NJ TRANSIT's recovery time.",
 f"<b>Buffers at meets plus longer layovers fix it.</b> B8 uses the same 8 trains and {m['proposal_B8']['train_hours']:.0f} train-hours (today: {m['njt_current']['train_hours']:.0f}) and is on time {100*f('proposal_B8')['otp']:.0f}% of trips ({100*h('proposal_B8')['otp']:.0f}% on a hot day, vs {100*h('njt_current')['otp']:.0f}% today). Its on-time rate beats today's in every sensitivity case we ran. The price: it gives back the even spacing (longest AM gap {max(m['proposal_B8']['NB_am_max'],m['proposal_B8']['SB_am_max']):.0f} min, average wait {m['proposal_B8']['day_wait']:.1f} vs {m['njt_current']['day_wait']:.1f} min), so wait plus lateness per rider is about the same ({wl('proposal_B8'):.1f} vs {wl('njt_current'):.1f} min). With 8 trains, reliability and even spacing trade off; B8 buys reliability.",
 f"<b>Moving slack to the sidings did not help on its own</b> (S8: {100*f('proposal_S8')['otp']:.0f}%), and longer layovers alone (R8: {100*f('proposal_R8')['otp']:.0f}%) or meet buffers alone (G8: {100*f('proposal_G8')['otp']:.0f}%) each recover only part of the loss. Both are needed.",
 f"<b>A published summer timetable pays off.</b> W7 plans for heat speed restrictions with 7 trains: {100*h('proposal_W7')['otp']:.0f}% on time on a hot day vs {100*h('njt_current')['otp']:.0f}% for today's timetable, at the cost of a longer average wait ({m['proposal_W7']['day_wait']:.1f} vs {m['njt_current']['day_wait']:.1f} min).",
 f"<b>E5 frees a car midday</b> ({m['proposal_E5']['train_hours']:.0f} train-hours instead of {m['njt_current']['train_hours']:.0f}) with midday trains still every ~30 min; useful on days a car is due for maintenance.",
]
json.dump(dict(props=props, rules=rules), open(R / "results" / "proposals_dashboard.json", "w"), indent=1)
for r in rules: print("-", r)
