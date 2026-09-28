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
js = json.dumps(D, separators=(",", ":")).replace("NaN", "null")
src = (R / "deck" / "deck_src.html").read_text()
assert src.count("__DATA__") == 1
src = src.replace("/*__INTERACTIVE__*/", (R / "deck" / "interactive.js").read_text())
import base64
for key, fn in [("__IMG_PHOTO__", "riverline_train_camden_2004.jpg"), ("__IMG_MAP__", "riverline_system_map.jpg")]:
    src = src.replace(key, "data:image/jpeg;base64," + base64.b64encode((R / "deck" / "img" / fn).read_bytes()).decode())
(R / "deck" / "river_line_deck.html").write_text(src.replace("__DATA__", js))
print("data kB", len(js) // 1000)
