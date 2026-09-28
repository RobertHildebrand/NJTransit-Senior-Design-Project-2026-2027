"""Assemble RL_DATA3 for the dashboard: timetables, metrics, delay-simulation results, replays, proposals."""
import json, pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parent.parent
tt = json.load(open(R / "timetables" / "timetables_dashboard.json"))
M = pd.read_csv(R / "timetables" / "timetable_metrics.csv")
lab2key = {v["label"]: k for k, v in tt.items()}
metrics = {lab2key[r["label"]]: {k: (None if pd.isna(v) else v) for k, v in r.items()} for r in M.to_dict("records")}
de = json.load(open(R / "results" / "delay_eval.json"))
delay = {"par": de["par"], "tt": {k: {"normal": v["normal"], "hot": v["hot"]} for k, v in de["tt"].items()}, "slack": de["slack"], "sens": de.get("sens", {})}
replay = json.load(open(R / "timetables" / "delay_replays.json"))
cfg = json.load(open(R / "results" / "proposals_dashboard.json"))
year = json.load(open(R / "results" / "js_year_proposals.json")) if (R / "results" / "js_year_proposals.json").exists() else []
reg = json.load(open(R / "results" / "delay_regimes.json"))
delayRegimes = {k: {"p_inc": v["p_inc"], "tt": {n: {"normal": {"otp": x["normal"]["otp"]}, "hot": {"otp": x["hot"]["otp"]}} for n, x in v["tt"].items()}} for k, v in reg.items()}
out = dict(delayRegimes=delayRegimes, tt=tt, metrics=metrics, delay=delay, replay=replay, props=cfg["props"], propRules=cfg["rules"], year=year)
open("data3.json", "w").write(json.dumps(out, separators=(",", ":")))
print("data3.json", round(len(json.dumps(out)) / 1e6, 2), "MB")
