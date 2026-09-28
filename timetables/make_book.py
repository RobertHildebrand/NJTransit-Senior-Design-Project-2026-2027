import pandas as pd
m=pd.read_csv('timetable_metrics.csv')
BS="\\\\"
def row(r):
    lab=r.label.replace('&','\\&').replace('%','\\%')
    return f"{lab} & {r.vehicles_peak}/{r.vehicles_midday} & {r.trips} & {r.train_hours:.0f} & {r.NB_am_mean:.1f}/{r.NB_am_max:.0f} & {r.SB_am_mean:.1f}/{r.SB_am_max:.0f} & {r.NB_mid_mean:.1f} & {r.day_wait:.1f} & {r.conflicts} "+BS
rows="\n".join(row(r) for r in m.itertuples())
head=open('book_head.tex').read()
open('timetable_book.tex','w').write(head.replace('%%ROWS%%',rows))
