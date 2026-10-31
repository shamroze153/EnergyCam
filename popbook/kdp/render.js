// Render the book's scenes at print resolution (2700 px square) for the KDP edition.
const { chromium } = require('playwright'); const fs=require('fs');
const [S, file, outDir, only] = process.argv.slice(2);
const SHOTS = [
  // i, action?, wait after action (ms), camera, hidden snowflake [x,y,z]
  { i: 0, name: 'p00-castle', act: true, wait: 4200, cam: { tx: 2.0, ty: 1.25, dist: 11.2, pitch: .52 }, seek: null },
  { i: 1, name: 'p01-coldest-night', act: true, wait: 2600, cam: { tx: 2.0, ty: 1.2, dist: 11.0, pitch: .42 }, seek: [3.45, .55, 1.75] },
  { i: 2, name: 'p02-lantern-fox', act: true, wait: 2600, cam: { tx: 2.0, ty: .95, dist: 10.6, pitch: .5 }, seek: [3.55, .95, 1.35] },
  { i: 3, name: 'p03-whispering-pines', act: true, wait: 3000, cam: { tx: 2.0, ty: 1.15, dist: 11.0, pitch: .48 }, seek: [.55, 1.55, -1.2] },
  { i: 4, name: 'p04-frozen-lake', act: true, wait: 2800, cam: { tx: 2.0, ty: .7, dist: 11.4, pitch: .82 }, seek: [3.35, .32, 2.0] },
  { i: 5, name: 'p05-wishing-hill', act: true, wait: 4200, cam: { tx: 2.0, ty: 1.35, dist: 11.0, pitch: .4 }, seek: [.55, 1.05, -1.3] },
  { i: 6, name: 'p06-first-light', act: true, wait: 4600, cam: { tx: 2.0, ty: 1.0, dist: 11.0, pitch: .52 }, seek: [3.25, 1.25, -1.15] },
  { i: 7, name: 'p07-home-again', act: 'mid', wait: 1200, cam: { tx: 2.0, ty: 1.15, dist: 11.0, pitch: .5 }, seek: [.6, .75, .95] },
];
(async()=>{
  const b=await chromium.launch({proxy:process.env.HTTPS_PROXY?{server:process.env.HTTPS_PROXY}:undefined,args:['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const p=await b.newPage({viewport:{width:1350,height:1350},deviceScaleFactor:2,ignoreHTTPSErrors:true});
  const errs=[]; p.on('pageerror',e=>errs.push(e.message));
  await p.route('**/three@0.160.0/**',r=>r.fulfill({contentType:'application/javascript',body:fs.readFileSync(S+'/vendor/three.module.js')}));
  const html='<!doctype html><html><head><meta charset="utf-8"></head><body>'+fs.readFileSync(file,'utf8')+'</body></html>';
  await p.route('http://local.test/**',r=>r.fulfill({contentType:'text/html',body:html}));
  await p.goto('http://local.test/?print'); await p.waitForFunction(()=>window.__book,null,{timeout:120000});
  await p.addStyleTag({content:'.top,.bar,.hint,.toast,.swipe,.intro,.vignette,.bubble,.story,.vchip,.loader{display:none!important}'});
  await p.evaluate(()=>{ window.__book.prefs.chosen = true; window.__book.prefs.sound = false; });
  const idle=()=>p.waitForFunction(()=>!window.__book.S.busy && !window.__book.S.acting,null,{timeout:180000});
  await p.evaluate(()=>window.__book.go(1)); await idle();
  for (const sh of SHOTS) {
    while (await p.evaluate(()=>window.__book.S.cur) < sh.i) { await p.evaluate(()=>window.__book.go(1)); await idle(); }
    if (only && !only.split(',').includes(String(sh.i))) continue;
    await p.evaluate(c=>{ window.__print = Object.assign({ yaw: 0, zoom: 1, intro: 1, sz: 1, shift: 0, tpitch: c.pitch, tyaw: 0 }, c); }, sh.cam);
    if (sh.seek) await p.evaluate(([i,x,y,z])=>window.__book.seek(i,x,y,z), [sh.i, ...sh.seek]);
    if (sh.act === 'mid') { p.evaluate(()=>window.__book.act()); await p.waitForTimeout(sh.wait); }
    else if (sh.act) { await p.evaluate(()=>window.__book.act()); await p.waitForTimeout(sh.wait); }
    else await p.waitForTimeout(sh.wait);
    await p.screenshot({path:`${outDir}/${sh.name}.png`, timeout: 240000});
    console.log('rendered', sh.name);
    if (sh.act === 'mid') await idle();
  }
  console.log(errs.join('\n')||'no errors'); await b.close();
})();
