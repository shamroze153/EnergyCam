const { chromium } = require('playwright'); const fs = require('fs');
const [S, file, out, limitMs] = process.argv.slice(2);
const FPS = 25, DT = 1000 / FPS;
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5 });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.addInitScript(() => { try { localStorage.setItem('fox-prefs', JSON.stringify({ chosen: true, layout: 'split', sound: false })); } catch (e) { } });
  await p.route('**/three@0.160.0/**', r => r.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(S + '/vendor/three.module.js') }));
  await p.route('http://local.test/', r => r.fulfill({ contentType: 'text/html', body: fs.readFileSync(file, 'utf8') }));
  await p.clock.install({ time: 0 });
  await p.goto('http://local.test/');
  for (let i = 0; i < 400; i++) { await p.clock.runFor(100); if (await p.evaluate(() => !!window.__book)) break; }
  await p.clock.runFor(1500);
  await p.addStyleTag({ content: `.top,.bar,#hint,#swipe,.toast{display:none!important}
    #cap{position:fixed;left:0;right:0;bottom:0;padding:70px 0 46px;text-align:center;font:italic 500 50px/1.15 "Cormorant Garamond",Georgia,serif;color:#fff6e0;text-shadow:0 2px 14px rgba(0,0,0,.75);background:linear-gradient(transparent,rgba(10,12,30,.72));opacity:0;z-index:50;pointer-events:none}
    #card{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;background:radial-gradient(ellipse at center,rgba(20,29,68,.82),rgba(8,10,26,.96));opacity:0;z-index:60;pointer-events:none;text-align:center}
    #card h1{margin:0;font:italic 600 92px/1 "Cormorant Garamond",Georgia,serif;color:#ffe3a3;text-shadow:0 0 30px rgba(255,200,103,.45)}
    #card p{margin:0;font:500 30px/1.3 "Alegreya Sans",sans-serif;color:#dfe6ff}
    #card .k{margin-top:18px;font:700 26px "Alegreya Sans",sans-serif;background:#ffc867;color:#2a1d0a;padding:12px 30px;border-radius:40px}` });
  await p.evaluate(() => { const c = document.createElement('div'); c.id = 'cap'; document.body.append(c); const k = document.createElement('div'); k.id = 'card'; document.body.append(k); });
  const card = (h1, sub, k) => p.evaluate(([a, b2, c]) => { document.getElementById('card').innerHTML = `<h1>${a}</h1><p>${b2}</p>` + (c ? `<div class="k">${c}</div>` : ''); }, [h1, sub, k]);
  const set = (id, o, txt) => p.evaluate(([i, op, t]) => { const e = document.getElementById(i); e.style.opacity = op; if (t != null) e.textContent = t; }, [id, o, txt]);
  const B = fn => p.evaluate(fn);
  let t = 0, frame = 0; const caps = [];  // [start, end, text]
  const cards = [];  // [start, end]
  const events = [];  // [time, fn]
  async function shoot() {
    let co = 0, ct = ''; for (const [s, e, txt] of caps) if (t >= s && t <= e) { co = Math.min(1, (t - s) / 400, (e - t) / 400); ct = txt; }
    let ko = 0; for (const [s, e] of cards) if (t >= s && t <= e) ko = Math.min(1, (t - s) / 500, (e - t) / 500);
    await p.evaluate(([co, ct, ko]) => { const c = document.getElementById('cap'); c.style.opacity = co; if (ct) c.textContent = ct; document.getElementById('card').style.opacity = ko; }, [co, ct, ko]);
    await p.screenshot({ path: `${out}/f${String(frame++).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 92 });
  }
  async function until(ms) { while (t < ms) { for (let i = events.length - 1; i >= 0; i--) if (events[i][0] <= t) { const [, fn] = events.splice(i, 1)[0]; await fn(); } await p.clock.runFor(DT); t += DT; await shoot(); if (limitMs && t >= +limitMs) throw new Error('limit'); } }
  const at = (ms, fn) => events.push([ms, fn]);
  try {
    await card('The Fox of the First Snow', 'A 3D pop-up storybook'); cards.push([0, 2600]);
    caps.push([3000, 6600, 'A storybook that pops up off the page']);
    [2900, 3500, 4100].forEach((ms, i) => at(ms, () => p.evaluate(i => { window.__book.catchFlake(window.__book.HOOK.flakes[i]); }, i)));
    await until(8600);
    let T0 = 8600;
    const plan = [[0, 4200, 'Starring your child, by name'], [1, 0, 'Tap the characters to bring them to life'], [2, 0, ''], [3, 0, 'Every page is a different adventure'], [4, 0, ''], [5, 900, 'Swipe the pages like a real book'], [6, 0, 'Read in English or اردو'], [7, 1400, 'Record it in your own voice']];
    for (const [i, extra, txt] of plan) {
      if (i > 0) { await B(() => { window.__book.go(1); }); T0 = t; await until(T0 + 2400); }
      const s = t; await B(() => { window.__book.act(); });
      if (txt) caps.push([s + 300, s + 2900 + extra, txt]);
      await until(s + 3000 + extra);
    }
    const e = t + 300; await card('The Fox of the First Snow', 'Put in your child’s name. Make it theirs.', 'Play free in your browser'); cards.push([e, e + 4200]);
    await until(e + 4400);
  } catch (err) { if (err.message !== 'limit') throw err; }
  console.log('frames', frame, 'ms', Math.round(t), errs.join('\n') || 'no errors'); await b.close();
})();
