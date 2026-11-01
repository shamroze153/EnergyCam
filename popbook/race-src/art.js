/* ================================================================== the rain race: weather, track and runners (all original designs) */
const MIKAAL = { y: 'short', h: '#1d130f', c: '#2f8fa8', a: 'none', s: '#e3b48e' };
function kid(g, cx, by, k, look = {}, o = {}) { const keep = CFG; CFG = { ...CFG, ...look }; try { princess(g, cx, by, k, { noScarf: true, ...o }); } finally { CFG = keep; } }
function bib(g, cx, by, k, n, col) { const X = v => cx + v * k, Y = v => by - v * k; cut(g, '#ffffff', g => rr(g, X(-.11), Y(1.0), .22 * k, .16 * k, .02 * k), { blur: 2, oy: 1 }); text(g, String(n), X(0), Y(.92), .12 * k, { style: '700', font: '"Alegreya Sans", sans-serif', color: col }); }
function zainabRunner(g, cx, by, k, o = {}) { princess(g, cx, by, k, { noScarf: true, ...o }); bib(g, cx, by, k, 1, '#cc2f3b'); }
function mikaalRunner(g, cx, by, k, o = {}) { kid(g, cx, by, k, MIKAAL, o); bib(g, cx, by, k, 2, '#2f6f8a'); }
function raincloud(g, x, y, s, col = '#8a9ab5') { cut(g, col, g => { circ(g, x, y, .22 * s); circ(g, x + .25 * s, y - .1 * s, .28 * s); circ(g, x + .52 * s, y, .2 * s); rr(g, x - .15 * s, y - .02 * s, .85 * s, .2 * s, .1 * s); }, { blur: 8, oy: 3 }); cut(g, shade(col, .2), g => { circ(g, x + .2 * s, y - .17 * s, .13 * s); circ(g, x - .05 * s, y - .05 * s, .09 * s); }, { shadow: false }); }
function rainSky(g, w, h, o = {}) {
  backdrop(g, w, h, o.stops || [[0, '#5d6f8f'], [.6, '#9fb3c9'], [1, '#d7e3ea']], g => {
    if (o.paint0) o.paint0(g);
    (o.clouds || [[.4, .45, 1.2], [1.9, .3, 1.5], [3.0, .6, 1.0]]).forEach(([x, y, s]) => raincloud(g, x, y, s, o.cloud));
    if (o.streaks !== false) stroke(g, 'rgba(255,255,255,.35)', .012, g => { const r = rng(o.seed || 3); for (let i = 0; i < 70; i++) { const x = r() * w, y = .7 + r() * (h - .7); g.moveTo(x, y); g.lineTo(x - .04, y + .16); } }, false);
    if (o.paint) o.paint(g);
  });
}
function bunting(g, x0, x1, y, sag, cols = ['#e2456f', '#ffcf4a', '#3d8fd8', '#5fbf6a', '#c9a6ff']) {
  stroke(g, '#6a5a4a', .012, g => { g.moveTo(x0, y); g.quadraticCurveTo((x0 + x1) / 2, y + sag * 2, x1, y); }, false);
  const n = Math.max(3, Math.round((x1 - x0) / .17));
  for (let i = 0; i < n; i++) { const t = (i + .5) / n, x = x0 + (x1 - x0) * t, yy = y + 4 * sag * t * (1 - t); cut(g, cols[i % cols.length], g => poly(g, [x - .06, yy, x + .06, yy, x, yy + .14]), { blur: 2, oy: 1 }); }
}
function umbrellaTop(g, cx, cy, r, cols) {
  const n = cols.length;
  for (let i = 0; i < n; i++) { const a0 = Math.PI + i * Math.PI / n, a1 = a0 + Math.PI / n; cut(g, cols[i], g => { g.moveTo(cx, cy); g.arc(cx, cy, r, a0, a1); g.closePath(); }, { blur: 4, oy: 2 }); }
  cut(g, 'rgba(0,0,0,.12)', g => { for (let i = 0; i < n; i++) { const a = Math.PI + (i + .5) * Math.PI / n; ell(g, cx + Math.cos(a) * r * .96, cy + .01, r / n * 1.4, r * .06); } }, { shadow: false });
  stroke(g, '#3a3a4a', .015, g => { g.moveTo(cx, cy - r); g.lineTo(cx, cy - r - .06); }, false);
}
function shamUmb(g, cx, by, k, o = {}) {
  const X = v => cx + v * k, Y = v => by - v * k;
  shamroze(g, cx, by, k, { lantern: false, ...o });
  stroke(g, '#e2456f', .012 * k, g => { g.moveTo(X(-.09), Y(1.6)); g.quadraticCurveTo(X(-.05), Y(1.38), X(-.02), Y(1.36)); g.moveTo(X(.09), Y(1.6)); g.quadraticCurveTo(X(.05), Y(1.38), X(.02), Y(1.36)); }, false);
  cut(g, '#d6dde8', g => rr(g, X(-.05), Y(1.37), .1 * k, .055 * k, .02 * k), { blur: 2, oy: 1 });
  if (o.umbrella !== false) {
    stroke(g, '#3a3a4a', .022 * k, g => { g.moveTo(X(.46), Y(.92)); g.lineTo(X(.46), Y(2.45)); g.moveTo(X(.46), Y(.92)); g.quadraticCurveTo(X(.46), Y(.84), X(.4), Y(.87)); }, false);
    umbrellaTop(g, X(.46), Y(2.45), .62 * k, ['#e2456f', '#ffcf4a', '#3d8fd8', '#5fbf6a', '#ff8f4a']);
  }
}
function puddle(g, x, y, rx, ry) { cut(g, '#5f7f9f', g => ell(g, x, y, rx, ry), { blur: 3, oy: 1 }); cut(g, '#8fb0cf', g => ell(g, x - rx * .1, y - ry * .1, rx * .82, ry * .7), { shadow: false }); stroke(g, 'rgba(255,255,255,.5)', .01, g => { ell(g, x - rx * .3, y - ry * .2, rx * .25, ry * .12); }, false); }
function wetGround(g, seed = 5, o = {}) {
  g.fillStyle = o.col || '#8cc077'; g.fillRect(0, 0, W, D); const r = rng(seed);
  cut(g, '#7ab066', g => { for (let i = 0; i < 7; i++) ell(g, r() * W, r() * D, .5 + r() * .5, .25 + r() * .2, r()); }, { shadow: false });
  stroke(g, '#5a9a4c', .01, g => { for (let i = 0; i < 160; i++) { const x = r() * W, y = r() * D; g.moveTo(x, y); g.lineTo(x + (r() - .5) * .05, y - .06); } }, false);
  for (let i = 0; i < 40; i++) dots(g, ['#ffffff', '#ffd27a', '#f4a6c4'][i % 3], [[r() * W, r() * D]], .014);
}
function track(g, y0, y1, o = {}) {
  cut(g, '#c79a6a', g => { g.moveTo(-.1, y0); g.bezierCurveTo(1.3, y0 - .25, 2.7, y0 + .25, W + .1, y0); g.lineTo(W + .1, y1); g.bezierCurveTo(2.7, y1 + .25, 1.3, y1 - .25, -.1, y1); g.closePath(); }, { blur: 4, oy: 1 });
  stroke(g, 'rgba(255,255,255,.8)', .02, g => { const m = (y0 + y1) / 2; g.moveTo(-.1, m); g.bezierCurveTo(1.3, m - .25, 2.7, m + .25, W + .1, m); }, false, [.14, .12]);
  const r = rng(o.seed || 9); dots(g, '#a77f55', Array.from({ length: 50 }, () => [r() * W, y0 + .05 + r() * (y1 - y0 - .1)]), .02);
}
function oak(g, x, by, s) {
  cut(g, '#6e4f36', g => { g.moveTo(x - .12 * s, by); g.quadraticCurveTo(x - .05 * s, by - .7 * s, x - .2 * s, by - 1.1 * s); g.lineTo(x + .18 * s, by - 1.1 * s); g.quadraticCurveTo(x + .05 * s, by - .7 * s, x + .12 * s, by); g.closePath(); });
  cut(g, '#4f8f4f', g => { circ(g, x, by - 1.45 * s, .5 * s); circ(g, x - .42 * s, by - 1.2 * s, .36 * s); circ(g, x + .42 * s, by - 1.22 * s, .38 * s); circ(g, x - .1 * s, by - 1.85 * s, .34 * s); }, { blur: 8, oy: 3 });
  cut(g, '#6aab5f', g => { circ(g, x - .15 * s, by - 1.6 * s, .2 * s); circ(g, x + .3 * s, by - 1.35 * s, .16 * s); }, { shadow: false });
}
function posterArt(g, w, h) {
  cut(g, '#fff6dc', g => rr(g, .02, .02, w - .04, h - .04, .02), { blur: 4, oy: 2 });
  text(g, 'THE GREAT', w / 2, .13, .08, { style: '700', font: '"Alegreya Sans", sans-serif', color: '#2d3f7a' });
  text(g, 'RAIN RACE', w / 2, .26, .12, { style: '700', font: '"Alegreya Sans", sans-serif', color: '#cc2f3b' });
  stroke(g, '#3d8fd8', .012, g => { g.moveTo(.08, .35); g.quadraticCurveTo(w / 2, .3, w - .08, .38); }, false);
  [[.15, .45], [.3, .5], [.45, .43]].forEach(([x, y]) => cut(g, '#3d8fd8', g => { g.moveTo(x, y - .04); g.quadraticCurveTo(x + .03, y + .01, x, y + .02); g.quadraticCurveTo(x - .03, y + .01, x, y - .04); }, { shadow: false }));
  text(g, 'bridge · hill · castle', w / 2, h - .08, .045, { style: 'italic', color: '#5a5f7a' });
  cut(g, '#c9963a', g => circ(g, w / 2, .05, .015), { shadow: false });
}
function duckArt(g, w, h) {
  cut(g, '#ffd23f', g => { ell(g, w * .48, h * .65, w * .32, h * .22); circ(g, w * .7, h * .35, h * .17); }, { blur: 3, oy: 1 });
  cut(g, '#ff8f2a', g => poly(g, [w * .82, h * .35, w * .98, h * .4, w * .82, h * .44]), { shadow: false });
  dots(g, '#1d1410', [[w * .74, h * .3]], h * .035);
  cut(g, '#f2b92a', g => ell(g, w * .42, h * .6, w * .14, h * .09, -.3), { shadow: false });
}
function boatArt(g, w, h, c = '#fdf6e8') { cut(g, c, g => poly(g, [.02, h * .55, w - .02, h * .55, w * .78, h - .02, w * .22, h - .02]), { blur: 4, oy: 2 }); cut(g, shade(c, -.08), g => poly(g, [w * .3, h * .55, w * .5, .02, w * .7, h * .55]), { blur: 3, oy: 1 }); stroke(g, 'rgba(80,90,120,.35)', .008, g => { g.moveTo(w * .5, .04); g.lineTo(w * .5, h * .55); }, false); }
function medalArt(g, w, h, col = '#ffcf4a') { stroke(g, '#3d6fb8', .035, g => { g.moveTo(w * .25, 0); g.lineTo(w / 2, h * .55); g.lineTo(w * .75, 0); }, false); cut(g, col, g => circ(g, w / 2, h * .7, w * .26), { sc: col === '#ffcf4a' ? 'rgba(255,200,80,.9)' : 'rgba(220,230,255,.9)', blur: 10, oy: 0 }); stroke(g, shade(col, -.25), .01, g => circ(g, w / 2, h * .7, w * .17), false); }
function boltArt(g, w, h) { cut(g, '#fff6b0', g => poly(g, [w * .55, 0, w * .25, h * .5, w * .48, h * .5, w * .3, h, w * .78, h * .38, w * .52, h * .38, w * .72, 0]), { sc: 'rgba(255,250,200,1)', blur: 20, oy: 0 }); }
function rainbowArt(g, w, h) { ['#ff5f6d', '#ff9f43', '#ffd93f', '#6bd36b', '#4fa8ff', '#8a6bff'].forEach((c, i) => stroke(g, c, .09, g => g.arc(w / 2, h, w / 2 - .06 - i * .085, Math.PI, 0), false)); }
function crowdArt(g, w, h, seed = 4) {
  const r = rng(seed), cols = [['#e2456f', '#ffd0dc'], ['#3d8fd8', '#bfe0ff'], ['#ffcf4a', '#fff1b8'], ['#5fbf6a', '#d0f5c9'], ['#c9a6ff', '#efe3ff']];
  for (let i = 0; i < Math.round(w / .32); i++) { const x = .18 + i * .32 + (r() - .5) * .05, y = h - .25 - r() * .12, c = cols[i % cols.length];
    cut(g, ['#e8b98f', '#c68a5e', '#a76a43', '#f3d2b8'][i % 4], g => circ(g, x, y + .08, .07), { blur: 2, oy: 1 });
    cut(g, '#3a3a4a', g => rr(g, x - .1, y + .14, .2, .2, .05), { blur: 2, oy: 1 });
    umbrellaTop(g, x, y - .02, .16, [c[0], c[1], c[0]]); }
}
function stoneArt(g, w, h) { cut(g, '#9aa3ad', g => ell(g, w / 2, h * .6, w * .45, h * .35), { blur: 4, oy: 2 }); cut(g, '#c2c9d0', g => ell(g, w * .42, h * .45, w * .2, h * .1), { shadow: false }); }
function snailArt(g, w, h) { cut(g, '#c9a07a', g => { rr(g, .02, h - .07, w * .8, .06, .03); circ(g, w * .12, h - .1, .04); }, { blur: 2, oy: 1 }); cut(g, '#d9685a', g => circ(g, w * .52, h - .17, .12), { blur: 3, oy: 1 }); stroke(g, '#a8463a', .012, g => g.arc(w * .52, h - .17, .06, 0, Math.PI * 1.6), false); stroke(g, '#8a6a4a', .008, g => { g.moveTo(w * .1, h - .12); g.lineTo(w * .07, h - .2); g.moveTo(w * .14, h - .12); g.lineTo(w * .15, h - .2); }, false); cut(g, '#ffffff', g => rr(g, w * .44, h - .23, .1, .07, .01), { shadow: false }); text(g, '3', w * .49, h - .195, .05, { style: '700', font: '"Alegreya Sans", sans-serif', color: '#5a5f7a' }); }
function mudArt(g, w, h) { cut(g, '#7a5236', g => ell(g, w / 2, h * .6, w * .48, h * .38), { blur: 4, oy: 1 }); cut(g, '#946747', g => { ell(g, w * .35, h * .5, w * .12, h * .1); ell(g, w * .68, h * .62, w * .1, h * .08); }, { shadow: false }); }
function finishArt(g, w, h) {
  cut(g, '#f6f1e7', g => { rr(g, .08, .35, .08, h - .35, .02); rr(g, w - .16, .35, .08, h - .35, .02); }, { blur: 4, oy: 2 });
  cut(g, '#2d3f7a', g => rr(g, 0, .08, w, .3, .05), { blur: 6, oy: 2 });
  for (let i = 0; i < 12; i++) cut(g, i % 2 ? '#ffffff' : '#22253a', g => rr(g, .06 + i * (w - .12) / 12, .3, (w - .12) / 12, .05, 0), { shadow: false });
  text(g, 'FINISH', w / 2, .2, .15, { style: '700', font: '"Alegreya Sans", sans-serif', color: '#ffd27a' });
}
function tapeArt(g, w, h) { cut(g, '#e2304f', g => rr(g, 0, h * .3, w, h * .4, .01), { blur: 3, oy: 1 }); stroke(g, '#ffd27a', .008, g => { g.moveTo(0, h * .36); g.lineTo(w, h * .36); }, false); }
function picnicArt(g, w, h) {
  cut(g, '#e2456f', g => ell(g, w / 2, h * .7, w * .48, h * .28), { blur: 4, oy: 2 });
  stroke(g, '#ffffff', .02, g => { for (let i = -3; i <= 3; i++) { g.moveTo(w / 2 + i * .12, h * .45); g.lineTo(w / 2 + i * .12, h * .95); } }, false);
  cut(g, '#f6f1e7', g => { rr(g, w * .2, h * .28, .16, .16, .05); ell(g, w * .62, h * .55, .18, .06); }, { blur: 3, oy: 1 });
  stroke(g, '#f6f1e7', .02, g => { g.moveTo(w * .2 + .16, h * .33); g.quadraticCurveTo(w * .2 + .24, h * .3, w * .2 + .2, h * .42); }, false);
  dots(g, '#c98a2a', [[w * .56, h * .52], [w * .62, h * .5], [w * .68, h * .53], [w * .6, h * .56], [w * .66, h * .57]], .035);
  cut(g, '#ffffff', g => { rr(g, w * .38, h * .45, .07, .09, .015); rr(g, w * .8, h * .5, .07, .09, .015); }, { blur: 2, oy: 1 });
}
function dropTex() { const c = mk(128, 128), g = c.getContext('2d'); g.fillStyle = '#ffffff'; g.beginPath(); g.moveTo(64, 10); g.quadraticCurveTo(108, 72, 64, 112); g.quadraticCurveTo(20, 72, 64, 10); g.fill(); g.fillStyle = 'rgba(160,200,255,.6)'; g.beginPath(); ell(g, 52, 74, 9, 16, .3); g.fill(); return new THREE.CanvasTexture(c); }
function bootPrint() { const c = mk(64, 64), g = c.getContext('2d'); g.fillStyle = '#fff'; g.beginPath(); ell(g, 32, 24, 13, 17); ell(g, 32, 50, 10, 9); g.fill(); return new THREE.CanvasTexture(c); }
