/* ================================================================== loose pieces that travel through the scene (the runners, the ducks, the boats) */
function loose(sp, id, w, h, draw, o = {}) {
  const [c, g] = layerCanvas(w, h); draw(g, w, h); if (!o.basic) grain(c);
  const m = paperMesh(c, w, h, o.px ?? .5, o.py ?? 0, o), grp = new THREE.Group(); grp.add(m); sp.fx.add(grp);
  const rec = { grp, mesh: m, P: { x: 0, y: 0, w, h } }; sp.o[id] = rec;
  if (o.tap) { m.userData = { spread: SP.indexOf(sp), id }; taps.push(m); }
  return rec;
}
function ripple(sp, x, z, s = .7, dur = 1.4, col = '#e8fbff') {
  const m = new THREE.Mesh(new THREE.RingGeometry(.86, 1, 40), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: .7, depthWrite: false }));
  m.rotation.x = -Math.PI / 2; m.position.set(x, Y0 + .014, z); m.scale.setScalar(.05); sp.fx.add(m);
  tween(dur, p => { m.scale.setScalar(.05 + s * p); m.material.opacity = .7 * (1 - p); }, E.out).then(() => { sp.fx.remove(m); m.geometry.dispose(); m.material.dispose(); });
}
const arc = (a, b, p, hgt) => [lerp(a[0], b[0], p), lerp(a[1], b[1], p) + Math.sin(p * Math.PI) * hgt, lerp(a[2], b[2], p)];
async function hop(rec, a, b, hgt, dur = .55, spin = 0) { await tween(dur, p => { rec.grp.position.set(...arc(a, b, p, hgt)); rec.grp.rotation.z = spin * Math.sin(p * Math.PI); }, E.inOut); }
function rainTick(sp, dt, pts, rate = 5) { wind = .55 + .25 * Math.sin(performance.now() / 1300); if (Math.random() < dt * rate) { const [x, z, r] = pts[Math.floor(Math.random() * pts.length)]; ripple(sp, x + (Math.random() - .5) * r, z + (Math.random() - .5) * r * .6, .14 + Math.random() * .1, .8); } }
function lightning(o, bolt) { sfx.thunder(); const h0 = moodNow.hi; if (bolt) tween(.5, p => { bolt.mesh.material.opacity = p < .15 ? 1 : p < .3 ? .2 : p < .45 ? 1 : 1 - p; }); return tween(.6, p => { hemi.intensity = h0 + 2.4 * (p < .2 ? 1 : 1 - p); }); }
function confetti(obj, at, n = 3) { ['#e2456f', '#ffcf4a', '#3d8fd8', '#5fbf6a', '#c9a6ff'].slice(0, n + 2).forEach((c, i) => burstAt(obj, [at[0] + (i - 2) * .15, at[1], at[2]], c, 40, 1.8, .08, 1.8, -1.4)); }
const run = (rec, x, z, t, k = 1, lean = .12) => { rec.grp.position.set(x, Y0 + Math.abs(Math.sin(t * 11 * k)) * .09, z); rec.grp.rotation.z = -lean + Math.sin(t * 11 * k) * .06; };
const zr = (g, w, h, k) => zainabRunner(g, w / 2, h, k), mr = (g, w, h, k) => mikaalRunner(g, w / 2, h, k);

/* ================================================================== the story (original text, written for this book) */
const SP = [
  {
    dedication: true, numeral: '', title: 'For {TN}', page: 'iii', mood: 'rain', snow: .7, fall: '#d6e9ff', rain: true,
    shot: { pitch: .72, zoom: .95, ty: 1.15, sway: .06 },
    async intro(o) { await tween(1.4, p => { if (!o._lit) o.win.mesh.material.opacity = lerp(.25, .6, p); }); },
    hint: 'Tap the castle', button: o => o._lit ? 'Rainbow sparkles' : 'Bring out the rainbow',
    get paras() { return ['Written by {G}', '§For {TN}', ...CFG.m.split('\n').map(l => '#' + l)]; },
    ground(g) { wetGround(g, 3); cut(g, '#c79a6a', g => { g.moveTo(1.75, D); g.bezierCurveTo(1.9, 4.2, 2.2, 3.4, 1.95, 2.3); g.lineTo(2.15, 2.3); g.bezierCurveTo(2.4, 3.4, 2.15, 4.2, 2.3, D); g.closePath(); }, { blur: 4, oy: 1 }); puddle(g, 3.0, 5.0, .45, .2); puddle(g, 1.0, 3.2, .35, .15); puddle(g, 2.6, 3.6, .25, .1); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { rainSky(g, w, h, { seed: 5, paint: g => { cut(g, '#6f8fa0', g => { ell(g, .7, h, 1.5, .7); ell(g, 3.2, h, 1.4, .6); }); cut(g, '#6f9a7a', g => ell(g, 1.9, h + .15, 2.2, .5)); } }); },
        props: [{ id: 'rbow', x: 0, y: .9, w: 3.4, h: 1.7, basic: true, opacity: 0, dz: .004, draw(g, w, h) { rainbowArt(g, w, h); } }] },
      { z: -1.3, rise: 'grow', x: 2, w: 3.8, h: 2.75, draw(g, w, h) { cut(g, '#7ab066', g => ell(g, 1.9, h + .1, 1.7, .4)); castleDay(g, 1.9, h - .2, .86); },
        props: [{ id: 'win', x: 0, y: 0, w: 3.8, h: 2.75, basic: true, opacity: .25, dz: .006, draw(g, w, h) { castleWindows(g, 1.9, h - .2, .86, '#ffd27a', 'rgba(255,200,100,1)'); } }] },
      { z: -0.25, rise: 'grow', x: 2, w: 3.8, h: 2.0, draw(g, w, h) { oak(g, .45, h, .82); oak(g, 3.35, h, .86); },
        props: [{ id: 'banner', x: 0, y: 1.0, w: 2.5, h: .56, px: .5, py: 0, dz: .02, draw(g, w, h) { ribbon(g, w, h, T('{TN}'), .3); } }] },
      { z: .55, rise: 'slide', dir: -1, x: .95, w: 1.2, h: 2.4, draw: null, props: [{ id: 'sham', x: 0, y: 0, w: 1.2, h: 2.35, tap: true, draw(g, w, h) { shamUmb(g, .35, h, .75); } }] },
      { z: 1.4, x: 2, w: 3.9, h: .7, draw(g, w, h) { bank(g, 0, 1.3, h, .35, 3); bank(g, 2.6, 3.9, h, .4, 4); } },
    ],
    setup(o, sp) { o.banner.grp.scale.x = .06; loose(sp, 'boat', .32, .22, (g, w, h) => boatArt(g, w, h), { tap: true }); o.boat.grp.position.set(3.0, Y0, 2.3); },
    lamp: o => ({ obj: o.win.grp, at: [0, 1.6, .3], i: 2.5 }),
    reset(o) { o._lit = false; o.banner.grp.scale.x = .06; o.win.mesh.material.opacity = .25; o.rbow.mesh.material.opacity = 0; },
    tick(o, t, dt) {
      rainTick(SP[0], dt, [[3.0, 2.3, .6], [1.0, .5, .5], [2.6, .9, .3]]);
      o.boat.grp.position.set(3.0 + Math.sin(t * .6) * .18, Y0 + Math.abs(Math.sin(t * 2)) * .015, 2.3); o.boat.grp.rotation.z = Math.sin(t * 1.7) * .1;
      o.sham.grp.rotation.z = Math.sin(t * 1.3) * .02;
      if (o._lit) { o.rbow.mesh.material.opacity = .8 + .15 * Math.sin(t * 2); if (Math.random() < dt * 4) spark(wpos(o.rbow.grp, (Math.random() - .5) * 3, .9 + Math.random() * .7, .05), '#fff6dc', 0, .1, 0, 1.4); }
    },
    async action(o, id) {
      if (id === 'boat') { sfx.plip(); ripple(SP[0], o.boat.grp.position.x, 2.3, .4); await tween(.5, p => { o.boat.grp.position.y = Y0 + Math.sin(p * Math.PI) * .12; }); return; }
      if (id === 'sham') { bubble('“This story is for you, {TN}.”', o.sham, 2.35, 2600); sfx.chime([659, 784, 988]); return; }
      if (!o._lit) {
        bubble('“This story is for you, {TN}.”', o.sham, 2.35, 2200); sfx.chime([523, 659, 784, 1046]);
        await tween(1.1, p => { o.banner.grp.scale.x = lerp(.06, 1, p); }, E.back);
        burstAt(o.banner.grp, [0, .3, .1], '#ffe7a8', 50, 1.3);
        snowTarget = .25; sfx.wish();
        await tween(1.6, p => { o.rbow.mesh.material.opacity = p * .9; o.win.mesh.material.opacity = lerp(.25, 1, p); L.target = lerp(2.5, 7, p); }, E.out);
        o._lit = true;
      }
      for (let i = 0; i < 6; i++) { burstAt(o.rbow.grp, [-1.4 + i * .56, 1.2 + Math.sin(i / 5 * Math.PI) * .45, .05], ['#ff5f6d', '#ff9f43', '#ffd93f', '#6bd36b', '#4fa8ff', '#8a6bff'][i], 30, 1.0, .08, 1.2); sfx.note(523 * Math.pow(2, [0, 2, 4, 7, 9, 12][i] / 12)); await wait(160); }
    },
  },
  {
    numeral: 'I', title: 'The Great Rain Race', page: 1, mood: 'rain', snow: .95, fall: '#d6e9ff', rain: true,
    shot: { pitch: .58, zoom: .86, ty: 1.2, sway: .06 },
    hint: 'Tap the poster on the tree', button: () => 'Get ready to race',
    paras: [
      'It had rained for seven days and seven nights. The gutters gurgled, the frogs sang, and every puddle in the kingdom was as big as a bathtub.',
      'On the eighth morning, a poster appeared on the old oak tree: THE GREAT RAIN RACE. Over the stream, up the muddy hill, and home to the castle gate. Everyone welcome. Wellies essential.',
      '“I’m going to run,” said {TN}, buttoning up her red raincoat. “Me too!” said Mikaal, already bouncing on both feet.',
      'Shamroze opened the biggest, brightest umbrella in the kingdom. “Then I shall be the starter,” said Shamroze, “and I shall hold the finish ribbon.”',
    ],
    ground(g) { wetGround(g, 11); track(g, 3.4, 4.05); stroke(g, '#ffffff', .05, g => { g.moveTo(.95, 3.32); g.lineTo(.95, 4.12); }, false); puddle(g, 2.6, 3.0, .35, .14); puddle(g, 3.3, 4.7, .4, .16); puddle(g, .7, 4.8, .3, .12); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { rainSky(g, w, h, { seed: 12, paint: g => { cut(g, '#87ad86', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .65); }); castleDay(g, 3.1, h - .45, .5); } }); },
        props: [{ id: 'bolt', x: -.8, y: 1.3, w: .5, h: 1.0, basic: true, opacity: 0, dz: .01, draw(g, w, h) { boltArt(g, w, h); } }] },
      { z: -1.4, rise: 'grow', x: 2, w: 3.8, h: 2.4, draw(g, w, h) { oak(g, .7, h, 1.0); hedge(g, 2.2, 3.8, h, .8, true, 14); bunting(g, 1.25, 3.8, .55, .14); },
        props: [{ id: 'poster', x: -1.2, y: .55, w: .55, h: .62, dz: .02, tap: true, draw(g, w, h) { posterArt(g, w, h); } }] },
      { z: -0.35, rise: 'swing', dir: -1, x: 2, w: 3.8, h: .1, draw: null, props: [{ id: 'sham', x: 1.15, y: 0, w: 1.2, h: 2.35, tap: true, draw(g, w, h) { shamUmb(g, .35, h, .75); } }] },
      { z: 0.45, rise: 'slide', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'zainab', x: -1.0, y: 0, w: 1.0, h: 1.65, tap: true, draw(g, w, h) { zr(g, w, h, .9); } },
        { id: 'mikaal', x: -.3, y: 0, w: 1.0, h: 1.5, tap: true, draw(g, w, h) { mr(g, w, h, .82); } },
      ] },
      { z: 1.5, rise: 'drop', x: 2, w: 3.9, h: .5, draw(g, w, h) { bank(g, 0, .9, h, .3, 15); bank(g, 3.0, 3.9, h, .3, 16); },
        props: [{ id: 'frog', x: 1.45, y: .1, w: .45, h: .42, tap: true, dz: .02, draw(g, w, h) { frogArt(g, w / 2, h, .5, 'sit', { crown: false }); } }] },
    ],
    lamp: o => ({ obj: o.sham.grp, at: [.3, 1.6, .5], i: 1.0 }),
    reset(o) { o._jump = false; },
    async intro(o) { bubble('“The Great Rain Race!”', o.zainab, 1.65, 2000); },
    tick(o, t, dt) {
      rainTick(SP[1], dt, [[2.6, .3, .5], [3.3, 2.0, .6], [.7, 2.1, .4]]);
      if (!o._jump) { o.zainab.grp.scale.y = 1 + .04 * Math.sin(t * 5); o.zainab.grp.rotation.z = Math.sin(t * 2.5) * .06; o.mikaal.grp.scale.y = 1 + .04 * Math.sin(t * 5 + 1.5); o.mikaal.grp.rotation.z = Math.sin(t * 2.5 + 2) * .06; }
      o.sham.grp.rotation.z = Math.sin(t * 1.3) * .02; o.poster.grp.rotation.z = Math.sin(t * 1.9) * .04 * wind;
      o.frog.grp.scale.y = 1 + .04 * Math.sin(t * 3);
    },
    async action(o, id) {
      if (id === 'poster') { bubble('“Over the stream, up the hill, home to the castle!”', o.poster, .62, 2800); sfx.rustle(); await tween(.5, p => { o.poster.grp.rotation.z = Math.sin(p * Math.PI * 3) * .12; }); return; }
      if (id === 'frog') { sfx.ribbit(); bubble('“Ribbit! Good luck!”', o.frog, .42, 1600); await tween(.45, p => { o.frog.grp.position.y = .1 + Math.sin(p * Math.PI) * .3; }); return; }
      if (id === 'mikaal') { bubble('“I’m ready!”', o.mikaal, 1.5, 1500); return; }
      o._jump = true; await lightning(o, o.bolt);
      bubble('“The Great Rain Race starts today!”', o.sham, 2.35, 2200); await wait(700);
      bubble('“Let’s go, Mikaal!”', o.zainab, 1.65, 1600);
      await tween(.9, p => { o.zainab.grp.position.y = Math.abs(Math.sin(p * Math.PI * 2)) * .35; o.mikaal.grp.position.y = Math.abs(Math.sin(p * Math.PI * 2 + .6)) * .3; });
      sfx.chime([659, 784, 988]); burstAt(o.zainab.grp, [0, 1.6, .05], '#ffd27a', 30, .9, .07, 1.0);
      o.zainab.grp.position.y = 0; o.mikaal.grp.position.y = 0; o._jump = false;
    },
  },
  {
    numeral: 'II', title: 'Ready, Steady, Splash!', page: 3, mood: 'rain', snow: .95, fall: '#d6e9ff', rain: true,
    shot: { pitch: .62, zoom: .88, ty: 1.05, sway: .06 },
    hint: 'Tap the duck', button: () => 'Start the race!',
    paras: [
      '“On your marks,” called Shamroze. “Get set…” PHWEEEET! went the whistle, and off they ran.',
      'Splish went the wellies. Splash went the puddles. Splosh went a very surprised duck.',
      '#Everyone was soaked in a second, and nobody minded one bit.',
      '{N} ran with her arms pumping and her crown bouncing, and Mikaal ran right beside her, laughing all the way.',
    ],
    ground(g) { wetGround(g, 21); track(g, 2.95, 4.3); [[1.3, 3.35], [2.4, 3.9], [3.2, 3.3]].forEach(([x, y]) => puddle(g, x, y, .3, .12)); puddle(g, 3.3, 2.3, .55, .22); stroke(g, '#ffffff', .05, g => { g.moveTo(.6, 2.9); g.lineTo(.6, 4.35); }, false); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { rainSky(g, w, h, { seed: 22, clouds: [[.2, .5, 1.3], [1.6, .35, 1.4], [2.9, .55, 1.2]], paint: g => { cut(g, '#87ad86', g => { ell(g, 1.0, h, 1.8, .55); ell(g, 3.3, h, 1.3, .6); }); castleDay(g, 1.0, h - .4, .42); } }); } },
      { z: -1.45, rise: 'grow', x: 2, w: 3.8, h: 1.3, draw(g, w, h) { bunting(g, 0, 3.8, .12, .1); cut(g, '#7ab066', g => rr(g, 0, h - .3, w, .3, 0)); },
        props: Array.from({ length: 8 }, (_, i) => ({ id: 'cr' + i, x: -1.7 + i * .48, y: .1, w: .34, h: .62, dz: .01, draw(g, w, h) { crowdArt(g, w, h, i + 3); } })) },
      { z: -0.6, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [{ id: 'sham', x: -1.35, y: 0, w: 1.2, h: 2.35, tap: true, draw(g, w, h) { shamUmb(g, .35, h, .75); } }] },
      { z: 1.6, rise: 'drop', x: 2, w: 3.9, h: .45, draw(g, w, h) { bank(g, 0, .7, h, .28, 23); bank(g, 3.2, 3.9, h, .28, 24); } },
    ],
    setup(o, sp) {
      loose(sp, 'zainab', .95, 1.5, (g, w, h) => zr(g, w, h, .8), { tap: true });
      loose(sp, 'mikaal', .95, 1.4, (g, w, h) => mr(g, w, h, .74), { tap: true });
      loose(sp, 'duck', .4, .3, duckArt, { tap: true });
    },
    lamp: o => ({ obj: o.sham.grp, at: [.3, 1.6, .5], i: .8 }),
    reset(o) { o._race = false; o.zainab.grp.position.set(.4, Y0, 1.15); o.mikaal.grp.position.set(.4, Y0, .62); o.zainab.grp.rotation.z = 0; o.mikaal.grp.rotation.z = 0; o.duck.grp.position.set(3.3, Y0, -.4); },
    async intro(o) { bubble('“On your marks…”', o.sham, 2.35, 1800); },
    tick(o, t, dt) {
      rainTick(SP[2], dt, [[1.3, .65, .4], [2.4, 1.2, .4], [3.2, .6, .4], [3.3, -.4, .7]], 7);
      for (let i = 0; i < 8; i++) o['cr' + i].grp.position.y = .1 + Math.abs(Math.sin(t * (o._race ? 7 : 2) + i)) * (o._race ? .1 : .03);
      if (!o._race) { o.zainab.grp.position.y = Y0 + Math.abs(Math.sin(t * 4)) * .03; o.mikaal.grp.position.y = Y0 + Math.abs(Math.sin(t * 4 + 1)) * .03; o.duck.grp.position.x = 3.3 + Math.sin(t * .5) * .25; o.duck.grp.scale.x = Math.cos(t * .5) > 0 ? 1 : -1; o.duck.grp.position.y = Y0 + Math.sin(t * 2) * .01; }
      o.sham.grp.rotation.z = Math.sin(t * 1.3) * .02;
    },
    async action(o, id) {
      if (id === 'duck') { sfx.quack(); bubble('“Quack!”', o.duck, .3, 1200); await tween(.45, p => { o.duck.grp.position.y = Y0 + Math.sin(p * Math.PI) * .25; }); return; }
      if (o._race) return;
      this.reset(o); o._race = true; const sp = SP[2];
      bubble('“On your marks… get set…”', o.sham, 2.35, 1500); await wait(1300);
      sfx.whistle(); bubble('“GO!”', o.sham, 2.35, 900); await wait(250);
      const puds = [1.3, 2.4, 3.2], hit = { z: new Set(), m: new Set() }; let quacked = false;
      await tween(3.0, p => {
        const t = performance.now() / 1000, xz = lerp(.4, 3.55, E.inOut(p)), xm = lerp(.4, 3.4, E.inOut(Math.max(0, p - .03)));
        run(o.zainab, xz, 1.15, t); run(o.mikaal, xm, .62, t, .95);
        puds.forEach((px, i) => { [['z', xz, 1.15, o.zainab], ['m', xm, .62, o.mikaal]].forEach(([k, x, z, r]) => { if (!hit[k].has(i) && Math.abs(x - px) < .12) { hit[k].add(i); sfx.splash(); burst(new THREE.Vector3(x, Y0 + .08, z), '#cfe6ff', 36, 1.4, .07, .9, -3); ripple(sp, x, z, .45, 1.0); } }); });
        if (!quacked && xz > 2.9) { quacked = true; sfx.quack(); bubble('“Quack!”', o.duck, .3, 1100); tween(.6, q => { o.duck.grp.position.y = Y0 + Math.sin(q * Math.PI) * .45; o.duck.grp.rotation.z = Math.sin(q * Math.PI * 2) * .4; }); }
      }, E.lin);
      bubble('“Splish, splash, splosh!”', o.zainab, 1.5, 1800); sfx.cheer();
      await wait(1600);
      await tween(.3, p => { o.zainab.grp.scale.setScalar(Math.max(.001, 1 - p)); o.mikaal.grp.scale.setScalar(Math.max(.001, 1 - p)); });
      this.reset(o); o._race = true;
      await tween(.35, p => { o.zainab.grp.scale.setScalar(Math.max(.001, p)); o.mikaal.grp.scale.setScalar(Math.max(.001, p)); }, E.back);
      o._race = false;
    },
  },
  {
    numeral: 'III', title: 'The Muddy Hill', page: 5, mood: 'rain', snow: .8, fall: '#d6e9ff', rain: true,
    shot: { pitch: .56, zoom: .86, ty: 1.15, sway: .06 },
    hint: 'Tap {N} to help', button: o => o._up ? 'Slip and help again' : 'Help Mikaal up',
    paras: [
      'Then came the muddy hill. It was slippery as soap and steep as a slide. Up, up they climbed, until, whoops! Mikaal’s boots slid out, and down went Mikaal into a big brown puddle with a SPLAT.',
      'Some of the runners didn’t stop. But {N} did. She ran back, held out her hand, and pulled with all her might.',
      '“Are you hurt?” she asked. Mikaal wiped off a big splodge of mud and burst out laughing. “I’m a chocolate cake!”',
      '#And together they climbed to the top.',
    ],
    ground(g) { wetGround(g, 31, { col: '#86b872' }); cut(g, '#8a6040', g => { ell(g, 1.9, 3.1, .9, .35); ell(g, 3.1, 4.4, .5, .2); ell(g, .8, 4.0, .4, .15); }, { blur: 4, oy: 1 }); puddle(g, 3.2, 2.2, .3, .12); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { rainSky(g, w, h, { seed: 32, stops: [[0, '#55678a'], [.6, '#8fa3bb'], [1, '#c9d6e0']] }); },
        props: [{ id: 'bolt', x: 1.1, y: 1.4, w: .45, h: .9, basic: true, opacity: 0, dz: .01, draw(g, w, h) { boltArt(g, w, h); } }] },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 2.1, draw(g, w, h) {
        cut(g, '#6faa5f', g => { g.moveTo(-.05, h); g.bezierCurveTo(1.0, h - .2, 2.2, .7, 3.85, .45); g.lineTo(3.85, h); g.closePath(); }, { blur: 8, oy: 3 });
        stroke(g, '#8a6040', .09, g => { g.moveTo(.2, h - .05); g.bezierCurveTo(1.2, h - .25, 2.3, .9, 3.6, .6); }, false);
        cut(g, '#7a5236', g => { [[1.2, h - .32], [2.0, 1.25], [2.8, .82]].forEach(([x, y]) => ell(g, x, y, .18, .05)); }, { shadow: false });
        stroke(g, '#5a4a3a', .02, g => { g.moveTo(3.55, .6); g.lineTo(3.55, .1); }, false); cut(g, '#e2456f', g => poly(g, [3.55, .1, 3.8, .18, 3.55, .26]), { blur: 3, oy: 1 });
      } },
      { z: -0.3, rise: 'swing', dir: -1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'snail', x: -1.5, y: 0, w: .45, h: .32, dz: .005, tap: true, draw(g, w, h) { snailArt(g, w, h); } },
        { id: 'mikaal', x: -.15, y: -.4, w: 1.0, h: 1.5, tap: true, draw(g, w, h) { mr(g, w, h, .82); cut(g, 'rgba(122,82,54,.85)', g => { ell(g, .3, h - .5, .08, .05); ell(g, .62, h - .8, .06, .04); ell(g, .5, h - 1.25, .05, .03); }, { shadow: false }); } },
        { id: 'mud', x: -.15, y: -.06, w: 1.05, h: .36, dz: .06, draw(g, w, h) { mudArt(g, w, h); } },
        { id: 'zainab', x: .7, y: 0, w: 1.0, h: 1.65, tap: true, dz: .02, draw(g, w, h) { zr(g, w, h, .9); } },
      ] },
      { z: 1.45, rise: 'drop', x: 2, w: 3.9, h: .5, draw(g, w, h) { bank(g, 0, 1.0, h, .3, 33); bank(g, 3.0, 3.9, h, .3, 34); } },
    ],
    lamp: o => ({ obj: o.zainab.grp, at: [0, 1.6, .5], i: .8 }),
    reset(o) { o._up = false; o._busy = false; o.mikaal.grp.position.set(-.15, -.4, .012); o.mikaal.grp.rotation.z = .25; o.zainab.grp.position.set(.7, 0, .02); o.zainab.grp.rotation.z = 0; o.mud.grp.visible = true; o.snailX = -1.5; },
    async intro(o) { sfx.splash(); bubble('“SPLAT!”', o.mikaal, 1.15, 1500); },
    tick(o, t, dt) {
      rainTick(SP[3], dt, [[1.9, .4, .9], [3.1, 1.7, .5], [.8, 1.3, .4]]);
      o.snailX = Math.min(1.7, (o.snailX ?? -1.5) + dt * .03); o.snail.grp.position.x = o.snailX; o.snail.grp.scale.x = 1 + .06 * Math.sin(t * 3);
      if (!o._busy && !o._up) { o.mikaal.grp.rotation.z = .25 + Math.sin(t * 2) * .03; o.zainab.grp.rotation.z = Math.sin(t * 1.6) * .03; }
    },
    async action(o, id) {
      if (id === 'snail') { bubble('“I’m racing too! Slowly.”', o.snail, .32, 2000); sfx.note(392); return; }
      if (o._busy) return; o._busy = true;
      if (o._up) { this.reset(o); o._busy = true; sfx.splash(); burstAt(o.mud.grp, [0, .2, .1], '#7a5236', 30, 1.2, .07, .9, -2); await wait(500); }
      await tween(.6, p => { o.zainab.grp.position.x = lerp(.7, .45, p); o.zainab.grp.rotation.z = .18 * p; });
      bubble('“Are you hurt?”', o.zainab, 1.65, 1600); await wait(900);
      bubble('“Hold on… pull!”', o.zainab, 1.65, 1300);
      await tween(1.0, p => { o.mikaal.grp.position.y = lerp(-.4, 0, E.back(p)); o.mikaal.grp.rotation.z = lerp(.25, 0, p); o.zainab.grp.rotation.z = lerp(.18, -.1, p); });
      sfx.splash(); burstAt(o.mud.grp, [0, .25, .1], '#7a5236', 50, 1.6, .08, 1.0, -2.5);
      bubble('“I’m a chocolate cake!”', o.mikaal, 1.5, 2000); sfx.chime([523, 659, 784]);
      await wait(1500);
      bubble('“Together, then!”', o.zainab, 1.65, 1600);
      await tween(1.6, p => { const t = performance.now() / 1000; o.zainab.grp.position.x = lerp(.45, 1.35, p); o.mikaal.grp.position.x = lerp(-.15, .75, p); o.zainab.grp.position.y = p * .35 + Math.abs(Math.sin(t * 9)) * .05; o.mikaal.grp.position.y = p * .3 + Math.abs(Math.sin(t * 9 + 1)) * .05; });
      o._up = true; o._busy = false;
    },
  },
  {
    numeral: 'IV', title: 'Thunder at the Stream', page: 7, mood: 'rain', snow: 1, fall: '#d6e9ff', rain: true,
    shot: { pitch: .7, zoom: .88, ty: 1.0, sway: .06 },
    hint: 'Tap the ducks, or cross the stream', button: o => o._across ? 'Cross again' : 'Cross the stepping stones',
    paras: [
      'At the bottom of the hill, the stream had grown wide and wild, and the little wooden bridge wobbled in the wind. Then the sky went BOOM!',
      'Mikaal stood very still. “I don’t like thunder,” Mikaal whispered.',
      '{N} took Mikaal’s hand. “Thunder is just the clouds playing drums,” she said. “Let’s march to the beat. One, two, three!”',
      '#And stone by stone, drum by drum, they crossed the stream without once looking down.',
    ],
    ground(g) {
      wetGround(g, 41);
      const gr = g.createLinearGradient(0, 2.5, 0, 3.5); gr.addColorStop(0, '#4f86b0'); gr.addColorStop(.5, '#6aa6cf'); gr.addColorStop(1, '#4f86b0');
      cut(g, gr, g => { g.moveTo(-.1, 2.55); g.bezierCurveTo(1.3, 2.35, 2.6, 2.75, W + .1, 2.5); g.lineTo(W + .1, 3.45); g.bezierCurveTo(2.6, 3.65, 1.3, 3.3, -.1, 3.5); g.closePath(); }, { blur: 5, oy: 1 });
      stroke(g, 'rgba(255,255,255,.55)', .015, g => { const r = rng(42); for (let i = 0; i < 26; i++) { const x = r() * W, y = 2.65 + r() * .7; g.moveTo(x, y); g.quadraticCurveTo(x + .1, y - .04, x + .2, y); } }, false);
      [[1.75, 3.2], [2.3, 3.2], [1.8, 2.9], [2.3, 2.9]].forEach(([x, y]) => { cut(g, '#9aa3ad', g => ell(g, x, y, .2, .1), { blur: 4, oy: 2 }); cut(g, '#c2c9d0', g => ell(g, x - .04, y - .03, .09, .04), { shadow: false }); });
      puddle(g, .6, 4.6, .35, .14);
    },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { rainSky(g, w, h, { seed: 43, stops: [[0, '#3d4a68'], [.6, '#6f81a0'], [1, '#a9b9cc']], cloud: '#6f7f9a', clouds: [[.2, .4, 1.4], [1.5, .3, 1.6], [2.9, .5, 1.3], [1.0, .9, 1.0]], paint: g => { cut(g, '#5f8a6f', g => { ell(g, .8, h, 1.5, .55); ell(g, 3.2, h, 1.4, .5); }); } }); },
        props: [{ id: 'bolt', x: .7, y: 1.2, w: .55, h: 1.1, basic: true, opacity: 0, dz: .01, draw(g, w, h) { boltArt(g, w, h); } }] },
      { z: -1.6, rise: 'grow', x: 2, w: 3.8, h: 2.1, draw(g, w, h) { oak(g, .5, h, .9); oak(g, 3.35, h, .85); hedge(g, 1.1, 2.7, h, .6, false); } },
      { z: -0.75, rise: 'grow', x: 2, w: 3.8, h: .9, draw(g, w, h) { cut(g, '#7ab066', g => { ell(g, .3, h, .6, .25); ell(g, 3.5, h, .6, .25); }); },
        props: [{ id: 'bridge', x: -1.15, y: 0, w: 1.4, h: .75, dz: .01, draw(g, w, h) {
          stroke(g, '#8a5a3a', .07, g => { g.moveTo(.05, h - .05); g.quadraticCurveTo(w / 2, h - .55, w - .05, h - .05); }, true);
          stroke(g, '#6e4529', .03, g => { for (let i = 0; i <= 8; i++) { const t = i / 8, x = lerp(.05, w - .05, t), y = h - .05 - Math.sin(t * Math.PI) * .25; g.moveTo(x, y); g.lineTo(x, y - .22); } g.moveTo(.05, h - .27); g.quadraticCurveTo(w / 2, h - .78, w - .05, h - .27); }, false);
        } }] },
      { z: 1.55, rise: 'drop', x: 2, w: 3.9, h: .55, draw(g, w, h) { bank(g, 0, 1.0, h, .3, 44); bank(g, 3.0, 3.9, h, .3, 45); reeds(g, .4, h, .8); reeds(g, 3.5, h, .8, 4); } },
    ],
    setup(o, sp) {
      loose(sp, 'zainab', .8, 1.3, (g, w, h) => zr(g, w, h, .68), { tap: true });
      loose(sp, 'mikaal', .8, 1.2, (g, w, h) => mr(g, w, h, .62), { tap: true });
      [0, 1].forEach(i => loose(sp, 'duck' + i, .34, .26, duckArt, { tap: true }));
    },
    lamp: o => ({ obj: o.zainab.grp, at: [0, 1.2, .5], i: .6 }),
    reset(o) { o._across = false; o._busy = false; o.zainab.grp.position.set(1.75, Y0, 1.15); o.mikaal.grp.position.set(2.3, Y0, 1.15); o.zainab.grp.rotation.z = 0; o.mikaal.grp.rotation.z = 0; },
    async intro(o) { await lightning(o, o.bolt); bubble('“BOOM!”', o.bolt, .9, 1200); },
    tick(o, t, dt) {
      rainTick(SP[4], dt, [[2.0, .3, 2.6], [.6, 1.9, .4]], 9);
      o.bridge.grp.rotation.z = Math.sin(t * 2.3) * .03 * (1 + wind);
      for (let i = 0; i < 2; i++) { const d = o['duck' + i], ph = ((t * .05 + i * .5) % 1); d.grp.position.set(lerp(-.2, 4.2, ph), Y0 + Math.sin(t * 2 + i) * .012, .05 + i * .45); d.grp.scale.x = -1; }
      if (!o._busy && !o._across) { o.mikaal.grp.rotation.z = Math.sin(t * 20) * .015; }
    },
    async action(o, id) {
      if (id && id.startsWith('duck')) { sfx.quack(); bubble('“Quack quack!”', o[id], .26, 1200); return; }
      if (id === 'mikaal' && !o._busy) { bubble('“I don’t like thunder…”', o.mikaal, 1.2, 1800); return; }
      if (o._busy) return; this.reset(o); o._busy = true; const sp = SP[4];
      await lightning(o, o.bolt); bubble('“I don’t like thunder…”', o.mikaal, 1.2, 1800); await wait(1500);
      bubble('“It’s just the clouds playing drums!”', o.zainab, 1.3, 2200); await wait(1800);
      const steps = [.82, .52, -.45], words = ['“One!”', '“Two!”', '“Three!”'];
      for (let i = 0; i < 3; i++) {
        sfx.drum(); bubble(words[i], o.zainab, 1.3, 900);
        const zz = o.zainab.grp.position.z, zm = o.mikaal.grp.position.z;
        hop(o.mikaal, [2.3, Y0, zm], [2.3, Y0, steps[i]], .4, .6);
        await hop(o.zainab, [1.75, Y0, zz], [1.75, Y0, steps[i]], .45, .6);
        ripple(sp, 1.75, steps[i], .35, .9); ripple(sp, 2.3, steps[i], .35, .9); if (i < 2) sfx.plip();
        await wait(250);
      }
      sfx.chime([523, 659, 784, 1046]); burstAt(o.zainab.grp, [0, 1.2, .05], '#ffd27a', 40, 1.0, .07, 1.1);
      bubble('“We did it!”', o.mikaal, 1.2, 1800);
      o._across = true; o._busy = false;
    },
  },
  {
    numeral: 'V', title: 'The Finish Line', page: 9, mood: 'rain', snow: .55, fall: '#d6e9ff', rain: true,
    shot: { pitch: .6, zoom: .88, ty: 1.1, sway: .06 },
    hint: 'Tap Mikaal to cheer', button: o => o._won ? 'Run it again' : 'Sprint for the finish',
    paras: [
      'Over the last field they flew, past the cheering umbrellas, past the clapping ducks, towards the castle gate, where Shamroze stood beside the long red ribbon.',
      '“Run, Queen Zainab, RUN!” shouted Mikaal, puffing along behind. And {N} ran faster than the wind, faster than the rain, so fast that her crown sparkled like a shooting star.',
      '#SNAP! went the ribbon.',
      '{N} had won the Great Rain Race!',
    ],
    ground(g) { wetGround(g, 51); track(g, 3.25, 4.05); stroke(g, '#ffffff', .06, g => { g.moveTo(2.35, 3.15); g.lineTo(2.35, 4.15); }, false); puddle(g, 1.2, 3.5, .25, .1); puddle(g, .7, 2.4, .35, .13); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { rainSky(g, w, h, { seed: 52, stops: [[0, '#6f86a8'], [.6, '#b3c6d6'], [1, '#e8eef0']], clouds: [[.3, .4, 1.1], [2.6, .35, 1.2]], paint: g => cut(g, '#87ad86', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .65); }) }); } },
      { z: -1.6, rise: 'grow', x: 2, w: 3.8, h: 2.4, draw(g, w, h) { castleDay(g, 2.75, h, .74); hedge(g, 0, 1.5, h, .8, true, 53); } },
      { z: -0.85, rise: 'grow', x: 2, w: 3.8, h: .8, draw(g, w, h) { bunting(g, 0, 3.8, .05, .08); },
        props: Array.from({ length: 7 }, (_, i) => ({ id: 'cr' + i, x: -1.7 + i * .5, y: .02, w: .34, h: .62, dz: .01, draw(g, w, h) { crowdArt(g, w, h, i + 7); } })) },
      { z: 0.95, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'finish', x: .35, y: 0, w: 1.3, h: 1.35, draw(g, w, h) { finishArt(g, w, h); } },
        { id: 'tapeL', x: -.14, y: .72, w: .5, h: .07, px: 0, py: .5, dz: .02, draw(g, w, h) { tapeArt(g, w, h); } },
        { id: 'tapeR', x: .84, y: .72, w: .5, h: .07, px: 1, py: .5, dz: .02, draw(g, w, h) { tapeArt(g, w, h); } },
        { id: 'sham', x: 1.25, y: 0, w: 1.0, h: 1.75, tap: true, dz: .01, draw(g, w, h) { shamUmb(g, .4, h, .55); } },
      ] },
      { z: 1.6, rise: 'drop', x: 2, w: 3.9, h: .4, draw(g, w, h) { bank(g, 0, .8, h, .25, 54); bank(g, 3.1, 3.9, h, .25, 55); } },
    ],
    setup(o, sp) {
      loose(sp, 'zainab', .9, 1.45, (g, w, h) => zr(g, w, h, .78), { tap: true });
      loose(sp, 'mikaal', .9, 1.35, (g, w, h) => mr(g, w, h, .72), { tap: true });
      o.crownGlow = glow('#fff1b8', .4, 0); o.crownGlow.position.set(0, 1.32, .03); o.zainab.grp.add(o.crownGlow);
    },
    lamp: o => ({ obj: o.zainab.grp, at: [0, 1.4, .4], i: 1.2 }),
    reset(o) { o._won = false; o._busy = false; o.zainab.grp.position.set(.45, Y0, 1.08); o.mikaal.grp.position.set(.3, Y0, .62); o.zainab.grp.rotation.z = 0; o.mikaal.grp.rotation.z = 0; o.tapeL.grp.rotation.z = 0; o.tapeR.grp.rotation.z = 0; o.crownGlow.material.opacity = 0; },
    async intro(o) { bubble('“Here they come!”', o.sham, 1.7, 1800); },
    tick(o, t, dt) {
      rainTick(SP[5], dt, [[1.2, .8, .4], [.7, -.3, .5]], 4);
      for (let i = 0; i < 7; i++) o['cr' + i].grp.position.y = .02 + Math.abs(Math.sin(t * (o._won || o._busy ? 7 : 2.2) + i)) * (o._won || o._busy ? .1 : .03);
      if (!o._busy && !o._won) { o.zainab.grp.position.y = Y0 + Math.abs(Math.sin(t * 4)) * .03; o.mikaal.grp.position.y = Y0 + Math.abs(Math.sin(t * 4 + 1)) * .03; }
      if (o._won) { o.crownGlow.material.opacity = .6 + .3 * Math.sin(t * 5); if (Math.random() < dt * 6) spark(wpos(o.zainab.grp, (Math.random() - .5) * .3, 1.35, .05), '#fff1b8', 0, .3, 0, 1.0); }
    },
    async action(o, id) {
      if (id === 'mikaal' && !o._busy) { bubble('“Run, Queen Zainab, RUN!”', o.mikaal, 1.35, 1800); sfx.cheer(); return; }
      if (id === 'sham' && !o._busy) { bubble(o._won ? '“The winner is Queen Zainab!”' : '“Here they come!”', o.sham, 1.7, 1800); return; }
      if (o._busy) return; this.reset(o); o._busy = true;
      bubble('“Run, Queen Zainab, RUN!”', o.mikaal, 1.35, 1500); sfx.cheer(); await wait(700);
      let snapped = false;
      await tween(2.4, p => {
        const t = performance.now() / 1000, xz = lerp(.45, 3.3, E.in(p) * .4 + p * .6), xm = lerp(.3, 2.35, p);
        run(o.zainab, xz, 1.08, t, 1.25, .2); run(o.mikaal, xm, .62, t, .9);
        o.crownGlow.material.opacity = .9; if (Math.random() < .7) spark(wpos(o.zainab.grp, 0, 1.35, .05), ['#fff1b8', '#ffd27a', '#ffffff'][Math.floor(Math.random() * 3)], -.6, .1, 0, .9);
        if (!snapped && xz > 2.35) { snapped = true; sfx.pop(.6); tween(.7, q => { o.tapeL.grp.rotation.z = -1.35 * E.out(q); o.tapeR.grp.rotation.z = 1.35 * E.out(q); }); confetti(o.finish.grp, [0, 1.2, .1]); sfx.cheer(); bubble('SNAP!', o.finish, 1.35, 1100); }
      }, E.lin);
      o._won = true; snowTarget = .25;
      bubble('“The winner is Queen Zainab!”', o.sham, 1.7, 2400); sfx.chime([523, 659, 784, 1046]);
      await tween(1.0, p => { o.zainab.grp.position.y = Y0 + Math.abs(Math.sin(p * Math.PI * 3)) * .35; o.zainab.grp.rotation.z = Math.sin(p * Math.PI * 3) * .1; });
      confetti(o.zainab.grp, [0, 1.5, .1], 3);
      bubble('“Hooray, Zainab!”', o.mikaal, 1.35, 1800);
      o._busy = false;
    },
  },
  {
    numeral: 'VI', title: 'The Biggest Rainbow', page: 11, mood: 'day', snow: .3, fall: '#fff6c4', up: true, end: true,
    shot: { pitch: .62, zoom: .88, ty: 1.15, sway: .07 },
    hint: 'Tap the medals', button: () => 'Hip hip hooray!',
    paras: [
      'And just then, as if it had been waiting for the very end of the race, the rain stopped. The clouds rolled away, and the biggest rainbow anybody had ever seen stretched right over the castle.',
      'Shamroze hung a shiny gold medal around Zainab’s neck, and a silver one around Mikaal’s, “for the bravest runner in the mud.” Then everyone shared hot pakoras and sweet chai, and sailed paper boats in the puddles until the sun went down.',
      '#Because the best races are the ones you run together.',
    ],
    ground(g) { wetGround(g, 61, { col: '#9fd37f' }); puddle(g, 2.95, 4.7, .5, .2); puddle(g, 1.0, 4.95, .45, .17); g.save(); g.translate(1.5, 3.0); picnicArt(g, 1.1, .6); g.restore(); },
    layers: [
      { z: -2.3, x: 2, w: 3.8, h: 2.9, draw(g, w, h) { daySky(g, w, h, { sun: [3.25, .5, .24], paint: g => { cut(g, '#b5dc96', g => { ell(g, .8, h, 1.5, .6); ell(g, 3.1, h, 1.6, .65); }); castleDay(g, 1.9, h - .3, .62); cloud2(g, .3, .55, .9); } }); },
        props: [{ id: 'rbow', x: 0, y: .55, w: 3.6, h: 1.85, basic: true, opacity: .85, dz: .004, draw(g, w, h) { rainbowArt(g, w, h); } }] },
      { z: -1.5, rise: 'grow', x: 2, w: 3.8, h: 1.2, draw(g, w, h) { hedge(g, 0, 1.4, h, .9, true, 62); hedge(g, 2.4, 3.8, h, .9, true, 63); } },
      { z: -0.3, rise: 'swing', dir: 1, x: 2, w: 3.8, h: .1, draw: null, props: [
        { id: 'mikaal', x: -1.05, y: 0, w: 1.0, h: 1.5, tap: true, draw(g, w, h) { mr(g, w, h, .85); } },
        { id: 'sham', x: -.12, y: 0, w: 1.0, h: 1.85, tap: true, dz: .01, draw(g, w, h) { shamUmb(g, .45, h - .02, .8, { umbrella: false }); } },
        { id: 'zainab', x: .85, y: 0, w: 1.0, h: 1.7, tap: true, dz: .02, draw(g, w, h) { zr(g, w, h, .92); } },
        { id: 'zmed', x: .85, y: .62, w: .22, h: .3, dz: .05, tap: true, draw(g, w, h) { medalArt(g, w, h); } },
        { id: 'mmed', x: -1.05, y: .56, w: .22, h: .3, dz: .05, tap: true, draw(g, w, h) { medalArt(g, w, h, '#dfe6ee'); } },
      ] },
      { z: 1.45, rise: 'drop', x: 2, w: 3.9, h: .9, draw(g, w, h) { bank(g, 0, 1.3, h, .35, 64); bank(g, 2.6, 3.9, h, .35, 65); },
        props: [{ id: 'end', x: 0, y: .32, w: 1.6, h: .48, dz: .02, draw(g, w, h) { ribbon(g, w, h, TR('The End'), .28, '#3d8fd8'); } },
          { id: 'frog', x: 1.5, y: .3, w: .45, h: .42, tap: true, dz: .03, draw(g, w, h) { frogArt(g, w / 2, h, .5, 'sit', { crown: false }); } }] },
    ],
    setup(o, sp) {
      [0, 1].forEach(i => loose(sp, 'boat' + i, .3, .2, (g, w, h) => boatArt(g, w, h, i ? '#ffe7a8' : '#fdf6e8'), { tap: true }));
      o.zg = glow('#ffe39a', .45, .6); o.zg.position.set(0, .1, .02); o.zmed.grp.add(o.zg);
    },
    lamp: o => ({ obj: o.zainab.grp, at: [0, 1.4, .5], i: 1.0 }),
    reset(o) { o._busy = false; },
    async intro(o) { bubble('“Look! The biggest rainbow!”', o.zainab, 1.7, 2200); },
    tick(o, t, dt) {
      o.rbow.mesh.material.opacity = .8 + .12 * Math.sin(t * 1.5);
      if (Math.random() < dt * 3) spark(wpos(o.rbow.grp, (Math.random() - .5) * 3.2, .8 + Math.random() * .9, .05), '#fff6dc', 0, .1, 0, 1.4);
      [[2.95, 2.0], [1.0, 2.25]].forEach(([x, z], i) => { const b = o['boat' + i]; b.grp.position.set(x + Math.sin(t * .5 + i * 2) * .25, Y0 + .005, z); b.grp.rotation.z = Math.sin(t * 1.6 + i) * .1; });
      if (!o._busy) { o.zmed.grp.rotation.z = Math.sin(t * 2) * .08; o.mmed.grp.rotation.z = Math.sin(t * 2 + 1) * .08; }
      o.zg.material.opacity = .45 + .25 * Math.sin(t * 4); o.frog.grp.scale.y = 1 + .04 * Math.sin(t * 3);
    },
    async action(o, id) {
      if (id && id.startsWith('boat')) { sfx.plip(); ripple(SP[6], o[id].grp.position.x, o[id].grp.position.z, .4); return; }
      if (id === 'frog') { sfx.ribbit(); bubble('“Ribbit! Well run!”', o.frog, .42, 1600); return; }
      if (id === 'mikaal' || id === 'mmed') { bubble('“Silver, for the bravest runner in the mud!”', o.mikaal, 1.5, 2400); burstAt(o.mmed.grp, [0, .2, .05], '#ffffff', 30, .8, .06, 1.0); return; }
      if (id === 'sham') { bubble('“Who wants hot pakoras and chai?”', o.sham, 1.85, 2200); return; }
      if (o._busy) return; o._busy = true;
      sfx.wish(); await tween(1.0, p => { o.zmed.grp.rotation.y = p * Math.PI * 4; o.mmed.grp.rotation.y = p * Math.PI * 4; });
      burstAt(o.zmed.grp, [0, .2, .05], '#ffd27a', 50, 1.2, .08, 1.2);
      bubble('“Hip hip hooray for Queen Zainab!”', o.sham, 1.85, 2400); sfx.cheer();
      await tween(1.1, p => { ['zainab', 'mikaal', 'sham', 'zmed', 'mmed'].forEach((k, i) => { o[k].grp.position.y = o[k].P.y + Math.abs(Math.sin(p * Math.PI * 2)) * (k === 'sham' ? .2 : .35); }); });
      ['zainab', 'mikaal', 'sham'].forEach(k => burstAt(o[k].grp, [0, .05, .1], '#cfe6ff', 30, 1.3, .07, .8, -3)); sfx.splash();
      confetti(o.rbow.grp, [0, 1.5, .1], 3);
      bubble('“And for the mud!”', o.mikaal, 1.5, 1800);
      o._busy = false;
    },
  },
];
