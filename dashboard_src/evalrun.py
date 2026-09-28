import asyncio, json, time
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':1300,'height':900})
        errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.route('**/d3.min.js', lambda r: r.fulfill(path='node_modules/d3/dist/d3.min.js', content_type='application/javascript'))
        await pg.route('https://fonts.googleapis.com/**', lambda r: r.fulfill(body='', content_type='text/css'))
        await pg.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body>'+open('river_line_sim.html').read()+'</body></html>')
        await pg.wait_for_timeout(800); print('errs',errs)
        t=time.time(); pb=await pg.evaluate("RL_EVAL.playbook(300)"); print('playbook',len(pb),round(time.time()-t,1))
        t=time.time(); yr=await pg.evaluate("RL_EVAL.year(10)"); print('year',round(time.time()-t,1))
        t=time.time(); st=await pg.evaluate("RL_EVAL.staging(10)"); print('staging',round(time.time()-t,1))
        json.dump(dict(playbook=pb,year=yr,staging=st),open('/home/claude/river_line/results/js_eval.json','w'),indent=1)
        await b.close()
asyncio.run(main())
