"""140-H as a 3D twin: every floor, every room, who is in it and whether
its AC runs, live (Shamroze, 23 Nov 2026: "140-H ke andar 3D ka column
... poori building ka 3D structure, bilkul real lagna chahiye").

What it is, honestly: building.yaml's sketch of the building (places on
four floors, from the camera names, floors and pictures -- not a floor
plan), each room drawn as a glass box on its floor's slab, with the
cameras' live numbers in it: a figure for each person counted, the AC
unit lit when it runs, and red when it runs with nobody in. Turn it, zoom
it, lift one floor out, point at a room for its numbers. With a floor
plan (the fire-exit plans) the boxes take the rooms' real sizes and
places; nothing else changes.

No picture: the scene is drawn from numbers alone, in the viewer's
browser, with three.js from a CDN (pinned). On the Progress tab (behind
its own password) the five employees can be drawn in it too.
"""
import json

import building

THREE = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"
ORBIT = ("https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/"
         "OrbitControls.js")


def scene_data(b, latest=None, employees=None):
    """Everything the scene draws, as plain JSON-able numbers and names.

    latest: rows {room, status, people, ac_state, ac_units_on} (the
    dashboard's load_state); employees: [{code, place, how, colour}]."""
    live = {}
    for r in latest or []:
        live[r.get("room")] = r
    floors = building.floors(b)
    rooms = []
    for name, p in (b.get("places") or {}).items():
        p = p or {}
        x, y = (float(v) for v in (p.get("at") or (0, 0))[:2])
        r = live.get(name) or {}
        people = r.get("people")
        try:
            people = int(people) if people is not None and people == people \
                else None
        except (TypeError, ValueError):
            people = None
        units = r.get("ac_units_on")
        try:
            units = int(units) if units is not None and units == units \
                else None
        except (TypeError, ValueError):
            units = None
        rooms.append({
            "n": name, "f": building.level(b, p.get("floor")), "x": x, "y": y,
            "o": bool(p.get("outside")), "s": bool(p.get("stairs")),
            "st": r.get("status") or "unknown", "p": people,
            "ac": r.get("ac_state"), "u": units})
    links = [[a, z] for a, z in (tuple(l[:2]) for l in b.get("links") or [])]
    return {"floors": floors, "rooms": rooms, "links": links,
            "emp": list(employees or [])}


PALETTE = {
    "dark": {"bg1": "#151a22", "bg2": "#07080a", "slab": "#2a2d33",
             "edge": "#8a93a3", "glass": "#9fc4ff", "text": "#f0efec",
             "muted": "#a9a8a0", "occupied": "#3987e5", "empty": "#3a3d43",
             "unknown": "#2b2c2f", "waste": "#e5484d", "ac": "#3fd6e8",
             "outside": "#26332b", "person": "#f2c39b", "panel":
             "rgba(20,21,24,.82)", "line": "rgba(255,255,255,.12)"},
    "light": {"bg1": "#eef1f5", "bg2": "#d9dee6", "slab": "#f7f6f2",
              "edge": "#5d6470", "glass": "#7fa8e8", "text": "#0b0b0b",
              "muted": "#52514e", "occupied": "#2a78d6", "empty": "#d9d7cf",
              "unknown": "#e9e8e3", "waste": "#d03b3b", "ac": "#0fa3b8",
              "outside": "#cfe3cf", "person": "#b5774f", "panel":
              "rgba(252,252,251,.9)", "line": "rgba(11,11,11,.12)"},
}

_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<style>
html,body{margin:0;height:100%;background:transparent;font-family:Inter,
-apple-system,"Segoe UI",Roboto,sans-serif}
#wrap{position:relative;width:100%;height:__H__px;border-radius:16px;
overflow:hidden;background:radial-gradient(ellipse at 50% 30%,__BG1__,__BG2__)}
canvas{display:block}
.bar{position:absolute;left:12px;top:12px;display:flex;flex-wrap:wrap;gap:6px;
z-index:2}
.bar button{font:600 12px/1 inherit;padding:7px 11px;border-radius:99px;
border:1px solid __LINE__;background:__PANEL__;color:__TEXT__;cursor:pointer;
backdrop-filter:blur(6px)}
.bar button.on{background:__OCC__;color:#fff;border-color:transparent}
.key{position:absolute;left:12px;bottom:12px;display:flex;flex-wrap:wrap;
gap:6px 12px;padding:8px 11px;border-radius:12px;background:__PANEL__;
color:__MUTED__;font-size:11.5px;z-index:2;backdrop-filter:blur(6px);
max-width:calc(100% - 48px)}
.key i{display:inline-block;width:10px;height:10px;border-radius:3px;
margin-right:5px;vertical-align:-1px}
.tip{position:absolute;pointer-events:none;padding:8px 10px;border-radius:10px;
background:__PANEL__;color:__TEXT__;font-size:12px;line-height:1.45;
border:1px solid __LINE__;display:none;z-index:3;max-width:240px;
backdrop-filter:blur(6px)}
.tip b{font-size:13px}
.hint{position:absolute;right:14px;bottom:14px;color:__MUTED__;font-size:11px;
z-index:2;text-align:right}
@media (max-width:640px){.hint{display:none}}
.err{position:absolute;inset:0;display:none;align-items:center;
justify-content:center;color:__MUTED__;font-size:13px;padding:20px;
text-align:center}
</style></head><body>
<div id="wrap">
 <div class="bar" id="bar"></div>
 <div class="hint">drag to turn &middot; click it, then wheel to zoom</div>
 <div class="key">
  <span><i style="background:__OCC__"></i>people in</span>
  <span><i style="background:__EMPTY__"></i>empty</span>
  <span><i style="background:__WASTE__"></i>AC on, nobody in</span>
  <span><i style="background:__AC__"></i>AC running</span>
  <span><i style="background:__UNK__;outline:1px solid __LINE__"></i>not known</span>
  __EMPKEY__
 </div>
 <div class="tip" id="tip"></div>
 <div class="err" id="err">The 3D view needs a browser with WebGL.</div>
</div>
<script src="__THREE__"></script>
<script src="__ORBIT__"></script>
<script>
(function(){
const D = __DATA__;
const C = __COLS__;
const S = 3.4, CX = 6, CZ = 4.4;          // storey height, scene centre
const wrap = document.getElementById('wrap');
if (!window.THREE || !THREE.OrbitControls) {
  document.getElementById('err').style.display = 'flex'; return; }
let renderer;
try { renderer = new THREE.WebGLRenderer({antialias: true, alpha: true}); }
catch (e) { document.getElementById('err').style.display = 'flex'; return; }
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
renderer.setSize(wrap.clientWidth, wrap.clientHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputEncoding = THREE.sRGBEncoding;
wrap.insertBefore(renderer.domElement, wrap.firstChild);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, wrap.clientWidth /
  wrap.clientHeight, 0.1, 400);
camera.position.set(17, 15, 19);
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.08;
controls.target.set(0, S * 1.2, 0);
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 6; controls.maxDistance = 60;
controls.autoRotate = true; controls.autoRotateSpeed = 0.35;
// The wheel zooms only once the scene has been clicked: a page scrolled
// past it must not zoom it by accident.
controls.enableZoom = false;
renderer.domElement.addEventListener('pointerdown',
  () => { controls.autoRotate = false; controls.enableZoom = true; });
renderer.domElement.addEventListener('pointerleave',
  () => { controls.enableZoom = false; });

scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 0.75));
const sun = new THREE.DirectionalLight(0xffffff, 0.85);
sun.position.set(14, 30, 10); sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
const sc = sun.shadow.camera; sc.left = -16; sc.right = 16; sc.top = 16;
sc.bottom = -16; sc.near = 1; sc.far = 80;
scene.add(sun);

function col(c) { return new THREE.Color(c); }
function label(text, size, color) {
  const pad = 10, fs = 44;
  const cv = document.createElement('canvas'); const g = cv.getContext('2d');
  g.font = '600 ' + fs + 'px Inter, Segoe UI, sans-serif';
  const w = Math.ceil(g.measureText(text).width) + pad * 2;
  cv.width = w; cv.height = fs + pad * 2;
  g.font = '600 ' + fs + 'px Inter, Segoe UI, sans-serif';
  g.fillStyle = C.panel; const r = 16;
  g.beginPath(); g.moveTo(r, 0); g.arcTo(w, 0, w, cv.height, r);
  g.arcTo(w, cv.height, 0, cv.height, r); g.arcTo(0, cv.height, 0, 0, r);
  g.arcTo(0, 0, w, 0, r); g.fill();
  g.fillStyle = color || C.text; g.textBaseline = 'middle';
  g.fillText(text, pad, cv.height / 2 + 2);
  const tex = new THREE.CanvasTexture(cv); tex.anisotropy = 4;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({map: tex,
    depthTest: false, transparent: true}));
  sp.scale.set(size * w / cv.height, size, 1); sp.renderOrder = 10;
  return sp;
}
function rng(seed) { let s = seed % 2147483647; if (s <= 0) s += 2147483646;
  return () => (s = s * 16807 % 2147483647) / 2147483647; }
function hash(t) { let h = 7; for (const ch of t) h = (h * 31 +
  ch.charCodeAt(0)) % 1000003; return h; }

const groups = D.floors.map(() => new THREE.Group());
groups.forEach(g => scene.add(g));
const pick = [], pulses = [];
// the slabs: the ground floor wide enough for the street and the garden
D.floors.forEach((name, i) => {
  const g = groups[i], y = i * S;
  const wide = (name === 'Ground floor');
  const w = wide ? 14.6 : 9.6, d = wide ? 11.6 : 7.4;
  const cx = wide ? 5.8 : 6.1, cz = wide ? 4.1 : 4.8;
  const slab = new THREE.Mesh(new THREE.BoxGeometry(w, 0.14, d),
    new THREE.MeshStandardMaterial({color: col(C.slab), roughness: 0.92,
      metalness: 0.0, transparent: true, opacity: i === 0 ? 0.96 : 0.82}));
  slab.position.set(cx - CX, y - 0.07, cz - CZ); slab.receiveShadow = true;
  g.add(slab);
  // the building's own outline on every floor
  const bw = 8.6, bd = 6.8;
  const shell = new THREE.LineSegments(new THREE.EdgesGeometry(
    new THREE.BoxGeometry(bw, S * 0.82, bd)),
    new THREE.LineBasicMaterial({color: col(C.edge), transparent: true,
      opacity: 0.35}));
  shell.position.set(6.1 - CX, y + S * 0.41, 4.8 - CZ); g.add(shell);
  const tag = label(name, 0.42, C.muted);
  tag.position.set((wide ? cx + w / 2 : 6.1 + bw / 2) - CX + 0.4, y + 0.3,
    (wide ? cz - d / 2 : 4.8 - bd / 2) - CZ);
  g.add(tag);
});
// the ways between places, faint on the floor
const pos = {};
D.rooms.forEach(r => { pos[r.n] = [r.x - CX, r.f * S, r.y - CZ]; });
D.links.forEach(([a, z]) => {
  if (!pos[a] || !pos[z]) return;
  const pa = pos[a], pz = pos[z];
  const m = new THREE.Line(new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(pa[0], pa[1] + 0.03, pa[2]),
    new THREE.Vector3(pz[0], pz[1] + 0.03, pz[2])]),
    new THREE.LineDashedMaterial({color: col(C.edge), dashSize: 0.12,
      gapSize: 0.08, transparent: true, opacity: 0.45}));
  m.computeLineDistances();
  const ga = D.rooms.find(r => r.n === a), gz = D.rooms.find(r => r.n === z);
  (ga.f === gz.f ? groups[ga.f] : scene).add(m);
});
// the rooms
const personGeo = new THREE.CylinderGeometry(0.055, 0.07, 0.26, 10);
const headGeo = new THREE.SphereGeometry(0.06, 14, 10);
const personMat = new THREE.MeshStandardMaterial({color: col(C.person),
  roughness: 0.6});
D.rooms.forEach(r => {
  const g = groups[r.f] || scene, y = r.f * S;
  const x = r.x - CX, z = r.y - CZ;
  const waste = r.ac === 'on' && r.st === 'empty';
  const fill = waste ? C.waste : (r.st === 'occupied' ? C.occupied :
    (r.st === 'empty' ? C.empty : C.unknown));
  const w = r.o ? 1.25 : (r.s ? 0.8 : 1.05), d = r.o ? 1.0 : (r.s ? 0.8 : 0.86);
  const tile = new THREE.Mesh(new THREE.BoxGeometry(w, 0.05, d),
    new THREE.MeshStandardMaterial({color: col(fill), roughness: 0.55,
      emissive: col(fill), emissiveIntensity: r.st === 'occupied' ? 0.18 :
      (waste ? 0.35 : 0.02)}));
  tile.position.set(x, y + 0.03, z); tile.receiveShadow = true;
  tile.userData = r; g.add(tile); pick.push(tile);
  if (waste) pulses.push(tile.material);
  if (!r.o) {
    const h = r.s ? 2.6 : 1.05;
    const box = new THREE.Mesh(new THREE.BoxGeometry(w, h, d),
      new THREE.MeshPhysicalMaterial({color: col(C.glass), transparent: true,
        opacity: 0.11, roughness: 0.15, metalness: 0.1, depthWrite: false}));
    box.position.set(x, y + h / 2 + 0.05, z); box.userData = r;
    g.add(box); pick.push(box);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(
      box.geometry), new THREE.LineBasicMaterial({color: col(C.edge),
      transparent: true, opacity: 0.6}));
    edges.position.copy(box.position); g.add(edges);
    if (r.s) {   // the stairs: a few steps
      for (let k = 0; k < 6; k++) {
        const st = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.06, 0.12),
          new THREE.MeshStandardMaterial({color: col(C.edge)}));
        st.position.set(x, y + 0.1 + k * 0.38, z - 0.3 + k * 0.12);
        g.add(st);
      }
    }
  }
  // the AC unit on its back wall: lit when it runs
  if (r.ac === 'on' || r.ac === 'off') {
    const on = r.ac === 'on';
    const ac = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.12, 0.08),
      new THREE.MeshStandardMaterial({color: on ? col(C.ac) : col(C.edge),
        emissive: on ? col(waste ? C.waste : C.ac) : col('#000000'),
        emissiveIntensity: on ? 0.9 : 0}));
    ac.position.set(x, y + 0.88, z - d / 2 + 0.06); g.add(ac);
    if (on && waste) pulses.push(ac.material);
  }
  // a figure for each person counted (up to eight)
  const n = Math.min(8, r.p || 0); const rand = rng(hash(r.n));
  for (let k = 0; k < n; k++) {
    const px = x + (rand() - 0.5) * (w - 0.3), pz = z + (rand() - 0.5) *
      (d - 0.3);
    const body = new THREE.Mesh(personGeo, personMat);
    body.position.set(px, y + 0.18, pz); body.castShadow = true; g.add(body);
    const head = new THREE.Mesh(headGeo, personMat);
    head.position.set(px, y + 0.37, pz); head.castShadow = true; g.add(head);
  }
  const named = r.s || (r.p || 0) > 0 || r.ac === 'on' ||
    ['140-H Reception', 'Prompt Cafe', '140-H Entry Area'].includes(r.n);
  if (named) {
    const t = label(r.n + ((r.p || 0) > 0 ? '  ' + r.p : ''), 0.26,
      waste ? C.waste : C.text);
    t.position.set(x, y + (r.s ? 2.85 : 1.35), z); g.add(t);
  }
});
// the employees (Progress tab only)
(D.emp || []).forEach((e, i) => {
  const r = D.rooms.find(q => q.n === e.place); if (!r) return;
  const g = groups[r.f] || scene;
  const x = r.x - CX + ((i % 3) - 1) * 0.22, z = r.y - CZ +
    (Math.floor(i / 3) - 0.5) * 0.22, y = r.f * S;
  const ball = new THREE.Mesh(new THREE.SphereGeometry(0.13, 20, 16),
    new THREE.MeshStandardMaterial({color: col(e.colour), emissive:
      col(e.colour), emissiveIntensity: e.how === 'possible' ? 0.25 : 0.7,
      transparent: e.how === 'possible', opacity: e.how === 'possible' ?
      0.55 : 1}));
  ball.position.set(x, y + 1.7, z); g.add(ball); pulses.push(null);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.6,
    6), new THREE.MeshBasicMaterial({color: col(e.colour), transparent: true,
    opacity: 0.6}));
  beam.position.set(x, y + 0.85, z); g.add(beam);
  const t = label(e.code + (e.how === 'possible' ? ' ?' : ''), 0.3, e.colour);
  t.position.set(x, y + 2.05, z); g.add(t);
});

// floors one at a time, or all
const bar = document.getElementById('bar');
function show(k) {
  groups.forEach((g, i) => { g.visible = (k < 0 || i === k); });
  [...bar.children].forEach((b, i) => b.classList.toggle('on', i === k + 1));
  controls.target.set(0, k < 0 ? S * 1.2 : k * S + 0.6, 0);
}
['All floors'].concat(D.floors).forEach((name, i) => {
  const b = document.createElement('button'); b.textContent = name;
  b.onclick = () => { controls.autoRotate = false; show(i - 1); };
  bar.appendChild(b);
});
show(-1);

// point at a room for its numbers
const tip = document.getElementById('tip');
const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
renderer.domElement.addEventListener('pointermove', ev => {
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
  mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
  ray.setFromCamera(mouse, camera);
  const hit = ray.intersectObjects(pick.filter(m => m.parent &&
    m.parent.visible), false)[0];
  if (!hit) { tip.style.display = 'none'; return; }
  const r = hit.object.userData;
  const ppl = r.p == null ? 'not known' : (r.p === 0 ? 'nobody' :
    r.p + (r.p === 1 ? ' person' : ' people'));
  const ac = r.ac === 'on' ? ('AC running' + (r.u ? ' (' + r.u +
    ' unit' + (r.u === 1 ? '' : 's') + ')' : '') + (r.st === 'empty' ?
    ' &mdash; nobody in' : '')) : (r.ac === 'off' ? 'AC off' :
    'AC not read');
  tip.innerHTML = '<b>' + r.n + '</b><br>' + D.floors[r.f] + '<br>' + ppl +
    ' &middot; ' + ac;
  tip.style.display = 'block';
  tip.style.left = Math.min(rect.width - 250, ev.clientX - rect.left + 14) +
    'px';
  tip.style.top = (ev.clientY - rect.top + 14) + 'px';
});
renderer.domElement.addEventListener('pointerleave',
  () => { tip.style.display = 'none'; });

function resize() {
  renderer.setSize(wrap.clientWidth, wrap.clientHeight);
  camera.aspect = wrap.clientWidth / wrap.clientHeight;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
const clock = new THREE.Clock();
(function tick() {
  const t = clock.getElapsedTime();
  pulses.forEach(m => { if (m) m.emissiveIntensity = 0.35 + 0.35 *
    Math.sin(t * 3.2); });
  controls.update(); renderer.render(scene, camera);
  requestAnimationFrame(tick);
})();
})();
</script></body></html>"""


def page(data, mode="dark", height=640):
    """The scene as one HTML page (for st.components.v1.html)."""
    c = PALETTE.get(mode, PALETTE["dark"])
    emp_key = "".join(
        '<span><i style="background:%s;border-radius:50%%"></i>%s</span>'
        % (e.get("colour", "#888"), e.get("code", "?"))
        for e in data.get("emp") or [])
    out = _PAGE
    for k, v in (("__H__", str(int(height))), ("__BG1__", c["bg1"]),
                 ("__BG2__", c["bg2"]), ("__LINE__", c["line"]),
                 ("__PANEL__", c["panel"]), ("__TEXT__", c["text"]),
                 ("__MUTED__", c["muted"]), ("__OCC__", c["occupied"]),
                 ("__EMPTY__", c["empty"]), ("__WASTE__", c["waste"]),
                 ("__AC__", c["ac"]), ("__UNK__", c["unknown"]),
                 ("__EMPKEY__", emp_key), ("__THREE__", THREE),
                 ("__ORBIT__", ORBIT)):
        out = out.replace(k, v)
    # the data last: a room's name can never be read as a placeholder
    out = out.replace("__COLS__", json.dumps(c))
    return out.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
