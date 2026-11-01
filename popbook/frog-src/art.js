/* ================================================================== the royal garden: scenery and characters for this book (all original designs) */
const G = { grass: '#9fd37f', grass2: '#7dbb64', grass3: '#5a9a4c', hedge: '#4f9a5c', hedge2: '#357a48', lily: '#5fae55', lily2: '#3f8a45',
  frog: '#6cbf4f', frog2: '#4e9a3c', belly: '#e6f5b8', gold: '#ffcf4a', rose: '#ef5f86', rose2: '#ffd0dc', water: '#6cc3d6', water2: '#3b93ad', deep: '#1d5a75', bark: '#7a5a3e' };
function withPal(p, fn) { const keep = {}; for (const k in p) { keep[k] = N[k]; N[k] = p[k]; } try { fn(); } finally { Object.assign(N, keep); } }
function castleDay(g, cx, by, k) { withPal({ snow: '#fbf3e4', roof: '#d9557d', stone: '#f1e6d6', stone2: '#d8c6b0' }, () => castle(g, cx, by, k)); }
function daySky(g, w, h, o = {}) {
  backdrop(g, w, h, o.stops || [[0, '#7cc3ee'], [.62, '#c8e9f8'], [1, '#f4f7df']], g => {
    if (o.sun) cut(g, '#fff3b0', g => circ(g, o.sun[0], o.sun[1], o.sun[2]), { sc: 'rgba(255,230,150,1)', blur: 40, oy: 0 });
    if (o.stars) skyStars(g, w, h, o.stars, o.seed || 4, .55);
    if (o.paint) o.paint(g);
  });
}
function hills(g, w, h, col, pts) { cut(g, col, g => { g.moveTo(-.1, h + .1); pts.forEach(([x, y, r]) => g.quadraticCurveTo(x - r, y, x, y)); g.lineTo(w + .1, h + .1); g.closePath(); }, { blur: 6, oy: 2 }); }
function rose(g, x, y, r, c = G.rose) { cut(g, c, g => circ(g, x, y, r), { blur: 2, oy: 1 }); stroke(g, shade(c, -.28), r * .22, g => g.arc(x, y, r * .5, .3, Math.PI * 1.7), false); }
function hedge(g, x0, x1, by, hgt, roses = true, seed = 3) {
  const n = Math.max(2, Math.round((x1 - x0) / .26)), st = (x1 - x0) / n;
  cut(g, G.hedge2, g => { rr(g, x0, by - hgt * .7, x1 - x0, hgt * .7 + .02, .05); for (let i = 0; i <= n; i++) circ(g, x0 + i * st, by - hgt * .7 - ((i * 37) % 5) * .012, st * .62); }, { blur: 6, oy: 2 });
  cut(g, G.hedge, g => { for (let i = 0; i <= n; i++) circ(g, x0 + i * st - st * .1, by - hgt * .76 - ((i * 37) % 5) * .012, st * .4); }, { shadow: false });
  if (roses) { const r = rng(seed); for (let i = 0; i < n * 2.4; i++) rose(g, x0 + .05 + r() * (x1 - x0 - .1), by - .06 - r() * hgt * .85, .03 + r() * .022, r() < .6 ? G.rose : G.rose2); }
}
function bank(g, x0, x1, by, hgt, seed = 1) {
  drift(g, x0, x1, by, hgt, G.grass, G.grass3); const r = rng(seed);
  stroke(g, G.grass3, .012, g => { for (let i = 0; i < (x1 - x0) * 12; i++) { const x = x0 + r() * (x1 - x0); g.moveTo(x, by + .02); g.lineTo(x + (r() - .5) * .06, by - .04 - r() * .07); } }, false);
  for (let i = 0; i < (x1 - x0) * 5; i++) dots(g, ['#ffffff', '#ffd27a', '#f4a6c4', '#c9a6ff'][i % 4], [[x0 + .05 + r() * (x1 - x0 - .1), by - .03 - r() * hgt * .45]], .018);
}
function willow(g, x, by, s) {
  cut(g, G.bark, g => { g.moveTo(x - .1 * s, by); g.quadraticCurveTo(x - .02 * s, by - .6 * s, x - .14 * s, by - 1.15 * s); g.lineTo(x + .1 * s, by - 1.15 * s); g.quadraticCurveTo(x + .03 * s, by - .6 * s, x + .1 * s, by); g.closePath(); });
  cut(g, '#5f9a52', g => { ell(g, x, by - 1.3 * s, .62 * s, .36 * s); ell(g, x - .35 * s, by - 1.15 * s, .35 * s, .25 * s); ell(g, x + .38 * s, by - 1.18 * s, .33 * s, .24 * s); }, { blur: 8, oy: 3 });
  for (let i = 0; i < 16; i++) { const a = -.6 + i / 15 * 1.2, sx = x + a * 1.0 * s, len = .55 + ((i * 37) % 10) / 22; stroke(g, i % 2 ? '#86c46a' : '#6fb058', .05 * s, g => { g.moveTo(x + a * .7 * s, by - 1.38 * s); g.quadraticCurveTo(sx + a * .18 * s, by - 1.05 * s, sx + a * .12 * s, by - (1.3 - len) * s); }, false); }
}
function reeds(g, x, by, s, n = 5) {
  for (let i = 0; i < n; i++) { const xx = x + (i - n / 2) * .06 * s, hh = (.5 + ((i * 37) % 10) / 25) * s, lean = (i - n / 2) * .03 * s;
    stroke(g, '#4f8a3c', .018 * s, g => { g.moveTo(xx, by); g.quadraticCurveTo(xx + lean, by - hh * .6, xx + lean * 1.6, by - hh); }, false);
    if (i % 2) cut(g, '#7a4a2a', g => rr(g, xx + lean * 1.5 - .025 * s, by - hh - .02 * s, .05 * s, .16 * s, .025 * s), { blur: 2, oy: 1 }); }
  cut(g, '#5fa04a', g => { for (let i = 0; i < 4; i++) { const xx = x + (i - 1.5) * .09 * s; g.moveTo(xx, by); g.quadraticCurveTo(xx + (i - 1.5) * .08 * s, by - .2 * s, xx + (i - 1.5) * .14 * s, by - .38 * s); g.quadraticCurveTo(xx + (i - 1.5) * .03 * s, by - .15 * s, xx + .03 * s, by); } }, { blur: 2, oy: 1 });
}
function lotus(g, x, y, r) { cut(g, '#ffc6da', g => { for (let i = -2; i <= 2; i++) ell(g, x + i * r * .32, y - r * .35, r * .2, r * .5, i * .4); }, { blur: 3, oy: 1 }); cut(g, '#ff9fbf', g => ell(g, x, y - r * .3, r * .18, r * .42), { shadow: false }); dots(g, '#ffd27a', [[x, y - r * .08]], r * .12); }
function lilyPad(g, x, y, rx, ry, rot = 0, fl = false) {
  cut(g, G.lily, g => { g.moveTo(x, y); g.ellipse(x, y, rx, ry, rot, .3, Math.PI * 2 - .05); g.closePath(); }, { blur: 4, oy: 1 });
  stroke(g, G.lily2, .008, g => { for (let i = 0; i < 6; i++) { const a = rot + .7 + i * .9; g.moveTo(x, y); g.lineTo(x + Math.cos(a) * rx * .85, y + Math.sin(a) * ry * .85); } }, false);
  if (fl) lotus(g, x - rx * .25, y + ry * .1, rx * .45);
}
function pond(g, cx, cy, rx, ry, seed = 2) {
  const r = rng(seed);
  cut(g, '#7d6a52', g => ell(g, cx, cy, rx + .1, ry + .08), { blur: 8, oy: 2 });
  const gr = g.createRadialGradient(cx, cy, .05, cx, cy, Math.max(rx, ry)); gr.addColorStop(0, G.deep); gr.addColorStop(.65, G.water2); gr.addColorStop(1, G.water);
  cut(g, gr, g => ell(g, cx, cy, rx, ry), { shadow: false });
  stroke(g, 'rgba(255,255,255,.3)', .012, g => { ell(g, cx - rx * .35, cy - ry * .3, rx * .3, ry * .12); ell(g, cx + rx * .3, cy + ry * .35, rx * .22, ry * .09); }, false);
  cut(g, '#d9d1bd', g => { for (let i = 0; i < 30; i++) { const a = i / 30 * Math.PI * 2 + r() * .1; ell(g, cx + Math.cos(a) * (rx + .07), cy + Math.sin(a) * (ry + .06), .07 + r() * .04, .05 + r() * .02, a); } }, { blur: 3, oy: 1 });
}
function gardenGround(g, seed = 5) {
  g.fillStyle = G.grass; g.fillRect(0, 0, W, D); const r = rng(seed);
  cut(g, G.grass2, g => { for (let i = 0; i < 7; i++) ell(g, r() * W, r() * D, .5 + r() * .5, .25 + r() * .2, r()); }, { shadow: false });
  for (let i = 0; i < 70; i++) dots(g, ['#ffffff', '#ffd27a', '#f4a6c4', '#c9a6ff'][i % 4], [[r() * W, r() * D]], .014 + r() * .01);
  stroke(g, G.grass3, .01, g => { for (let i = 0; i < 160; i++) { const x = r() * W, y = r() * D; g.moveTo(x, y); g.lineTo(x + (r() - .5) * .05, y - .06); } }, false);
}
function pathStones(g, pts) { cut(g, '#efe2c4', g => pts.forEach(([x, y, s]) => ell(g, x, y, .16 * s, .1 * s, (x * 7) % 1)), { blur: 3, oy: 1 }); }
function ballArt(g, w, h) {
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) * .44;
  if (COLORING) { cut(g, '#fff', g => circ(g, cx, cy, r)); stroke(g, '#1a1a1a', .012, g => { g.ellipse(cx, cy, r, r * .35, -.5, 0, Math.PI * 2); }, false); return; }
  const gr = g.createRadialGradient(cx - r * .35, cy - r * .4, r * .08, cx, cy, r); gr.addColorStop(0, '#fff6c4'); gr.addColorStop(.45, '#ffcf4a'); gr.addColorStop(1, '#c4860f');
  cut(g, gr, g => circ(g, cx, cy, r), { sc: 'rgba(255,200,80,.9)', blur: 14, oy: 0 });
  stroke(g, 'rgba(150,90,10,.5)', r * .07, g => g.ellipse(cx, cy, r * .98, r * .34, -.5, 0, Math.PI * 2), false);
  stroke(g, 'rgba(150,90,10,.4)', r * .06, g => g.ellipse(cx, cy, r * .34, r * .98, -.5, 0, Math.PI * 2), false);
  cut(g, 'rgba(255,255,255,.8)', g => ell(g, cx - r * .38, cy - r * .42, r * .24, r * .12, -.6), { shadow: false });
}
function frogArt(g, cx, by, k = 1, pose = 'sit', o = {}) {
  // Shamroze as a frog: a tiny gold crown and his blue polka-dot tie, worn as a bow tie
  const X = v => cx + v * k, Y = v => by - v * k, C = o.col || G.frog, C2 = shade(C, -.2);
  const foot = (x, y, d) => cut(g, C2, g => { for (let i = -1; i <= 1; i++) ell(g, x + d * i * .05 * k, y, .035 * k, .02 * k, i * .5); ell(g, x, y - .02 * k, .05 * k, .03 * k); }, { blur: 3, oy: 1 });
  if (pose === 'leap') {
    cut(g, C2, g => { [-1, 1].forEach(d => { g.moveTo(X(d * .1), Y(.2)); g.quadraticCurveTo(X(d * .3), Y(.02), X(d * .24), Y(-.22)); g.lineTo(X(d * .15), Y(-.2)); g.quadraticCurveTo(X(d * .14), Y(.02), X(d * .01), Y(.15)); g.closePath(); }); });
    foot(X(-.22), Y(-.24), -1); foot(X(.22), Y(-.24), 1);
  } else {
    cut(g, C2, g => { ell(g, X(-.2), Y(.12), .15 * k, .11 * k, -.35); ell(g, X(.2), Y(.12), .15 * k, .11 * k, .35); });
    foot(X(-.3), Y(.02), -1); foot(X(.3), Y(.02), 1);
  }
  cut(g, C, g => ell(g, X(0), Y(.26), .2 * k, .21 * k));
  cut(g, G.belly, g => ell(g, X(0), Y(.22), .13 * k, .14 * k), { shadow: false });
  if (pose === 'leap' || o.armsUp) cut(g, C, g => { rr(g, X(-.24), Y(.62), .06 * k, .3 * k, .03 * k); rr(g, X(.18), Y(.62), .06 * k, .3 * k, .03 * k); });
  else { cut(g, C, g => { rr(g, X(-.14), Y(.32), .06 * k, .3 * k, .03 * k); rr(g, X(.08), Y(.32), .06 * k, .3 * k, .03 * k); }); foot(X(-.11), Y(.02), -1); foot(X(.11), Y(.02), 1); }
  cut(g, C, g => { ell(g, X(0), Y(.45), .25 * k, .16 * k); circ(g, X(-.12), Y(.58), .085 * k); circ(g, X(.12), Y(.58), .085 * k); });
  if (o.crown !== false) { cut(g, G.gold, g => poly(g, [X(-.075), Y(.6), X(-.085), Y(.73), X(-.035), Y(.67), X(0), Y(.76), X(.035), Y(.67), X(.085), Y(.73), X(.075), Y(.6)]), { blur: 3, oy: 1 }); dots(g, '#e2456f', [[X(0), Y(.645)]], .018 * k); }
  cut(g, '#ffffff', g => { circ(g, X(-.12), Y(.585), .06 * k); circ(g, X(.12), Y(.585), .06 * k); }, { shadow: false });
  if (o.closed) stroke(g, '#1d1410', .016 * k, g => { g.arc(X(-.12), Y(.59), .035 * k, .15 * Math.PI, .85 * Math.PI); g.moveTo(X(.155), Y(.59)); g.arc(X(.12), Y(.59), .035 * k, .15 * Math.PI, .85 * Math.PI); }, false);
  else { dots(g, '#1d1410', [[X(-.11), Y(.58)], [X(.13), Y(.58)]], .034 * k); dots(g, '#ffffff', [[X(-.098), Y(.595)], [X(.142), Y(.595)]], .011 * k); }
  dots(g, '#2a4a24', [[X(-.03), Y(.5)], [X(.03), Y(.5)]], .009 * k);
  stroke(g, '#2a4a24', .016 * k, g => { g.moveTo(X(-.16), Y(.45)); g.quadraticCurveTo(X(0), Y(.33), X(.16), Y(.45)); }, false);
  dots(g, 'rgba(240,110,140,.55)', [[X(-.18), Y(.41)], [X(.18), Y(.41)]], .032 * k);
  cut(g, '#3d6fb8', g => { poly(g, [X(0), Y(.31), X(-.11), Y(.36), X(-.11), Y(.26)]); poly(g, [X(0), Y(.31), X(.11), Y(.36), X(.11), Y(.26)]); }, { blur: 3, oy: 1 });
  cut(g, '#2f5a9a', g => circ(g, X(0), Y(.31), .026 * k), { shadow: false });
  dots(g, '#dfe9ff', [[X(-.07), Y(.32)], [X(-.05), Y(.29)], [X(.06), Y(.33)], [X(.08), Y(.29)]], .008 * k);
}
function prince(g, cx, by, k = 1, o = {}) { shamroze(g, cx, by, k, { lantern: false, crown: true, ...o }); }
function sparkleArt(g, w, h) { twinkle(g, w / 2, h / 2, w * .42, '#fff3c4'); dots(g, '#ffffff', [[w / 2, h / 2]], w * .1); }
function heartArt(g, w, h) { cut(g, '#ff7aa2', g => heart(g, w / 2, h * .55, Math.min(w, h) * .32), { sc: 'rgba(255,120,160,.9)', blur: 10, oy: 0 }); }
function fishArt(g, w, h, c) { cut(g, c, g => { ell(g, w * .45, h / 2, w * .32, h * .3); poly(g, [w * .72, h / 2, w * .98, h * .15, w * .98, h * .85]); }, { blur: 3, oy: 1 }); cut(g, shade(c, .35), g => ell(g, w * .38, h * .58, w * .16, h * .1), { shadow: false }); dots(g, '#1d1410', [[w * .26, h * .44]], h * .07); dots(g, '#fff', [[w * .25, h * .42]], h * .025); }
function weedArt(g, w, h, c) { stroke(g, c, .05, g => { g.moveTo(w / 2, h); for (let y = h, i = 0; y > .05; y -= .18, i++) g.quadraticCurveTo(w / 2 + (i % 2 ? .1 : -.1), y - .09, w / 2, y - .18); }, false); cut(g, shade(c, .15), g => { for (let y = h - .2, i = 0; y > .15; y -= .22, i++) ell(g, w / 2 + (i % 2 ? .07 : -.07), y, .07, .03, i % 2 ? .5 : -.5); }, { blur: 2, oy: 1 }); }
function dragonflyArt(g, w, h) { cut(g, 'rgba(200,240,255,.75)', g => { ell(g, w * .38, h * .3, w * .2, h * .12, -.3); ell(g, w * .62, h * .3, w * .2, h * .12, .3); ell(g, w * .38, h * .55, w * .17, h * .1, .3); ell(g, w * .62, h * .55, w * .17, h * .1, -.3); }, { shadow: false }); stroke(g, '#2f7fa8', .02, g => { g.moveTo(w / 2, h * .15); g.lineTo(w / 2, h * .95); }, false); dots(g, '#2f7fa8', [[w / 2, h * .15]], .025); }
function frogPrint() { const c = mk(64, 64), g = c.getContext('2d'); g.fillStyle = '#fff'; g.beginPath(); ell(g, 32, 42, 9, 11); [[-1, 0], [0, 1], [1, 0]].forEach(([d, u]) => { g.moveTo(32, 36); g.lineTo(32 + d * 16, 18 - u * 4); g.lineTo(32 + d * 10, 34); }); circ(g, 16, 17, 5); circ(g, 32, 12, 5); circ(g, 48, 17, 5); g.fill(); return new THREE.CanvasTexture(c); }
function roseBush(g, w, h) { stroke(g, '#3f7a3c', .025, g => { g.moveTo(w / 2, h); g.quadraticCurveTo(w / 2 - .05, h * .55, w / 2, h * .22); }, false); cut(g, '#4f9a4a', g => { ell(g, w / 2 - .08, h * .62, .08, .035, -.5); ell(g, w / 2 + .08, h * .45, .08, .035, .5); }, { blur: 2, oy: 1 }); rose(g, w / 2, h * .2, .1); }
function tearArt(g, w, h) { cut(g, '#bfe6ff', g => { g.moveTo(w / 2, .005); g.quadraticCurveTo(w / 2 + w * .45, h * .6, w / 2, h - .005); g.quadraticCurveTo(w / 2 - w * .45, h * .6, w / 2, .005); g.closePath(); }, { shadow: false }); }
const WATER_F = 'uniform float uTime; varying vec2 vUv; void main(){ vec2 p = vUv * 2. - 1.; float r = length(p); if (r > 1.) discard; float w = sin(p.x * 17. + uTime * 1.4 + sin(p.y * 6. + uTime)) * sin(p.y * 15. - uTime * 1.1 + sin(p.x * 5.)); float c = smoothstep(.5, 1., w) * .4 * (1. - smoothstep(.75, 1., r)); gl_FragColor = vec4(vec3(.85, .97, 1.) * c, 1.); }';
function waterSheen(rx, rz) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(rx * 2, rz * 2), new THREE.ShaderMaterial({ uniforms: { uTime: { value: 0 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }', fragmentShader: WATER_F }));
  m.rotation.x = -Math.PI / 2; return m;
}
