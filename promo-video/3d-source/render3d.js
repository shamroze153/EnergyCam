// node render3d.js stills 3,9,16 [w h]  |  node render3d.js frames <worker> <nworkers> [w h]  |  node render3d.js cues
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => {
  const [mode, a1, a2, w = '1080', h = '1350'] = process.argv.slice(2);
  const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: +w, height: +h } });
  page.on('pageerror', e => console.error('PAGE ERROR', e.message)); page.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()) });
  await page.goto(`http://127.0.0.1:8765/index.html?w=${w}&h=${h}`); await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
  const tag = +w > +h ? 'wide' : 'tall';
  if (mode === 'cues') { fs.writeFileSync(path.join(__dirname, 'cues.json'), JSON.stringify(await page.evaluate(() => window.CUES))); }
  else if (mode === 'stills') { for (const t of a1.split(',').map(Number)) { const b = await page.evaluate(t => frame(t, .9), t); fs.writeFileSync(path.join(__dirname, `st_${tag}_${t}.jpg`), Buffer.from(b, 'base64')); } }
  else { const k = +a1, n = +a2; const N = Math.round(await page.evaluate(() => DUR * FPS)); const dir = path.join(__dirname, 'frames_' + tag); fs.mkdirSync(dir, { recursive: true });
    const t0 = Date.now(); for (let i = k; i < N; i += n) { const f = path.join(dir, String(i).padStart(5, '0') + '.jpg'); if (fs.existsSync(f)) continue; const b = await page.evaluate(t => frame(t, .93), i / 30); fs.writeFileSync(f, Buffer.from(b, 'base64')); if (i % 60 === k) console.log(`w${k} frame ${i}/${N} ${((Date.now() - t0) / 1000).toFixed(0)}s`); } }
  await browser.close();
})();
