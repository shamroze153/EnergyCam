import { SITE, SERVICES, INDUSTRIES, I, LOGO, wa, svcByKey } from '../site.mjs';
import { ctaBand } from '../layout.mjs';

const svcCard = (s, r, size) => `
    <a class="svc ${size}" href="${r}services/${s.slug}.html" data-reveal>
      <div class="media"><span class="pill-3d">3D SCENE</span><img src="${r}assets/img/scenes/${s.key}-s.jpg" alt="3D scene: ${s.solution.t}" loading="lazy" width="1600" height="1000"></div>
      <div class="body">
        <span class="num">${s.num} · ${s.name}</span>
        <h3>${s.short}</h3>
        ${size === 'big' ? `<p>${s.lede}</p>` : ''}
        <span class="more link-arrow">Explore ${s.lc} ${I.arrow}</span>
      </div>
    </a>`;

const faq = [
  { q: 'Do we need to buy new hardware?', a: 'Usually not to start. EnergyCam runs on your existing IP cameras, digital twins start from your drawings, and the quotation agent works from email. We tell you up front if anything extra is needed.' },
  { q: 'How does a project start?', a: 'With a short site walk and a conversation about what costs you most. Then we run a small pilot on one floor, one building or one plant room, so you see results before rolling it out.' },
  { q: 'How is pricing worked out?', a: 'Every building is different, so we scope each project after the site walk and send you a clear quote.' },
  { q: 'Where do you work?', a: 'We are based in Karachi and work with buildings across Pakistan. Message us on WhatsApp to talk about your site.' },
  { q: 'Who is behind Mimar AI?', a: 'Mimar AI was founded by Shamroze Nasir, a facility engineer who spent years running buildings. Everything we build comes from problems he saw on site.' },
];

export default {
  path: 'index.html',
  title: '',
  description: SITE.description,
  three: true,
  jsonld: [{
    '@context': 'https://schema.org', '@type': 'Organization', name: 'Mimar AI', slogan: SITE.tagline, email: SITE.email,
    telephone: '+' + SITE.whatsapp, address: { '@type': 'PostalAddress', addressLocality: 'Karachi', addressCountry: 'PK' },
    knowsAbout: SERVICES.map((s) => s.name), founder: { '@type': 'Person', name: 'Shamroze Nasir', jobTitle: 'Founder' },
  }, {
    '@context': 'https://schema.org', '@type': 'FAQPage',
    mainEntity: faq.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
  }],
  body: (r) => `
<section class="hero blueprint">
  <div class="container">
    <div class="hero-copy">
      <span class="eyebrow">AI for buildings · Karachi</span>
      <h1 class="display">AI for the buildings <span class="accent">you already run.</span></h1>
      <p class="lede">Cameras, drawings and data you already have, turned into answers. We build computer vision, 3D digital twins and AI agents for facility teams.</p>
      <div class="hero-actions">
        <a class="btn btn-primary btn-lg" href="${r}contact.html">Book a site visit ${I.arrow}</a>
        <a class="btn btn-ghost btn-lg" href="${r}experience.html">${I.play}Watch the 3D tour</a>
      </div>
      <div class="hero-proof">
        <span>${I.checkCircle}Uses your existing CCTV</span>
        <span>${I.checkCircle}No new hardware to start</span>
        <span>${I.checkCircle}A person approves every spend</span>
      </div>
    </div>
    <div class="hero-stage m3 m3-bare" data-mimar-building data-base="${r}">
      <img class="m3-poster" src="${r}assets/img/hero-building.png" alt="3D model of a building showing where each Mimar AI service works" width="1400" height="1100">
    </div>
  </div>
</section>

<section class="strip" aria-label="Industries we work with">
  <div class="container">
    <span class="label">Built for</span>
    <ul>
      <li>${I.office}Offices</li><li>${I.bank}Banks</li><li>${I.hospital}Hospitals</li><li>${I.school}Schools</li><li>${I.factory}Factories</li><li>${I.hotel}Hotels</li>
    </ul>
  </div>
</section>

<section class="section" id="services">
  <div class="container stack-lg">
    <div class="section-head-row">
      <div class="section-head">
        <span class="eyebrow">What we build · 5 services</span>
        <h2 class="h2">One team for the <span class="accent">whole building.</span></h2>
        <p class="lede">From the camera on the ceiling to the panels on the roof. Start with the problem that costs you most, and add the rest when you’re ready.</p>
      </div>
      <a class="btn btn-ghost" href="${r}services.html">Compare all services ${I.arrow}</a>
    </div>
    <div class="svc-grid">
      ${svcCard(SERVICES[0], r, 'big')}
      ${svcCard(SERVICES[1], r, 'big')}
      ${svcCard(SERVICES[2], r, 'small')}
      ${svcCard(SERVICES[3], r, 'small')}
      ${svcCard(SERVICES[4], r, 'small')}
    </div>
  </div>
</section>

<section class="section section-alt" id="scenes">
  <div class="container stack-lg">
    <div class="section-head-row">
      <div class="section-head">
        <span class="eyebrow">Interactive 3D</span>
        <h2 class="h2">Watch the problem. <span class="accent">Then watch the fix.</span></h2>
        <p class="lede">Each scene plays a problem we see in buildings every week, then the system we build for it. Switch services, flip between problem and solution, and drag to look around.</p>
      </div>
      <a class="btn btn-ghost" href="${r}experience.html">Open full screen ${I.arrow}</a>
    </div>
    <div class="m3" data-mimar-scenes data-reveal>
      <img class="m3-poster" src="${r}assets/img/scenes/vision-s.jpg" alt="3D scene of an office where the CCTV spots an empty room and the AC is switched off" loading="lazy">
    </div>
  </div>
</section>

<section class="band-night section">
  <div class="container stack-lg">
    <div class="section-head">
      <span class="eyebrow">Why Mimar AI</span>
      <h2 class="h2">Built on what’s already <span class="accent">in your building.</span></h2>
      <p class="lede">No rip-and-replace. We start from your cameras, drawings, bills and processes, and add intelligence on top.</p>
    </div>
    <div class="stats" data-reveal>
      <div class="stat"><span class="v">10 s</span><span class="k">From empty room to alert</span><p>EnergyCam waits 10 seconds to be sure, then emails your team a snapshot.</p></div>
      <div class="stat"><span class="v">0</span><span class="k">New sensors to start</span><p>Existing IP cameras, PDF drawings and email are enough for a pilot.</p></div>
      <div class="stat"><span class="v">24/7</span><span class="k">Watching, with self-repair</span><p>Streams reconnect by themselves and log a heartbeat every 30 minutes.</p></div>
      <div class="stat"><span class="v">1</span><span class="k">Team for five services</span><p>Vision, twins, agents, portals and energy, designed to work together.</p></div>
    </div>
  </div>
</section>

<section class="section" id="industries">
  <div class="container stack-lg">
    <div class="section-head">
      <span class="eyebrow">Industries</span>
      <h2 class="h2">Different buildings. <span class="accent">The same leaks.</span></h2>
      <p class="lede">Wherever there are ACs, plant rooms, drawings and vendors, there is money to save. Here is where each service fits.</p>
    </div>
    <div class="grid-3">
      ${INDUSTRIES.map((x, i) => `
      <div class="card ind" data-reveal="${i % 3}">
        <div class="ic-tile${i % 3 === 1 ? ' air' : i % 3 === 2 ? ' amber' : ''}">${I[x.i]}</div>
        <h3>${x.t}</h3>
        <p>${x.d}</p>
        <div class="uses">${x.uses.map((k) => `<a href="${r}services/${svcByKey[k].slug}.html">${svcByKey[k].name}</a>`).join('')}</div>
      </div>`).join('')}
    </div>
  </div>
</section>

<section class="section section-white" id="process">
  <div class="container stack-lg">
    <div class="section-head">
      <span class="eyebrow">How we work</span>
      <h2 class="h2">Start with one floor. <span class="accent">Scale what works.</span></h2>
    </div>
    <div class="process">
      <div class="step" data-reveal="0"><span class="dot">01</span><h3>Site walk</h3><p>We visit, look at your cameras, drawings and bills, and agree on the problem worth solving first.</p></div>
      <div class="step" data-reveal="1"><span class="dot">02</span><h3>Pilot</h3><p>A working system on one floor, building or plant room, measured against your real numbers.</p></div>
      <div class="step" data-reveal="2"><span class="dot">03</span><h3>Roll out</h3><p>Extend to the whole site once the pilot has proven itself, with your team trained along the way.</p></div>
      <div class="step" data-reveal="3"><span class="dot">04</span><h3>Support</h3><p>Monitoring, fixes and a regular report of what the system caught and what it saved.</p></div>
    </div>
  </div>
</section>

<section class="section" id="work">
  <div class="container split wide-left">
    <div class="stack-lg" style="gap:28px">
      <div class="section-head">
        <span class="eyebrow">Featured build · EnergyCam</span>
        <h2 class="h2">The room emptied. <span class="accent">The AC didn’t notice.</span></h2>
        <p class="lede">EnergyCam is our first product in the field. It reads the CCTV stream, counts people with YOLOv8, checks each AC, and emails the facilities team a snapshot when cooling runs in an empty room. When someone returns or the AC goes off, a second email closes the alert.</p>
      </div>
      <ul class="checklist">
        <li>${I.check}<span><strong>Two ACs per room,</strong> tracked separately, with readings smoothed over four frames.</span></li>
        <li>${I.check}<span><strong>One alert per event,</strong> then a “resolved” email with how long the waste lasted.</span></li>
        <li>${I.check}<span><strong>A live dashboard</strong> with a cost ticker in rupees, month-on-month waste and CO2 impact.</span></li>
      </ul>
      <div class="hero-actions">
        <a class="btn btn-primary" href="${r}services/computer-vision.html">See how EnergyCam works ${I.arrow}</a>
        <a class="btn btn-ghost" href="${r}projects.html">See all projects</a>
      </div>
    </div>
    <div data-reveal>
      <div class="video-frame portrait">
        <video src="${r}assets/video/energycam-promo.mp4" poster="${r}assets/img/energycam-poster.jpg" controls playsinline preload="none" muted width="1080" height="1350"></video>
      </div>
      <p class="video-caption">EnergyCam promo · 35 seconds</p>
    </div>
  </div>
</section>

<section class="section section-alt">
  <div class="container stack-lg">
    <div class="section-head">
      <span class="eyebrow">Trust and privacy</span>
      <h2 class="h2">Your building. <span class="accent">Your data. Your call.</span></h2>
      <p class="lede">We design every system so your team stays in control and sensitive data stays where it belongs.</p>
    </div>
    <div class="trust">
      <div class="card" data-reveal="0"><div class="ic-tile">${I.server}</div><h3>Runs on your site</h3><p>EnergyCam can run on a computer inside your building, next to the cameras.</p></div>
      <div class="card" data-reveal="1"><div class="ic-tile air">${I.eyeOff}</div><h3>Counts, never identifies</h3><p>Computer vision counts people in a room. It does not recognise who they are.</p></div>
      <div class="card" data-reveal="2"><div class="ic-tile amber">${I.userCheck}</div><h3>A person decides</h3><p>AI agents check and recommend. A person on your team approves every spend.</p></div>
      <div class="card" data-reveal="3"><div class="ic-tile">${I.shield}</div><h3>You own the data</h3><p>Logs, models and reports belong to you. We never share them with vendors.</p></div>
    </div>
  </div>
</section>

<section class="section">
  <div class="container">
    <div class="founder" data-reveal>
      <div class="mark photo"><img src="${r}assets/img/shamroze-nasir.jpg" alt="Shamroze Nasir, founder of Mimar AI" width="720" height="720" loading="lazy"></div>
      <div>
        <span class="eyebrow">About Mimar AI</span>
        <blockquote style="margin-top:18px">“Mimar means architect. After years inside plant rooms and on site walks, the same problems kept coming back. Mimar AI builds the tools I wished I had.”</blockquote>
        <cite><strong>Shamroze Nasir</strong> · Founder, Mimar AI · Facility engineer, Karachi</cite>
        <div class="hero-actions" style="margin-top:24px"><a class="btn btn-ghost" href="${r}about.html">Our story ${I.arrow}</a><a class="btn btn-ghost" href="https://shamroze.vercel.app/" target="_blank" rel="noopener">Shamroze’s portfolio ${I.arrow}</a></div>
      </div>
    </div>
  </div>
</section>

<section class="section section-white">
  <div class="container stack-lg">
    <div class="section-head-row">
      <div class="section-head">
        <span class="eyebrow">Build logs</span>
        <h2 class="h2">What worked, what broke, <span class="accent">and what it cost.</span></h2>
      </div>
      <a class="btn btn-ghost" href="${r}logs.html">All build logs ${I.arrow}</a>
    </div>
    <div class="grid-3">
      <a class="card log-card" href="${r}logs.html#log-01" data-reveal="0"><div class="cover"><img src="${r}assets/img/scenes/vision-p.jpg" alt="" loading="lazy"></div><div class="in"><span class="meta">Log 01 · Computer vision</span><h3>How EnergyCam decides a room is really empty</h3><span class="small">6 min read</span></div></a>
      <a class="card log-card" href="${r}logs.html#coming" data-reveal="1"><div class="cover"><img src="${r}assets/img/scenes/twin-p.jpg" alt="" loading="lazy"></div><div class="in"><span class="meta">Log 02 · Digital twins</span><h3>From a PDF floor plan to a 3D building</h3><span class="soon">Coming soon</span></div></a>
      <a class="card log-card" href="${r}logs.html#coming" data-reveal="2"><div class="cover"><img src="${r}assets/img/scenes/agents-s.jpg" alt="" loading="lazy"></div><div class="in"><span class="meta">Log 03 · AI agents</span><h3>What an AI catches in vendor quotations</h3><span class="soon">Coming soon</span></div></a>
    </div>
  </div>
</section>

<section class="section">
  <div class="container faq-wrap">
    <div class="section-head"><span class="eyebrow">FAQ</span><h2 class="h2">Questions facility teams ask us.</h2></div>
    <div class="faq">
      ${faq.map((f) => `<details><summary>${f.q}${I.plus}</summary><p>${f.a}</p></details>`).join('')}
    </div>
  </div>
</section>

${ctaBand(r)}
`,
};
