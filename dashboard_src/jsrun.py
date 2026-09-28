"""Headless runner for the dashboard engine: jsrun.run(list_of_(params, policies), runs)."""
import asyncio, json, os
from pathlib import Path
from playwright.async_api import async_playwright
HERE = Path(__file__).resolve().parent
HTML = str(HERE / 'river_line_sim.html')   # run build.py in this folder first
D3_LOCAL = HERE / 'node_modules' / 'd3' / 'dist' / 'd3.min.js'   # optional; otherwise d3 loads from cdnjs
async def _run(jobs, runs):
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 1300, 'height': 900})
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        if D3_LOCAL.exists(): await pg.route('**/d3.min.js', lambda r: r.fulfill(path=str(D3_LOCAL), content_type='application/javascript'))
        await pg.route('https://fonts.googleapis.com/**', lambda r: r.fulfill(body='', content_type='text/css'))
        await pg.set_content('<!doctype html><html><head><meta charset="utf-8"></head><body>' + open(HTML).read() + '</body></html>')
        await pg.wait_for_timeout(500)
        if errs: raise RuntimeError(errs)
        base = await pg.evaluate("RL_EVAL.setP({})")
        out = []
        for params, pols in jobs:
            await pg.evaluate("o=>RL_EVAL.setP(o)", {**base, **params})
            out.append(await pg.evaluate("([l,n])=>RL_EVAL.yearP(l,n)", [pols, runs]))
        await pg.evaluate("o=>RL_EVAL.setP(o)", base)
        await b.close(); return out
def run(jobs, runs=10): return asyncio.run(_run(jobs, runs))
