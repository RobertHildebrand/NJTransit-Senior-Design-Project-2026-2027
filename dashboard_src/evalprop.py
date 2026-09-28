import asyncio, json, time
from playwright.async_api import async_playwright
POL = [
 ["Today's timetable (cancel what cannot run)", {"policy":"gtfs","reserve":0}],
 ["Tiers T8–T3, 1 protect", {"policy":"prop","reserve":1}],
 ["Robust tiers B8/B7/T6–T3, 1 protect", {"policy":"prop","reserve":1,"tiers":{"8":"proposal_B8","7":"proposal_B7"}}],
 ["Robust tiers + summer W7, 1 protect", {"policy":"prop","reserve":1,"tiers":{"8":"proposal_B8","7":"proposal_B7"},"summerKey":"proposal_W7"}],
 ["B8 every day (cancel what cannot run)", {"policy":"fixedKey","key":"proposal_B8","reserve":0}],
 ["Robust tiers B8/B7/T6–T3, 0 protect", {"policy":"prop","reserve":0,"tiers":{"8":"proposal_B8","7":"proposal_B7"}}],
]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':1300,'height':900})
        errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.route('**/d3.min.js', lambda r: r.fulfill(path='node_modules/d3/dist/d3.min.js', content_type='application/javascript'))
        await pg.route('https://fonts.googleapis.com/**', lambda r: r.fulfill(body='', content_type='text/css'))
        await pg.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body>'+open('river_line_sim.html').read()+'</body></html>')
        await pg.wait_for_timeout(800); print('errs',errs)
        t=time.time(); yr=await pg.evaluate("l=>RL_EVAL.yearP(l,10)", POL); print('year',round(time.time()-t,1))
        for r in yr: print(r["name"], round(r["cancel_pct"],2), {k:round(v,1) for k,v in r["bySeason"].items()}, round(r["wait"],2), round(r["op"]))
        json.dump(yr,open('/home/claude/river_line/results/js_year_proposals.json','w'),indent=1)
        await b.close()
asyncio.run(main())
