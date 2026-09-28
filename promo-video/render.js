// usage: node render.js stills 2,6,12   |   node render.js video out.mp4
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
(async () => {
  const [mode, arg] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  page.on('pageerror', e => console.error('PAGE ERROR', e.message));
  await page.goto('file://' + path.join(__dirname, 'promo.html'));
  await page.evaluate(async () => {
    for (const f of ["700 66px Archivo", "600 22px Archivo", "400 28px Archivo", "600 22px 'IBM Plex Mono'", "500 12px 'IBM Plex Mono'", "700 20px 'IBM Plex Mono'"]) await document.fonts.load(f);
  });
  const grab = t => page.evaluate(t => { render(t); return document.getElementById('c').toDataURL('image/png').split(',')[1]; }, t);
  if (mode === 'stills') {
    for (const t of arg.split(',').map(Number)) require('fs').writeFileSync(path.join(__dirname, `still_${t}.png`), Buffer.from(await grab(t), 'base64'));
  } else {
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '30', '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', arg], { stdio: ['pipe', 'inherit', 'inherit'] });
    const N = Math.round(await page.evaluate(() => DUR * FPS));
    for (let i = 0; i < N; i++) {
      const buf = Buffer.from(await grab(i / 30), 'base64');
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 150 === 0) console.log('frame', i, '/', N);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  }
  await browser.close();
})();
