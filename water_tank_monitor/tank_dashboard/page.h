// Dashboard page, served once; it then polls /data every 2 s.
// Everything is inline (no internet on the Tank-Monitor WiFi). Theme colors: the :root block.
#pragma once

const char PAGE[] PROGMEM = R"rawliteral(<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#070d1a">
<title>Tank Level</title>
<style>
:root{
  --bg:#070d1a; --card:rgba(255,255,255,.055); --line:rgba(255,255,255,.1);
  --text:#eef3ff; --muted:#93a3c4;
  --accent:#3fb6ff; --accent2:#7c5cff;
  --water1:#5fd0ff; --water2:#1f6bff;
  --ok:#2fd28a; --mid:#ffb547; --low:#ff5470;
}
*{box-sizing:border-box;margin:0}
body{font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,system-ui,sans-serif;color:var(--text);background:var(--bg);
  background-image:radial-gradient(900px 520px at 8% -12%,rgba(124,92,255,.26),transparent 62%),
                   radial-gradient(720px 520px at 108% 6%,rgba(63,182,255,.18),transparent 62%);
  background-attachment:fixed;min-height:100vh;padding:20px 16px 28px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1040px;margin:0 auto;display:grid;gap:16px}
.num{font-variant-numeric:tabular-nums}

header{display:flex;align-items:center;gap:14px}
.logo{width:46px;height:46px;flex:none;border-radius:14px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 10px 28px rgba(63,182,255,.32)}
.logo svg{width:22px;height:22px}
h1{font-size:clamp(19px,4.4vw,27px);font-weight:700;letter-spacing:-.015em;line-height:1.15}
.sub{color:var(--muted);font-size:13px;margin-top:4px;display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok);animation:ping 1.8s infinite}
.off .dot{background:var(--low);animation:none}
@keyframes ping{0%{box-shadow:0 0 0 0 rgba(47,210,138,.6)}70%,100%{box-shadow:0 0 0 9px rgba(47,210,138,0)}}

.alert{display:none;align-items:center;gap:12px;padding:14px 18px;border-radius:16px;font-weight:600;
  background:rgba(255,84,112,.14);border:1px solid rgba(255,84,112,.45);color:#ffd6dd;animation:glow 1.6s ease-in-out infinite}
.alert b{color:#fff}
.low .alert{display:flex}
@keyframes glow{50%{box-shadow:0 0 0 4px rgba(255,84,112,.12),0 0 30px rgba(255,84,112,.25)}}

.card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:20px;
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
.hero{display:grid;grid-template-columns:minmax(190px,270px) 1fr;gap:30px;align-items:center;padding:24px 28px}
.low .hero{border-color:rgba(255,84,112,.5)}

.tank{width:100%;height:auto;display:block;overflow:visible}
.tankbg{fill:rgba(255,255,255,.04)}
.tankline{fill:none;stroke:rgba(255,255,255,.28);stroke-width:2.5}
.s1{stop-color:var(--water1)} .s2{stop-color:var(--water2)}
.low .s1{stop-color:#ff8a9c} .low .s2{stop-color:#e2244a}
.lvl{transition:transform 1.4s cubic-bezier(.22,1,.36,1)}
.w1{animation:wave 4s linear infinite}
.w2{animation:wave 6.5s linear infinite reverse}
@keyframes wave{to{transform:translateX(120px)}}
.bub{fill:rgba(255,255,255,.55);animation:rise 5s ease-in infinite;opacity:0}
@keyframes rise{0%{transform:translateY(0);opacity:0}15%{opacity:.8}100%{transform:translateY(-230px);opacity:0}}
.maxline{stroke:rgba(255,255,255,.55);stroke-width:1.5;stroke-dasharray:5 5}
.tick{stroke:rgba(255,255,255,.3);stroke-width:1.5}
.tlabel{fill:var(--muted);font-size:12px;font-family:inherit}
.maxlabel{fill:#fff;font-size:11px;font-weight:700;letter-spacing:.08em}

.label{color:var(--muted);font-size:13px;font-weight:600;letter-spacing:.12em;text-transform:uppercase}
.pct{font-size:clamp(64px,15vw,112px);font-weight:800;line-height:.95;letter-spacing:-.04em;margin:6px 0 12px}
.pct small{font-size:.38em;font-weight:700;color:var(--muted);margin-left:4px;letter-spacing:0}
.pill{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border-radius:999px;font-weight:700;font-size:14px;
  background:rgba(255,255,255,.08);color:var(--muted)}
.pill:before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor}
.ok .pill{background:rgba(47,210,138,.14);color:var(--ok)}
.mid .pill{background:rgba(255,181,71,.14);color:var(--mid)}
.low .pill{background:rgba(255,84,112,.16);color:var(--low)}
.ft{margin-top:18px;font-size:20px;font-weight:600}
.ft span{color:var(--muted);font-weight:500}
.bar{height:10px;border-radius:99px;background:rgba(255,255,255,.08);margin-top:12px;overflow:hidden}
.bar i{display:block;height:100%;width:0;border-radius:99px;background:linear-gradient(90deg,var(--water2),var(--water1));
  transition:width 1.4s cubic-bezier(.22,1,.36,1)}
.low .bar i{background:linear-gradient(90deg,#e2244a,#ff8a9c)}

.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.stat .k{color:var(--muted);font-size:13px;font-weight:600}
.stat .v{font-size:26px;font-weight:750;margin-top:8px;letter-spacing:-.02em}
.stat .s{color:var(--muted);font-size:13px;margin-top:4px}

.trend{display:grid;gap:10px}
.trend .top{display:flex;justify-content:space-between;align-items:baseline}
.trend svg{width:100%;height:110px;display:block}
.sline{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round}
.ga{stop-color:var(--accent)}
.grid{stroke:rgba(255,255,255,.07);stroke-width:1}
.empty{fill:var(--muted);font-size:13px}

footer{color:var(--muted);font-size:12px;text-align:center;margin-top:4px}

@media(max-width:760px){.stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:640px){
  .hero{grid-template-columns:1fr;justify-items:center;text-align:center;padding:22px 18px;gap:18px}
  .tank{max-width:230px}
  .info{width:100%}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head>
<body>
<div class="wrap">
  <header>
    <div class="logo"><svg viewBox="0 0 24 24" fill="#fff"><path d="M12 2.5c-.3 0-.6.2-.8.4C9 6 5.5 10.6 5.5 14.5a6.5 6.5 0 0 0 13 0C18.5 10.6 15 6 12.8 2.9c-.2-.2-.5-.4-.8-.4z"/></svg></div>
    <div>
      <h1 id="name">Water Tank</h1>
      <div class="sub" id="conn"><span class="dot"></span><span id="connText">Connecting…</span></div>
    </div>
  </header>

  <div class="alert" role="alert">⚠ <span><b>Low water</b>: only <b id="alertPct">--%</b> left in the tank</span></div>

  <section class="card hero">
    <svg class="tank" viewBox="0 0 270 320" aria-hidden="true">
      <defs>
        <clipPath id="clip"><rect x="30" y="20" width="180" height="280" rx="26"/></clipPath>
        <linearGradient id="wg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="s1"/><stop offset="1" class="s2"/></linearGradient>
      </defs>
      <rect x="30" y="20" width="180" height="280" rx="26" class="tankbg"/>
      <g clip-path="url(#clip)">
        <g id="lvl" class="lvl" style="transform:translateY(300px)">
          <g transform="translate(-40,-6)"><g class="w2"><path fill="url(#wg)" opacity=".45" d="M-180 0Q-150-9-120 0T-60 0T0 0T60 0T120 0T180 0T240 0T300 0T360 0V330H-180Z"/></g></g>
          <g class="w1"><path fill="url(#wg)" d="M-180 0Q-150-9-120 0T-60 0T0 0T60 0T120 0T180 0T240 0T300 0T360 0V330H-180Z"/></g>
          <circle class="bub" cx="70" cy="250" r="3" style="animation-delay:0s"/>
          <circle class="bub" cx="120" cy="265" r="2.2" style="animation-delay:1.6s"/>
          <circle class="bub" cx="165" cy="255" r="3.4" style="animation-delay:3.1s"/>
          <circle class="bub" cx="95" cy="270" r="2" style="animation-delay:4.2s"/>
        </g>
      </g>
      <g id="ticks"></g>
      <rect x="30" y="20" width="180" height="280" rx="26" class="tankline"/>
    </svg>

    <div class="info">
      <div class="label">Water level</div>
      <div class="pct num"><span id="pct">--</span><small>%</small></div>
      <div class="pill" id="pill">Connecting</div>
      <div class="ft num"><b id="ft">--</b> ft <span>of <span id="maxft">--</span> ft max</span></div>
      <div class="bar"><i id="bar"></i></div>
    </div>
  </section>

  <section class="stats">
    <div class="card stat"><div class="k">Water height</div><div class="v num" id="hcm">--</div><div class="s" id="hft">&nbsp;</div></div>
    <div class="card stat" id="volCard"><div class="k" id="volK">Tank depth</div><div class="v num" id="vol">--</div><div class="s" id="volS">&nbsp;</div></div>
    <div class="card stat"><div class="k">Sensor to water</div><div class="v num" id="dist">--</div><div class="s" id="sens">&nbsp;</div></div>
    <div class="card stat"><div class="k">Last update</div><div class="v num" id="ago">--</div><div class="s num" id="clock">&nbsp;</div></div>
  </section>

  <section class="card trend">
    <div class="top"><div class="label">Last 60 minutes</div><div class="stat"><span class="s num" id="range"></span></div></div>
    <svg viewBox="0 0 300 100" preserveAspectRatio="none" id="spark">
      <defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ga" stop-opacity=".35"/><stop offset="1" class="ga" stop-opacity="0"/></linearGradient></defs>
      <line class="grid" x1="0" x2="300" y1="10" y2="10"/><line class="grid" x1="0" x2="300" y1="50" y2="50"/><line class="grid" x1="0" x2="300" y1="90" y2="90"/>
      <path id="area" fill="url(#ag)"/><path id="sline" class="sline" vector-effect="non-scaling-stroke"/>
      <text id="empty" class="empty" x="150" y="55" text-anchor="middle">Collecting data…</text>
    </svg>
  </section>

  <footer>Live from the tank sensor · updates every 2 seconds</footer>
</div>

<script>
const $ = id => document.getElementById(id);
const FT = 30.48, TOP = 20, H = 280;
let shown = 0, lastOk = 0, fails = 0, ticksDone = false;

function countTo(to) {
  const from = shown, t0 = performance.now();
  cancelAnimationFrame(countTo.raf);
  const step = t => {
    const k = Math.min(1, (t - t0) / 1000), e = 1 - Math.pow(1 - k, 3);
    $('pct').textContent = Math.round(from + (to - from) * e);
    if (k < 1) countTo.raf = requestAnimationFrame(step);
  };
  countTo.raf = requestAnimationFrame(step);
  shown = to;
}

// Scale on the right of the tank: every foot, plus a dashed MAX line
function drawTicks(depthCm, maxCm) {
  const ns = 'http://www.w3.org/2000/svg', g = $('ticks');
  const y = cm => TOP + H - H * cm / depthCm;
  const el = (tag, attrs, text) => {
    const e = document.createElementNS(ns, tag);
    for (const a in attrs) e.setAttribute(a, attrs[a]);
    if (text) e.textContent = text;
    g.appendChild(e);
  };
  for (let f = 0; f * FT <= depthCm + 0.5; f++) {
    el('line', {class: 'tick', x1: 214, x2: 224, y1: y(f * FT), y2: y(f * FT)});
    el('text', {class: 'tlabel', x: 230, y: y(f * FT) + 4}, f + ' ft');
  }
  el('line', {class: 'maxline', x1: 30, x2: 210, y1: y(maxCm), y2: y(maxCm)});
  el('text', {class: 'maxlabel', x: 42, y: y(maxCm) - 7}, 'MAX ' + (maxCm / FT).toFixed(1) + ' ft');
}

function drawTrend(hist) {
  const pts = [];
  const n = 60, dx = 300 / (n - 1), off = n - hist.length;
  hist.forEach((v, i) => { if (v >= 0) pts.push([(off + i) * dx, 90 - v * 0.8]); });
  $('empty').style.display = pts.length > 1 ? 'none' : '';
  if (pts.length < 2) { $('sline').setAttribute('d', ''); $('area').setAttribute('d', ''); $('range').textContent = ''; return; }
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('');
  $('sline').setAttribute('d', line);
  $('area').setAttribute('d', line + 'L' + pts[pts.length - 1][0].toFixed(1) + ' 100L' + pts[0][0].toFixed(1) + ' 100Z');
  const vals = hist.filter(v => v >= 0);
  $('range').textContent = 'Low ' + Math.min(...vals) + '%  ·  High ' + Math.max(...vals) + '%';
}

function setState(cls, text) {
  document.body.className = cls;
  $('pill').textContent = text;
}

function render(d) {
  document.title = d.name + ' · ' + (d.ok ? d.pct + '%' : '--');
  $('name').textContent = d.name;
  $('maxft').textContent = (d.maxCm / FT).toFixed(1);
  if (!ticksDone) { drawTicks(d.depthCm, d.maxCm); ticksDone = true; }
  drawTrend(d.hist || []);

  if (d.cap > 0) {
    $('volK').textContent = 'Water in tank';
    $('vol').textContent = Math.round(d.cap * d.pct / 100).toLocaleString() + ' L';
    $('volS').textContent = 'of ' + Math.round(d.cap).toLocaleString() + ' L';
  } else {
    $('vol').textContent = (d.depthCm / FT).toFixed(1) + ' ft';
    $('volS').textContent = 'Max water ' + (d.maxCm / FT).toFixed(1) + ' ft';
  }

  if (!d.ok) {
    setState('na', 'Check sensor');
    $('pct').textContent = '--'; $('ft').textContent = '--';
    $('hcm').textContent = '--'; $('hft').innerHTML = '&nbsp;';
    $('dist').textContent = '--'; $('sens').textContent = 'No echo from sensor';
    return;
  }
  lastOk = Date.now();
  countTo(d.pct);
  $('lvl').style.transform = 'translateY(' + (TOP + H - H * Math.min(1, d.waterCm / d.depthCm)).toFixed(1) + 'px)';
  $('bar').style.width = d.pct + '%';
  $('ft').textContent = (d.waterCm / FT).toFixed(2);
  $('hcm').textContent = Math.round(d.waterCm) + ' cm';
  $('hft').textContent = (d.waterCm / FT).toFixed(2) + ' ft';
  $('dist').textContent = Math.round(d.distCm) + ' cm';
  $('sens').textContent = 'Sensor online';
  $('alertPct').textContent = d.pct + '%';
  if (d.pct < d.low) setState('low', 'Low water');
  else if (d.pct < 50) setState('mid', 'Half full');
  else setState('ok', 'Good level');
}

function tickClock() {
  if (lastOk) {
    const s = Math.round((Date.now() - lastOk) / 1000);
    $('ago').textContent = s < 3 ? 'Just now' : s < 60 ? s + 's ago' : Math.floor(s / 60) + 'm ago';
    $('clock').textContent = new Date(lastOk).toLocaleTimeString();
  }
}

async function poll() {
  try {
    const r = await fetch('/data', {cache: 'no-store'});
    render(await r.json());
    fails = 0;
    $('conn').classList.remove('off');
    $('connText').textContent = 'Live';
  } catch (e) {
    if (++fails >= 3) { $('conn').classList.add('off'); $('connText').textContent = 'Disconnected · retrying…'; }
  }
  setTimeout(poll, 2000);
}

setInterval(tickClock, 1000);
poll();
</script>
</body></html>)rawliteral";
