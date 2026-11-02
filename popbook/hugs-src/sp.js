/* ================================================================== loose pieces, and the hug that floats up to become a star */
function loose(sp, id, w, h, draw, o = {}) {
  const [c, g] = layerCanvas(w, h); draw(g, w, h); if (!o.basic) grain(c);
  const m = paperMesh(c, w, h, o.px ?? .5, o.py ?? 0, o), grp = new THREE.Group(); grp.add(m); sp.fx.add(grp);
  const rec = { grp, mesh: m, P: { x: 0, y: 0, w, h } }; sp.o[id] = rec;
  if (o.tap) { m.userData = { spread: SP.indexOf(sp), id }; taps.push(m); }
  return rec;
}
function clearStars(sp, o) { (o.extra || []).forEach(s => { sp.fx.remove(s); s.material.dispose(); }); o.extra = []; }
function twinkleStars(o, t) { (o.extra || []).forEach((s, i) => { s.material.opacity = .75 + .25 * Math.sin(t * 3 + i * 1.7); }); }
async function hugStar(sp, o, fromObj, fl, toObj, tl, col = '#fff1c4') {
  if (!o.heart) { loose(sp, 'heart', .28, .26, heartArt, { basic: true, py: .5 }); o.heart.grp.visible = false; }
  const h = o.heart.grp, a = sp.fx.worldToLocal(wpos(fromObj, ...fl)), b = sp.fx.worldToLocal(wpos(toObj, ...tl));
  h.visible = true; h.position.copy(a); h.scale.setScalar(.2); sfx.wish();
  burst(wpos(fromObj, ...fl), '#ff9cc0', 40, 1.0, .08, 1.0, -.2);
  await tween(1.9, p => { const q = E.inOut(p); h.position.set(lerp(a.x, b.x, q) + Math.sin(p * 9) * .14 * (1 - p), lerp(a.y, b.y, q) + Math.sin(p * Math.PI) * .45, lerp(a.z, b.z, q)); h.scale.setScalar(p < .15 ? lerp(.2, 1.1, p / .15) : lerp(1.1, .3, (p - .15) / .85)); if (Math.random() < .6) spark(h.getWorldPosition(new THREE.Vector3()), '#ffc2d6', (Math.random() - .5) * .2, -.1, 0, 1.1); });
  h.visible = false; burst(h.getWorldPosition(new THREE.Vector3()), '#fff3c4', 50, 1.2, .08, 1.3, 0); sfx.chime([988, 1319, 1568]);
  const s = glow(col, .1, 1); s.position.copy(b); sp.fx.add(s); (o.extra ||= []).push(s);
  await tween(.6, p => s.scale.setScalar(.1 + E.back(p) * .55));
}
const SKY = [[-1.2, 2.25], [.5, 2.55], [1.3, 2.2], [-.4, 2.6], [-1.55, 2.6], [1.0, 2.75], [.0, 2.15], [1.65, 2.55]];
const hugTogether = (a, b, ax, bx, dur = .7) => tween(dur, p => { const q = E.inOut(p); a.grp.position.x = lerp(a._x ??= a.grp.position.x, ax, q); b.grp.position.x = lerp(b._x ??= b.grp.position.x, bx, q); }).then(() => { a._x = b._x = undefined; });

/* ================================================================== the story (original text, written for this book) */
const SP = [
  {
    dedication: true, numeral: '', title: 'For {TN}', page: 'iii', mood: 'twilight', snow: .3, fall: '#fff3c4', up: true,
    shot: { pitch: .72, zoom: .95, ty: 1.15, sway: .06 },
    hint: 'Tap the foxes', button: () => 'Light up the sky',
    get paras() { return ['Written by {G}', '§For {TN}', ...CFG.m.split('\n').map(l => '#' + l)]; },
    ground(g) { gardenGround(g, 3); cut(g, '#efe2c4', g => { g.moveTo(1.75, D); g.bezierCurveTo(1.9, 4.2, 2.2, 3.4, 1.95, 2.3); g.lineTo(2.15, 2.3); g.bezierCurveTo(2.4, 3.4, 2.15, 4.2, 2.3, D); g.closePath(); }, { blur: 4, oy: 1 }); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { nightBack(g, w, h, { moon: [3.1, .55, .22], seed: 5 }); } },
      { z: -1.3, rise: 'grow', x: 2, w: 3.8, h: 1.6, draw(g, w, h) { den(g, 1.9, h, 1.0); } },
      { z: -0.2, rise: 'grow', x: 2, w: 3.8, h: 2.0, draw(g, w, h) { tree(g, .45, h, .9, '#3f6a5a', '#4f7f6a'); tree(g, 3.35, h, .95, '#3f6a5a', '#4f7f6a'); },
        props: [{ id: 'banner', x: 0, y: 1.15, w: 2.6, h: .56, px: .5, py: 0, dz: .02, draw(g, w, h) { ribbon(g, w, h, T('{TN}'), .28, '#7a5bb8'); } }] },
      { z: .6, rise: 'slide', dir: -1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'big', x: -.45, y: 0, w: 1.5, h: 1.4, tap: true, draw(g, w, h) { kit(g, .9, h, 1.15); } },
        { id: 'lit', x: .45, y: 0, w: .85, h: .8, tap: true, dz: .02, draw(g, w, h) { kit(g, .3, h, .62, { flip: true, young: true }); } },
      ] },
      { z: 1.4, x: 2, w: 3.9, h: .7, draw(g, w, h) { bank(g, 0, 1.3, h, .35, 3); bank(g, 2.6, 3.9, h, .4, 4); mushrooms(g, .5, h - .1, 1); mushrooms(g, 3.3, h - .12, .8); } },
    ],
    setup(o) { o.banner.grp.scale.x = .06; },
    reset(o) { o._lit = false; o.banner.grp.scale.x = .06; clearStars(SP[0], o); },
    tick(o, t, dt) { twinkleStars(o, t); o.lit.grp.rotation.z = Math.sin(t * 1.5) * .03; if (Math.random() < dt * 4) spark(wpos(o.$h[4], (Math.random() - .5) * 3.6, .3 + Math.random() * .8, .1), '#efff9e', (Math.random() - .5) * .1, .15, 0, 2.0); },
    async action(o, id) {
      if (id === 'lit') { bubble('“Goodnight, Big Fox.”', o.lit, .82, 1800); return; }
      if (id === 'big') { bubble('“Goodnight, Little Fox.”', o.big, 1.4, 1800); return; }
      if (!o._lit) { sfx.chime([523, 659, 784, 1046]); await tween(1.1, p => { o.banner.grp.scale.x = lerp(.06, 1, p); }, E.back); burstAt(o.banner.grp, [0, .3, .1], '#ffe7a8', 50, 1.3); o._lit = true; }
      const n = (o.extra || []).length; await hugStar(SP[0], o, o.big.grp, [.25, .75, .1], o.$h[0], [...SKY[n % SKY.length], .05]);
    },
  },
  {
    numeral: 'I', title: 'The Question', page: 1, mood: 'night', snow: .25, fall: '#fff3c4', up: true,
    shot: { pitch: .58, zoom: .86, ty: 1.15, sway: .06 },
    hint: 'Tap Big Fox', button: () => 'Give a hug',
    paras: [
      'In a cozy den beneath the hill, where the roots made a roof and the moss made a bed, Little Fox was not one bit sleepy.',
      '“Big Fox,” Little Fox whispered, “where do hugs go when they’re finished?”',
      'Big Fox thought for a long moment. Then Big Fox wrapped two warm, fluffy arms around Little Fox and squeezed, just so.',
      '#“Watch,” said Big Fox. “Look up.”',
    ],
    ground(g) { gardenGround(g, 11); g.fillStyle = 'rgba(20,24,60,.18)'; g.fillRect(0, 0, W, D); cut(g, '#c9a07a', g => ell(g, 1.9, 1.7, .5, .25), { blur: 3, oy: 1 }); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { nightBack(g, w, h, { moon: [.75, .6, .24], seed: 12 }); } },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 1.75, draw(g, w, h) { tree(g, .3, h, .95, '#2a4a52', '#35585e'); tree(g, 3.55, h, .9, '#2a4a52', '#35585e'); den(g, 1.9, h, 1.1); } },
      { z: -0.15, rise: 'slide', dir: -1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'big', x: -.6, y: 0, w: 1.5, h: 1.45, tap: true, draw(g, w, h) { kit(g, .9, h, 1.2); } },
        { id: 'lit', x: .55, y: 0, w: .85, h: .8, tap: true, dz: .02, draw(g, w, h) { kit(g, .3, h, .62, { flip: true, young: true }); } },
      ] },
      { z: 1.35, rise: 'drop', x: 2, w: 3.9, h: .6, draw(g, w, h) { bank(g, 0, 1.2, h, .32, 13); bank(g, 2.7, 3.9, h, .32, 14); mushrooms(g, .6, h - .1, 1.1); mushrooms(g, 3.4, h - .1, .9); } },
    ],
    lamp: o => ({ obj: o.big.grp, at: [.3, 1.0, .5], i: 1.2 }),
    reset(o) { clearStars(SP[1], o); o.big.grp.position.x = -.6; o.lit.grp.position.x = .55; },
    async intro(o) { bubble('“Where do hugs go when they’re finished?”', o.lit, .82, 2800); },
    tick(o, t, dt) { twinkleStars(o, t); if (!o._hug) { o.lit.grp.rotation.z = Math.sin(t * 2) * .04; o.big.grp.scale.y = 1 + .015 * Math.sin(t * 1.5); } if (Math.random() < dt * 3) spark(wpos(o.$h[3], (Math.random() - .5) * 3.6, .3 + Math.random() * .6, .1), '#efff9e', 0, .12, 0, 2.0); },
    async action(o, id) {
      if (id === 'lit' && !o._hug) { bubble('“Where do they go?”', o.lit, .82, 1600); return; }
      if (o._hug) return; o._hug = true;
      await hugTogether(o.big, o.lit, -.35, .3);
      tween(.8, p => { o.lit.grp.rotation.z = -.15 * Math.sin(p * Math.PI); o.big.grp.rotation.z = .06 * Math.sin(p * Math.PI); });
      bubble('“Watch. Look up.”', o.big, 1.45, 1800);
      const n = (o.extra || []).length; await hugStar(SP[1], o, o.big.grp, [.45, .7, .15], o.$h[0], [...SKY[n % SKY.length], .05]);
      bubble(n ? '“Another one!”' : '“Ohhh!”', o.lit, .82, 1500);
      await hugTogether(o.big, o.lit, -.6, .55, .6); o._hug = false;
    },
  },
  {
    numeral: 'II', title: 'Up, Up, Up', page: 3, mood: 'night', snow: .4, fall: '#fff3c4', up: true,
    shot: { pitch: .52, zoom: .86, ty: 1.35, sway: .05 },
    hint: 'Tap the sky', button: o => o._done ? 'Send them up again' : 'Send the hugs up',
    paras: [
      '“Every hug floats up,” said Big Fox, “up past the treetops, up past the clouds, all the way to the sky. And there it becomes a star.”',
      'Little Fox looked up. There were so many stars. Thousands. Millions.',
      '“Are those ALL hugs?”',
      '#“Every single one,” said Big Fox. “And some of them are ours.”',
    ],
    ground(g) { gardenGround(g, 21); g.fillStyle = 'rgba(20,24,60,.25)'; g.fillRect(0, 0, W, D); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { nightBack(g, w, h, { stars: 150, seed: 22, paint: g => cut(g, 'rgba(220,210,255,.12)', g => ell(g, 1.9, 1.0, 2.2, .35, -.35), { shadow: false }) }); },
        props: [{ id: 'hc', x: 0, y: 2.0, w: 1.7, h: 1.4, py: .5, basic: true, opacity: .0, dz: .01, draw(g, w, h) { heartConstArt(g, w, h); } }] },
      { z: -1.6, rise: 'grow', x: 2, w: 3.8, h: 1.0, draw(g, w, h) { cut(g, '#26305e', g => { ell(g, .7, h + .2, 1.3, .7); ell(g, 3.1, h + .2, 1.4, .6); }); for (let i = 0; i < 9; i++) pine(g, .2 + i * .43, h, .38 + (i % 3) * .08, '#1c2550', false); } },
      { z: -0.5, rise: 'grow', x: 2, w: 3.8, h: .9, draw(g, w, h) { cut(g, '#2f4a4a', g => ell(g, 1.9, h + .55, 1.7, 1.05)); },
        props: [
          { id: 'big', x: -.3, y: .38, w: 1.5, h: 1.45, tap: true, draw(g, w, h) { kit(g, .9, h, 1.15); } },
          { id: 'lit', x: .5, y: .38, w: .85, h: .8, tap: true, dz: .02, draw(g, w, h) { kit(g, .3, h, .6, { flip: true, young: true }); } },
        ] },
      { z: 1.3, rise: 'drop', x: 2, w: 3.9, h: .9, draw(g, w, h) { [.2, .55, 3.4, 3.75].forEach((x, i) => pine(g, x, h, .55 + (i % 2) * .15, '#22406a', false)); bank(g, 0, 1.0, h, .25, 23); bank(g, 2.9, 3.9, h, .25, 24); } },
    ],
    setup(o, sp) { o.hp = heartPts(1.7, 1.4).map(([x, y]) => { const s = glow('#fff3c4', .32, 0); s.position.set(x, 2.0 + y, .06); sp.hinges[0].add(s); return s; }); },
    lamp: o => ({ obj: o.big.grp, at: [.3, 1.0, .6], i: .8 }),
    reset(o) { o._done = false; o._busy = false; o.hc.mesh.material.opacity = 0; o.hp.forEach(s => { s.material.opacity = 0; s.scale.setScalar(.32); }); },
    async intro(o) { bubble('“Are those ALL hugs?”', o.lit, .8, 2200); },
    tick(o, t, dt) { if (o._done) { o.hp.forEach((s, i) => s.material.opacity = .7 + .3 * Math.sin(t * 2.5 + i)); o.hc.mesh.material.opacity = .85 + .15 * Math.sin(t * 1.5); } if (Math.random() < dt * 2) spark(wpos(o.$h[1], (Math.random() - .5) * 3.4, .5 + Math.random() * .4, .1), '#fff3c4', 0, .5, 0, 2.5); },
    async action(o, id) {
      if (id === 'lit' && !o._busy) { bubble('“Are those ALL hugs?”', o.lit, .8, 1800); return; }
      if (id === 'big' && !o._busy) { bubble('“Every single one.”', o.big, 1.45, 1800); return; }
      if (o._busy) return; o._busy = true; this.reset(o); o._busy = true;
      sfx.wish();
      for (let i = 0; i < o.hp.length; i++) {
        const s = o.hp[i], from = wpos(o.$h[1], (Math.random() - .5) * 3.4, .6, .1), to = s.getWorldPosition(new THREE.Vector3());
        tween(.9, p => { const v = from.clone().lerp(to, E.inOut(p)); v.y += Math.sin(p * Math.PI) * .3; spark(v, ['#ffc2d6', '#fff3c4', '#bfe0ff'][i % 3], 0, 0, 0, .6); }).then(() => { s.material.opacity = 1; tween(.4, p => s.scale.setScalar(.32 + .4 * Math.sin(p * Math.PI))); sfx.note(523 * Math.pow(2, [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24][i] / 12)); });
        await wait(230);
      }
      await wait(900);
      await tween(1.2, p => { o.hc.mesh.material.opacity = p; }, E.out);
      burstAt(o.hc.grp, [0, 0, .05], '#ffc2d6', 80, 1.4, .09, 1.6, 0); sfx.chime([659, 784, 988, 1319]);
      bubble('“Every single one. And some of them are ours.”', o.big, 1.45, 2800);
      o._done = true; o._busy = false;
    },
  },
  {
    numeral: 'III', title: 'The Very First Hug', page: 5, mood: 'day', snow: .5, fall: '#ffc6da',
    shot: { pitch: .58, zoom: .86, ty: 1.2, sway: .06 },
    hint: 'Tap the little cub', button: () => 'Remember the first hug',
    paras: [
      '“Which one is the brightest?” asked Little Fox.',
      'Big Fox pointed. “That one. That was our very first hug. It was spring, the blossoms were falling, and you were so small you fit right here, in the curl of my tail.”',
      '#“You were the smallest thing I had ever seen, and the biggest thing that ever happened to me.”',
    ],
    ground(g) { gardenGround(g, 31); const r = rng(32); dots(g, '#ffc6da', Array.from({ length: 80 }, () => [r() * W, r() * D]), .03); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { stops: [[0, '#9fd3f0'], [.6, '#ffe1ec'], [1, '#fff6e0']], sun: [3.2, .55, .22], paint: g => { cut(g, '#b5dc96', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .65); }); cloud2(g, .4, .6, .9); cloud2(g, 1.9, .4, 1.1); } }); },
        props: [{ id: 'star', x: .9, y: 2.35, w: .34, h: .34, py: .5, basic: true, opacity: .7, dz: .02, draw(g, w, h) { sparkleArt(g, w, h); } }] },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 2.25, draw(g, w, h) { tree(g, .55, h, 1.05, '#f6b7d0', '#ffd6e6', '#ffffff'); tree(g, 3.3, h, .95, '#f2a6c4', '#ffd0e0', '#ffffff'); hedge(g, 1.3, 2.6, h, .5, true, 33); } },
      { z: -0.2, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'big', x: -.15, y: 0, w: 1.5, h: 1.45, tap: true, draw(g, w, h) { kit(g, .9, h, 1.2); } },
        { id: 'cub', x: -.62, y: .02, w: .5, h: .45, tap: true, dz: .03, draw(g, w, h) { kit(g, .2, h, .36, { young: true }); } },
      ] },
      { z: 1.4, rise: 'drop', x: 2, w: 3.9, h: .55, draw(g, w, h) { bank(g, 0, 1.3, h, .3, 34); bank(g, 2.6, 3.9, h, .3, 35); },
        props: [...['daisy', 'bell', 'crocus', 'daisy', 'bell'].map((k, i) => ({ id: 'fl' + i, x: (i < 2 ? -1.7 : 1.0) + (i % 3) * .3, y: .1, w: .3, h: .42, dz: .01, draw(g, w, h) { flower(g, w, h, k); } })),
          ...['#ff9cc0', '#c9a6ff'].map((c, i) => ({ id: 'bf' + i, x: -1 + i * 2, y: 1.0, w: .26, h: .2, py: .5, dz: .05, draw(g, w, h) { butterflyArt(g, w, h, c); } }))] },
    ],
    lamp: o => ({ obj: o.big.grp, at: [0, 1.0, .5], i: .8 }),
    reset(o) { o._busy = false; },
    async intro(o) { bubble('“That one. Our very first hug.”', o.big, 1.45, 2400); },
    tick(o, t, dt) {
      o.star.grp.scale.setScalar(1 + .15 * Math.sin(t * 2)); o.star.grp.rotation.z = t * .3;
      o.cub.grp.scale.y = 1 + .05 * Math.sin(t * 3.5); o.big.grp.rotation.z = Math.sin(t * .8) * .015;
      for (let i = 0; i < 5; i++) o['fl' + i].grp.rotation.z = Math.sin(t * 1.4 + i) * .09;
      for (let i = 0; i < 2; i++) { const b = o['bf' + i]; b.grp.position.set(Math.sin(t * .4 + i * 2.1) * 1.5, .9 + Math.sin(t * .9 + i) * .3, .05); b.grp.scale.x = .2 + .8 * Math.abs(Math.sin(t * 13 + i)); }
    },
    async action(o, id) {
      if (o._busy) return; o._busy = true;
      bubble('“Hello, little one.”', o.big, 1.45, 2200); sfx.chime([784, 988, 1175, 1568]);
      for (let i = 0; i < 5; i++) burstAt(o.$h[1], [-1.6 + i * .8, 1.6 + (i % 2) * .3, .2], i % 2 ? '#ffd6e6' : '#ffb3d1', 40, 1.3, .08, 2.2, -.3);
      await tween(1.2, p => { o.cub.grp.position.y = .02 + Math.abs(Math.sin(p * Math.PI * 2)) * .12; o.big.grp.rotation.z = -.08 * Math.sin(p * Math.PI); o.star.grp.scale.setScalar(1 + 1.2 * Math.sin(p * Math.PI)); o.star.mesh.material.opacity = .7 + .3 * Math.sin(p * Math.PI); });
      burstAt(o.star.grp, [0, 0, .05], '#fff3c4', 60, 1.0, .08, 1.4, 0);
      bubble('“The smallest thing I ever saw…”', o.big, 1.45, 2600); await wait(1200); o._busy = false;
    },
  },
  {
    numeral: 'IV', title: 'The Scraped-Knee Hug', page: 7, mood: 'day', snow: .4, fall: '#f6ff8a', up: true,
    shot: { pitch: .58, zoom: .86, ty: 1.15, sway: .06 },
    hint: 'Tap the log', button: o => o._fell ? 'Try the log again' : 'Cross the log',
    paras: [
      'Then there was the summer hug. Little Fox tried to cross the big log all alone. Wobble, wobble, whoops! Down came Little Fox with a bump and a scraped knee.',
      'Big Fox didn’t say “I told you so.” Big Fox just held on until the crying stopped and the fireflies came out.',
      '#Some hugs fix things that bandages can’t.',
    ],
    ground(g) { gardenGround(g, 41); cut(g, '#6aa6cf', g => { g.moveTo(-.1, 3.0); g.bezierCurveTo(1.3, 2.8, 2.6, 3.3, W + .1, 3.0); g.lineTo(W + .1, 3.5); g.bezierCurveTo(2.6, 3.8, 1.3, 3.3, -.1, 3.5); g.closePath(); }, { blur: 5, oy: 1 }); stroke(g, 'rgba(255,255,255,.55)', .015, g => { const r = rng(42); for (let i = 0; i < 16; i++) { const x = r() * W, y = 3.05 + r() * .4; g.moveTo(x, y); g.quadraticCurveTo(x + .1, y - .04, x + .2, y); } }, false); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { stops: [[0, '#7cc3ee'], [.6, '#ffe9b8'], [1, '#fff4d6']], sun: [2.9, .6, .3], paint: g => { cut(g, '#9fd37f', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .65); }); cloud2(g, .5, .5, 1.0); } }); } },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 2.15, draw(g, w, h) { tree(g, .5, h, 1.0, '#4f9a4f', '#6fbf5f'); tree(g, 3.3, h, 1.05, '#4f9a4f', '#6fbf5f'); hedge(g, 1.2, 2.7, h, .55, false); } },
      { z: -0.3, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'big', x: -1.2, y: 0, w: 1.5, h: 1.45, tap: true, draw(g, w, h) { kit(g, .9, h, 1.15); } },
        { id: 'log', x: .45, y: 0, w: 1.5, h: .36, tap: true, draw(g, w, h) { logArt(g, w, h); } },
        { id: 'lit', x: .3, y: .27, w: .85, h: .8, tap: true, dz: .02, draw(g, w, h) { kit(g, .3, h, .6, { young: true }); } },
      ] },
      { z: 1.4, rise: 'drop', x: 2, w: 3.9, h: .5, draw(g, w, h) { bank(g, 0, 1.2, h, .3, 43); bank(g, 2.7, 3.9, h, .3, 44); reeds(g, .5, h, .8); reeds(g, 3.4, h, .8, 4); } },
    ],
    lamp: o => ({ obj: o.big.grp, at: [0, 1.0, .5], i: .6 }),
    reset(o) { o._fell = false; o._busy = false; o.lit.grp.position.set(.3, .27, .02); o.lit.grp.rotation.z = 0; o.big.grp.position.x = -1.2; },
    async intro(o) { bubble('“Look! No paws!”', o.lit, .8, 1800); },
    tick(o, t, dt) { if (!o._busy && !o._fell) { o.lit.grp.rotation.z = Math.sin(t * 3) * .12; o.lit.grp.position.x = .3 + Math.sin(t * .7) * .2; } if (o._fell && Math.random() < dt * 6) spark(wpos(o.lit.grp, (Math.random() - .5) * 1.5, .2 + Math.random() * .8, .1), '#f6ff8a', (Math.random() - .5) * .1, .15, 0, 1.8); },
    async action(o, id) {
      if (o._busy) return; o._busy = true;
      if (o._fell) { this.reset(o); o._busy = true; await wait(300); }
      bubble('“Wobble… wobble…”', o.lit, .8, 1200);
      await tween(1.0, p => { o.lit.grp.rotation.z = Math.sin(p * Math.PI * 6) * (.15 + p * .2); });
      sfx.whoosh();
      await tween(.55, p => { o.lit.grp.position.set(lerp(.3, .95, p), .27 + Math.sin(p * Math.PI) * .2 - .27 * E.in(p), .02); o.lit.grp.rotation.z = -1.1 * p; });
      sfx.thud(); burstAt(o.lit.grp, [0, .1, .1], '#c9a07a', 25, .8, .06, .8, -2); bubble('“Ow!”', o.lit, .7, 1200);
      await wait(600);
      await tween(.9, p => { o.big.grp.position.x = lerp(-1.2, .05, E.inOut(p)); o.big.grp.position.y = Math.abs(Math.sin(p * Math.PI * 3)) * .08; });
      await tween(.6, p => { o.lit.grp.rotation.z = lerp(-1.1, 0, E.out(p)); o.lit.grp.position.y = lerp(0, .05, p); });
      bubble('“I’ve got you.”', o.big, 1.45, 1800); sfx.chime([659, 784, 988]);
      for (let i = 0; i < 4; i++) burstAt(o.lit.grp, [(i - 1.5) * .3, .5, .1], '#f6ff8a', 20, .9, .07, 2.0, .1);
      await wait(1500); bubble('“All better.”', o.lit, .8, 1800);
      o._fell = true; o._busy = false;
    },
  },
  {
    numeral: 'V', title: 'The Goodbye Hug', page: 9, mood: 'dawn', snow: .55, fall: '#f08a3c',
    shot: { pitch: .58, zoom: .86, ty: 1.15, sway: .06 },
    hint: 'Tap Little Fox', button: o => o._gone ? 'Say goodbye again' : 'Hug goodbye',
    paras: [
      'And there was the autumn hug, on the morning Little Fox went off to school for the very first time, with a brand-new backpack and a brave, wobbly smile.',
      'Big Fox hugged extra long that day. And then Big Fox let go. That was the hardest part.',
      '#Letting go is a kind of hug too. The biggest kind.',
    ],
    ground(g) { gardenGround(g, 51); g.fillStyle = 'rgba(200,140,60,.18)'; g.fillRect(0, 0, W, D); const r = rng(52); dots(g, '#e8742c', Array.from({ length: 70 }, () => [r() * W, r() * D]), .035); dots(g, '#c9533d', Array.from({ length: 40 }, () => [r() * W, r() * D]), .03); cut(g, '#efe2c4', g => { g.moveTo(.6, D); g.bezierCurveTo(1.2, 4.0, 2.4, 3.2, 3.0, 1.6); g.lineTo(3.25, 1.6); g.bezierCurveTo(2.7, 3.3, 1.6, 4.2, 1.1, D); g.closePath(); }, { blur: 4, oy: 1 }); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { stops: [[0, '#8fb8e0'], [.6, '#f6d3a8'], [1, '#ffe8c8']], sun: [.6, .7, .24], paint: g => { cut(g, '#d9b47a', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .65); }); cloud2(g, 2.2, .5, 1.0); } }); } },
      { z: -1.6, rise: 'grow', x: 2, w: 3.8, h: 2.1, draw(g, w, h) { tree(g, .45, h, 1.0, '#e07a2c', '#f2a23a', '#c9533d'); tree(g, 1.5, h, .8, '#d9533d', '#f08a3c'); schoolhouse(g, 3.1, h - .02, 1.1); } },
      { z: -0.35, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'big', x: -1.05, y: 0, w: 1.5, h: 1.45, tap: true, draw(g, w, h) { kit(g, .9, h, 1.15); } },
        { id: 'lit', x: -.15, y: 0, w: .85, h: .85, tap: true, dz: .02, draw(g, w, h) { kit(g, .3, h, .66, { flip: true, young: true, pack: true }); } },
      ] },
      { z: 1.4, rise: 'drop', x: 2, w: 3.9, h: .5, draw(g, w, h) { bank(g, 0, 1.2, h, .3, 53); bank(g, 2.7, 3.9, h, .3, 54); cut(g, '#e8742c', g => { ell(g, .5, h - .05, .3, .08); ell(g, 3.4, h - .05, .35, .09); }, { blur: 3, oy: 1 }); } },
    ],
    lamp: o => ({ obj: o.big.grp, at: [0, 1.0, .5], i: .6 }),
    reset(o) { o._gone = false; o._busy = false; o.big.grp.position.x = -1.05; o.lit.grp.position.set(-.15, 0, .02); o.lit.grp.scale.set(1, 1, 1); },
    async intro(o) { bubble('“I’m going to be brave.”', o.lit, .85, 2000); },
    tick(o, t, dt) { if (!o._busy && !o._gone) o.lit.grp.rotation.z = Math.sin(t * 2.5) * .04; if (Math.random() < dt * 2) burstAt(o.$h[1], [(Math.random() - .5) * 3.4, 1.6, .1], ['#e8742c', '#c9533d', '#f2a23a'][Math.floor(Math.random() * 3)], 3, .3, .07, 3, -.25); },
    async action(o, id) {
      if (o._busy) return; o._busy = true;
      if (o._gone) { this.reset(o); o._busy = true; await wait(300); }
      await hugTogether(o.big, o.lit, -.75, -.4, .7);
      bubble('“Have a wonderful day.”', o.big, 1.45, 2200); sfx.chime([523, 659, 784]);
      await tween(1.6, p => { o.lit.grp.rotation.z = -.12 * Math.sin(p * Math.PI); });
      await wait(400); o.lit.grp.scale.x = -1; bubble('“Bye! I’ll be brave!”', o.lit, .85, 1800);
      for (let i = 0; i < 4; i++) burstAt(o.$h[1], [-1.4 + i * .9, 1.4, .2], ['#e8742c', '#c9533d', '#f2a23a', '#ffcf4a'][i], 25, 1.1, .08, 2.2, -.4);
      await tween(2.4, p => { const t = performance.now() / 1000; o.lit.grp.position.set(lerp(-.4, 1.15, p), Math.abs(Math.sin(t * 9)) * .05 + p * .1, .02); const s = lerp(1, .55, p); o.lit.grp.scale.set(-s, s, s); });
      sfx.chime([1319, 1319, 1568]); bubble('Ding, ding!', o.lit, .7, 1200);
      o._gone = true; o._busy = false;
    },
  },
  {
    numeral: 'VI', title: 'The Winter Hug', page: 11, mood: 'night', snow: 1, fall: '#ffffff',
    shot: { pitch: .58, zoom: .86, ty: 1.2, sway: .06 },
    hint: 'Tap the foxes', button: () => 'Hug Big Fox',
    paras: [
      'The years went by the way the seasons do: quietly, and then all at once.',
      'Little Fox grew tall and strong and quick. Big Fox grew slower, and a little grey around the ears.',
      'And one snowy night, it was Little Fox who wrapped two warm, fluffy arms around Big Fox, and squeezed, just so.',
      '#“Look up,” said Little Fox.',
    ],
    ground(g) { g.fillStyle = N.snow; g.fillRect(0, 0, W, D); cut(g, N.snow2, g => { ell(g, 1.2, 2.0, 1.2, .5); ell(g, 3.2, 4.4, .8, .5); ell(g, .7, 4.6, .7, .3); }, { shadow: false }); dots(g, N.snow3, [[1.3, 4.9], [1.5, 4.6], [1.35, 4.3], [1.55, 4.0]], .04); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { nightBack(g, w, h, { stops: [[0, '#141a48'], [.6, '#33407e'], [1, '#7f8cc4']], seed: 61, moon: [3.2, .5, .2] }); } },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 1.7, draw(g, w, h) { pine(g, .3, h, .9); pine(g, 3.55, h, .85); den(g, 1.9, h, 1.05, true); } },
      { z: -0.1, rise: 'slide', dir: -1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'old', x: -.6, y: 0, w: 1.5, h: 1.4, tap: true, draw(g, w, h) { kit(g, .9, h, 1.1, { old: true }); } },
        { id: 'grown', x: .55, y: 0, w: 1.5, h: 1.5, tap: true, dz: .02, draw(g, w, h) { kit(g, .6, h, 1.2, { flip: true, scarf: '#cc2f3b' }); } },
      ] },
      { z: 1.35, rise: 'drop', x: 2, w: 3.9, h: .9, draw(g, w, h) { drift(g, 0, 1.4, h, .35); drift(g, 2.5, 3.9, h, .35); pine(g, 3.6, h, .7); pine(g, .3, h, .6); } },
    ],
    setup(o, sp) { o.aur = [aurora(3.4, 1.1, 0, '#3cffb4', '#8a6bff'), aurora(3.0, .9, 2, '#5af0ff', '#ff7ad9')]; o.aur.forEach((a, i) => { a.position.set(0, 2.15 + i * .2, .03 + i * .01); sp.hinges[0].add(a); }); },
    lamp: o => ({ obj: o.old.grp, at: [.4, 1.0, .5], i: 1.2 }),
    reset(o) { o._busy = false; clearStars(SP[6], o); o.old.grp.position.x = -.6; o.grown.grp.position.x = .55; o.aur.forEach(a => a.material.uniforms.uAmp.value = .15); },
    async intro(o) { bubble('“Big Fox, do you remember?”', o.grown, 1.5, 2200); },
    tick(o, t, dt) { twinkleStars(o, t); o.aur.forEach(a => a.material.uniforms.uTime.value = t); o.old.grp.scale.y = 1 + .012 * Math.sin(t * 1.2); },
    async action(o, id) {
      if (id === 'old' && !o._busy) { bubble('“I remember every one.”', o.old, 1.4, 2000); return; }
      if (o._busy) return; o._busy = true;
      await hugTogether(o.old, o.grown, -.35, .25, .9);
      tween(1.0, p => { o.old.grp.rotation.z = -.06 * Math.sin(p * Math.PI); o.grown.grp.rotation.z = .08 * Math.sin(p * Math.PI); });
      bubble('“Look up.”', o.grown, 1.5, 1800);
      const n = (o.extra || []).length; await hugStar(SP[6], o, o.grown.grp, [-.2, .9, .15], o.$h[0], [...SKY[n % SKY.length], .05]);
      sfx.wish(); await tween(2.2, p => o.aur.forEach(a => a.material.uniforms.uAmp.value = lerp(.15, 1.1, p)), E.out);
      bubble('“There they all are.”', o.old, 1.4, 2600);
      await wait(1800); await hugTogether(o.old, o.grown, -.6, .55, .8); o._busy = false;
    },
  },
  {
    numeral: 'VII', title: 'Where Hugs Go', page: 13, mood: 'twilight', snow: .35, fall: '#fff3c4', up: true, end: true,
    shot: { pitch: .6, zoom: .88, ty: 1.2, sway: .07 },
    hint: 'Tap the stars', button: () => 'Look up',
    paras: [
      'Now, on the hill beneath the stars, there is a new little fox who is not one bit sleepy.',
      '“Where do hugs go when they’re finished?”',
      'And a fox who was once very little smiles, and points up at a sky so full of stars there is hardly any dark left at all.',
      '#No hug is ever finished. It just goes up, and waits for you.',
    ],
    ground(g) { gardenGround(g, 71); g.fillStyle = 'rgba(30,24,70,.22)'; g.fillRect(0, 0, W, D); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { nightBack(g, w, h, { stops: [[0, '#0f1440'], [.6, '#3b3478'], [1, '#c48aa8']], stars: 50, seed: 72 }); },
        props: [
          { id: 'fill', x: 0, y: .8, w: 3.6, h: 2.0, basic: true, opacity: .1, dz: .008, draw(g, w, h) { starfillArt(g, w, h, 73); } },
          { id: 'hc', x: -.9, y: 2.05, w: 1.2, h: 1.0, py: .5, basic: true, opacity: 0, dz: .012, draw(g, w, h) { heartConstArt(g, w, h); } },
          { id: 'bright', x: 1.1, y: 2.4, w: .36, h: .36, py: .5, basic: true, opacity: .9, dz: .016, draw(g, w, h) { sparkleArt(g, w, h); } },
        ] },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 1.4, draw(g, w, h) { cut(g, '#3a3a6e', g => { ell(g, .8, h + .2, 1.4, .8); ell(g, 3.1, h + .2, 1.3, .7); }); tree(g, .4, h, .65, '#c98aa8', '#e2a6c4', '#ffffff'); tree(g, 3.45, h, .6, '#c98aa8', '#e2a6c4', '#ffffff'); } },
      { z: -0.3, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .9, draw(g, w, h) { cut(g, '#3f5a52', g => ell(g, 1.9, h + .55, 1.8, 1.05)); },
        props: [
          { id: 'grown', x: -.35, y: .4, w: 1.5, h: 1.5, tap: true, draw(g, w, h) { kit(g, .9, h, 1.2, { scarf: '#cc2f3b' }); } },
          { id: 'cub', x: .5, y: .4, w: .8, h: .75, tap: true, dz: .02, draw(g, w, h) { kit(g, .3, h, .55, { flip: true, young: true }); } },
        ] },
      { z: 1.4, rise: 'drop', x: 2, w: 3.9, h: .9, draw(g, w, h) { bank(g, 0, 1.4, h, .35, 74); bank(g, 2.5, 3.9, h, .35, 75); mushrooms(g, .5, h - .12, 1); },
        props: [{ id: 'end', x: 0, y: .32, w: 1.6, h: .48, dz: .02, draw(g, w, h) { ribbon(g, w, h, TR('The End'), .28, '#7a5bb8'); } }] },
    ],
    lamp: o => ({ obj: o.grown.grp, at: [.3, 1.0, .5], i: 1.0 }),
    reset(o) { o._busy = false; o._full = false; o.fill.mesh.material.opacity = .1; o.hc.mesh.material.opacity = 0; },
    async intro(o) { bubble('“Where do hugs go when they’re finished?”', o.cub, .78, 2800); },
    tick(o, t, dt) {
      o.bright.grp.scale.setScalar(1 + .12 * Math.sin(t * 2)); o.bright.grp.rotation.z = t * .2; o.cub.grp.rotation.z = Math.sin(t * 2) * .04;
      if (o._full) { o.fill.mesh.material.opacity = .85 + .15 * Math.sin(t * 1.3); o.hc.mesh.material.opacity = .8 + .2 * Math.sin(t * 2); }
      if (Math.random() < dt * 3) spark(wpos(o.$h[3], (Math.random() - .5) * 3.6, .3 + Math.random() * .6, .1), '#efff9e', 0, .15, 0, 2.0);
    },
    async action(o, id) {
      if (id === 'cub' && !o._busy) { bubble('“Is that one ours?”', o.cub, .78, 1800); return; }
      if (o._busy) return; o._busy = true;
      bubble('“Look up.”', o.grown, 1.5, 1600); sfx.wish();
      await tween(2.2, p => { o.fill.mesh.material.opacity = lerp(.1, 1, E.out(p)); });
      await tween(1.0, p => { o.hc.mesh.material.opacity = p; }); burstAt(o.hc.grp, [0, 0, .05], '#ffc2d6', 60, 1.2, .08, 1.5, 0);
      shootingStar(o.$h[0], [1.6, 2.7, .12], [-.6, 2.1, .12]);
      bubble('“Is that one ours?”', o.cub, .78, 1800); await wait(1600);
      for (let i = 0; i < 3; i++) { sfx.blink(); await tween(.45, p => { o.bright.grp.scale.setScalar(1 + 1.4 * Math.sin(p * Math.PI)); }); await wait(140); }
      bubble('“Every single one.”', o.grown, 1.5, 2600);
      o._full = true; await wait(1200); o._busy = false;
    },
  },
];
