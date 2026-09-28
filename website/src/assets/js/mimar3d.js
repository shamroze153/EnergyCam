/*!
 * Mimar AI 3D engine
 * - MimarScenes: problem -> solution scenes for each service
 * - MimarBuilding: the interactive hero building with a hotspot per service
 * Needs three.js r147 (global THREE). Falls back to the poster image when WebGL is missing.
 */
(function () {
  'use strict';

  var THREE = window.THREE;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function webglOK() {
    try { var c = document.createElement('canvas'); return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl'))); }
    catch (e) { return false; }
  }

  /* ---------------- helpers ---------------- */
  var clamp = function (x, a, b) { a = a === undefined ? 0 : a; b = b === undefined ? 1 : b; return Math.min(b, Math.max(a, x)); };
  var ease = function (x) { x = clamp(x); return 1 - Math.pow(1 - x, 3); };
  var inout = function (x) { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  var seg = function (t, a, b) { return clamp((t - a) / (b - a)); };
  var lerp = function (a, b, k) { return a + (b - a) * k; };
  var frac = function (x) { return x - Math.floor(x); };
  function rng(s) { var a = (s * 9301 + 49297) % 233280; return function () { a = (a * 9301 + 49297) % 233280; return a / 233280; }; }

  /* light "architectural model" palette */
  var P = {
    bg: 0xF4F7F5, ground: 0xEDF2EF, grid1: 0xD5DFDA, grid2: 0xE3EAE6, plat: 0xFFFFFF,
    floor: 0xD6DFDB, wall: 0xEDF2EF, wall2: 0xDFE6E3, desk: 0xBAC6C1, cab: 0x9FADA8, chair: 0x7E918A,
    dark: 0x55665F, legs: 0x2B3D37, appliance: 0xFFFFFF, metal: 0xA3B0AB, screen: 0x1C2A26,
    people: [0x3E5C54, 0x5E7D74, 0x2F4A43], head: 0xE6ECE9, tech: 0x2FB27E,
    mint: 0x45D099, mintDark: 0x1FA877, air: 0x7ED4E5, airDark: 0x2A9DB5, teal: 0x0F6E83,
    alert: 0xF2B84B, red: 0xEF6B5B, paper: 0xFFFFFF, note: 0xF2D36B, window: 0xA9CFD7,
    building: 0xE2E9E6, roof: 0xC3CEC9, panel: 0x1D3A4C, sun: 0xFFC766
  };

  function mat(color, o) {
    o = o || {};
    var m = new THREE.MeshStandardMaterial({
      color: color, roughness: o.r !== undefined ? o.r : .86, metalness: o.m !== undefined ? o.m : .03,
      emissive: o.e !== undefined ? o.e : 0x000000, emissiveIntensity: o.ei !== undefined ? o.ei : 1,
      transparent: !!o.t, opacity: o.o !== undefined ? o.o : 1, side: o.side || THREE.FrontSide,
      depthWrite: o.dw !== undefined ? o.dw : true
    });
    if (o.t) m.userData.baseO = m.opacity;
    return m;
  }
  function box(w, h, d, m, x, y, z, parent) {
    var b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    b.position.set(x || 0, y || 0, z || 0); b.castShadow = true; b.receiveShadow = true;
    if (parent) parent.add(b); return b;
  }
  function cyl(rt, rb, h, m, x, y, z, parent, s) {
    var c = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, s || 20), m);
    c.position.set(x || 0, y || 0, z || 0); c.castShadow = true; c.receiveShadow = true;
    if (parent) parent.add(c); return c;
  }
  function edges(w, h, d, color, opacity) {
    opacity = opacity === undefined ? 1 : opacity;
    var e = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d)),
      new THREE.LineBasicMaterial({ color: color, transparent: opacity < 1, opacity: opacity }));
    e.material.userData.baseO = opacity; return e;
  }
  function canvasTex(w, h, draw) {
    var c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
    var t = new THREE.CanvasTexture(c); t.encoding = THREE.sRGBEncoding; t.anisotropy = 4; return t;
  }
  function setOpacity(obj, o) {
    obj.traverse(function (n) {
      if (!n.material) return;
      (Array.isArray(n.material) ? n.material : [n.material]).forEach(function (m) {
        m.transparent = true; m.opacity = o * (m.userData.baseO !== undefined ? m.userData.baseO : 1);
      });
    });
    obj.visible = o > 0.01;
  }
  function person(color) {
    var g = new THREE.Group(), m = mat(color), skin = mat(P.head), dk = mat(P.legs);
    var legL = new THREE.Group(), legR = new THREE.Group(); legL.position.set(-.1, .62, 0); legR.position.set(.1, .62, 0);
    var lg = new THREE.BoxGeometry(.13, .62, .15);
    [legL, legR].forEach(function (p) { var l = new THREE.Mesh(lg, dk); l.position.y = -.31; l.castShadow = true; p.add(l); });
    var body = new THREE.Mesh(new THREE.CapsuleGeometry(.21, .42, 4, 10), m); body.position.y = 1.03; body.castShadow = true;
    var head = new THREE.Mesh(new THREE.SphereGeometry(.16, 16, 12), skin); head.position.y = 1.56; head.castShadow = true;
    g.add(legL, legR, body, head); g.userData = { legL: legL, legR: legR, head: head }; return g;
  }
  function pose(p, phase, moving) { var a = moving ? Math.sin(phase) * .55 : 0; p.userData.legL.rotation.x = a; p.userData.legR.rotation.x = -a; }
  function pathAt(pts, k) {
    var L = 0, sl = [], i;
    for (i = 1; i < pts.length; i++) { var l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); sl.push(l); L += l; }
    var d = clamp(k) * L;
    for (i = 0; i < sl.length; i++) {
      if (d <= sl[i] || i === sl.length - 1) {
        var f = sl[i] ? clamp(d / sl[i]) : 0, a = pts[i], b = pts[i + 1];
        return { x: lerp(a[0], b[0], f), z: lerp(a[1], b[1], f), dir: Math.atan2(b[0] - a[0], b[1] - a[1]) };
      }
      d -= sl[i];
    }
  }
  function fan(r, m) {
    var g = new THREE.Group(); cyl(r, r, .04, mat(P.dark), 0, 0, 0, g, 24);
    for (var i = 0; i < 3; i++) { var b = box(r * 1.7, .02, r * .35, m); b.rotation.y = i * Math.PI / 1.5; b.position.y = .03; g.add(b); }
    return g;
  }
  function points(n, color, size) {
    var geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    return new THREE.Points(geo, new THREE.PointsMaterial({ color: color, size: size, transparent: true, depthWrite: false }));
  }

  /* textures */
  function planTex(seed) {
    return canvasTex(512, 360, function (x, w, h) {
      var r = rng(seed); x.fillStyle = '#f4f7f5'; x.fillRect(0, 0, w, h); x.strokeStyle = '#2f433d'; x.lineWidth = 7; x.strokeRect(22, 22, w - 44, h - 44); x.lineWidth = 3.5;
      for (var i = 0; i < 4; i++) { var xx = 70 + r() * 370; x.beginPath(); x.moveTo(xx, 22); x.lineTo(xx, 110 + r() * 140); x.stroke(); }
      for (i = 0; i < 3; i++) { var yy = 90 + r() * 200; x.beginPath(); x.moveTo(22, yy); x.lineTo(150 + r() * 300, yy); x.stroke(); }
      x.lineWidth = 1.5; for (i = 0; i < 5; i++) { x.beginPath(); x.arc(70 + r() * 380, 60 + r() * 240, 16, 0, Math.PI / 2); x.stroke(); }
      x.fillStyle = '#2f433d'; x.font = '600 20px monospace'; x.fillText('A-10' + seed + '  FLOOR PLAN', 36, 58);
    });
  }
  function docTex(kind) {
    return canvasTex(256, 330, function (x, w, h) {
      x.fillStyle = '#ffffff'; x.fillRect(0, 0, w, h); x.fillStyle = '#2f433d'; x.fillRect(20, 20, 110, 14); x.fillStyle = '#9aa6a2'; x.fillRect(20, 42, 70, 6);
      for (var i = 0; i < 10; i++) {
        var y = 74 + i * 23;
        if (i === 6 && (kind === 'flag' || kind === 'bad')) { x.fillStyle = kind === 'flag' ? '#f2b84b' : '#ef6b5b'; x.fillRect(12, y - 7, w - 24, 21); }
        x.fillStyle = (i === 6 && kind !== 'raw' && kind !== 'ok') ? '#1a2420' : '#c5cfcb'; x.fillRect(20, y, 140, 8); x.fillRect(176, y, 40, 8);
        if (kind === 'ok') { x.strokeStyle = '#1fa877'; x.lineWidth = 4; x.beginPath(); x.moveTo(224, y + 3); x.lineTo(229, y + 8); x.lineTo(238, y - 2); x.stroke(); }
      }
      x.fillStyle = '#2f433d'; x.fillRect(150, h - 40, 86, 12);
    });
  }
  function qrTex(seed) {
    return canvasTex(128, 128, function (x, w, h) {
      var r = rng(seed); x.fillStyle = '#45d099'; x.fillRect(0, 0, w, h); x.fillStyle = '#fff'; x.fillRect(8, 8, 112, 112); x.fillStyle = '#0b1a16';
      for (var i = 0; i < 12; i++) for (var j = 0; j < 12; j++) if (r() > .52) x.fillRect(16 + i * 8, 16 + j * 8, 8, 8);
      [[16, 16], [80, 16], [16, 80]].forEach(function (p) { x.fillStyle = '#0b1a16'; x.fillRect(p[0], p[1], 32, 32); x.fillStyle = '#fff'; x.fillRect(p[0] + 5, p[1] + 5, 22, 22); x.fillStyle = '#0b1a16'; x.fillRect(p[0] + 10, p[1] + 10, 12, 12); });
    });
  }
  var TEX = {};
  function tex(name, make) { return TEX[name] || (TEX[name] = make()); }
  function docMesh(t) { var side = mat(0xE9EEEB); var top = new THREE.MeshStandardMaterial({ map: t, roughness: .9 }); return box(.85, .022, 1.1, [side, side, top, side, side, side]); }

  /* ---------------- stage: renderer, lights, labels, loop, drag ---------------- */
  function createStage(el, opts) {
    opts = opts || {};
    var view = document.createElement('div'); view.className = 'm3-view';
    var canvas = document.createElement('canvas'); canvas.className = 'm3-canvas';
    canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', opts.label || 'Interactive 3D scene. Drag to look around.');
    var layer = document.createElement('div'); layer.className = 'm3-labels';
    view.appendChild(canvas); view.appendChild(layer); el.insertBefore(view, el.firstChild);

    var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, preserveDrawingBuffer: !!opts.preserve });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, window.innerWidth < 700 ? 1.5 : 2));
    renderer.outputEncoding = THREE.sRGBEncoding; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = opts.exposure || .92;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.setClearColor(0x000000, 0);

    var scene = new THREE.Scene(); scene.fog = new THREE.Fog(P.bg, opts.fogNear || 24, opts.fogFar || 50);
    var camera = new THREE.PerspectiveCamera(opts.fov || 34, 16 / 9, .1, 160);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xaebcb6, .78));
    var sun = new THREE.DirectionalLight(0xfffaf0, 1.25); sun.position.set(7, 13, 8); sun.castShadow = true;
    var ss = opts.shadowSize || (window.innerWidth < 700 ? 1024 : 2048); sun.shadow.mapSize.set(ss, ss);
    var sc = opts.shadowExtent || 10;
    sun.shadow.camera.left = -sc; sun.shadow.camera.right = sc; sun.shadow.camera.top = sc; sun.shadow.camera.bottom = -sc; sun.shadow.camera.near = 1; sun.shadow.camera.far = 45;
    sun.shadow.bias = -.0004; sun.shadow.normalBias = .02; sun.shadow.radius = 4; scene.add(sun);
    var fill = new THREE.DirectionalLight(0xe6fbff, .28); fill.position.set(-8, 5, -6); scene.add(fill);

    if (opts.bare) {
      var sh = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ opacity: .12 }));
      sh.rotation.x = -Math.PI / 2; sh.position.y = -.4; sh.receiveShadow = true; scene.add(sh); scene.fog = null;
    } else {
      var ground = new THREE.Mesh(new THREE.CircleGeometry(44, 64), mat(P.ground, { r: 1 }));
      ground.rotation.x = -Math.PI / 2; ground.position.y = -.4; ground.receiveShadow = true; scene.add(ground);
      var grid = new THREE.GridHelper(88, 88, P.grid1, P.grid2); grid.position.y = -.395; scene.add(grid);
    }
    if (opts.platform !== false) {
      var pr = opts.platformRadius || 7.4;
      cyl(pr, pr + .2, .4, mat(P.plat, { r: .8 }), 0, -.2, 0, scene, 72);
      var ring = new THREE.Mesh(new THREE.TorusGeometry(pr + .02, .03, 8, 160), mat(P.mint, { e: P.mint, ei: .6 }));
      ring.rotation.x = Math.PI / 2; ring.position.y = .005; scene.add(ring);
    }

    var st = {
      el: el, view: view, canvas: canvas, renderer: renderer, scene: scene, camera: camera, layer: layer,
      W: 1, H: 1, visible: false, frameFn: null, onShow: null, onUser: null, dAz: 0, dEl: 0, zoom: 1, labels: [], started: false
    };

    var v3 = new THREE.Vector3();
    st.label = function (cls) {
      var e = document.createElement('div'); e.className = 'm3-lbl ' + cls; layer.appendChild(e);
      var L = {
        el: e, cls: cls, want: false, a: 0, pos: new THREE.Vector3(), text: '',
        show: function (p, text, a, newCls) {
          this.want = true; this.a = a === undefined ? 1 : a; this.pos.set(p[0], p[1], p[2]);
          if (text !== this.text) { this.text = text; e.textContent = text; }
          if (newCls && newCls !== this.cls) { e.classList.remove(this.cls); e.classList.add(newCls); this.cls = newCls; }
        }
      };
      st.labels.push(L); return L;
    };
    st.beginLabels = function () { for (var i = 0; i < st.labels.length; i++) st.labels[i].want = false; };
    st.project = function (pos) {
      v3.copy(pos).project(camera);
      return { x: (v3.x + 1) / 2 * st.W, y: (1 - v3.y) / 2 * st.H, behind: v3.z > 1 };
    };
    st.applyLabels = function () {
      for (var i = 0; i < st.labels.length; i++) {
        var L = st.labels[i];
        if (!L.want || L.a <= .01) { if (L.el.style.opacity !== '0') L.el.style.opacity = '0'; continue; }
        var p = st.project(L.pos); if (p.behind) { L.el.style.opacity = '0'; continue; }
        L.el.style.transform = 'translate(' + p.x.toFixed(1) + 'px,' + p.y.toFixed(1) + 'px) translate(-50%,-100%) translateY(-6px) scale(' + (.85 + .15 * L.a).toFixed(3) + ')';
        L.el.style.opacity = L.a.toFixed(3);
      }
    };
    st.setView = function (az, el2, r, target, offset) {
      camera.position.set(target.x + r * Math.sin(az) * Math.cos(el2), target.y + r * Math.sin(el2), target.z + r * Math.cos(az) * Math.cos(el2));
      camera.lookAt(target);
      if (offset && (offset[0] || offset[1])) camera.setViewOffset(st.W, st.H, offset[0] * st.W, offset[1] * st.H, st.W, st.H);
      else camera.clearViewOffset();
    };
    st.resize = function () {
      var r = view.getBoundingClientRect(); var w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
      if (w === st.W && h === st.H) return;
      st.W = w; st.H = h; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
      el.classList.toggle('m3-narrow', el.getBoundingClientRect().width < 760);
    };
    if (window.ResizeObserver) new ResizeObserver(st.resize).observe(el); else window.addEventListener('resize', st.resize);
    st.resize();

    function tick(ms) {
      requestAnimationFrame(tick);
      if (!st.visible || document.hidden || !st.frameFn) return;
      st.frameFn(ms / 1000);
    }
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) { var was = st.visible; st.visible = e.isIntersecting; if (st.visible && !was && st.onShow) st.onShow(); });
      }, { threshold: 0.05 }).observe(el);
    } else st.visible = true;
    requestAnimationFrame(tick);

    /* drag to orbit, pinch/ctrl-wheel to zoom */
    var drag = null;
    canvas.addEventListener('pointerdown', function (e) { drag = { x: e.clientX, y: e.clientY, id: e.pointerId, moved: false }; });
    window.addEventListener('pointermove', function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 5) { drag.moved = true; el.classList.add('m3-dragging'); if (st.onUser) st.onUser(); try { canvas.setPointerCapture(drag.id); } catch (_) { } }
      if (drag.moved) { st.dAz -= dx * .006; st.dEl = clamp(st.dEl + dy * .004, -.3, .45); drag.x = e.clientX; drag.y = e.clientY; }
    });
    window.addEventListener('pointerup', function () { drag = null; el.classList.remove('m3-dragging'); });
    canvas.addEventListener('wheel', function (e) { if (!e.ctrlKey) return; e.preventDefault(); st.zoom = clamp(st.zoom * (1 + e.deltaY * .01), .7, 1.4); if (st.onUser) st.onUser(); }, { passive: false });

    st.ready = function () {
      if (st.started) return; st.started = true;
      var poster = el.querySelector('.m3-poster'); if (poster) poster.classList.add('m3-poster-hide');
      el.classList.add('m3-live');
    };
    return st;
  }

  /* ================= SCENE 1: COMPUTER VISION ================= */
  function sVision(st) {
    var g = new THREE.Group(), S = { g: g };
    box(9, .1, 7, mat(P.floor), 0, .05, 0, g);
    box(9, 3, .18, mat(P.wall), 0, 1.5, -3.5, g);
    var w2 = mat(P.wall2);
    box(.18, 3, 4.1, w2, -4.5, 1.5, -1.45, g); box(.18, 3, 1.5, w2, -4.5, 1.5, 2.75, g); box(.18, .6, 1.4, w2, -4.5, 2.7, 1.3, g);
    box(2.3, 1.2, .05, mat(P.window, { r: .2, m: .1 }), -1.3, 1.85, -3.39, g);
    [[-1.9, -1.5], [1.3, -1.5], [.3, 1.3]].forEach(function (p) {
      var x = p[0], z = p[1];
      box(1.7, .07, .85, mat(P.desk), x, .76, z, g); box(1.5, .7, .7, mat(P.cab), x, .38, z, g);
      box(.62, .4, .04, mat(P.screen, { e: P.air, ei: .3 }), x, 1.02, z - .22, g); box(.5, .5, .5, mat(P.chair), x, .25, z + .75, g);
    });
    box(1.7, .45, .38, mat(P.appliance, { r: .45 }), 1.8, 2.45, -3.28, g); box(1.5, .04, .03, mat(P.dark), 1.8, 2.27, -3.08, g);
    S.led = new THREE.Mesh(new THREE.SphereGeometry(.045, 10, 8), mat(P.mint, { e: P.mint, ei: 2 })); S.led.position.set(2.5, 2.56, -3.08); g.add(S.led);
    S.air = points(110, P.airDark, .075); S.airSeed = []; for (var i = 0; i < 110; i++) S.airSeed.push([rng(i + 3)(), rng(i + 99)()]); g.add(S.air);
    var cam = new THREE.Group(); cam.position.set(-4.25, 2.75, -3.25); g.add(cam); box(.08, .3, .08, mat(P.dark), 0, .15, 0, cam);
    var cb = new THREE.Group(); cam.add(cb); box(.24, .24, .55, mat(P.appliance, { r: .4 }), 0, 0, 0, cb);
    cyl(.08, .08, .06, mat(P.screen), 0, 0, .3, cb).rotation.x = Math.PI / 2; cb.lookAt(new THREE.Vector3(.8, -2.75, 3.5).add(cam.position));
    var cg = new THREE.ConeGeometry(3.4, 7.2, 32, 1, true); cg.rotateX(-Math.PI / 2); cg.translate(0, 0, 3.6);
    S.cone = new THREE.Mesh(cg, new THREE.MeshBasicMaterial({ color: P.mint, transparent: true, opacity: .16, side: THREE.DoubleSide, depthWrite: false }));
    S.cone.position.copy(cam.position); S.cone.lookAt(.6, 0, .6); g.add(S.cone);
    S.people = P.people.map(function (c) { var p = person(c); g.add(p); return p; });
    S.paths = [[[-1.9, -.7], [-3.0, .4], [-4.1, 1.3], [-6.4, 1.3]], [[1.3, -.7], [0, .4], [-2.6, 1.1], [-4.1, 1.3], [-6.4, 1.3]], [[.3, 2.1], [-2, 1.8], [-4.1, 1.3], [-6.4, 1.3]]];
    S.boxes = S.people.map(function () { var e = edges(.8, 1.95, .8, P.mintDark); g.add(e); return e; });
    S.waste = new THREE.PointLight(0xff5a3c, 0, 9, 1.6); S.waste.position.set(0, 2.3, 0); g.add(S.waste);
    S.L = { people: st.label('mint'), ac: st.label('air'), cost: st.label('red'), alert: st.label('alert'), mail: st.label('dark'), ids: [st.label('mint'), st.label('mint'), st.label('mint')] };
    S.update = function (mode, tm, T) {
      var prob = mode === 'problem', s0 = prob ? 1.0 : .3, stg = .45, dur = prob ? 2.6 : 1.7, inRoom = 0;
      S.people.forEach(function (p, i) {
        var k = seg(tm, s0 + i * stg, s0 + i * stg + dur), q = pathAt(S.paths[i], k);
        p.position.set(q.x, .1, q.z); p.rotation.y = k > 0 ? q.dir : Math.PI; pose(p, T * 9 + i * 2, k > 0 && k < 1);
        p.visible = q.x > -5.2; var inside = q.x > -4.45; if (p.visible && inside) inRoom++;
        var bx = S.boxes[i]; bx.visible = !prob && p.visible && inside && tm > .3; bx.position.set(q.x, 1.08, q.z);
        if (bx.visible) S.L.ids[i].show([q.x, 2.2, q.z], 'ID ' + (17 + i * 4) + ' · 0.9' + (4 - i), seg(tm, .3, .6));
      });
      var emptyAt = s0 + 2 * stg + dur, empty = tm >= emptyAt, alertAt = emptyAt + .5, offAt = alertAt + 1.0;
      var ac = prob ? 1 : 1 - seg(tm, offAt, offAt + .6);
      var pos = S.air.geometry.attributes.position;
      for (var i = 0; i < pos.count; i++) {
        var a = S.airSeed[i][0], b = S.airSeed[i][1], u = frac(T * .33 + a);
        pos.setXYZ(i, 1.8 + (b - .5) * 1.5 + Math.sin(u * 5 + a * 9) * .12, 2.22 - u * 1.7 - Math.sin(u * 3) * .1, -3.05 + u * 2.6 + Math.sin(u * 7 + b * 6) * .12);
      }
      pos.needsUpdate = true; S.air.material.opacity = .9 * ac; S.air.visible = ac > .02;
      S.led.material.emissive.setHex(ac > .5 ? P.mint : 0x1a1f1d); S.led.material.color.setHex(ac > .5 ? P.mint : P.dark);
      S.waste.intensity = prob && empty ? (2.6 + .8 * Math.sin(T * 4)) * seg(tm, emptyAt, emptyAt + 1) : 0;
      S.cone.visible = !prob; S.cone.material.opacity = .16 * seg(tm, 0, .6) * (1 - .4 * seg(tm, offAt, offAt + 1));
      S.L.people.show([-4.25, 3.25, -3.25], 'PEOPLE ' + inRoom, 1, inRoom === 0 ? 'alert' : 'mint');
      S.L.ac.show([1.8, 2.95, -3.28], ac > .5 ? 'AC-02 · ON' : 'AC-02 · OFF', 1, ac > .5 ? 'air' : 'dark');
      var mins, cost;
      if (prob) {
        mins = empty ? (tm - emptyAt) * 20 : 0; cost = mins / 60 * 132;
        if (empty) S.L.cost.show([0, 3.6, 0], 'EMPTY ROOM · AC ON · Rs ' + cost.toFixed(0) + ' WASTED', seg(tm, emptyAt, emptyAt + .4), 'red');
      } else {
        var run = empty ? (Math.min(tm, offAt) - emptyAt) * 16.7 : 0; mins = run / 60; cost = run / 3600 * 132;
        if (tm >= alertAt) S.L.alert.show([1.8, 3.55, -3.28], tm < offAt ? 'ALERT · EMPTY ROOM, AC ON' : 'RESOLVED · AC SWITCHED OFF', seg(tm, alertAt, alertAt + .3), tm < offAt ? 'alert' : 'mint');
        if (tm >= alertAt + .25) S.L.mail.show([-1.3, 3.05, -3.3], 'EMAIL SENT · SNAPSHOT ATTACHED', seg(tm, alertAt + .25, alertAt + .55));
      }
      S.metric = prob
        ? { k: 'Waste this evening', v: 'Rs ' + cost.toFixed(0), tone: 'red', n: empty ? 'Empty for ' + Math.floor(mins / 60) + 'h ' + String(Math.floor(mins % 60)).padStart(2, '0') + 'm · time-lapse' : 'People still at their desks' }
        : { k: tm < offAt ? 'Empty room detected' : 'Waste stopped at', v: 'Rs ' + cost.toFixed(2), tone: 'mint', n: tm < alertAt ? 'Counting people on CAM-03' : (tm < offAt ? 'Alert sent after 10 seconds' : 'AC off, event logged to the dashboard') };
    };
    return S;
  }

  /* ================= SCENE 2: DIGITAL TWINS ================= */
  function sTwin(st) {
    var g = new THREE.Group(), S = { g: g };
    var table = new THREE.Group(); g.add(table);
    box(4.4, .12, 2.7, mat(P.desk), 0, .8, 0, table);
    [[-2, -1.2], [2, -1.2], [-2, 1.2], [2, 1.2]].forEach(function (p) { box(.12, .8, .12, mat(P.dark), p[0], .4, p[1], table); });
    [[0x2f9e70, 1.55], [0x7ed4e5, 1.82], [0xf2b84b, 2.09], [0x6b7c76, 2.36]].forEach(function (b) { box(.24, .9, .7, mat(b[0]), b[1] - .6, 1.31, -.8, table); });
    var scat = [[-1.3, .87, .3, .3], [-.2, .875, -.2, -.25], [.9, .88, .5, .5], [-.7, .885, -.8, 1.2], [.4, .89, .9, -.8], [-2.9, .02, 1.6, .7], [2.8, .02, 2.2, -.4]];
    S.sheets = scat.map(function (s, i) {
      var m = new THREE.Mesh(new THREE.PlaneGeometry(1.25, .88), new THREE.MeshStandardMaterial({ map: planTex(i + 1), roughness: .95, side: THREE.DoubleSide, transparent: true }));
      m.castShadow = true; m.receiveShadow = true; g.add(m); m.userData.s = s; return m;
    });
    S.floors = []; var FW = 5.2, FD = 3.7, FH = .95;
    for (var i = 0; i < 4; i++) {
      var f = new THREE.Group(); g.add(f);
      var slab = box(FW, .05, FD, mat(P.air, { t: true, o: .22, dw: false }), 0, 0, 0, f); slab.castShadow = false;
      var e = edges(FW, FH, FD, P.teal, .75); e.position.y = FH / 2; f.add(e);
      var walls = new THREE.Group(); f.add(walls); var r = rng(i + 5);
      for (var k = 0; k < 3; k++) { var wv = box(.04, FH, FD * (.4 + r() * .5), mat(P.teal, { t: true, o: .16, dw: false }), -FW / 2 + .8 + r() * (FW - 1.6), FH / 2, -FD / 2 + FD * .3, walls); wv.castShadow = false; }
      for (k = 0; k < 2; k++) { var wh = box(FW * (.3 + r() * .4), FH, .04, mat(P.teal, { t: true, o: .16, dw: false }), -FW / 2 + FW * .35, FH / 2, -FD / 2 + .9 + r() * (FD - 1.8), walls); wh.castShadow = false; }
      f.userData = { walls: walls }; S.floors.push(f);
    }
    S.stair = edges(.8, 4 * FH, .8, 0xD08A12, .95); g.add(S.stair);
    S.room = box(1.4, .8, 1.15, mat(P.mint, { t: true, o: .6, e: P.mint, ei: .35, dw: false }), 0, 0, 0, g); S.room.castShadow = false;
    S.route = [[-1.3, -.9], [-1.3, .95], [2.1, .95], [2.1, 1.35]];
    S.dots = []; for (i = 0; i < 7; i++) { var d = new THREE.Mesh(new THREE.SphereGeometry(.07, 10, 8), mat(P.alert, { e: P.alert, ei: 1.2 })); g.add(d); S.dots.push(d); }
    S.panels = []; for (i = 0; i < 4; i++) for (var j = 0; j < 3; j++) { var p = box(1, .05, .62, mat(P.panel, { m: .35, r: .35 }), -1.8 + i * 1.2, 0, -.9 + j * .85, g); p.rotation.x = .32; S.panels.push(p); }
    S.L = { tag: st.label('dark'), q1: st.label('dark'), q2: st.label('dark'), q3: st.label('dark'), twin: st.label('air'), room: st.label('mint'), exit: st.label('alert'), pv: st.label('air') };
    S.update = function (mode, tm, T) {
      var prob = mode === 'problem', k1 = prob ? 0 : inout(seg(tm, .1, 1.5)), lift = prob ? 0 : ease(seg(tm, 1.2, 2.2)), exp = prob ? 0 : ease(seg(tm, 2.0, 2.8)) * .35;
      var tableS = 1 - ease(seg(tm, 0, .8)); table.visible = prob || tableS > .01; table.scale.setScalar(prob ? 1 : Math.max(.001, tableS));
      var fy = function (i) { return .12 + i * FH + i * exp; };
      S.sheets.forEach(function (m, i) {
        var s = m.userData.s, flutter = prob ? Math.sin(T * 1.5 + i) * .02 : 0;
        if (i < 4) {
          var ty = fy(i);
          m.position.set(lerp(s[0], 0, k1), lerp(s[1], ty + .035, k1) + Math.sin(k1 * Math.PI) * 1.2, lerp(s[2], 0, k1));
          m.rotation.set(-Math.PI / 2 + flutter, 0, lerp(s[3], 0, k1)); m.scale.set(lerp(1, FW / 1.25, k1), lerp(1, FD / .88, k1), 1);
          m.material.opacity = 1 - .75 * lift; m.visible = true;
        } else {
          m.position.set(s[0], s[1], s[2]); m.rotation.set(-Math.PI / 2, 0, s[3]); m.scale.set(1, 1, 1);
          m.material.opacity = prob ? 1 : 1 - seg(tm, 0, .5); m.visible = m.material.opacity > .01;
        }
      });
      S.floors.forEach(function (f, i) { f.position.y = fy(i); setOpacity(f, prob ? 0 : seg(tm, 1.1 + i * .12, 1.6 + i * .12)); f.userData.walls.scale.y = Math.max(.001, prob ? 0 : ease(seg(tm, 1.3 + i * .12, 2 + i * .12))); });
      setOpacity(S.stair, prob ? 0 : seg(tm, 2.2, 2.6)); S.stair.position.set(2.2, fy(0) + 2 * FH + 1.5 * exp, 1.35); S.stair.scale.y = 1 + exp * .5;
      var rp = prob ? 0 : seg(tm, 2.8, 3.1); setOpacity(S.room, rp * (.75 + .25 * Math.sin(T * 5))); S.room.position.set(-1.3, fy(1) + .42, -.9);
      var dv = !prob && tm > 3.4; S.dots.forEach(function (d, i) { d.visible = dv; if (dv) { var q = pathAt(S.route, frac(T * .35 + i / 7)); d.position.set(q.x, fy(0) + .12, q.z); } });
      var roofY = fy(3) + FH + .1;
      S.panels.forEach(function (p, i) { var s = prob ? 0 : ease(seg(tm, 4.1 + i * .07, 4.4 + i * .07)); p.visible = s > .01; p.scale.setScalar(Math.max(.001, s)); p.position.y = roofY + .2; });
      if (prob) {
        S.L.tag.show([-1.3, 1.05, .3], 'A-101 · GROUND FLOOR.PDF', seg(tm, .2, .5));
        S.L.q1.show([-2.2, 2.4, -.2], 'WHERE IS ROOM 204?', seg(tm, .9, 1.2)); S.L.q2.show([1.9, 2.8, .4], 'WHICH WAY IS THE EXIT?', seg(tm, 1.7, 2)); S.L.q3.show([.2, 3.4, -1.2], 'HOW MUCH ROOF FOR SOLAR?', seg(tm, 2.5, 2.8));
      } else {
        S.L.twin.show([-2.6, roofY + .6, -1.9], '3D TWIN · 4 FLOORS · SYNCED', seg(tm, 2, 2.3)); S.L.room.show([-1.3, fy(1) + 1.1, -.9], 'ROOM 204 · FOUND', rp);
        if (tm > 3.4) S.L.exit.show([2.2, fy(0) + 1.1, 1.35], 'EXIT → STAIR B', seg(tm, 3.4, 3.7));
        if (tm > 4.2) S.L.pv.show([1.4, roofY + .9, .6], 'ROOFTOP PV · 12 PANELS', seg(tm, 4.3, 4.6));
      }
      S.metric = prob ? { k: 'Your drawings today', v: '7 PDFs', tone: 'alert', n: 'Scattered, flat and slow to search when it matters' }
        : { k: 'Your building today', v: tm < 2.8 ? 'Building…' : '1 live model', tone: 'mint', n: 'Search rooms, trace exits, plan the roof' };
    };
    return S;
  }

  /* ================= SCENE 3: AI AGENTS ================= */
  function sAgents(st) {
    var g = new THREE.Group(), S = { g: g };
    var desk = new THREE.Group(); g.add(desk);
    box(4.6, .12, 2.4, mat(P.desk), 0, .8, 0, desk);
    [[-2.1, -1], [2.1, -1], [-2.1, 1], [2.1, 1]].forEach(function (p) { box(.12, .8, .12, mat(P.dark), p[0], .4, p[1], desk); });
    function tray(x, z, c) {
      var t = new THREE.Group(); t.position.set(x, .86, z); var m = mat(c);
      box(1.1, .04, 1.3, m, 0, 0, 0, t); box(1.1, .16, .04, m, 0, .08, .65, t); box(1.1, .16, .04, m, 0, .08, -.65, t); box(.04, .16, 1.3, m, .55, .08, 0, t); box(.04, .16, 1.3, m, -.55, .08, 0, t);
      desk.add(t); return t;
    }
    tray(-1.2, 0, P.dark); tray(1.4, .1, P.mintDark);
    var raw = tex('docRaw', function () { return docTex('raw'); }); S.pile = []; var r = rng(7);
    for (var i = 0; i < 34; i++) { var d = docMesh(raw); d.userData = { x: -1.2 + (r() - .5) * .18, z: (r() - .5) * .18, ry: (r() - .5) * .35 }; d.position.set(d.userData.x, .9 + i * .024, d.userData.z); d.rotation.y = d.userData.ry; desk.add(d); S.pile.push(d); }
    S.bad = docMesh(tex('docBad', function () { return docTex('bad'); })); desk.add(S.bad);
    S.clerk = person(P.people[2]); S.clerk.position.set(-1.2, .1, 1.6); S.clerk.rotation.y = Math.PI; g.add(S.clerk);
    var line = new THREE.Group(); g.add(line);
    box(9.4, .32, 1.2, mat(P.dark), 0, .5, 0, line);
    box(9.4, .02, 1.05, mat(0x3a4843), 0, .67, 0, line);
    for (i = 0; i < 16; i++) box(.04, .021, 1.05, mat(0x5e6c67), -4.5 + i * .6, .68, 0, line);
    var arch = new THREE.Group(); line.add(arch);
    box(.22, 2.3, .22, mat(P.metal), 0, 1.15, -.85, arch); box(.22, 2.3, .22, mat(P.metal), 0, 1.15, .85, arch); box(.3, .26, 1.95, mat(P.mint, { e: P.mint, ei: .45 }), 0, 2.3, 0, arch);
    S.scan = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.5), new THREE.MeshBasicMaterial({ color: P.mint, transparent: true, opacity: .24, side: THREE.DoubleSide, depthWrite: false }));
    S.scan.rotation.y = Math.PI / 2; S.scan.position.set(0, 1.45, 0); line.add(S.scan);
    S.scanLine = box(.05, .03, 1.6, mat(P.mintDark, { e: P.mint, ei: 1.5 }), 0, 1, 0, line);
    S.tex = { raw: raw, ok: tex('docOk', function () { return docTex('ok'); }), flag: tex('docFlag', function () { return docTex('flag'); }) };
    S.flow = []; for (i = 0; i < 7; i++) { var fd = docMesh(raw); line.add(fd); S.flow.push(fd); }
    S.stack = new THREE.Group(); line.add(S.stack);
    S.approver = person(P.people[0]); S.approver.position.set(4.6, .1, 1.6); S.approver.rotation.y = Math.PI * 1.1; line.add(S.approver);
    S.L = { count: st.label('dark'), bad: st.label('red'), scan: st.label('mint'), flag: st.label('alert'), stack: st.label('dark'), human: st.label('mint') };
    S.update = function (mode, tm, T) {
      var prob = mode === 'problem'; desk.visible = prob; line.visible = !prob;
      if (prob) {
        S.pile.forEach(function (d, i) { d.rotation.y = d.userData.ry + Math.sin(T * 1.3 + i * .3) * .015 * (i / 34); });
        var k = inout(seg(tm, 2.2, 3.4)), top = .9 + 34 * .024;
        S.bad.position.set(lerp(-1.2, 1.4, k), lerp(top + .02, .92, k) + Math.sin(k * Math.PI) * .8, lerp(0, .1, k)); S.bad.rotation.set(0, lerp(.2, -.1, k), Math.sin(k * Math.PI) * .3);
        S.clerk.userData.head.rotation.z = Math.sin(T * 2) * .12;
        S.L.count.show([-1.2, 2.45, 1.6], 'CHECKED BY HAND · 3 OF 40', seg(tm, .4, .7));
        if (tm > 2.4) S.L.bad.show([1.4, 1.7, .1], 'OVERPRICED LINE · APPROVED ANYWAY', seg(tm, 3.2, 3.5));
        S.metric = { k: 'Quotations checked', v: '3 of 40', tone: 'red', n: tm < 3.3 ? 'Line by line, by hand, for days' : 'An overpriced item slipped through' };
      } else {
        S.scanLine.position.y = .75 + (Math.sin(T * 3) * .5 + .5) * 1.35;
        var passed = 0, flagUp = 0;
        S.flow.forEach(function (d, i) {
          var t0 = .3 + i * .45, k = clamp((tm - t0) * 2.6 / 8), x = -4.4 + k * 8, isFlag = i === 3;
          var want = x > 0 ? (isFlag ? S.tex.flag : S.tex.ok) : S.tex.raw; if (d.material[2].map !== want) d.material[2].map = want;
          if (tm < t0) { d.visible = false; return; }
          d.visible = true;
          if (isFlag && x > .9) { var f = ease(seg(tm, t0 + 2.04, t0 + 2.6)); flagUp = f; d.position.set(.9 + f * .3, .7 + f * 1.6, f * .2); d.rotation.set(f * 1.1, 0, 0); return; }
          if (k >= 1) { d.visible = false; passed++; return; }
          d.position.set(x, .7, 0); d.rotation.set(0, 0, 0);
        });
        while (S.stack.children.length < passed) { var sd = docMesh(S.tex.ok); sd.position.set(4.35, .7 + S.stack.children.length * .03, 0); S.stack.add(sd); }
        while (S.stack.children.length > passed) S.stack.remove(S.stack.children[S.stack.children.length - 1]);
        S.L.scan.show([-1.7, 1.9, .5], 'AI CHECKS EVERY LINE', seg(tm, .2, .5));
        if (flagUp > .05) S.L.flag.show([1.5, 3.35, .4], 'LINE 7 · 3.2× PAST RATE · FLAGGED', flagUp);
        if (passed > 0) S.L.stack.show([4.35, 1.3, 0], 'READY FOR APPROVAL · ' + passed, 1);
        if (tm > 4.3) S.L.human.show([4.6, 2.35, 1.6], 'A PERSON APPROVES EVERY SPEND', seg(tm, 4.3, 4.6));
        var checked = S.flow.filter(function (d, i) { return tm > .3 + i * .45 + 1.69; }).length;
        S.metric = { k: 'Quotations checked', v: checked + ' of 7', tone: 'mint', n: flagUp > .05 ? '1 flagged for a person to review' : 'Rates compared with past orders' };
      }
    };
    return S;
  }

  /* ================= SCENE 4: FACILITY PORTALS ================= */
  function sPortal(st) {
    var g = new THREE.Group(), S = { g: g };
    box(10, .1, 7, mat(P.floor), 0, .05, 0, g); box(10, 3, .18, mat(P.wall), 0, 1.5, -3.5, g);
    box(.3, .3, 7, mat(P.metal), -4.9, 2.6, 0, g);
    var ahu = new THREE.Group(); ahu.position.set(-3, 0, -1.9); g.add(ahu); box(1.8, 1.2, 1, mat(P.appliance, { r: .5 }), 0, .7, 0, ahu);
    S.fan1 = fan(.42, mat(P.dark)); S.fan1.rotation.x = Math.PI / 2; S.fan1.position.set(-.35, .7, .52); ahu.add(S.fan1);
    var pump = new THREE.Group(); pump.position.set(.2, 0, -.6); g.add(pump); box(1.4, .25, .7, mat(P.dark), 0, .2, 0, pump);
    cyl(.26, .26, .9, mat(0x2f9e70, { r: .5 }), -.2, .62, 0, pump).rotation.z = Math.PI / 2; cyl(.38, .38, .3, mat(0x3f7f66), .45, .62, 0, pump).rotation.z = Math.PI / 2;
    cyl(.1, .1, 2.4, mat(P.metal, { m: .4, r: .4 }), .45, 1.8, 0, pump); cyl(.1, .1, 2.8, mat(P.metal, { m: .4, r: .4 }), .45, .62, -1.4, pump).rotation.x = Math.PI / 2;
    S.pl = new THREE.Mesh(new THREE.SphereGeometry(.08, 12, 10), mat(P.red, { e: P.red, ei: 2 })); S.pl.position.set(-.2, 1.0, 0); pump.add(S.pl);
    var panel = new THREE.Group(); panel.position.set(3.1, 0, -2.9); g.add(panel); box(1.3, 2.2, .45, mat(0x7a8a84), 0, 1.2, 0, panel);
    for (var i = 0; i < 3; i++) for (var j = 0; j < 4; j++) { var l = new THREE.Mesh(new THREE.SphereGeometry(.035, 8, 6), mat(P.mint, { e: P.mint, ei: 1.5 })); l.position.set(-.35 + i * .35, 1.8 - j * .25, .24); panel.add(l); }
    var ch = new THREE.Group(); ch.position.set(2.7, 0, 1.1); g.add(ch); box(2.2, 1.1, 1.1, mat(0xeef2f0, { r: .5 }), 0, .65, 0, ch);
    S.fan2 = fan(.35, mat(P.dark)); S.fan2.position.set(-.5, 1.22, 0); ch.add(S.fan2); S.fan3 = fan(.35, mat(P.dark)); S.fan3.position.set(.5, 1.22, 0); ch.add(S.fan3);
    S.leak = points(40, P.airDark, .07); g.add(S.leak);
    S.puddle = new THREE.Mesh(new THREE.CircleGeometry(.8, 32), new THREE.MeshBasicMaterial({ color: 0x5aa9bd, transparent: true, opacity: .4, depthWrite: false }));
    S.puddle.rotation.x = -Math.PI / 2; S.puddle.position.set(.4, .11, .1); g.add(S.puddle);
    S.puffs = []; for (i = 0; i < 6; i++) { var pf = new THREE.Mesh(new THREE.SphereGeometry(.22, 12, 10), new THREE.MeshBasicMaterial({ color: 0x7e8c87, transparent: true, depthWrite: false })); g.add(pf); S.puffs.push(pf); }
    var noteM = mat(P.note, { side: THREE.DoubleSide }), r = rng(21);
    S.notes = []; for (i = 0; i < 11; i++) {
      var n = new THREE.Mesh(new THREE.PlaneGeometry(.3, .3), noteM.clone()), onWall = i < 4;
      n.userData.p = onWall ? [-2.4 + i * 1.5, 1.4 + r() * .8, -3.39, 0, 0, (r() - .5) * .4] : [-4 + r() * 8, .12, -2 + r() * 4.5, -Math.PI / 2, 0, r() * 6];
      n.castShadow = true; g.add(n); S.notes.push(n);
    }
    S.qrs = [[-3, 1.1, -1.38], [-.2, .62, -.33], [3.1, 1.6, -2.66], [2.7, .75, 1.67]].map(function (p, i) {
      var q = new THREE.Mesh(new THREE.PlaneGeometry(.36, .36), new THREE.MeshStandardMaterial({ map: qrTex(i + 2), roughness: .6 }));
      q.position.set(p[0], p[1], p[2]); g.add(q); return q;
    });
    S.tech = person(P.tech); g.add(S.tech);
    S.phone = new THREE.Group(); box(.14, .26, .02, mat(P.screen), 0, 0, 0, S.phone); var scr = box(.12, .22, .005, mat(P.mint, { e: P.mint, ei: 1 }), 0, 0, .012, S.phone); scr.castShadow = false; g.add(S.phone);
    var bg = new THREE.ConeGeometry(.3, 1, 20, 1, true); bg.rotateX(-Math.PI / 2); bg.translate(0, 0, .5);
    S.beam = new THREE.Mesh(bg, new THREE.MeshBasicMaterial({ color: P.mint, transparent: true, opacity: .3, side: THREE.DoubleSide, depthWrite: false })); g.add(S.beam);
    S.L = { over: st.label('red'), who: st.label('dark'), notes: st.label('dark'), wo: st.label('mint'), r1: st.label('dark'), r2: st.label('dark'), r3: st.label('dark') };
    S.update = function (mode, tm, T) {
      var prob = mode === 'problem';
      S.fan1.rotation.y = T * 6; S.fan2.rotation.y = T * 7; S.fan3.rotation.y = T * 7.4;
      var fixed = !prob && tm > 4.0, leakOn = prob ? 1 : 1 - seg(tm, 3.5, 4.0);
      S.pl.material.emissive.setHex(fixed ? P.mint : P.red); S.pl.material.color.setHex(fixed ? P.mint : P.red); S.pl.material.emissiveIntensity = fixed ? 1.5 : (Math.sin(T * 8) > 0 ? 2.5 : .3);
      var lp = S.leak.geometry.attributes.position;
      for (var i = 0; i < lp.count; i++) { var u = frac(T * .9 + i / lp.count); lp.setXYZ(i, .55 + Math.sin(i * 7) * .08, .62 - u * .5, .05 + Math.cos(i * 3) * .08); }
      lp.needsUpdate = true; S.leak.material.opacity = .9 * leakOn; S.leak.visible = leakOn > .02;
      S.puddle.material.opacity = .4 * leakOn; S.puddle.scale.setScalar(.8 + .2 * leakOn);
      S.puffs.forEach(function (p, i) { var u = frac(T * .25 + i / 6); p.position.set(.2 + Math.sin(i * 2 + T * .5) * .3, 1.1 + u * 2.2, -.6 + Math.cos(i) * .2); p.scale.setScalar(.6 + u * 1.4); p.material.opacity = .3 * (1 - u) * leakOn; p.visible = leakOn > .02; });
      S.notes.forEach(function (n, i) { var q = n.userData.p, f = prob ? 0 : ease(seg(tm, i * .05, .8 + i * .05)); n.position.set(q[0], q[1] + f * 3, q[2] + f * .5); n.rotation.set(q[3] + f * 2, q[4], q[5] + f * 3); n.material.transparent = true; n.material.opacity = 1 - f; n.visible = f < .99; });
      S.qrs.forEach(function (q, i) { var s = prob ? 0 : ease(seg(tm, .6 + i * .35, .9 + i * .35)); q.visible = s > .01; q.scale.setScalar(Math.max(.001, s * (1 + .25 * Math.sin(Math.PI * s)))); });
      var tp, q;
      if (prob) { q = pathAt([[-2.8, 1.6], [.8, 1.4], [1.6, .4], [-1.2, 1.9], [-2.8, 1.6]], frac(tm / 5.2)); tp = { x: q.x, z: q.z, dir: q.dir, moving: true }; }
      else { var k = ease(seg(tm, .4, 2.3)); q = pathAt([[-2.8, 1.6], [-1, 1.3], [-.2, .55]], k); tp = { x: q.x, z: q.z, dir: k >= 1 ? Math.PI : q.dir, moving: k > 0 && k < 1 }; }
      S.tech.position.set(tp.x, .1, tp.z); S.tech.rotation.y = tp.dir; pose(S.tech, T * 9, tp.moving);
      var ph = !prob && tm > 2.3 ? ease(seg(tm, 2.3, 2.6)) : 0; S.phone.visible = ph > .01; S.phone.position.set(tp.x + .05, 1.25, tp.z - .28); S.phone.rotation.set(-.5, Math.PI, 0); S.phone.scale.setScalar(Math.max(.001, ph));
      var bm = !prob ? seg(tm, 2.6, 2.8) * (1 - seg(tm, 3.4, 3.6)) : 0; S.beam.visible = bm > .01; S.beam.material.opacity = .35 * bm;
      S.beam.position.copy(S.phone.position); S.beam.lookAt(S.qrs[1].position); S.beam.scale.set(1, 1, S.phone.position.distanceTo(S.qrs[1].position));
      if (prob) {
        S.L.over.show([.2, 2.25, -.6], 'PUMP P-2 · SERVICE OVERDUE 94 DAYS', seg(tm, .5, .8)); S.L.who.show([tp.x, 2.3, tp.z], 'WHO FIXED THIS LAST?', seg(tm, 1.5, 1.8)); S.L.notes.show([-1.5, 2.7, -3.3], 'SERVICE HISTORY ON STICKY NOTES', seg(tm, 2.4, 2.7));
      } else {
        if (tm > 2.9) S.L.wo.show([.2, 2.25, -.6], fixed ? 'WO-1042 · CLOSED · PHOTO LOGGED' : 'WO-1042 · PUMP P-2 · ASSIGNED', seg(tm, 2.9, 3.2), 'mint');
        if (tm > 4.5) { S.L.r1.show([-3, 1.9, -1.9], 'NEXT SERVICE · 12 OCT', seg(tm, 4.5, 4.8)); S.L.r2.show([3.1, 2.9, -2.9], 'INSPECTED · TODAY', seg(tm, 4.7, 5)); S.L.r3.show([2.7, 2.2, 1.1], 'NEXT SERVICE · 3 NOV', seg(tm, 4.9, 5.2)); }
      }
      S.metric = prob ? { k: 'Overdue jobs', v: 'Unknown', tone: 'red', n: 'History lives on paper and in chat threads' }
        : { k: 'Open work orders', v: tm < 2.9 ? '0' : (fixed ? '0 · closed' : '1'), tone: 'mint', n: tm < 2 ? 'Tagging every asset with a QR code' : 'Scan, assign, fix, log' };
    };
    return S;
  }

  /* ================= SCENE 5: ENERGY + SOLAR ================= */
  function sEnergy(st) {
    var g = new THREE.Group(), S = { g: g };
    var b = new THREE.Group(); b.position.set(-.8, 0, -.2); g.add(b);
    box(4.6, 3.2, 3.6, mat(P.building), 0, 1.6, 0, b); box(4.8, .12, 3.8, mat(P.roof), 0, 3.26, 0, b);
    var wm = mat(P.window, { r: .25, m: .15 }), i, f;
    for (f = 0; f < 3; f++) for (i = 0; i < 6; i++) { var w = box(.5, .55, .02, wm, -1.9 + i * .76, .65 + f * 1.0, 1.81, b); w.castShadow = false; }
    for (f = 0; f < 3; f++) for (i = 0; i < 4; i++) { var w2 = box(.02, .55, .5, wm, 2.31, .65 + f * 1.0, -1.2 + i * .8, b); w2.castShadow = false; }
    S.hvac = [-1.4, 0, 1.4].map(function (x) { box(.9, .5, .9, mat(P.appliance, { r: .5 }), x, 3.57, -1.15, b); var fn = fan(.32, mat(P.dark)); fn.position.set(x, 3.84, -1.15); b.add(fn); return fn; });
    S.heat = new THREE.Mesh(new THREE.PlaneGeometry(4.6, 3.6), new THREE.MeshBasicMaterial({ color: 0xff5a3c, transparent: true, opacity: .3, depthWrite: false }));
    S.heat.rotation.x = -Math.PI / 2; S.heat.position.set(0, 3.33, 0); b.add(S.heat);
    S.hw = points(70, 0xff7a4c, .09); b.add(S.hw);
    S.sunM = new THREE.Mesh(new THREE.SphereGeometry(.75, 24, 18), new THREE.MeshBasicMaterial({ color: P.sun })); S.sunM.position.set(4.8, 7.2, -5); g.add(S.sunM);
    S.halo = new THREE.Mesh(new THREE.SphereGeometry(1.4, 24, 18), new THREE.MeshBasicMaterial({ color: P.alert, transparent: true, opacity: .18, depthWrite: false })); S.halo.position.copy(S.sunM.position); g.add(S.halo);
    var py = new THREE.Group(); py.position.set(5, 0, 2.3); g.add(py); var pm = mat(0x8c9a95, { m: .5, r: .5 });
    [[-.35, -.35], [.35, -.35], [-.35, .35], [.35, .35]].forEach(function (p) { var l = box(.08, 4.6, .08, pm, p[0] * .5, 2.3, p[1] * .5, py); l.rotation.z = p[0] * .08; l.rotation.x = -p[1] * .08; });
    box(1.6, .08, .08, pm, 0, 4.2, 0, py); box(1.1, .08, .08, pm, 0, 3.5, 0, py);
    S.curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(4.3, 4.15, 2.3), new THREE.Vector3(3, 3.1, 2), new THREE.Vector3(1.5, 3.0, 1.6));
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(S.curve.getPoints(40)), new THREE.LineBasicMaterial({ color: 0x6b7c76 })));
    S.gridDots = []; for (i = 0; i < 14; i++) { var d = new THREE.Mesh(new THREE.SphereGeometry(.07, 10, 8), mat(P.alert, { e: P.alert, ei: 1.5 })); g.add(d); S.gridDots.push(d); }
    S.panels = []; for (i = 0; i < 5; i++) for (var j = 0; j < 2; j++) { var p = box(.8, .05, .58, mat(P.panel, { m: .35, r: .3 }), -1.75 + i * .87, 3.52, .35 + j * .72, b); p.rotation.x = .3; S.panels.push(p); }
    var rg = new THREE.BufferGeometry(); rg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(10 * 6), 3));
    S.rays = new THREE.LineSegments(rg, new THREE.LineBasicMaterial({ color: 0xf2a73b, transparent: true, opacity: .5 })); g.add(S.rays);
    S.sd = points(50, P.mintDark, .1); b.add(S.sd);
    S.b = b; S.L = { grid: st.label('alert'), heat: st.label('red'), pv: st.label('air'), hv: st.label('mint'), roof: st.label('dark') };
    S.update = function (mode, tm, T) {
      var prob = mode === 'problem', sol = prob ? 0 : ease(seg(tm, .5, 4));
      var fs = prob ? 16 : lerp(16, 6, ease(seg(tm, .4, 1.6))); S.hvac.forEach(function (fn, i) { fn.rotation.y = T * fs + i; });
      var heat = prob ? (.28 + .1 * Math.sin(T * 3)) * seg(tm, 0, 1) : .3 * (1 - ease(seg(tm, .2, 2))); S.heat.material.opacity = heat; S.heat.visible = heat > .01;
      var hp = S.hw.geometry.attributes.position;
      for (var i = 0; i < hp.count; i++) { var u = frac(T * .4 + i / hp.count), r = rng(i + 1); hp.setXYZ(i, (r() - .5) * 4.2 + Math.sin(u * 6 + i) * .1, 3.4 + u * 1.8, (r() - .5) * 3.2); }
      hp.needsUpdate = true; S.hw.material.opacity = Math.min(1, heat * 2.6); S.hw.visible = heat > .02;
      var gs = prob ? 1 : lerp(1, .35, sol), n = prob ? 14 : Math.round(lerp(14, 5, sol));
      S.gridDots.forEach(function (d, i) { d.visible = i < n; if (d.visible) d.position.copy(S.curve.getPoint(frac(T * .55 * gs + i / 14))); });
      var bp = S.b.position, ra = S.rays.geometry.attributes.position;
      S.panels.forEach(function (p, i) {
        var s = prob ? 0 : ease(seg(tm, .9 + i * .14, 1.25 + i * .14)); p.visible = s > .01; p.scale.setScalar(Math.max(.001, s));
        ra.setXYZ(i * 2, S.sunM.position.x, S.sunM.position.y, S.sunM.position.z); ra.setXYZ(i * 2 + 1, bp.x + p.position.x, bp.y + p.position.y, bp.z + p.position.z);
      });
      ra.needsUpdate = true; S.rays.material.opacity = prob ? 0 : .55 * seg(tm, 2.4, 3) * (.7 + .3 * Math.sin(T * 4)); S.rays.visible = !prob && tm > 2.4;
      var sp = S.sd.geometry.attributes.position;
      for (i = 0; i < sp.count; i++) { var u2 = frac(T * .5 + i / sp.count), r2 = rng(i + 40); sp.setXYZ(i, -1.75 + Math.floor(r2() * 5) * .87, 3.45 - u2 * 3.2, 1.85); }
      sp.needsUpdate = true; S.sd.material.opacity = prob ? 0 : .95 * seg(tm, 2.8, 3.3); S.sd.visible = !prob && tm > 2.8;
      S.halo.scale.setScalar(1 + .06 * Math.sin(T * 2));
      var load = prob ? 100 : lerp(100, 54, ease(seg(tm, 1.2, 5)));
      if (prob) { S.L.grid.show([4.9, 4.9, 2.3], 'GRID POWER · PEAK RATE', seg(tm, .4, .7)); S.L.heat.show([-.8, 4.7, -.2], 'CHILLERS FIGHTING THE SUN', seg(tm, 1.4, 1.7)); S.L.roof.show([-3.1, 1.8, 1.6], 'ROOF SITS EMPTY', seg(tm, 2.4, 2.7)); }
      else { S.L.hv.show([-.8, 4.55, -1.35], 'HVAC + BMS TUNED', seg(tm, .5, .8)); if (tm > 2) S.L.pv.show([.9, 4.4, .6], 'ROOFTOP PV · 10 PANELS', seg(tm, 2, 2.3)); S.L.grid.show([4.9, 4.9, 2.3], 'GRID DRAW ↓', seg(tm, 3.5, 3.8), 'mint'); }
      S.metric = { k: 'Grid draw at noon', v: prob ? 'Peak' : (load < 60 ? 'Lower' : 'Falling'), tone: prob ? 'red' : 'mint', bar: load, n: prob ? 'Paying peak rates to cool against the sun' : 'Audit fixes plus solar on the roof' };
    };
    return S;
  }

  /* ---------------- service definitions ---------------- */
  var DEFS = {
    vision: { name: 'Computer vision', tag: '01 · Computer vision', build: sVision, cam: { t: [-.2, 1.1, 0], r: 13.4, az: .62, el: .55 },
      p: { h: 'People leave.<br><em>The AC stays on.</em>', t: 'Rooms empty out at 6 pm and the cooling keeps running for hours. Nobody sees it until the bill.' },
      s: { h: 'Your CCTV<br><em>catches it in seconds.</em>', t: 'EnergyCam counts people on the cameras you already have, alerts your team with a snapshot, and logs when the AC goes off.' } },
    twin: { name: 'Digital twins', tag: '02 · Digital twins', build: sTwin, cam: { t: [0, 2.5, 0], r: 14.2, az: .72, el: .46 },
      p: { h: 'Drawings nobody<br><em>can find in time.</em>', t: 'Floor plans live in PDFs and binders. In an emergency, nobody can say where Room 204 is or how to get out.' },
      s: { h: 'Your building<br><em>in 3D, from its PDFs.</em>', t: 'We turn your drawings into a live 3D model. Search any room, trace exit routes and plan the roof for solar.' } },
    agents: { name: 'AI agents', tag: '03 · AI agents', build: sAgents, cam: { t: [.3, 1.1, 0], r: 11.6, az: .38, el: .5 },
      p: { h: 'Forty quotations.<br><em>No time to check.</em>', t: 'Checking every line by hand takes days, so overpriced items slip through and get approved.' },
      s: { h: 'AI checks every line.<br><em>A person approves.</em>', t: 'The agent reads each quotation, compares rates with past orders and flags anything unusual before money is spent.' } },
    portal: { name: 'Facility portals', tag: '04 · Facility portals', build: sPortal, cam: { t: [0, 1.1, -.5], r: 12, az: .55, el: .55 },
      p: { h: 'Maintenance<br><em>on sticky notes.</em>', t: 'Service history lives on paper and in chat threads. Jobs get missed until something breaks.' },
      s: { h: 'Scan the tag.<br><em>The job is logged.</em>', t: 'Every asset gets a QR tag. Technicians scan to open work orders, attach photos and get reminders on their phones.' } },
    energy: { name: 'Energy + solar', tag: '05 · Energy + solar', build: sEnergy, cam: { t: [.6, 2.4, 0], r: 14.2, az: .78, el: .34 },
      p: { h: 'Paying the grid<br><em>to fight the sun.</em>', t: 'Chillers and HVAC work hardest at noon, when grid power costs the most and the roof sits empty.' },
      s: { h: 'Tune the HVAC.<br><em>Put the sun to work.</em>', t: 'We audit your HVAC and BMS, then design rooftop solar sized to your real daytime load.' } }
  };
  var ORDER = ['vision', 'twin', 'agents', 'portal', 'energy'];
  var PAGES = { vision: 'services/computer-vision.html', twin: 'services/digital-twins.html', agents: 'services/ai-agents.html', portal: 'services/facility-portals.html', energy: 'services/energy-solar.html' };

  var ICON = {
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5v14l12-7z" fill="currentColor"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor"/></svg>',
    replay: '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.5-5.8"/><path d="M4 4v4h4"/></svg>'
  };

  /* ================= MimarScenes: problem -> solution stage ================= */
  function mountScenes(el) {
    var keys = (el.getAttribute('data-services') || ORDER.join(',')).split(',').map(function (s) { return s.trim(); }).filter(function (k) { return DEFS[k]; });
    var compact = keys.length === 1;
    var st = createStage(el, { label: 'Interactive 3D scene showing a building problem and its solution. Drag to look around.' });
    var list = keys.map(function (k) { var S = DEFS[k].build(st); S.g.visible = false; st.scene.add(S.g); return { key: k, def: DEFS[k], S: S }; });

    /* overlay UI */
    var ui = document.createElement('div'); ui.className = 'm3-ui';
    ui.innerHTML =
      '<div class="m3-cap"><div class="m3-chips"><span class="m3-tag"></span><span class="m3-mode"></span></div><h3 class="m3-h"></h3><p class="m3-p"></p></div>' +
      '<aside class="m3-metric" aria-live="polite"><div class="k"></div><div class="v"></div><div class="bar" hidden><i></i></div><div class="n"></div><div class="ill">Illustrative scene</div></aside>' +
      '<div class="m3-controls">' + (compact ? '' : '<div class="m3-tabs" role="tablist" aria-label="Services"></div>') +
      '<div class="m3-right"><div class="m3-seg" role="group" aria-label="Show problem or solution"><button type="button" class="p">Problem</button><button type="button" class="s">Solution</button></div>' +
      '<button type="button" class="m3-tour"></button></div></div>' +
      '<div class="m3-hint">Drag to look around</div><div class="m3-prog"><i></i></div>';
    el.appendChild(ui);
    if (compact) el.classList.add('m3-compact');
    var q = function (s) { return ui.querySelector(s); };
    var tabs = q('.m3-tabs');
    if (tabs) list.forEach(function (it, i) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 'm3-tab'; b.setAttribute('role', 'tab');
      b.innerHTML = '<span>0' + (ORDER.indexOf(it.key) + 1) + '</span>' + it.def.name;
      b.addEventListener('click', function () { user(); setSvc(i); }); tabs.appendChild(b);
    });
    var PROB_LEN = 5.6, SOL_LEN = 7.2;
    var state = { i: 0, mode: 'problem', modeStart: 0, svcStart: 0, tour: !reduceMotion, now: 0, first: true, lastUI: '' };
    function renderUI() {
      var it = list[state.i], m = state.mode === 'problem' ? it.def.p : it.def.s, key = state.i + state.mode;
      if (key === state.lastUI) return; state.lastUI = key;
      q('.m3-tag').textContent = it.def.tag; var md = q('.m3-mode'); md.textContent = state.mode === 'problem' ? 'The problem' : 'The solution'; md.className = 'm3-mode ' + state.mode;
      var h = q('.m3-h'); h.innerHTML = m.h; h.className = 'm3-h ' + state.mode; q('.m3-p').textContent = m.t;
      if (tabs) Array.prototype.forEach.call(tabs.children, function (b, i) { b.setAttribute('aria-selected', String(i === state.i)); });
      q('.m3-seg .p').setAttribute('aria-pressed', String(state.mode === 'problem')); q('.m3-seg .s').setAttribute('aria-pressed', String(state.mode === 'solution'));
    }
    function renderTour() { var b = q('.m3-tour'); b.innerHTML = (state.tour ? ICON.pause : ICON.play) + '<span>' + (state.tour ? 'Pause' : 'Play') + '</span>'; b.setAttribute('aria-pressed', String(state.tour)); b.setAttribute('aria-label', state.tour ? 'Pause the tour' : 'Play the tour'); }
    function setMode(m) { state.mode = m; state.modeStart = state.now; renderUI(); }
    function setSvc(i) { list[state.i].S.g.visible = false; state.i = i; list[i].S.g.visible = true; state.svcStart = state.now; st.dAz = 0; st.dEl = 0; setMode('problem'); }
    function user() { if (state.tour) { state.tour = false; renderTour(); } }
    q('.m3-seg .p').addEventListener('click', function () { user(); setMode('problem'); });
    q('.m3-seg .s').addEventListener('click', function () { user(); setMode('solution'); });
    q('.m3-tour').addEventListener('click', function () { state.tour = !state.tour; if (state.tour) setMode('problem'); renderTour(); });
    st.onUser = user;
    st.onShow = function () { state.modeStart = state.now; state.svcStart = state.now - 2; };
    list[0].S.g.visible = true; renderUI(); renderTour();
    if (reduceMotion) setMode('solution');

    var tgt = new THREE.Vector3(), capEl = q('.m3-cap'), mK = q('.m3-metric .k'), mV = q('.m3-metric .v'), mN = q('.m3-metric .n'), mBW = q('.m3-metric .bar'), mB = q('.m3-metric .bar i'), prog = q('.m3-prog i');
    function frame(T, tm, opt) {
      opt = opt || {};
      var it = list[state.i];
      st.beginLabels(); it.S.update(state.mode, tm, T);
      var c = it.def.cam, arrive = opt.still ? 1 : ease(seg(T - state.svcStart, 0, 1.8));
      var r = c.r * lerp(1.14, 1, arrive) * st.zoom, asp = st.W / st.H; if (asp < 1.25) r *= Math.min(1.9, 1.25 / asp * .95);
      var az = c.az + st.dAz + (opt.still ? 0 : Math.sin(T * .16) * .09) + lerp(-.18, 0, arrive), elv = clamp(c.el + st.dEl + (opt.still ? 0 : Math.sin(T * .11) * .02), .08, 1.2);
      tgt.set(c.t[0], c.t[1], c.t[2]);
      var wide = !el.classList.contains('m3-narrow') && !opt.still;
      st.setView(az, elv, r, tgt, wide ? [compact ? -.1 : -.12, compact ? 0 : .02] : null);
      st.renderer.render(st.scene, st.camera); st.applyLabels(); st.ready();
      var m = it.S.metric || { k: '', v: '', n: '' };
      if (mV.textContent !== m.v) mV.textContent = m.v; mV.className = 'v ' + (m.tone || ''); if (mK.textContent !== m.k) mK.textContent = m.k; if (mN.textContent !== m.n) mN.textContent = m.n;
      if (m.bar != null) { mBW.hidden = false; mB.style.width = m.bar.toFixed(0) + '%'; mB.className = m.tone === 'mint' ? 'mint' : ''; } else mBW.hidden = true;
      var ca = .55 + .45 * ease(seg(tm, 0, .5)); capEl.style.opacity = ca.toFixed(3); capEl.style.transform = 'translateY(' + ((1 - ca) * 10).toFixed(1) + 'px)';
      prog.style.width = state.tour ? (clamp(tm / (state.mode === 'problem' ? PROB_LEN : SOL_LEN)) * 100).toFixed(1) + '%' : '0%';
    }
    st.frameFn = function (T) {
      state.now = T; if (state.first) { state.first = false; state.modeStart = state.svcStart = T; }
      var tm = T - state.modeStart;
      if (state.tour) {
        if (state.mode === 'problem' && tm > PROB_LEN) { setMode('solution'); tm = 0; }
        else if (state.mode === 'solution' && tm > SOL_LEN) { if (list.length > 1) setSvc((state.i + 1) % list.length); else setMode('problem'); tm = 0; }
      }
      frame(T, tm);
    };
    return {
      /* used by our poster renderer: draw one exact frame with no UI */
      still: function (i, mode, tm) {
        el.classList.add('m3-clean'); st.resize();
        if (i !== state.i) { list[state.i].S.g.visible = false; state.i = i; list[i].S.g.visible = true; }
        state.tour = false; state.mode = mode; state.svcStart = -10; state.now = 20 + tm; st.frameFn = null; renderUI(); frame(20 + tm, tm, { still: true });
      }
    };
  }

  /* ================= MimarBuilding: hero with a hotspot per service ================= */
  function buildBuilding(st) {
    var g = new THREE.Group(), B = { g: g }, FH = 1.65, W = 7.6, D = 5.2, i, j;
    var slabM = mat(0xF3F6F4, { r: .7 }), colM = mat(0xD3DCD8), finM = mat(0xD4DDD9), edgeM = mat(P.mint, { e: P.mint, ei: .25 });
    for (i = 0; i <= 3; i++) {
      box(W + .2, .16, D + .2, slabM, 0, i * FH, 0, g);
      if (i < 3) box(W - .3, .012, D - .3, finM, 0, i * FH + .086, 0, g).castShadow = false;
      box(W + .22, .035, .035, edgeM, 0, i * FH + .05, D / 2 + .1, g).castShadow = false;
      box(.035, .035, D + .22, edgeM, W / 2 + .1, i * FH + .05, 0, g).castShadow = false;
    }
    for (i = 0; i < 3; i++) [-W / 2 + .1, W / 2 - .1].forEach(function (x) { [-D / 2 + .1, D / 2 - .1].forEach(function (z) { box(.16, FH - .16, .16, colM, x, i * FH + FH / 2, z, g); }); });
    var y0 = .09, y1 = FH + .09, y2 = 2 * FH + .09, y3 = 3 * FH + .09;
    /* ground floor: lobby + plant room (facility portals) */
    box(W - .3, FH - .16, .1, mat(P.wall2), 0, FH / 2, -D / 2 + .15, g);
    box(.1, FH - .16, D * .55, mat(P.wall2), .1, FH / 2, -D * .2, g);
    box(1.7, .55, .55, mat(P.desk), -2.4, y0 + .28, .9, g); box(1.75, .06, .65, mat(0xffffff), -2.4, y0 + .58, .9, g);
    var vis1 = person(P.people[1]); vis1.scale.setScalar(.7); vis1.position.set(-2.4, y0, 1.7); vis1.rotation.y = Math.PI; g.add(vis1);
    var pump = new THREE.Group(); pump.position.set(1.7, y0, -1.3); pump.scale.setScalar(.85); g.add(pump);
    box(1.4, .25, .7, mat(P.dark), 0, .13, 0, pump); cyl(.26, .26, .9, mat(0x2f9e70, { r: .5 }), -.2, .55, 0, pump).rotation.z = Math.PI / 2; cyl(.38, .38, .3, mat(0x3f7f66), .45, .55, 0, pump).rotation.z = Math.PI / 2;
    cyl(.09, .09, 1.3, mat(P.metal, { m: .4, r: .4 }), .45 * .85 + 1.7, y0 + 1.0, -1.3, g);
    box(1.6, .65, .9, mat(0xeef2f0), 2.7, y0 + .33, 1.2, g);
    B.fansG = [fan(.24, mat(P.dark)), fan(.24, mat(P.dark))]; B.fansG[0].position.set(2.3, y0 + .68, 1.2); B.fansG[1].position.set(3.1, y0 + .68, 1.2); g.add(B.fansG[0], B.fansG[1]);
    box(.8, 1.15, .3, mat(0x7a8a84), 3.2, y0 + .58, -2.2, g);
    [[1.5, y0 + .45, -.99], [2.7, y0 + .36, 1.66], [3.2, y0 + .7, -2.04]].forEach(function (p, k) { var qr = new THREE.Mesh(new THREE.PlaneGeometry(.28, .28), new THREE.MeshStandardMaterial({ map: qrTex(k + 7), roughness: .6 })); qr.position.set(p[0], p[1], p[2]); g.add(qr); });
    B.tech = person(P.tech); B.tech.scale.setScalar(.72); g.add(B.tech);
    /* floor 1 left: office with CCTV (computer vision) */
    [[-3.0, -1.3], [-1.55, -1.3], [-3.0, .6], [-1.55, .6]].forEach(function (p) {
      box(1.1, .06, .6, mat(P.desk), p[0], y1 + .55, p[1], g); box(1.0, .5, .5, mat(P.cab), p[0], y1 + .26, p[1], g);
      box(.45, .3, .03, mat(P.screen, { e: P.air, ei: .35 }), p[0], y1 + .74, p[1] - .17, g);
    });
    box(W / 2 - .3, FH - .16, .1, mat(P.wall), -W / 4, y1 + FH / 2 - .04, -D / 2 + .15, g);
    box(1.4, .38, .3, mat(P.appliance), -2.2, y1 + 1.2, -2.4, g);
    B.air = points(60, P.airDark, .07); g.add(B.air);
    var cam = new THREE.Group(); cam.position.set(-3.55, y1 + 1.3, -2.3); g.add(cam); box(.2, .2, .42, mat(P.appliance), 0, 0, 0, cam); cam.lookAt(-1.8, y1, .8);
    var cg = new THREE.ConeGeometry(2.1, 4.4, 28, 1, true); cg.rotateX(-Math.PI / 2); cg.translate(0, 0, 2.2);
    B.cone = new THREE.Mesh(cg, new THREE.MeshBasicMaterial({ color: P.mint, transparent: true, opacity: .16, side: THREE.DoubleSide, depthWrite: false })); B.cone.position.copy(cam.position); B.cone.lookAt(-2.0, y1, .7); g.add(B.cone);
    var p1 = person(P.people[0]); p1.scale.setScalar(.72); p1.position.set(-1.55, y1, 1.15); g.add(p1);
    B.box1 = edges(.55, 1.35, .55, P.mintDark); B.box1.position.set(-1.55, y1 + .68, 1.15); g.add(B.box1);
    /* floor 1 right: quotation review (AI agents) */
    var part = box(.05, FH - .2, D - .5, mat(P.air, { t: true, o: .3, dw: false }), .2, y1 + FH / 2 - .06, 0, g); part.castShadow = false;
    box(2.4, .07, 1.25, mat(P.desk), 2.0, y1 + .55, 0, g); box(.1, .55, .1, mat(P.dark), .95, y1 + .27, 0, g); box(.1, .55, .1, mat(P.dark), 3.05, y1 + .27, 0, g);
    for (i = 0; i < 7; i++) { var d = docMesh(tex('docRaw', function () { return docTex('raw'); })); d.scale.setScalar(.62); d.position.set(1.4, y1 + .6 + i * .016, .15); d.rotation.y = i * .08; g.add(d); }
    B.holo = new THREE.Mesh(new THREE.PlaneGeometry(.8, 1.04), new THREE.MeshBasicMaterial({ map: tex('docOk', function () { return docTex('ok'); }), transparent: true, opacity: .96, side: THREE.DoubleSide }));
    B.holo.position.set(2.4, y1 + 1.15, .1); g.add(B.holo);
    B.scan = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.3), new THREE.MeshBasicMaterial({ color: P.mint, transparent: true, opacity: .24, side: THREE.DoubleSide, depthWrite: false }));
    B.scan.rotation.x = -Math.PI / 2; g.add(B.scan);
    var p3 = person(P.people[2]); p3.scale.setScalar(.72); p3.position.set(2.0, y1, 1.15); p3.rotation.y = Math.PI; g.add(p3);
    /* floor 2: digital twin (wireframe floor) */
    box(W - .3, .02, D - .3, mat(P.air, { t: true, o: .3, dw: false }), 0, y2 + .02, 0, g).castShadow = false;
    [[-2.2, -1.25, 2.8, 2.3], [1.3, -1.25, 4.0, 2.3], [-1.7, 1.35, 3.8, 2.1], [2.1, 1.35, 2.6, 2.1]].forEach(function (rm) { var e = edges(rm[2], FH - .3, rm[3], P.teal, .85); e.position.set(rm[0], y2 + (FH - .3) / 2, rm[1]); g.add(e); });
    B.room = box(2.6, FH - .4, 2.1, mat(P.mint, { t: true, o: .5, dw: false }), -2.2, y2 + (FH - .4) / 2, -1.25, g); B.room.castShadow = false;
    B.route = [[-2.2, -.05], [-2.2, .2], [3.0, .2], [3.35, 2.2]];
    B.dots = []; for (i = 0; i < 9; i++) { var dt = new THREE.Mesh(new THREE.SphereGeometry(.07, 10, 8), mat(P.alert, { e: P.alert, ei: 1.2 })); g.add(dt); B.dots.push(dt); }
    /* roof: solar + HVAC (energy) */
    for (i = 0; i < 5; i++) for (j = 0; j < 3; j++) { var pn = box(.9, .05, .62, mat(P.panel, { m: .35, r: .3 }), -3.1 + i * 1.0, y3 + .32, -1.3 + j * .85, g); pn.rotation.x = .32; }
    B.hvac = [[2.3, -1.3], [3.2, -1.3]].map(function (p) { box(.8, .5, .8, mat(P.appliance, { r: .5 }), p[0], y3 + .3, p[1], g); var fn = fan(.28, mat(P.dark)); fn.position.set(p[0], y3 + .57, p[1]); g.add(fn); return fn; });
    B.sunM = new THREE.Mesh(new THREE.SphereGeometry(.7, 24, 18), new THREE.MeshBasicMaterial({ color: P.sun })); B.sunM.position.set(7, 9, -6.5); g.add(B.sunM);
    var halo = new THREE.Mesh(new THREE.SphereGeometry(1.3, 24, 18), new THREE.MeshBasicMaterial({ color: P.alert, transparent: true, opacity: .2, depthWrite: false })); halo.position.copy(B.sunM.position); g.add(halo);
    /* highlight frames, in ORDER: vision, twin, agents, portal, energy */
    var fr = function (w, h, d, x, y, z) { var e = edges(w, h, d, P.mintDark, 1); e.position.set(x, y, z); g.add(e); return e; };
    B.frames = [
      fr(W / 2 + .1, FH, D + .4, -W / 4, FH * 1.5, 0),
      fr(W + .4, FH, D + .4, 0, FH * 2.5, 0),
      fr(W / 2 + .1, FH, D + .4, W / 4, FH * 1.5, 0),
      fr(W + .4, FH, D + .4, 0, FH * .5, 0),
      fr(W + .4, .9, D + .4, 0, y3 + .45, 0)
    ];
    B.hot = [[-2.6, y1 + 1.8, -1.5], [-1.2, y2 + 1.5, .9], [2.0, y1 + 1.85, 0], [2.0, y0 + 1.45, -1.1], [-1.0, y3 + 1.05, .3]];
    B.update = function (T, active) {
      B.fansG.forEach(function (f, k) { f.rotation.y = T * (6 + k); }); B.hvac.forEach(function (f, k) { f.rotation.y = T * (7 + k); });
      var pos = B.air.geometry.attributes.position;
      for (var k = 0; k < pos.count; k++) { var u = frac(T * .4 + k / pos.count), r = rng(k + 5); pos.setXYZ(k, -2.2 + (r() - .5) * 1.1, y1 + 1.05 - u * .85, -2.2 + u * 1.5 + Math.sin(u * 6 + k) * .06); }
      pos.needsUpdate = true;
      B.cone.material.opacity = .12 + .06 * (Math.sin(T * 2) * .5 + .5) + (active === 0 ? .06 : 0);
      B.holo.position.y = y1 + 1.15 + Math.sin(T * 1.6) * .05; B.holo.rotation.y = .35 + Math.sin(T * .7) * .2;
      B.scan.position.set(2.4, y1 + .65 + (Math.sin(T * 2.2) * .5 + .5) * 1.0, .1);
      var q = pathAt([[.8, .6], [3.2, .4], [2.9, -.3], [.8, .6]], frac(T / 7)); B.tech.position.set(q.x, y0, q.z); B.tech.rotation.y = q.dir; pose(B.tech, T * 9, true);
      B.dots.forEach(function (d, k) { var p = pathAt(B.route, frac(T * .22 + k / 9)); d.position.set(p.x, y2 + .1, p.z); });
      setOpacity(B.room, .75 + .25 * Math.sin(T * 3));
      B.frames.forEach(function (f, k) { var tgt = active === k ? .95 : 0; f.userData.o = B.instant ? tgt : lerp(f.userData.o || 0, tgt, .14); setOpacity(f, f.userData.o * (.75 + .25 * Math.sin(T * 4))); });
    };
    return B;
  }

  function mountBuilding(el) {
    var base = el.getAttribute('data-base') || '';
    var st = createStage(el, { label: 'Interactive 3D model of a building showing where each Mimar AI service works. Drag to look around.', platformRadius: 6.6, shadowExtent: 9, fov: 32, exposure: .92, bare: true });
    var B = buildBuilding(st); st.scene.add(B.g);
    var desc = {
      vision: 'Cameras spot empty rooms with the AC on.', twin: 'Your PDFs, rebuilt as a live 3D model.', agents: 'Every quotation checked, line by line.',
      portal: 'QR tags, work orders and reminders.', energy: 'HVAC audits and rooftop solar.'
    };
    var layer = document.createElement('div'); layer.className = 'm3-hotspots'; el.appendChild(layer);
    var hs = ORDER.map(function (k, i) {
      var a = document.createElement('a'); a.className = 'm3-hs'; a.href = base + PAGES[k];
      a.innerHTML = '<span class="n">0' + (i + 1) + '</span><span class="tx"><span class="t">' + DEFS[k].name + '</span><span class="d">' + desc[k] + '</span></span>';
      a.addEventListener('mouseenter', function () { pick(i); }); a.addEventListener('focus', function () { pick(i); });
      layer.appendChild(a); return a;
    });
    var state = { active: 0, lastUser: -100, now: 0 };
    function pick(i) { state.active = i; state.lastUser = state.now; }
    st.onUser = function () { state.lastUser = state.now; };
    var tgt = new THREE.Vector3(0, 2.75, 0), hv = new THREE.Vector3();
    st.frameFn = function (T) {
      state.now = T;
      if (T - state.lastUser > 9 && !reduceMotion) state.active = Math.floor(T / 4.2) % 5;
      B.update(T, state.active);
      var asp = st.W / st.H, r = 19 * st.zoom; if (asp < 1.1) r *= Math.min(1.7, 1.1 / asp * 1.05);
      var az = .78 + (reduceMotion ? 0 : Math.sin(T * .12) * .32) + st.dAz, elv = clamp(.3 + st.dEl, .1, 1);
      st.setView(az, elv, r, tgt, null);
      st.renderer.render(st.scene, st.camera); st.ready();
      hs.forEach(function (a, i) {
        hv.set(B.hot[i][0], B.hot[i][1], B.hot[i][2]); var p = st.project(hv);
        a.style.transform = 'translate(' + p.x.toFixed(1) + 'px,' + p.y.toFixed(1) + 'px)';
        a.classList.toggle('on', i === state.active);
      });
    };
    return {
      still: function (T, active, keepHotspots) { if (!keepHotspots) el.classList.add('m3-clean-hs'); state.lastUser = 1e9; state.active = active; B.instant = true; st.frameFn(T); st.frameFn = null; }
    };
  }

  /* ---------------- auto mount (lazy, when near the viewport) ---------------- */
  var mounted = [];
  function init(el) {
    if (el.__m3) return el.__m3;
    try {
      el.__m3 = el.hasAttribute('data-mimar-building') ? mountBuilding(el) : mountScenes(el);
    } catch (err) { el.classList.add('m3-failed'); if (window.console) console.warn('Mimar 3D failed to start', err); el.__m3 = null; }
    mounted.push(el); return el.__m3;
  }
  function boot() {
    var els = document.querySelectorAll('[data-mimar-scenes],[data-mimar-building]');
    if (!els.length) return;
    if (!THREE || !webglOK()) { Array.prototype.forEach.call(els, function (e) { e.classList.add('m3-failed'); }); return; }
    THREE.ColorManagement.legacyMode = false;
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.unobserve(e.target); init(e.target); } }); }, { rootMargin: '300px 0px' });
      Array.prototype.forEach.call(els, function (e) { io.observe(e); });
    } else Array.prototype.forEach.call(els, init);
  }
  window.Mimar3D = { init: init, boot: boot };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
