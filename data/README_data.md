# Data catalog (public sources, gathered 2026-09-28)

## Files in this folder

| File | Contents | Source |
|---|---|---|
| `river_line_stops.csv` | 21 stations south→north: lat/lon and distance along the GTFS shape (33.59 mi) | NJT rail GTFS, 2014 snapshot (github.com/heychrisek/njtransit) |
| `river_line_trips_2014.csv`, `river_line_stop_times_2014.csv` | Every scheduled trip (242) and its stop times, by service day | same |
| `river_line_interstation_runtimes_2014.csv` | Min/median/mean/max scheduled run time for each segment, by direction and day type | same |
| `river_line_blocks_2014.csv` | Trips chained into blocks (vehicle/train duties) | same |
| `river_line_track_segments.csv` | Single vs double track by milepost, with the sidings named | NJDOT Freight Guideway fact sheet (2021): https://nj.gov/transportation/capital/guideway/pdf/F_RiverLINE.pdf |
| `river_line_station_boardings_2024.csv` | Weekday boardings by station, 2024 (total ≈ 5,573; Pennsauken TC missing) | Wikipedia, citing NJT |
| `ntd_njt_light_rail_breakdowns_2022_2024.csv` | NTD breakdown counts. **The River Line is combined with Hudson-Bergen in "LR-PT"**, so these can't be used for the River Line alone | data.transportation.gov (NTD) |
| `river_line_weekday_northbound_2024-12-02_partial.csv` | Partial Dec-2024 NB timetable. Use only as a cross-check | third-party timetable site |
| `raw_gtfs_njt_rail_2014/` | Raw GTFS text files | same as GTFS |

## Key facts (with sources)

- **Line and track.** 34 mi and 21 stations. 12.7 mi is single track and 21.2 mi double track, with sidings at Pennsauken, South Burlington, Florence and Roebling (NJDOT).
- **Freight separation.** Freight runs 10 pm–5:45 am and light rail 5:45 am–10 pm (NJDOT; FRA waiver docket FRA-1999-6135). Maximum speed is 65 mph (NTSB RRD25FR001).
- **Schedule.** About 65–67 min end to end. Peak headway was 15 min in 2014 and base 30 min. Wikipedia and the NJT site say "every 15–30 minutes."
- **Fleet.** 20 Stadler GTW 2/6 diesel articulated cars, delivered 2002–03. Each carries 184 people (90 seated). 14 cars are in an overhaul program (railway-news.com, Jan 2026), and a full-replacement RFP is being prepared.
- **Operator.** In 2025–26 **NJ Transit took over operations from Alstom**; it was completed by Feb 14, 2026 (NJT press release, Sept 3, 2025; board minutes, Nov 12, 2025). Kinkisharyo is the vehicle maintenance contractor. So the "new company" in the client notes is really NJT operating the line directly.
- **Reliability.** Miles between breakdowns fell from 22,337 (2022) to 4,192 (2024) (ROI-NJ, Sept 2025).
  - Peak service was cut to every 30 min in Aug–Oct 2023 and again in Jun–Aug 2024, when heat-related failures led to bus supplements.
  - OTP was 80.4% (Aug 2023), 82% (Jul 2024) and 84% (2025), against 97–99% on HBLR and Newark LR. NJT counts a train on time if it is within 6 min.
- **Ridership.** 9,014 weekday riders (2014), 6,330 (2019) and about 5,350 (2022). The 2025 annual total was 1.6M, 59% of 2019.
- **Weather.** Use NOAA GHCND USW00014792 (Trenton-Mercer) and USW00013739 (PHL) for daily TMAX/TMIN/PRCP/SNOW.

## Still to get
- Current GTFS: the NJT developer portal (https://www.njtransit.com/developer-tools) needs a free registration, or use Transitland feed `f-dr5-nj~transit~rail`.
- The current timetable PDF: https://content.njtransit.com/sites/default/files/pdfs/rail/2025/07/10003/343.pdf
- The monthly OTP dashboard (https://www.njtransit.com/improve/on-time-performance/light-rail) and the CEO monthly reports. Both need a browser.
- The FTA 2024 Revenue Vehicle Inventory. Filter it on Stadler to isolate the River Line fleet.

## Ask NJ Transit for
1. The hold sheets since Feb 14, 2026 (cars available and down, twice a day). **This is the key input.**
2. Failure logs by car: date, type, mileage and time to repair.
3. On-time and cancellation records by train, with causes.
4. The spare-ratio policy and the status of the overhaul program.
5. Speed limits by segment, slow orders, and the meet/dwell rules at sidings.
6. Minimum layover times at Entertainment Center and Trenton, and yard capacity (Camden, Burlington).
7. Consist rules (1 or 2 cars), crew constraints, and passenger counts by trip (APC).
