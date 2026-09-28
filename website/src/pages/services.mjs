import { SERVICES, I, wa, svcByKey } from '../site.mjs';
import { ctaBand } from '../layout.mjs';

const bestIcon = (label) => {
  const l = label.toLowerCase();
  if (l.includes('bank')) return I.bank; if (l.includes('hospital')) return I.hospital; if (l.includes('school') || l.includes('campus')) return I.school;
  if (l.includes('factor') || l.includes('plant')) return I.factory; if (l.includes('hotel') || l.includes('mall')) return I.hotel;
  if (l.includes('procure') || l.includes('facility') || l.includes('manager')) return I.userCheck; if (l.includes('portfolio')) return I.layers;
  return I.office;
};

/* ---------- services overview ---------- */
const overview = {
  path: 'services.html',
  title: 'Services',
  description: 'Five services from one team: computer vision on your CCTV, 3D digital twins from PDF drawings, AI quotation checks, QR facility portals, and HVAC energy audits with rooftop solar.',
  active: 'services',
  three: false,
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>Services</span></div>
    <span class="eyebrow">Services · 5</span>
    <h1 class="display" style="max-width:15ch">Everything we build, <span class="accent">in one place.</span></h1>
    <p class="lede">Each service solves one problem facility teams deal with every week. They work on their own, and they work better together.</p>
  </div>
</section>

<section class="section">
  <div class="container" style="display:flex;flex-direction:column;gap:28px">
    ${SERVICES.map((s, i) => `
    <article class="card" style="padding:0;overflow:hidden" data-reveal>
      <div class="split" style="gap:0;${i % 2 ? '' : ''}">
        <a href="${r}services/${s.slug}.html" style="position:relative;display:block;height:100%;min-height:320px;background:var(--paper-2);order:${i % 2 ? 2 : 0}">
          <span class="pill-3d">3D SCENE</span>
          <img src="${r}assets/img/scenes/${s.key}-s.jpg" alt="3D scene: ${s.solution.t}" loading="lazy" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">
        </a>
        <div style="padding:clamp(24px,4vw,48px);display:flex;flex-direction:column;gap:16px">
          <span class="eyebrow">${s.num} · ${s.name}</span>
          <h2 class="h3" style="font-size:clamp(26px,2.6vw,36px)">${s.title} <span class="accent">${s.accent}</span></h2>
          <p class="lede" style="font-size:17px">${s.lede}</p>
          <ul class="outcomes">${s.outcomes.map((o) => `<li>${I.checkCircle}${o}</li>`).join('')}</ul>
          <div class="hero-actions" style="margin-top:6px">
            <a class="btn btn-primary" href="${r}services/${s.slug}.html">Explore ${s.lc} ${I.arrow}</a>
            <a class="btn btn-ghost" href="${wa(`Hi Mimar AI, I'd like to know more about ${s.name}.`)}" target="_blank" rel="noopener">${I.chat}Ask on WhatsApp</a>
          </div>
        </div>
      </div>
    </article>`).join('')}
  </div>
</section>

<section class="section section-white">
  <div class="container stack-lg">
    <div class="section-head">
      <span class="eyebrow">Where to start</span>
      <h2 class="h2">Match your problem <span class="accent">to a service.</span></h2>
      <p class="lede">Not sure which one you need? Find the sentence that sounds like your building.</p>
    </div>
    <div class="table-wrap">
      <table class="fit">
        <thead><tr><th>If this sounds familiar</th><th>Start with</th><th>First step</th></tr></thead>
        <tbody>
          <tr><td>“Our electricity bill is high and ACs run after everyone leaves.”</td><td><a href="${r}services/computer-vision.html">Computer vision</a></td><td>Pilot EnergyCam on one floor</td></tr>
          <tr><td>“Nobody can find the drawings, and we couldn’t guide people out in an emergency.”</td><td><a href="${r}services/digital-twins.html">Digital twins</a></td><td>Send drawings for one building</td></tr>
          <tr><td>“We approve quotations without checking every line.”</td><td><a href="${r}services/ai-agents.html">AI agents</a></td><td>Run ten past quotations through the agent</td></tr>
          <tr><td>“Maintenance history is on paper and services get missed.”</td><td><a href="${r}services/facility-portals.html">Facility portals</a></td><td>Tag one plant room</td></tr>
          <tr><td>“Chillers run hard at noon and the roof is empty.”</td><td><a href="${r}services/energy-solar.html">Energy + solar</a></td><td>Send 12 months of electricity bills</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</section>

${ctaBand(r, 'Not sure where to start?', 'Tell us about your building and the problem that costs you most. We’ll point you to the right first step.')}
`,
};

/* ---------- one page per service ---------- */
const servicePage = (s) => ({
  path: `services/${s.slug}.html`,
  title: s.name,
  description: `${s.short} ${s.lede}`,
  active: 'services',
  three: true,
  body: (r) => {
    const others = SERVICES.filter((x) => x.key !== s.key);
    return `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><a href="${r}services.html">Services</a><span>/</span><span>${s.name}</span></div>
    <div class="svc-hero">
      <div style="display:flex;flex-direction:column;gap:22px">
        <span class="eyebrow">${s.num} · ${s.name}${s.product ? ' · ' + s.product : ''}</span>
        <h1 class="display" style="font-size:clamp(40px,4.8vw,68px)">${s.title} <span class="accent">${s.accent}</span></h1>
        <p class="lede">${s.lede}</p>
        <ul class="outcomes">${s.outcomes.map((o) => `<li>${I.checkCircle}${o}</li>`).join('')}</ul>
        <div class="hero-actions">
          <a class="btn btn-primary btn-lg" href="${wa(`Hi Mimar AI, I'd like to talk about ${s.name} for my building.`)}" target="_blank" rel="noopener">${I.chat}Talk on WhatsApp</a>
          <a class="btn btn-ghost btn-lg" href="${r}contact.html">Book a site visit</a>
        </div>
      </div>
      <div class="m3 m3-compact" data-mimar-scenes data-services="${s.key}">
        <img class="m3-poster" src="${r}assets/img/scenes/${s.key}-s.jpg" alt="3D scene: ${s.solution.t}">
      </div>
    </div>
  </div>
</section>

<section class="section">
  <div class="container stack-lg">
    <div class="section-head">
      <span class="eyebrow">Before and after</span>
      <h2 class="h2">${s.problem.t.replace(/\.$/, '')}. <span class="accent">${s.solution.t}</span></h2>
    </div>
    <div class="pair">
      <div class="card" data-reveal="0"><div class="media"><span class="badge p">The problem</span><img src="${r}assets/img/scenes/${s.key}-p.jpg" alt="3D scene of the problem: ${s.problem.t}" loading="lazy"></div><div class="in"><h3>${s.problem.t}</h3><p>${s.problem.d}</p></div></div>
      <div class="card sol" data-reveal="1"><div class="media"><span class="badge s">The solution</span><img src="${r}assets/img/scenes/${s.key}-s.jpg" alt="3D scene of the solution: ${s.solution.t}" loading="lazy"></div><div class="in"><h3>${s.solution.t}</h3><p>${s.solution.d}</p></div></div>
    </div>
  </div>
</section>

<section class="section section-white">
  <div class="container stack-lg">
    <div class="section-head"><span class="eyebrow">How it works</span><h2 class="h2">Four steps, <span class="accent">start to finish.</span></h2></div>
    <div class="num-steps">
      ${s.steps.map((st, i) => `<div class="card" data-reveal="${i}"><span class="n">0${i + 1}</span><h3>${st.t}</h3><p>${st.d}</p></div>`).join('')}
    </div>
  </div>
</section>

<section class="section">
  <div class="container stack-lg">
    <div class="section-head"><span class="eyebrow">What you get</span><h2 class="h2">Built for facility teams, <span class="accent">not data scientists.</span></h2></div>
    <div class="grid-3">
      ${s.features.map((f, i) => `<div class="card" data-reveal="${i % 3}"><div class="ic-tile${i % 3 === 1 ? ' air' : i % 3 === 2 ? ' amber' : ''}">${I[f.i] || I.check}</div><h3>${f.t}</h3><p>${f.d}</p></div>`).join('')}
    </div>
    <div style="display:flex;flex-direction:column;gap:14px">
      <span class="eyebrow">Best for</span>
      <div class="best">${s.bestFor.map((b) => `<span>${bestIcon(b)}${b}</span>`).join('')}</div>
    </div>
  </div>
</section>

<section class="section-tight section-alt">
  <div class="container start">
    <div class="card main" data-reveal>
      <span class="eyebrow">How we start</span>
      <h2 class="h3" style="font-size:clamp(26px,2.8vw,38px);margin-top:14px">${s.start.t}</h2>
      <p style="font-size:17px">${s.start.d}</p>
    </div>
    <div class="card" data-reveal="1" style="display:flex;flex-direction:column;gap:14px;justify-content:center">
      <span class="eyebrow">Pricing</span>
      <p style="font-size:17px;color:var(--text-2)">Every building is different. We scope each project after a short site walk and send you a clear quote.</p>
      <a class="btn btn-mint" href="${wa(`Hi Mimar AI, could you send a quote for ${s.name}?`)}" target="_blank" rel="noopener">${I.chat}Ask for a quote</a>
    </div>
  </div>
</section>

<section class="section">
  <div class="container faq-wrap">
    <div class="section-head"><span class="eyebrow">FAQ</span><h2 class="h2">Questions about ${s.lc}.</h2></div>
    <div class="faq">${s.faq.map((f) => `<details><summary>${f.q}${I.plus}</summary><p>${f.a}</p></details>`).join('')}</div>
  </div>
</section>

<section class="section-tight section-white">
  <div class="container stack-lg" style="gap:28px">
    <div class="section-head-row"><h2 class="h3" style="font-size:28px">Works well with</h2><a class="link-arrow" href="${r}services.html">All services ${I.arrow}</a></div>
    <div class="related">
      ${others.map((o) => `<a class="card" href="${r}services/${o.slug}.html"><span class="num">${o.num} · ${o.name}</span><h3>${o.short}</h3></a>`).join('')}
    </div>
  </div>
</section>

${ctaBand(r, `Talk to us about ${s.lc}.`, s.start.d)}
`;
  },
});

export default [overview, ...SERVICES.map(servicePage)];
export { svcByKey };
