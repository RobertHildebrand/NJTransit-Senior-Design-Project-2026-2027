"""Merge the interactive-slide data into the deck data and build river_line_deck.html from deck_src.html."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent
D = json.load(open(R / "deck" / "deckdata_base.json"))
ix = json.load(open(R / "results" / "deck_interactive.json"))
for k, v in ix["tt"].items():
    v["meets"] = [m[:4] for m in v["meets"] if m[3] < 12]
    v["traj"] = [[d, [[x, t] for x, t in pts]] for d, pts in v["traj"]]
D["ix"] = ix
rp = json.load(open(R / "timetables" / "delay_replays.json"))
KEYS = ["njt_current", "proposal_B8", "proposed_T8", "proposal_B7"]
D["rp"] = {day: {k: dict(otp=round(v[k]["otp"] * 100, 1), late=round(v[k]["mean_late"], 1), knock=round(v[k]["knock"]),
                        trips=[[t["d"], t["p"], t["a"], t["k"], t["l"], [[w[0], w[1], w[2]] for w in t["w"]]] for t in v[k]["trips"]])
                 for k in KEYS} for day, v in rp["days"].items()}
# live line map: the dashboard's own map data and day engine inputs (subset)
DD = R / "dashboard_src"
m1 = json.load(open(DD / "data.json")); m2 = json.load(open(DD / "data2.json")); m3 = json.load(open(DD / "data3.json"))
LMK = ["njt_current", "proposal_B8", "proposal_B7", "proposed_T3", "proposed_T4", "proposed_T5", "proposed_T6", "proposed_T7", "proposed_T8"]
D["lm"] = dict(D={k: m1[k] for k in ["track", "stations", "sections", "yards", "river", "counties", "L", "plans"]},
               D2={"gtfs": {"stationPos": m2["gtfs"]["stationPos"]}},
               D3={"tt": {k: m3["tt"][k] for k in LMK},
                   "metrics": {k: {q: m3["metrics"][k][q] for q in ["vehicles_peak", "vehicles_midday"]} for k in LMK}})
js = json.dumps(D, separators=(",", ":")).replace("NaN", "null")
src = (R / "deck" / "deck_src.html").read_text()
assert src.count("__DATA__") == 1
src = src.replace("/*__INTERACTIVE__*/", (R / "deck" / "engine.js").read_text() + "\n" + (R / "deck" / "interactive.js").read_text() + "\n" + (R / "deck" / "livemap.js").read_text())
import base64
import re
src = re.sub(r"__IMG:([A-Za-z0-9_.\-]+)__", lambda mm: "data:image/jpeg;base64," + base64.b64encode((R / "deck" / "img" / mm.group(1)).read_bytes()).decode(), src)
assert "__IMG" not in src
src = src.replace("__DATA__", js)
# standalone document: opens in any browser, no Claude needed
i = src.index('<div class="app">')
page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + src[:i] + '</head>\n<body>\n' + src[i:] + '\n</body>\n</html>\n')
(R / "deck" / "river_line_deck.html").write_text(page)
print("data kB", len(js) // 1000)
