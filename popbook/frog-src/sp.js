/* ================================================================== loose pieces that travel through the scene (the ball, the frog) */
function loose(sp, id, w, h, draw, o = {}) {
  const [c, g] = layerCanvas(w, h); draw(g, w, h); if (!o.basic) grain(c);
  const m = paperMesh(c, w, h, o.px ?? .5, o.py ?? 0, o), grp = new THREE.Group(); grp.add(m); sp.fx.add(grp);
  const rec = { grp, mesh: m, P: { x: 0, y: 0, w, h } }; sp.o[id] = rec;
  if (o.tap) { m.userData = { spread: SP.indexOf(sp), id }; taps.push(m); }
  return rec;
}
function ripple(sp, x, z, s = .7, dur = 1.4, col = '#e8fbff') {
  const m = new THREE.Mesh(new THREE.RingGeometry(.86, 1, 48), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: .8, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.position.set(x, Y0 + .014, z); m.scale.setScalar(.05); sp.fx.add(m);
  tween(dur, p => { m.scale.setScalar(.05 + s * p); m.material.opacity = .8 * (1 - p); }, E.out).then(() => { sp.fx.remove(m); m.geometry.dispose(); m.material.dispose(); });
}
const arc = (a, b, p, hgt) => [lerp(a[0], b[0], p), lerp(a[1], b[1], p) + Math.sin(p * Math.PI) * hgt, lerp(a[2], b[2], p)];
async function hop(rec, a, b, hgt, dur = .55, spin = 0) { await tween(dur, p => { rec.grp.position.set(...arc(a, b, p, hgt)); rec.grp.rotation.z = spin * Math.sin(p * Math.PI); }, E.inOut); }
const pondPads = [[1.3, .8], [2.0, .42], [2.75, .85], [2.15, 1.3]];

/* ================================================================== the story (original text, written for this book) */
const SP = [
  {
    dedication: true, numeral: '', title: 'For {TN}', page: 'iii', mood: 'twilight', snow: .45, fall: '#efff9e', up: true,
    shot: { pitch: .72, zoom: .95, ty: 1.15, sway: .06 },
    async intro(o) { await tween(1.4, p => { if (!o._lit) o.win.mesh.material.opacity = lerp(.25, .6, p); }); },
    hint: 'Tap the castle', button: o => o._lit ? 'Fireworks again' : 'Light up the castle',
    get paras() { return ['Written by {G}', '§For {TN}', ...CFG.m.split('\n').map(l => '#' + l)]; },
    ground(g) {
      gardenGround(g, 3);
      cut(g, '#efe2c4', g => { g.moveTo(1.75, D); g.bezierCurveTo(1.9, 4.2, 2.2, 3.4, 1.95, 2.3); g.lineTo(2.15, 2.3); g.bezierCurveTo(2.4, 3.4, 2.15, 4.2, 2.3, D); g.closePath(); }, { blur: 4, oy: 1 });
      [[1.0, 2.8], [3.1, 3.2], [.7, 4.6], [3.3, 4.9]].forEach(([x, y]) => rose(g, x, y, .06));
    },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { stops: [[0, '#2c3477'], [.55, '#9a74b8'], [1, '#ffc29a']], stars: 45, seed: 5, paint: g => { moon(g, 3.1, .55, .2); cut(g, '#7f7fb8', g => { ell(g, .7, h, 1.5, .7); ell(g, 3.2, h, 1.4, .6); }); cut(g, '#6f9a7a', g => { ell(g, 1.9, h + .15, 2.2, .5); }); } }); } },
      { z: -1.3, rise: 'grow', x: 2, w: 3.8, h: 2.75, draw(g, w, h) { cut(g, G.grass2, g => ell(g, 1.9, h + .1, 1.7, .4)); castleDay(g, 1.9, h - .2, .86); },
        props: [{ id: 'win', x: 0, y: 0, w: 3.8, h: 2.75, basic: true, opacity: .25, dz: .006, draw(g, w, h) { castleWindows(g, 1.9, h - .2, .86, '#ffd27a', 'rgba(255,200,100,1)'); } }] },
      { z: -0.25, rise: 'grow', x: 2, w: 3.8, h: 2.0, draw(g, w, h) { willow(g, .42, h, .95); willow(g, 3.38, h, 1.0); },
        props: [{ id: 'banner', x: 0, y: 1.0, w: 2.5, h: .56, px: .5, py: 0, dz: .02, draw(g, w, h) { ribbon(g, w, h, T('{TN}'), .3); } }] },
      { z: .55, rise: 'slide', dir: -1, x: .95, w: 1.0, h: 2.3, draw: null, props: [{ id: 'sham', x: 0, y: 0, w: 1.0, h: 2.15, tap: true, draw(g, w, h) { prince(g, .45, h, .9, { ball: true, crown: false }); } }] },
      { z: 1.4, x: 2, w: 3.9, h: .7, draw(g, w, h) { bank(g, 0, 1.3, h, .35, 3); bank(g, 2.6, 3.9, h, .4, 4); },
        props: [{ id: 'frog', x: 1.0, y: .05, w: .6, h: .6, tap: true, draw(g, w, h) { frogArt(g, w / 2, h, .74); } }] },
    ],
    setup(o, sp) {
      o.banner.grp.scale.x = .06;
      o.shGlow = glow('#ffcf4a', .55, .8); o.shGlow.position.set(-.05 + .46 * .9, 1.0 * .9, .04); o.sham.grp.add(o.shGlow);
    },
    lamp: o => ({ obj: o.win.grp, at: [0, 1.6, .3], i: 2.5 }),
    reset(o) { o._lit = false; o.banner.grp.scale.x = .06; o.win.mesh.material.opacity = .25; },
    tick(o, t, dt) {
      o.shGlow.material.opacity = .7 + .15 * Math.sin(t * 3);
      o.frog.grp.scale.y = 1 + .035 * Math.sin(t * 3.2);
      if (Math.random() < dt * 6) spark(wpos(o.win.grp, (Math.random() - .5) * 2.2, .6 + Math.random() * 2.2, .2), '#fff1c4', (Math.random() - .5) * .05, .12, 0, 1.8);
      if (Math.random() < dt * 5) spark(wpos(o.sham.grp, .36 + (Math.random() - .5) * .08, .9, .05), '#ffcf4a', (Math.random() - .5) * .08, .25, 0, 1.2);
      if (o._lit && Math.random() < dt * .5) burstAt(o.win.grp, [(Math.random() - .5) * 2, 2.5 + Math.random() * .4, .2], ['#ffd27a', '#ff8fb8', '#9fe3ff'][Math.floor(Math.random() * 3)], 40, 1.2, .08, 1.5);
    },
    async action(o, id) {
      if (id === 'frog') { sfx.ribbit(); bubble('“Ribbit! This story is for you, {TN}!”', o.frog, .62, 2400); await tween(.5, p => { o.frog.grp.position.y = .05 + Math.sin(p * Math.PI) * .35; o.frog.grp.rotation.z = Math.sin(p * Math.PI * 2) * .2; }); return; }
      if (id === 'sham') { bubble('“This story is for you, {TN}.”', o.sham, 2.1, 2600); sfx.chime([659, 784, 988]); await tween(.6, p => { o.shGlow.scale.setScalar(.55 + .5 * Math.sin(p * Math.PI)); }); return; }
      if (!o._lit) {
        bubble('“This story is for you, {TN}.”', o.sham, 2.1, 2200);
        sfx.chime([523, 659, 784, 1046]);
        await tween(1.1, p => { o.banner.grp.scale.x = lerp(.06, 1, p); }, E.back);
        burstAt(o.banner.grp, [0, .3, .1], '#ffe7a8', 50, 1.3);
        await tween(1.2, p => { o.win.mesh.material.opacity = lerp(.25, 1, p); L.target = lerp(2.5, 9, p); }, E.out);
        o._lit = true;
      }
      for (let i = 0; i < 3; i++) { sfx.firework(); burstAt(o.win.grp, [(-1 + i) * .9, 2.6 + (i % 2) * .3, .2], ['#ffd27a', '#ff8fb8', '#9fe3ff'][i], 70, 1.6, .1, 1.7); await wait(380); }
    },
  },
  {
    numeral: 'I', title: 'The Golden Ball', page: 1, mood: 'day', snow: .4, fall: '#ffc6da',
    shot: { pitch: .55, zoom: .86, ty: 1.25, sway: .06 },
    hint: 'Tap the golden ball', button: () => 'Throw the golden ball',
    paras: [
      'In a garden full of roses, behind a castle with pink towers, lived {TN}. Of all her treasures, she loved one best of all: a little golden ball that shone like a piece of the sun.',
      'Every afternoon she ran out into the garden and threw it high, high into the sky, and caught it again.',
      '#Up it went… and down it came…',
      'and {N} laughed and laughed until the butterflies joined in.',
    ],
    ground(g) { gardenGround(g, 21); pathStones(g, [[1.9, 5.1, 1], [2.05, 4.7, .9], [1.85, 4.3, 1], [2.0, 3.9, .9], [1.9, 3.5, .8]]); cut(g, '#c7e8a8', g => { ell(g, .7, 3.4, .5, .25); ell(g, 3.3, 3.6, .5, .25); }, { shadow: false }); [[.6, 3.3], [.8, 3.45], [3.2, 3.5], [3.4, 3.65]].forEach(([x, y]) => rose(g, x, y, .05)); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { sun: [3.15, .55, .24], paint: g => { cut(g, '#b5dc96', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .65); }); castleDay(g, 1.0, h - .45, .52); } }); },
        props: [0, 1].map(i => ({ id: 'cl' + i, x: 0, y: 2.0 + i * .38, w: .9, h: .38, basic: true, opacity: .9, dz: .015, draw(g) { cloud2(g, .14, .24, 1.05); } })) },
      { z: -1.35, rise: 'grow', x: 2, w: 3.8, h: 2.05, draw(g, w, h) {
        hedge(g, 0, 1.35, h, .95, true, 7); hedge(g, 2.45, 3.8, h, .95, true, 8);
        stroke(g, '#8a6a4a', .07, g => { g.moveTo(1.38, h); g.lineTo(1.38, h - 1.3); g.quadraticCurveTo(1.9, h - 2.15, 2.42, h - 1.3); g.lineTo(2.42, h); });
        for (let i = 0; i <= 16; i++) { const t = i / 16, x = (1 - t) * (1 - t) * 1.38 + 2 * t * (1 - t) * 1.9 + t * t * 2.42, y = (1 - t) * (1 - t) * (h - 1.3) + 2 * t * (1 - t) * (h - 2.15) + t * t * (h - 1.3); cut(g, G.hedge, g => circ(g, x + (i % 2 ? .04 : -.04), y, .07), { blur: 3, oy: 1 }); if (i % 2 === 0) rose(g, x, y - .03, .045, i % 4 ? G.rose : G.rose2); }
      } },
      { z: -0.35, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'zainab', x: -.15, y: 0, w: 1.1, h: 2.0, tap: true, draw(g, w, h) { princess(g, w / 2, h, 1.08, { noScarf: true }); } },
        { id: 'ball', x: -.15, y: 1.0, w: .32, h: .32, py: .5, dz: .05, tap: true, basic: true, draw(g, w, h) { ballArt(g, w, h); } },
      ] },
      { z: .5, rise: 'drop', x: 2, w: 3.8, h: .65, draw(g, w, h) { bank(g, 0, 1.2, h, .32, 5); bank(g, 2.6, 3.8, h, .32, 6); },
        props: [...['daisy', 'bell', 'crocus', 'daisy', 'bell', 'crocus'].map((k, i) => ({ id: 'fl' + i, x: (i < 3 ? -1.65 : .95) + (i % 3) * .3, y: .12, w: .3, h: .42, dz: .01, draw(g, w, h) { flower(g, w, h, k); } })),
          ...['#ff9cc0', '#9fd0ff', '#ffd27a'].map((c, i) => ({ id: 'bf' + i, x: -1 + i, y: 1.0, w: .26, h: .2, py: .5, dz: .05 + i * .003, draw(g, w, h) { butterflyArt(g, w, h, c); } }))] },
      { z: 1.4, x: 2, w: 3.9, h: .5, draw(g, w, h) { bank(g, 0, 1.1, h, .28, 7); bank(g, 2.8, 3.9, h, .3, 8); },
        props: [{ id: 'peek', x: 1.35, y: -.16, w: .5, h: .45, dz: -.012, tap: true, draw(g, w, h) { frogArt(g, w / 2, h, .55); } }] },
    ],
    setup(o) { o.bg = glow('#ffcf4a', .9, .7); o.bg.position.set(0, 0, .02); o.ball.grp.add(o.bg); },
    lamp: o => ({ obj: o.ball.grp, at: [0, 0, .3], i: 1.2 }),
    reset(o) { o._throw = false; o.ball.grp.position.y = 1.0; },
    async intro(o) { bubble('“Up it goes!”', o.zainab, 2.0, 1800); },
    tick(o, t, dt) {
      for (let i = 0; i < 2; i++) { const c = o['cl' + i], ph = (t * .03 + i * .5) % 1; c.grp.position.x = lerp(-1.45, 1.45, ph); c.mesh.material.opacity = .9 * Math.sin(ph * Math.PI); }
      for (let i = 0; i < 3; i++) { const b = o['bf' + i]; b.grp.position.set(Math.sin(t * .4 + i * 2.1) * 1.5, .9 + Math.sin(t * .9 + i) * .35 + i * .12, .05 + i * .003); b.grp.scale.x = .2 + .8 * Math.abs(Math.sin(t * 13 + i)); b.grp.rotation.z = Math.sin(t * 1.3 + i) * .3; }
      for (let i = 0; i < 6; i++) o['fl' + i].grp.rotation.z = Math.sin(t * 1.4 + i) * .09;
      if (!o._peek) o.peek.grp.position.y = -.16 + Math.max(0, Math.sin(t * .8)) * .12;
      o.bg.material.opacity = .55 + .2 * Math.sin(t * 4);
      if (!o._throw) { const q = Math.abs(Math.sin(t * 2.1)); o.ball.grp.position.y = .95 + q * 1.15; o.ball.grp.rotation.z = t * 2; if (Math.random() < dt * 6) spark(wpos(o.ball.grp, 0, 0, .05), '#ffe7a8', (Math.random() - .5) * .1, -.1, 0, .8); }
    },
    async action(o, id) {
      if (id === 'peek') { o._peek = true; sfx.ribbit(); bubble('“Ribbit?”', o.peek, .5, 1600); await tween(.45, p => { o.peek.grp.position.y = -.16 + Math.sin(p * Math.PI) * .3; }); o._peek = false; return; }
      if (id === 'zainab') { bubble('“Watch this!”', o.zainab, 2.0, 1500); }
      o._throw = true; sfx.whoosh(); const y0 = o.ball.grp.position.y;
      bubble('“Up, up, UP!”', o.zainab, 2.0, 1800);
      await tween(1.0, p => { o.ball.grp.position.y = lerp(y0, 3.3, p); o.ball.grp.rotation.z += .25; spark(wpos(o.ball.grp, 0, 0, .05), ['#ffe7a8', '#ffcf4a', '#fff'][Math.floor(Math.random() * 3)], (Math.random() - .5) * .3, -.2, 0, 1.1); }, E.out);
      burstAt(o.ball.grp, [0, 0, .05], '#ffe7a8', 50, 1.4, .09, 1.4); sfx.sparkle(); await wait(250);
      await tween(.85, p => { o.ball.grp.position.y = lerp(3.3, 1.0, p); o.ball.grp.rotation.z -= .2; }, E.in);
      sfx.chime([784, 988, 1175]); burstAt(o.ball.grp, [0, 0, .05], '#ffcf4a', 40, 1.0, .08, 1.0); bubble('“Got it!”', o.zainab, 2.0, 1500);
      o._throw = false;
    },
  },
  {
    numeral: 'II', title: 'Splash!', page: 3, mood: 'day', snow: .25, fall: '#ffc6da',
    shot: { pitch: .74, zoom: .9, ty: 1.0, sway: .06 },
    hint: 'Throw it higher than ever', button: o => o._sunk ? 'Throw it again' : 'Throw it higher!',
    paras: [
      'One day, she threw the ball higher than ever before. It touched the top of the willow tree, bounced off a branch… and rolled, bump, bump, bump, all the way down to the old green pond.',
      '#SPLASH!',
      'The golden ball sank down, down, down, until it was only a glimmer far below. {N} ran to the edge of the water, and a tear rolled down her cheek.',
      '“My ball,” she whispered. “My beautiful golden ball.”',
    ],
    ground(g) { gardenGround(g, 31); pond(g, 2.0, 3.55, 1.25, .75); lilyPad(g, 1.3, 3.35, .18, .11, .4); lilyPad(g, 2.75, 3.95, .2, .12, 2.2, true); lilyPad(g, 2.55, 3.05, .14, .09, 1.2); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { sun: [.6, .5, .22], paint: g => { cut(g, '#b5dc96', g => { ell(g, 1.0, h, 1.6, .55); ell(g, 3.2, h, 1.4, .7); }); castleDay(g, 3.0, h - .5, .5); cloud2(g, 1.6, .7, 1.1); cloud2(g, 2.8, .45, .8); } }); } },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 2.45, draw(g, w, h) { hedge(g, 2.3, 3.8, h, .8, true, 12); willow(g, .95, h, 1.28); } },
      { z: -0.2, rise: 'swing', dir: -1, x: 2, w: 3.8, h: 1.2, draw(g, w, h) { reeds(g, .25, h, 1.4); reeds(g, 3.6, h, 1.1, 4); },
        props: [
          { id: 'zainab', x: 1.0, y: 0, w: 1.1, h: 1.9, tap: true, draw(g, w, h) { princess(g, w / 2, h, 1.0, { noScarf: true }); } },
          { id: 'tear', x: 1.095, y: 1.2, w: .05, h: .08, basic: true, opacity: 0, dz: .03, draw(g, w, h) { tearArt(g, w, h); } },
        ] },
      { z: 1.5, rise: 'drop', x: 2, w: 3.9, h: .55, draw(g, w, h) { bank(g, 0, .85, h, .3, 9); bank(g, 3.05, 3.9, h, .3, 10); reeds(g, .5, h, .8); reeds(g, 3.4, h, .7, 4); },
        props: [{ id: 'fly', x: 0, y: 1.0, w: .3, h: .22, py: .5, dz: .2, draw(g, w, h) { dragonflyArt(g, w, h); } }] },
    ],
    setup(o, sp) {
      o.sheen = waterSheen(1.2, .72); o.sheen.position.set(2.0, Y0 + .012, .85); sp.fx.add(o.sheen);
      loose(sp, 'ball', .3, .3, ballArt, { py: .5, basic: true }); o.bgl = glow('#ffcf4a', .8, .7); o.ball.grp.add(o.bgl);
      o.glim = glow('#ffcf4a', .9, 0); o.glim.position.set(2.1, Y0 + .03, .9); sp.fx.add(o.glim);
    },
    lamp: o => ({ obj: o.zainab.grp, at: [0, 1.6, .6], i: 0 }),
    reset(o) { o._sunk = false; o._sad = false; o.ball.grp.visible = true; o.ball.grp.position.set(3.0, Y0 + .66, -.12); o.ball.mesh.material.opacity = 1; o.bgl.material.opacity = .7; o.ball.grp.scale.setScalar(1); o.glim.material.opacity = 0; o.tear.mesh.material.opacity = 0; },
    tick(o, t, dt) {
      o.sheen.material.uniforms.uTime.value = t;
      o.fly.grp.position.set(Math.sin(t * .5) * 1.4, .9 + Math.sin(t * 1.7) * .2, .2); o.fly.grp.scale.x = Math.sign(Math.cos(t * .5)) || 1;
      if (o._sunk) { o.glim.material.opacity = .35 + .25 * Math.sin(t * 2.5); o.glim.scale.setScalar(.7 + .2 * Math.sin(t * 2.5)); if (Math.random() < dt * 2) ripple(SP[2], 2.1, .9, .35, 1.6); }
      if (o._sad) { const ph = (t * .45) % 1; o.tear.grp.position.y = 1.2 - ph * .2; o.tear.mesh.material.opacity = Math.sin(ph * Math.PI) * .95; }
    },
    async action(o, id) {
      if (id === 'zainab' && o._sunk) { bubble('“My beautiful golden ball…”', o.zainab, 1.9, 2000); return; }
      const b = o.ball.grp, sp = SP[2]; this.reset(o); o.tear.mesh.material.opacity = 0;
      bubble('“Higher than ever!”', o.zainab, 1.9, 1400); sfx.whoosh();
      await tween(.75, p => { b.position.set(lerp(3.0, 2.2, p), Y0 + .66 + Math.sin(p * Math.PI * .5) * 2.6, lerp(-.12, -.9, p)); b.rotation.z += .3; }, E.out);
      await tween(.45, p => { b.position.set(lerp(2.2, 1.25, p), Y0 + lerp(3.26, 2.25, E.in(p)), lerp(-.9, -1.3, p)); b.rotation.z += .3; });
      sfx.rustle(); burstAt(b, [0, 0, .05], '#86c46a', 40, 1.1, .07, 1.2, -1.2);
      const pts = [[1.25, 2.25, -1.3], [1.2, .15, -.6], [1.5, .15, -.15], [1.75, .15, .3], [2.05, .05, .78]], hs = [.35, .45, .25, .15];
      for (let i = 0; i < 4; i++) { const a = pts[i], c = pts[i + 1]; await tween(i ? .42 - i * .05 : .6, p => { b.position.set(lerp(a[0], c[0], p), Y0 + (i ? lerp(a[1], c[1], p) + Math.sin(p * Math.PI) * hs[i] : lerp(a[1], c[1], E.in(p))), lerp(a[2], c[2], p)); b.rotation.z -= .25; }); if (i < 3) { sfx.pop(.8 + i * .1); spark(b.position.clone().add(new THREE.Vector3(0, -.12, 0)), '#ffffff', 0, .2, 0, .5); } }
      sfx.splash(); bubble('SPLASH!', o.ball, .35, 1300);
      burst(new THREE.Vector3(2.05, Y0 + .1, .78), '#cfefff', 70, 2.1, .08, 1.1, -3.2); burst(new THREE.Vector3(2.05, Y0 + .1, .78), '#ffffff', 30, 1.4, .06, .9, -3);
      ripple(sp, 2.05, .78, .55); setTimeout(() => ripple(sp, 2.05, .78, .85, 1.6), 250); setTimeout(() => ripple(sp, 2.05, .78, 1.1, 1.8), 520);
      await tween(1.6, p => { b.position.y = Y0 + lerp(.05, -.12, p); b.position.x = lerp(2.05, 2.1, p); b.position.z = lerp(.78, .9, p); o.ball.mesh.material.opacity = 1 - p; o.bgl.material.opacity = .7 * (1 - p); b.scale.setScalar(lerp(1, .55, p)); if (Math.random() < .3) spark(new THREE.Vector3(2.08 + (Math.random() - .5) * .1, Y0 + .05, .85), '#e8fbff', 0, .3, 0, .6); });
      b.visible = false; o._sunk = true;
      await wait(300); o._sad = true; bubble('“My ball… my beautiful golden ball.”', o.zainab, 1.9, 2600);
    },
  },
  {
    numeral: 'III', title: 'The Frog in the Pond', page: 5, mood: 'day', snow: .25, fall: '#ffc6da',
    shot: { pitch: .72, zoom: .88, ty: .95, sway: .07 },
    hint: 'Tap the little frog', button: () => 'Say hello to the frog',
    paras: [
      '“Why are you crying, {TN}?” croaked a small voice.',
      '{N} looked down. There, on a lily pad, sat a little green frog. He wore a tiny golden crown and a blue spotted bow tie, and he had the kindest eyes she had ever seen.',
      '“I can dive to the very bottom of the pond,” said the frog. “My name is {G}. Shall I fetch your ball for you?”',
    ],
    ground(g) { gardenGround(g, 31); pond(g, 2.0, 3.55, 1.25, .75); pondPads.forEach(([x, z], i) => lilyPad(g, x, z + 2.7, .2, .12, i * 1.3 + .3, i > 1)); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { sun: [.7, .55, .2], paint: g => { cut(g, '#b5dc96', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .55); }); castleDay(g, 1.3, h - .45, .45); cloud2(g, 2.3, .6, 1.0); } }); } },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 2.45, draw(g, w, h) { hedge(g, 0, 1.6, h, .85, true, 15); willow(g, 3.0, h, 1.25); } },
      { z: -0.35, rise: 'swing', dir: 1, x: 2, w: 3.8, h: 1.1, draw(g, w, h) { reeds(g, 3.55, h, 1.3); },
        props: [{ id: 'zainab', x: -1.05, y: 0, w: 1.1, h: 1.9, tap: true, draw(g, w, h) { princess(g, w / 2, h, 1.0, { noScarf: true }); } }] },
      { z: 1.55, rise: 'drop', x: 2, w: 3.9, h: .5, draw(g, w, h) { bank(g, 0, .8, h, .3, 11); bank(g, 3.1, 3.9, h, .3, 12); },
        props: [0, 1, 2].map(i => ({ id: 'ct' + i, x: (i ? 1.45 : -1.6) + i * .12, y: .1, w: .3, h: .75, dz: .01, draw(g, w, h) { reeds(g, w / 2, h, .9, 3); } })) },
    ],
    setup(o, sp) {
      o.sheen = waterSheen(1.2, .72); o.sheen.position.set(2.0, Y0 + .012, .85); sp.fx.add(o.sheen);
      o.glim = glow('#ffcf4a', .8, .4); o.glim.position.set(2.35, Y0 + .03, .95); sp.fx.add(o.glim);
      loose(sp, 'frog', .7, .7, (g, w, h) => frogArt(g, w / 2, h, .82), { tap: true });
      o.sac = new THREE.Mesh(new THREE.CircleGeometry(.07, 24), new THREE.MeshBasicMaterial({ color: '#f1f8cf', transparent: true, opacity: .95 })); o.sac.position.set(0, .26, .01); o.frog.grp.add(o.sac);
      [0, 1].forEach(i => loose(sp, 'df' + i, .3, .22, dragonflyArt, { py: .5 }));
    },
    lamp: o => ({ obj: o.frog.grp, at: [0, .4, .4], i: 0 }),
    reset(o) { o._busy = false; o.frog.grp.position.set(2.0, Y0, .42); o.frog.grp.rotation.set(0, 0, 0); o.sac.scale.setScalar(.01); },
    async intro(o) { o._busy = true; sfx.ribbit(); bubble('“Why are you crying, {TN}?”', o.frog, .7, 2600); await tween(.7, p => o.sac.scale.setScalar(.01 + Math.sin(p * Math.PI) * 1.2)); o._busy = false; },
    tick(o, t, dt) {
      o.sheen.material.uniforms.uTime.value = t; o.glim.material.opacity = .3 + .2 * Math.sin(t * 2.3);
      if (!o._busy) { const ph = t % 3.2; o.sac.scale.setScalar(ph < .5 ? .01 + Math.sin(ph / .5 * Math.PI) * 1.1 : .01); o.frog.grp.scale.y = 1 + .03 * Math.sin(t * 3); }
      for (let i = 0; i < 2; i++) { const d = o['df' + i]; d.grp.position.set(2 + Math.sin(t * .45 + i * 3) * 1.3, Y0 + .7 + i * .25 + Math.sin(t * 1.6 + i) * .15, .5 + Math.cos(t * .35 + i) * .5); d.grp.rotation.z = Math.sin(t * 2 + i) * .15; }
      for (let i = 0; i < 3; i++) o['ct' + i].grp.rotation.z = Math.sin(t * 1.1 + i * .7) * .07;
    },
    async action(o, id) {
      if (id === 'zainab') { bubble('“A frog… with a crown?”', o.zainab, 1.9, 2000); return; }
      o._busy = true; const f = o.frog, sp = SP[3], route = [1, 2, 3, 0, 1];
      for (let i = 0; i < route.length - 1; i++) {
        const a = pondPads[route[i]], b = pondPads[route[i + 1]];
        sfx.ribbit(); await hop(f, [a[0], Y0, a[1]], [b[0], Y0, b[1]], .5, .55, i % 2 ? .25 : -.25);
        sfx.plip(); ripple(sp, b[0], b[1], .35, 1.0);
      }
      sfx.ribbit(); await tween(.5, p => o.sac.scale.setScalar(.01 + Math.sin(p * Math.PI) * 1.3));
      bubble('“I’m {G}. Shall I fetch your ball?”', f, .7, 2800); o._busy = false;
    },
  },
  {
    numeral: 'IV', title: 'Down to the Bottom', page: 7, mood: 'deep', snow: .6, fall: '#dff8ff', up: true,
    shot: { pitch: .46, zoom: .86, ty: 1.35, sway: .05 },
    hint: 'Tap the fish, or help the frog dive', button: o => o._got ? 'Dive again' : 'Dive for the ball',
    paras: [
      'Plip! The frog dived into the pond. Down he swam, past the lily roots, past the sleepy fish, past the silver bubbles, all the way to the bottom, where something golden was glowing in the dark.',
      'He wrapped his little green arms around the ball. It was almost as big as he was! But he kicked, and kicked, and kicked…',
      '#and up, up, up he came.',
    ],
    ground(g) {
      g.fillStyle = '#d8c28a'; g.fillRect(0, 0, W, D); const r = rng(41);
      stroke(g, 'rgba(255,255,255,.28)', .02, g => { for (let i = 0; i < 26; i++) { const x = r() * W, y = r() * D; g.moveTo(x, y); g.quadraticCurveTo(x + .2, y - .1, x + .4, y + .02); } }, false);
      for (let i = 0; i < 40; i++) dots(g, ['#b8a070', '#efe1b8', '#a8c8c0'][i % 3], [[r() * W, r() * D]], .03 + r() * .03);
      cut(g, '#ff9f8a', g => { for (let i = 0; i < 5; i++) { const a = i / 5 * Math.PI * 2 - Math.PI / 2; g.moveTo(3.2, 4.5); g.lineTo(3.2 + Math.cos(a) * .14, 4.5 + Math.sin(a) * .14); g.lineTo(3.2 + Math.cos(a + .63) * .05, 4.5 + Math.sin(a + .63) * .05); } }, { blur: 3, oy: 1 });
    },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { backdrop(g, w, h, [[0, '#9be6f2'], [.12, '#4fb3cc'], [.5, '#2a7f9c'], [1, '#123f58']], g => {
          cut(g, 'rgba(255,255,255,.1)', g => { for (let i = 0; i < 5; i++) { const x = .3 + i * .8; poly(g, [x, 0, x + .25, 0, x + .9, h, x + .45, h]); } }, { shadow: false });
          stroke(g, '#2f6f4a', .025, g => { [.6, 1.85, 3.1].forEach(x => { g.moveTo(x, .32); g.bezierCurveTo(x + .15, 1.0, x - .15, 1.8, x + .05, h); }); }, false);
          cut(g, '#2f7a4a', g => { [.6, 1.85, 3.1].forEach(x => ell(g, x, .3, .32, .06)); }, { blur: 4, oy: 2 });
          stroke(g, 'rgba(255,255,255,.55)', .02, g => { g.moveTo(0, .24); for (let x = 0; x <= w; x += .2) g.quadraticCurveTo(x + .1, .2, x + .2, .24); }, false);
          dots(g, 'rgba(255,255,255,.35)', Array.from({ length: 30 }, (_, i) => [(i * 0.137 % 1) * w, .5 + ((i * 0.619) % 1) * (h - .7)]), .02);
        }); }, props: [{ id: 'shafts', x: 0, y: .2, w: 3.6, h: 2.6, basic: true, opacity: .5, dz: .01, draw(g, w, h) { cut(g, 'rgba(220,250,255,.35)', g => { for (let i = 0; i < 4; i++) { const x = .4 + i * .9; poly(g, [x, 0, x + .18, 0, x + .7, h, x + .35, h]); } }, { shadow: false }); } }] },
      { z: -1.6, rise: 'grow', x: 2, w: 3.8, h: 1.6, draw(g, w, h) { cut(g, '#1f5f6a', g => { ell(g, .5, h, .7, .5); ell(g, 3.3, h, .8, .6); ell(g, 1.9, h + .1, .5, .3); }); [[.3, 1.3], [.8, 1.1], [3.0, 1.4], [3.5, 1.0], [2.1, .8]].forEach(([x, s]) => stroke(g, '#2a7468', .06, g => { g.moveTo(x, h); g.quadraticCurveTo(x + .2, h - s * .5, x - .05, h - s); }, false)); } },
      { z: -0.9, rise: 'grow', x: 2, w: 3.8, h: .4, draw(g, w, h) { cut(g, '#3a7f7a', g => { ell(g, .6, h, .6, .3); ell(g, 3.2, h, .7, .32); }); },
        props: [...[[-1.6, 1.5, '#3f9a5a'], [-1.25, 1.1, '#4fae6a'], [-.75, 1.7, '#3a8a5a'], [1.2, 1.3, '#4fae6a'], [1.6, 1.8, '#3f9a5a']].map(([x, hh, c], i) => ({ id: 'sw' + i, x, y: 0, w: .3, h: hh, dz: .01 + i * .002, draw(g, w, h) { weedArt(g, w, h, c); } })),
          ...[['#ff9f5a', .32], ['#ffd25a', .26], ['#ff7aa2', .3]].map(([c, s], i) => ({ id: 'fish' + i, x: -1 + i, y: .7 + i * .4, w: s * 1.6, h: s, py: .5, dz: .06 + i * .01, tap: true, draw(g, w, h) { fishArt(g, w, h, c); } }))] },
      { z: -0.1, rise: 'drop', x: 2, w: 3.8, h: .6, draw(g, w, h) { cut(g, '#e2cd97', g => ell(g, 2.3, h, 1.2, .38)); cut(g, '#8a9a9a', g => { ell(g, 1.3, h - .05, .2, .14); ell(g, 3.2, h - .05, .26, .18); ell(g, 3.5, h, .14, .1); }); cut(g, '#f6d9e6', g => { g.moveTo(1.85, h - .02); g.lineTo(1.75, h - .16); g.quadraticCurveTo(1.85, h - .26, 1.95, h - .16); g.closePath(); }, { blur: 3, oy: 1 }); } },
      { z: 1.3, x: 2, w: 3.9, h: 1.0, draw(g, w, h) { cut(g, '#2f6a6a', g => { ell(g, .3, h, .55, .35); ell(g, 3.6, h, .6, .4); }); [[.2, .9, '#3f9a5a'], [.5, .7, '#ff8f7a'], [3.4, .95, '#4fae6a'], [3.7, .75, '#ff9fbf']].forEach(([x, s, c]) => stroke(g, c, .07, g => { g.moveTo(x, h); g.quadraticCurveTo(x + .15, h - s * .5, x, h - s); g.moveTo(x, h - s * .5); g.quadraticCurveTo(x - .15, h - s * .7, x - .12, h - s * .85); }, false)); } },
    ],
    setup(o, sp) {
      loose(sp, 'ball', .32, .32, ballArt, { py: .5 }); o.bgl = glow('#ffcf4a', .8, .6); o.ball.grp.add(o.bgl);
      loose(sp, 'frog', .7, .95, (g, w, h) => frogArt(g, w / 2, h - .25, .85, 'leap'), { py: .4, tap: true });
    },
    lamp: o => ({ obj: o.ball.grp, at: [0, .1, .3], i: 1.3 }),
    reset(o) { o._got = false; o._dive = false; o.ball.grp.position.set(2.35, Y0 + .3, .05); o.ball.grp.scale.setScalar(1); o.frog.grp.position.set(1.3, Y0 + 2.45, .35); o.frog.grp.rotation.set(0, 0, 0); o.frog.grp.scale.setScalar(1); o.fishD = [0, 0, 0]; },
    async intro(o) { bubble('“Hold your breath… here I go!”', o.frog, .75, 2200); },
    tick(o, t, dt) {
      o.shafts.mesh.material.opacity = .35 + .2 * Math.sin(t * .7);
      for (let i = 0; i < 5; i++) o['sw' + i].grp.rotation.z = Math.sin(t * 1.1 + i * .9) * .12;
      for (let i = 0; i < 3; i++) { const f = o['fish' + i], sp = .12 + i * .04, dash = o.fishD[i] = Math.max(0, (o.fishD[i] || 0) - dt), ph = ((t * sp + i * .37 + (f.extra || 0)) % 1); if (dash > 0) f.extra = (f.extra || 0) + dt * 1.5; f.grp.position.x = lerp(-1.9, 1.9, ph); f.grp.position.y = .6 + i * .45 + Math.sin(t * 1.2 + i * 2) * .08; f.grp.scale.x = -1; f.grp.rotation.z = Math.sin(t * 5 + i) * .05; }
      if (!o._dive) { o.frog.grp.position.y = Y0 + 2.45 + Math.sin(t * 1.6) * .05; o.frog.grp.rotation.z = Math.sin(t * 1.1) * .08; }
      o.bgl.material.opacity = .45 + .2 * Math.sin(t * 2.2); o.bgl.scale.setScalar(.75 + .12 * Math.sin(t * 2.2));
      if (Math.random() < dt * 3) { const k = Math.floor(Math.random() * 5); spark(wpos(o['sw' + k].grp, 0, .4 + Math.random() * .8, .05), '#e8fbff', 0, .35, 0, 2.2); }
    },
    async action(o, id) {
      if (id && id.startsWith('fish')) { const i = +id.slice(4); o.fishD[i] = .7; sfx.plip(); burstAt(o[id].grp, [0, 0, .05], '#e8fbff', 16, .6, .05, .8, .4); return; }
      if (id === 'frog' && o._dive) return;
      this.reset(o); o._dive = true; const f = o.frog.grp, b = o.ball.grp;
      sfx.plip(); burstAt(f, [0, .3, .05], '#e8fbff', 26, .8, .05, .9, .5);
      const path = [[1.3, 2.45, .35], [1.05, 1.7, .3], [1.75, 1.1, .2], [2.0, .62, .12]];
      await tween(2.2, p => { const s = p * (path.length - 1), i = clamp(Math.floor(s), 0, path.length - 2), q = E.inOut(s - i), a = path[i], c = path[i + 1]; f.position.set(lerp(a[0], c[0], q), Y0 + lerp(a[1], c[1], q), lerp(a[2], c[2], q)); f.rotation.z = lerp(0, Math.PI * .85, Math.min(1, p * 4)) + Math.sin(p * 20) * .1; if (Math.random() < .4) spark(wpos(f, 0, .2, .05), '#e8fbff', (Math.random() - .5) * .1, .4, 0, 1.6); for (let k = 0; k < 3; k++) if (Math.abs(o['fish' + k].grp.position.x + 2 - f.position.x) < .4) o.fishD[k] = .5; });
      await tween(.45, p => { f.rotation.z = lerp(Math.PI * .85, 0, p); f.position.set(lerp(2.0, 2.35, p), Y0 + lerp(.62, .5, p), lerp(.12, .1, p)); });
      sfx.chime([659, 880, 1175]); burstAt(b, [0, 0, .05], '#ffcf4a', 60, 1.2, .08, 1.2, .2); bubble('“Got it!”', o.frog, .75, 1400); o._got = true;
      await wait(400); sfx.whoosh();
      await tween(1.9, p => { const y = lerp(.5, 2.6, E.inOut(p)), x = 2.35 + Math.sin(p * 9) * .08; f.position.set(x, Y0 + y, .1); b.position.set(x, Y0 + y + .48, .12); f.rotation.z = Math.sin(p * 16) * .12; if (Math.random() < .5) spark(wpos(f, 0, -.1, .05), '#e8fbff', (Math.random() - .5) * .2, .5, 0, 1.3); });
      burstAt(b, [0, .2, .05], '#ffffff', 40, 1.3, .07, 1.0, -1); sfx.splash();
      await tween(.35, p => { f.scale.setScalar(Math.max(.001, 1 - p)); b.scale.setScalar(Math.max(.001, 1 - p)); });
      o._dive = false; await wait(900);
      o.frog.grp.position.set(1.3, Y0 + 2.45, .35); f.rotation.z = 0; o.ball.grp.position.set(2.35, Y0 + .3, .05);
      await tween(.4, p => { f.scale.setScalar(Math.max(.001, p)); b.scale.setScalar(Math.max(.001, p)); }, E.back);
    },
  },
  {
    numeral: 'V', title: 'The Kindest Magic', page: 9, mood: 'dawn', snow: .35, fall: '#ffe6a0', up: true,
    shot: { pitch: .6, zoom: .88, ty: 1.15, sway: .07 },
    hint: 'Tap {N} to make the magic', button: o => o._prince ? 'Make the magic again' : 'Make the magic',
    paras: [
      'Splash! Up popped the frog, holding the golden ball high. {N} clapped her hands and laughed so happily that even the roses turned to look.',
      '“Thank you, {G}!” she cried. “You are the kindest friend in all the kingdom.” And because she was a true queen, with a heart full of kindness, a little magic began to sparkle in her crown.',
      'She smiled at the little frog and wished, with all her heart, that everyone could see him the way she did. The air began to shimmer. The frog began to glow. And then…',
      '#…there stood {G}, a kind young man in a fine blue suit, smiling the very same smile.',
    ],
    ground(g) { gardenGround(g, 51); pond(g, 3.25, 4.55, .75, .42, 7); lilyPad(g, 3.0, 4.6, .16, .1, 1, true); pathStones(g, [[1.4, 4.9, 1], [1.6, 4.4, .9], [1.5, 3.9, .9]]); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { stops: [[0, '#6a64b8'], [.5, '#f0a0a8'], [1, '#ffd59a']], sun: [1.9, 2.25, .38], stars: 12, seed: 9, paint: g => { cut(g, '#c98aa0', g => { ell(g, .6, h, 1.3, .55); ell(g, 3.3, h, 1.3, .5); }); castleDay(g, 3.15, h - .4, .45); } }); } },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 1.3, draw(g, w, h) { hedge(g, 0, 1.45, h, 1.05, true, 21); hedge(g, 2.35, 3.8, h, 1.05, true, 22); } },
      { z: -0.85, rise: 'slide', dir: -1, x: 2, w: 3.8, h: .1, draw: null, props: [-1.7, -1.25, -.8, .9, 1.35, 1.75].map((x, i) => ({ id: 'ro' + i, x, y: 0, w: .32, h: .7, dz: .01, draw(g, w, h) { roseBush(g, w, h); } })) },
      { z: 0.2, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'zainab', x: -.75, y: 0, w: 1.1, h: 2.0, tap: true, draw(g, w, h) { princess(g, w / 2, h, 1.05, { noScarf: true }); } },
        { id: 'frog', x: .75, y: 0, w: .75, h: .8, tap: true, draw(g, w, h) { frogArt(g, w / 2, h - .02, .95, 'sit', { armsUp: true }); } },
        { id: 'ball', x: .75, y: .86, w: .28, h: .28, py: .5, dz: .03, basic: true, draw(g, w, h) { ballArt(g, w, h); } },
        { id: 'sham', x: .75, y: 0, w: 1.0, h: 2.35, tap: true, dz: .02, draw(g, w, h) { prince(g, .45, h - .02, .95); } },
      ] },
      { z: 1.4, rise: 'drop', x: 2, w: 3.9, h: .55, draw(g, w, h) { bank(g, 0, 1.2, h, .3, 13); bank(g, 3.0, 3.9, h, .25, 14); } },
    ],
    setup(o, sp) {
      o.cg = glow('#ffe39a', .4, 0); o.cg.position.set(0, 1.72, .05); o.zainab.grp.add(o.cg);
      o.fg = glow('#b8ff9a', .9, 0); o.fg.position.set(0, .4, .05); o.frog.grp.add(o.fg);
      o.bgl = glow('#ffcf4a', .7, .7); o.ball.grp.add(o.bgl);
      o.flash = glow('#fff6dc', 2.6, 0); o.flash.position.set(.75, .8, .3); sp.hinges[3].add(o.flash);
    },
    lamp: o => ({ obj: o.zainab.grp, at: [.4, 1.6, .5], i: 1.2 }),
    reset(o) { o._prince = false; o._held = false; o._busy = false; o.sham.grp.scale.setScalar(.001); o.sham.grp.visible = false; o.frog.grp.scale.setScalar(1); o.frog.grp.rotation.y = 0; o.frog.grp.visible = true; o.ball.grp.position.set(.75, .86, .03); o.ball.grp.visible = true; o.cg.material.opacity = 0; o.fg.material.opacity = 0; o.flash.material.opacity = 0; for (let i = 0; i < 6; i++) o['ro' + i].grp.rotation.z = 0; },
    async intro(o) { if (!o._prince) bubble('“Ribbit! Here is your ball!”', o.frog, .8, 2200); },
    tick(o, t, dt) {
      if (!o._busy) { if (o.ball.grp.visible && !o._held) o.ball.grp.position.y = .86 + Math.sin(t * 2.4) * .04; o.frog.grp.scale.y = o._prince ? o.frog.grp.scale.y : 1 + .03 * Math.sin(t * 3); }
      o.bgl.material.opacity = .55 + .2 * Math.sin(t * 3);
      if (o._prince) { o.sham.grp.rotation.z = Math.sin(t * 1.2) * .015; if (Math.random() < dt * 4) spark(wpos(o.sham.grp, (Math.random() - .5) * .6, .4 + Math.random() * 1.6, .1), '#ffe39a', 0, .2, 0, 1.4); }
      if (Math.random() < dt * 3) spark(wpos(o.zainab.grp, (Math.random() - .5) * .3, 1.72, .08), '#fff1c4', (Math.random() - .5) * .1, .25, 0, 1.0);
    },
    async action(o, id) {
      if (id === 'sham' && o._prince) { bubble('“Thank you, {TN}. Your kindness broke the spell.”', o.sham, 2.3, 2800); sfx.chime([659, 784, 988]); return; }
      if (id === 'frog' && !o._prince) { sfx.ribbit(); bubble('“Ribbit! Here is your ball!”', o.frog, .8, 1800); return; }
      o._busy = true; const sp = SP[5], z = o.zainab.grp, fr = o.frog.grp, sh = o.sham.grp, ball = o.ball.grp;
      if (o._prince) { await tween(.5, p => { sh.scale.setScalar(Math.max(.001, 1 - p)); }); sh.visible = false; fr.visible = true; ball.visible = true; ball.position.set(.75, .86, .03); await tween(.4, p => fr.scale.setScalar(Math.max(.001, p)), E.back); o._prince = false; o._held = false; for (let i = 0; i < 6; i++) o['ro' + i].grp.rotation.z = 0; }
      o._held = true; sfx.whoosh();
      await tween(.9, p => { ball.position.set(lerp(.75, -.75 + .3, p), lerp(.86, .7, p) + Math.sin(p * Math.PI) * .7, .03); ball.rotation.z -= .2; });
      sfx.chime([784, 988]); burstAt(ball, [0, 0, .05], '#ffcf4a', 30, .8, .07, .9);
      bubble('“Thank you, {G}!”', o.zainab, 2.0, 2000);
      tween(1.0, p => { for (let i = 0; i < 6; i++) o['ro' + i].grp.rotation.z = (i < 3 ? -1 : 1) * .35 * Math.sin(p * Math.PI * .5); }, E.back);
      await wait(900); sfx.wish();
      await tween(1.0, p => { o.cg.material.opacity = p; o.cg.scale.setScalar(.4 + p * .9); L.target = lerp(1.2, 4, p); });
      const a = wpos(z, 0, 1.72, .1), c = wpos(fr, 0, .4, .1);
      await tween(1.5, p => { for (let k = 0; k < 4; k++) { const q = clamp(p - k * .04, 0, 1), m = a.clone().lerp(c, q); m.y += Math.sin(q * Math.PI) * .9; const ang = q * 18 + k * 1.57, r = .14 * Math.sin(q * Math.PI); spark(new THREE.Vector3(m.x + Math.cos(ang) * r, m.y + Math.sin(ang) * r, m.z + Math.sin(ang) * r), ['#ffd27a', '#ff9cc0', '#bfe0ff', '#c9a6ff'][k], 0, .1, 0, 1.0); } o.fg.material.opacity = p * .9; o.fg.scale.setScalar(.9 + p * .8); });
      sfx.sparkle();
      await tween(1.0, p => { fr.rotation.y = p * Math.PI * 4; o.fg.scale.setScalar(1.7 + p * 1.5); o.flash.material.opacity = p; o.flash.scale.setScalar(1 + p * 2.2); if (Math.random() < .7) spark(wpos(fr, (Math.random() - .5) * .5, Math.random() * .8, .1), '#fff6dc', (Math.random() - .5) * .5, .5, (Math.random() - .5) * .3, 1.0); }, E.in);
      sfx.firework(); fr.visible = false; fr.rotation.y = 0;
      ['#ffd27a', '#ff8fb8', '#9fe3ff', '#c9a6ff'].forEach((col, i) => burstAt(o.flash.parent, [.75, .9 + i * .1, .3], col, 50, 1.8, .09, 1.6, -.3));
      sh.visible = true;
      await tween(1.0, p => { sh.scale.setScalar(Math.max(.001, E.back(p))); o.flash.material.opacity = 1 - p; o.flash.scale.setScalar(3.2 - p * 1.5); });
      o.fg.material.opacity = 0; o._prince = true; o._busy = false;
      burstAt(sh, [0, 1.4, .1], '#ff7aa2', 40, 1.2, .1, 1.4, -.2); sfx.chime([523, 659, 784, 1046]);
      bubble('“Your kindness broke the spell, {TN}!”', o.sham, 2.3, 3000);
      await tween(.8, p => { o.cg.material.opacity = 1 - p * .6; L.target = lerp(4, 1.6, p); });
    },
  },
  {
    numeral: 'VI', title: 'Happily Ever After', page: 11, mood: 'twilight', snow: .5, fall: '#efff9e', up: true, end: true,
    shot: { pitch: .62, zoom: .88, ty: 1.15, sway: .07 },
    hint: 'Tap the little frogs', button: () => 'Fireworks over the castle',
    paras: [
      'From that day on, {N} and {G} were the very best of friends. They played catch with the golden ball in the rose garden every afternoon, and fed the fish in the old green pond, and never once forgot the day a little frog was brave enough to dive to the bottom.',
      'And whenever {N} hears a “ribbit” down by the water, she smiles and waves, just in case.',
      '#Because kindness is the best magic of all.',
    ],
    ground(g) { gardenGround(g, 61); pond(g, .95, 4.1, .7, .38, 9); lilyPad(g, .8, 4.05, .14, .08, .5); lilyPad(g, 1.2, 4.2, .12, .07, 2, true); pathStones(g, [[2.2, 5.0, 1], [2.05, 4.55, .9], [2.25, 4.1, .9], [2.1, 3.65, .8]]); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { stops: [[0, '#1b2350'], [.6, '#5a4f93'], [1, '#e9a3b8']], stars: 60, seed: 71, paint: g => { moon(g, .7, .6, .2); cut(g, '#5a4f93', g => { ell(g, .9, h + .2, 1.5, .9); ell(g, 3.0, h + .2, 1.4, .7); }); } }); } },
      { z: -1.6, rise: 'grow', x: 3.0, w: 1.7, h: 2.0, draw(g, w, h) { castleDay(g, w / 2, h, .64); },
        props: [{ id: 'cw', x: 0, y: 0, w: 1.7, h: 2.0, basic: true, opacity: .9, dz: .006, draw(g, w, h) { castleWindows(g, w / 2, h, .64, '#ffd27a', 'rgba(255,200,100,1)'); } }] },
      { z: -.8, rise: 'swing', dir: 1, x: 2, w: 3.8, h: 1.05, draw(g, w, h) { hedge(g, 0, 1.25, h, .8, true, 31); hedge(g, 2.65, 3.8, h, .8, true, 32); withPal({ snow: '#ffe7a8' }, () => { lampPost(g, 1.38, h - .02, .5); lampPost(g, 2.52, h - .02, .5); }); },
        props: Array.from({ length: 6 }, (_, i) => ({ id: 'sl' + i, x: -1.2 + i * .48, y: .3, w: .16, h: .2, basic: true, dz: -.06, draw(g, w, h) { skyLanternArt(g, w, h); } })) },
      { z: -0.05, rise: 'swing', dir: -1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'sham', x: -.75, y: 0, w: 1.0, h: 2.35, tap: true, draw(g, w, h) { prince(g, .5, h - .02, .88); } },
        { id: 'zainab', x: .65, y: 0, w: 1.1, h: 1.9, tap: true, dz: .02, draw(g, w, h) { princess(g, w / 2, h, .95, { noScarf: true }); } },
        { id: 'ball', x: 0, y: 1.0, w: .26, h: .26, py: .5, dz: .06, basic: true, draw(g, w, h) { ballArt(g, w, h); } },
      ] },
      { z: 1.4, rise: 'drop', x: 2, w: 3.9, h: .9, draw(g, w, h) { bank(g, 0, 1.4, h, .35, 15); bank(g, 2.5, 3.9, h, .35, 16); },
        props: [{ id: 'end', x: -.05, y: .32, w: 1.6, h: .48, dz: .02, draw(g, w, h) { ribbon(g, w, h, TR('The End'), .28, '#3f8a5a'); } },
          { id: 'fr0', x: -1.5, y: .28, w: .45, h: .45, tap: true, dz: .03, draw(g, w, h) { frogArt(g, w / 2, h, .5, 'sit', { crown: false, col: '#7fcf5f' }); } },
          { id: 'fr1', x: 1.5, y: .3, w: .45, h: .45, tap: true, dz: .03, draw(g, w, h) { frogArt(g, w / 2, h, .45, 'sit', { crown: false, col: '#5fb88a' }); } }] },
    ],
    setup(o, sp) {
      o.bgl = glow('#ffcf4a', .6, .7); o.ball.grp.add(o.bgl);
      o.sl = []; for (let i = 0; i < 6; i++) { const l = o['sl' + i]; l.gl = glow('#ffb04a', .45, .8); l.gl.position.set(0, .1, .01); l.grp.add(l.gl); l.ph = i / 6; o.sl.push(l); }
      o.A = [-.75 + .5 * 0 + .88 * .46 - .0, .9], o.B = [.65 - .27 * .95, .6];
    },
    lamp: o => ({ obj: o.ball.grp, at: [0, 0, .3], i: 1.6 }),
    reset(o) { o._boost = false; o._ph = 0; o._hop = [2, 3.5]; },
    async intro(o) { bubble('“Catch, {N}!”', o.sham, 2.3, 2000); },
    tick(o, t, dt) {
      o._ph = (o._ph + dt * (o._boost ? .9 : .55)) % 2; const p = o._ph < 1 ? o._ph : 2 - o._ph, q = E.inOut(p), hi = o._boost ? 1.9 : 1.05;
      o.ball.grp.position.set(lerp(o.A[0], o.B[0], q), lerp(o.A[1], o.B[1], q) + Math.sin(q * Math.PI) * hi, .06); o.ball.grp.rotation.z = -t * 3;
      if (Math.random() < dt * 8) spark(wpos(o.ball.grp, 0, 0, .05), '#ffe7a8', 0, -.05, 0, .6);
      o.sl.forEach((l, i) => { l.ph += dt * .05 * (o._boost ? 2.6 : 1); if (l.ph > 1) l.ph -= 1; const p = l.ph, a = Math.min(1, p * 6) * (1 - Math.max(0, (p - .75) / .25)); l.grp.position.set(l.P.x + Math.sin(t * .8 + i * 2) * .12, .3 + p * 2.6, -.06 - p * .6); l.mesh.material.opacity = a; l.gl.material.opacity = a * .8; });
      for (let k = 0; k < 2; k++) { o._hop[k] -= dt; const f = o['fr' + k]; if (o._hop[k] < 0) { o._hop[k] = 2.5 + Math.random() * 3; const y0 = f.P.y; tween(.45, p => { f.grp.position.y = y0 + Math.sin(p * Math.PI) * .25; }); sfx.ribbit(); } }
      if (Math.random() < dt * 5) spark(wpos(o.cw.grp, (Math.random() - .5) * 1.2, .4 + Math.random() * 1.4, .2), '#fff1c4', 0, .12, 0, 1.6);
    },
    async action(o, id) {
      if (id === 'sham') { bubble('“Catch, {TN}!”', o.sham, 2.3, 1800); return; }
      if (id === 'zainab') { bubble('“Got it! Your turn, {G}!”', o.zainab, 1.9, 2000); return; }
      if (id === 'fr0' || id === 'fr1') { const f = o[id], y0 = f.P.y; sfx.ribbit(); bubble('“Ribbit! Ribbit!”', f, .45, 1400); await tween(.5, p => { f.grp.position.y = y0 + Math.sin(p * Math.PI) * .4; f.grp.rotation.z = Math.sin(p * Math.PI * 2) * .3; }); return; }
      o._boost = true; sfx.wish();
      for (let i = 0; i < 4; i++) { sfx.firework(); burstAt(o.$h[1], [-.6 + i * .4, 2.3 + (i % 2) * .35, .2], ['#ffd27a', '#ff8fb8', '#9fe3ff', '#b8ff9a'][i], 70, 1.5, .1, 1.7); await wait(360); }
      shootingStar(o.$h[0], [1.6, 2.6, .12], [-.4, 2.1, .12]);
      bubble('“Happily ever after!”', o.zainab, 1.9, 2400); burstAt(o.zainab.grp, [0, 1.5, .1], '#ff7aa2', 30, 1.0, .09, 1.3, -.2);
      await wait(1800); o._boost = false;
    },
  },
];
