/* ================================================================== where do hugs go: foxes, seasons and stars (all original designs) */
function kit(g, cx, by, k, o = {}) {
  const draw = () => {
    g.save(); g.translate(cx - .72 * k, by - .44 * k); g.scale(.9 * k, .9 * k); foxTail(g); g.restore();
    foxArt(g, cx, by, k, o.pose || 'sit');
    if (o.pack) { cut(g, '#3d8fd8', g => rr(g, cx - .24 * k, by - .62 * k, .2 * k, .26 * k, .05 * k), { blur: 3, oy: 1 }); stroke(g, '#2f6fae', .02 * k, g => { g.moveTo(cx - .1 * k, by - .62 * k); g.lineTo(cx + .02 * k, by - .48 * k); }, false); }
    if (o.scarf) cut(g, o.scarf, g => { ell(g, cx + .12 * k, by - .66 * k, .16 * k, .05 * k, -.2); rr(g, cx + .02 * k, by - .66 * k, .06 * k, .2 * k, .03 * k); }, { blur: 3, oy: 1 });
  };
  const pal = o.old ? { fox: '#bfb0a2', fox2: '#a08f80', foxW: '#f6f1ea', sock: '#6a5a50' } : o.young ? { fox: '#f39a4a', fox2: '#d9772c' } : {};
  withPal(pal, () => { if (o.flip) { g.save(); g.translate(2 * cx, 0); g.scale(-1, 1); draw(); g.restore(); } else draw(); });
}
function tree(g, x, by, s, c1, c2, spots) {
  cut(g, '#6e4f36', g => { g.moveTo(x - .08 * s, by); g.quadraticCurveTo(x - .03 * s, by - .6 * s, x - .14 * s, by - .95 * s); g.lineTo(x + .14 * s, by - .95 * s); g.quadraticCurveTo(x + .03 * s, by - .6 * s, x + .08 * s, by); g.closePath(); });
  cut(g, c1, g => { circ(g, x, by - 1.25 * s, .42 * s); circ(g, x - .36 * s, by - 1.02 * s, .3 * s); circ(g, x + .36 * s, by - 1.05 * s, .32 * s); circ(g, x - .08 * s, by - 1.6 * s, .28 * s); }, { blur: 8, oy: 3 });
  cut(g, c2, g => { circ(g, x - .12 * s, by - 1.4 * s, .17 * s); circ(g, x + .26 * s, by - 1.18 * s, .13 * s); }, { shadow: false });
  if (spots) { const r = rng(Math.round(x * 97 + s * 13)); dots(g, spots, Array.from({ length: 22 }, () => { const a = r() * Math.PI * 2, d = r() * .5 * s; return [x + Math.cos(a) * d, by - 1.22 * s + Math.sin(a) * d * .8]; }), .025 * s); }
}
function den(g, cx, by, s, snow = false) {
  cut(g, snow ? '#e8eef8' : '#5f8a5a', g => { g.moveTo(cx - 1.3 * s, by); g.quadraticCurveTo(cx - .9 * s, by - 1.1 * s, cx, by - 1.15 * s); g.quadraticCurveTo(cx + .9 * s, by - 1.1 * s, cx + 1.3 * s, by); g.closePath(); }, { blur: 8, oy: 3 });
  if (!snow) cut(g, '#77a56a', g => { ell(g, cx - .4 * s, by - .85 * s, .25 * s, .08 * s); ell(g, cx + .5 * s, by - .7 * s, .2 * s, .06 * s); }, { shadow: false });
  cut(g, '#3a2a20', g => { g.moveTo(cx - .28 * s, by); g.lineTo(cx - .28 * s, by - .3 * s); g.arc(cx, by - .3 * s, .28 * s, Math.PI, 0); g.lineTo(cx + .28 * s, by); g.closePath(); });
  stroke(g, '#8a6a4a', .04 * s, g => { g.arc(cx, by - .3 * s, .3 * s, Math.PI, 0); }, false);
  cut(g, '#ffd27a', g => circ(g, cx + .65 * s, by - .55 * s, .1 * s), { sc: 'rgba(255,200,100,1)', blur: 24, oy: 0 });
  stroke(g, '#8a6a4a', .02 * s, g => { circ(g, cx + .65 * s, by - .55 * s, .1 * s); g.moveTo(cx + .55 * s, by - .55 * s); g.lineTo(cx + .75 * s, by - .55 * s); }, false);
  if (snow) cut(g, '#ffffff', g => ell(g, cx, by - 1.12 * s, .7 * s, .08 * s), { shadow: false });
}
function mushrooms(g, x, by, s) { [[0, 1], [.12, .7], [-.1, .55]].forEach(([dx, k]) => { cut(g, '#f6efe0', g => rr(g, x + dx * s - .02 * s * k, by - .12 * s * k, .04 * s * k, .12 * s * k, .02 * s), { blur: 2, oy: 1 }); cut(g, '#e2456f', g => { g.moveTo(x + dx * s - .08 * s * k, by - .11 * s * k); g.quadraticCurveTo(x + dx * s, by - .24 * s * k, x + dx * s + .08 * s * k, by - .11 * s * k); g.closePath(); }, { blur: 2, oy: 1 }); }); }
function schoolhouse(g, x, by, s) {
  cut(g, '#c9533d', g => rr(g, x - .35 * s, by - .45 * s, .7 * s, .45 * s, 0), { blur: 6, oy: 2 });
  cut(g, '#5a3a3a', g => poly(g, [x - .44 * s, by - .43 * s, x, by - .78 * s, x + .44 * s, by - .43 * s]));
  cut(g, '#f6f1e7', g => { rr(g, x - .06 * s, by - .95 * s, .12 * s, .2 * s, 0); rr(g, x - .26 * s, by - .34 * s, .14 * s, .14 * s, .01); rr(g, x + .12 * s, by - .34 * s, .14 * s, .14 * s, .01); });
  cut(g, '#ffcf4a', g => circ(g, x, by - .86 * s, .04 * s), { shadow: false });
  cut(g, '#6e4529', g => rr(g, x - .07 * s, by - .22 * s, .14 * s, .22 * s, .02));
}
function logArt(g, w, h) { cut(g, '#7a5236', g => rr(g, .02, h * .3, w - .04, h * .55, h * .27), { blur: 4, oy: 2 }); cut(g, '#c79a6a', g => ell(g, w - .06, h * .57, h * .14, h * .26), { shadow: false }); stroke(g, '#946747', .012, g => { ell(g, w - .06, h * .57, h * .07, h * .13); }, false); cut(g, '#6faa5f', g => { ell(g, w * .3, h * .3, .08, .03); ell(g, w * .55, h * .32, .06, .025); }, { shadow: false }); }
function heartConstArt(g, w, h) {
  const pts = []; for (let i = 0; i < 11; i++) { const t = i / 11 * Math.PI * 2, x = 16 * Math.pow(Math.sin(t), 3), y = 13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t); pts.push([w / 2 + x / 17 * w * .45, h / 2 - y / 17 * h * .45]); }
  stroke(g, 'rgba(255,240,200,.6)', .012, g => { g.moveTo(...pts[0]); pts.slice(1).forEach(p => g.lineTo(...p)); g.closePath(); }, false);
  pts.forEach(([x, y]) => twinkle(g, x, y, .05, '#fff3c4'));
  return pts;
}
function heartPts(w, h) { const pts = []; for (let i = 0; i < 11; i++) { const t = i / 11 * Math.PI * 2, x = 16 * Math.pow(Math.sin(t), 3), y = 13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t); pts.push([x / 17 * w * .45, y / 17 * h * .45]); } return pts; }
function starfillArt(g, w, h, seed = 9) { const r = rng(seed); for (let i = 0; i < 260; i++) dots(g, `rgba(255,248,225,${.4 + r() * .6})`, [[r() * w, r() * h]], .006 + r() * .014); for (let i = 0; i < 24; i++) twinkle(g, r() * w, r() * h, .03 + r() * .03, '#fff6dc'); }
function nightBack(g, w, h, o = {}) { nightSky(g, w, h, { stops: o.stops || [[0, '#0f1440'], [.6, '#2b2f78'], [1, '#5a4f93']], stars: o.stars ?? 90, seed: o.seed || 7, moon: o.moon, paint: o.paint }); }
