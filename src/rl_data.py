"""River Line network data: stations, scheduled running times, track sections.

Sources (see ../data/README_data.md):
  - stations + running times: NJ Transit rail GTFS (2014 snapshot; cross-checked
    against the Dec-2024 timetable, 65-67 min end to end)
  - single/double track by milepost: NJDOT Freight Guideway fact sheet (2021)

Positions are measured in miles from Entertainment Center (Camden) along the
GTFS shape. Railroad mileposts are rescaled onto the shape length; this is an
approximation the team should replace with the real track chart.
"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Line:
    stations: pd.DataFrame        # name, pos_mi
    t_nb: np.ndarray              # cumulative NB time (min) at each station, from Camden
    t_sb: np.ndarray              # cumulative SB time (min) at each station, from Trenton
    sections: pd.DataFrame        # track, start_mi, end_mi
    length_mi: float

    # --- trajectory helpers -------------------------------------------------
    def time_nb(self, x):
        """Minutes after leaving Camden at which a NB train is at position x."""
        return float(np.interp(x, self.stations.pos_mi, self.t_nb))

    def time_sb(self, x):
        """Minutes after leaving Trenton at which a SB train is at position x."""
        return float(np.interp(x, self.stations.pos_mi, self.t_sb))

    @property
    def run_nb(self):
        return float(self.t_nb[-1])

    @property
    def run_sb(self):
        return float(self.t_sb[0])

    def single_sections(self):
        return self.sections[self.sections.track == "Single"].reset_index(drop=True)


CAL_DELTA = 1.5


def load_line(runtime_stat: str = "median_run_min", service_day: str = "Weekday", calibrated: bool = True) -> Line:
    st = pd.read_csv(DATA / "river_line_stops.csv").sort_values("seq_south_to_north")
    st = st.rename(columns={"stop_name": "name", "dist_from_ent_center_mi_shape": "pos_mi"})
    st = st[["name", "pos_mi"]].reset_index(drop=True)

    rt = pd.read_csv(DATA / "river_line_interstation_runtimes_2014.csv")
    rt = rt[rt.service_day == service_day]
    names = list(st.name)

    # NB cumulative time
    nb = rt[rt.direction_id == 1].set_index(["from_stop", "to_stop"])[runtime_stat]
    t_nb = [0.0]
    for a, b in zip(names[:-1], names[1:]):
        t_nb.append(t_nb[-1] + float(nb[(a, b)]))
    # SB cumulative time measured from Trenton
    sb = rt[rt.direction_id == 0].set_index(["from_stop", "to_stop"])[runtime_stat]
    t_sb = [0.0] * len(names)
    for i in range(len(names) - 2, -1, -1):
        t_sb[i] = t_sb[i + 1] + float(sb[(names[i + 1], names[i])])

    sec = pd.read_csv(DATA / "river_line_track_segments.csv")
    L = float(st.pos_mi.iloc[-1])
    scale = L / float(sec.to_mp.max())
    # calibration (see analysis/calibrate_track.py): +1.5 mi shift north of MP 12, ramped over 2 mi,
    # so that every meet in NJ TRANSIT's Sept 2026 timetable falls on double track
    f = (lambda mp: np.minimum(mp * scale + CAL_DELTA * np.clip((mp - 12.0) / 2.0, 0, 1), L)) if calibrated else (lambda mp: mp * scale)
    sections = pd.DataFrame({
        "track": sec.track,
        "start_mi": f(sec.from_mp),
        "end_mi": f(sec.to_mp),
        "siding": sec.siding_name.fillna(""),
    })
    return Line(st, np.array(t_nb), np.array(t_sb), sections, L)


def weekday_demand_profile():
    """Assumed share of weekday boardings by hour (05..21). Placeholder until
    the team gets trip-level counts from NJ Transit. Peaky commuter shape."""
    w = {5: 2, 6: 7, 7: 10, 8: 8, 9: 5, 10: 4, 11: 4, 12: 4, 13: 4, 14: 5,
         15: 7, 16: 9, 17: 9, 18: 6, 19: 4, 20: 3, 21: 2}
    s = sum(w.values())
    return {h: v / s for h, v in w.items()}


if __name__ == "__main__":
    line = load_line()
    print(line.stations)
    print("NB run", line.run_nb, "SB run", line.run_sb)
    for _, s in line.single_sections().iterrows():
        oN = line.time_nb(s.end_mi) - line.time_nb(s.start_mi)
        oS = line.time_sb(s.start_mi) - line.time_sb(s.end_mi)
        print(f"single {s.start_mi:5.2f}-{s.end_mi:5.2f}  occ NB {oN:4.1f}  SB {oS:4.1f}")
