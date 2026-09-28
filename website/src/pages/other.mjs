import { SITE, SERVICES, I, LOGO, wa } from '../site.mjs';
import { ctaBand } from '../layout.mjs';

/* ---------- 3D experience ---------- */
const experience = {
  path: 'experience.html',
  title: '3D experience',
  description: 'Five interactive 3D scenes: the building problems we see every week, and the Mimar AI system that fixes each one.',
  active: 'experience',
  three: true,
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>3D experience</span></div>
    <span class="eyebrow">Interactive 3D · 5 scenes</span>
    <h1 class="display" style="max-width:16ch">Five problems. <span class="accent">Five fixes.</span> In 3D.</h1>
    <p class="lede">The tour plays each problem, then the system we build for it. Pause it any time, pick a service, flip between problem and solution, and drag to look around.</p>
  </div>
</section>
<section class="section-tight">
  <div class="container">
    <div class="m3" data-mimar-scenes style="height:clamp(560px,70vw,820px)">
      <img class="m3-poster" src="${r}assets/img/scenes/vision-s.jpg" alt="3D scene of an office where the CCTV spots an empty room">
    </div>
    <p class="small" style="margin-top:14px">Scenes are illustrations. Figures shown in them are examples, not client results.</p>
  </div>
</section>
<section class="section section-white">
  <div class="container split">
    <div class="section-head">
      <span class="eyebrow">The film</span>
      <h2 class="h2">All five scenes <span class="accent">in 64 seconds.</span></h2>
      <p class="lede">The same scenes as a short film with music. Share it with your team, or play it in a meeting.</p>
      <div class="hero-actions"><a class="btn btn-primary" href="${r}contact.html">Book a site visit ${I.arrow}</a></div>
    </div>
    <div class="video-frame" data-reveal>
      <video src="${r}assets/video/mimar-services-3d.mp4" poster="${r}assets/img/film-poster.jpg" controls playsinline preload="none" width="1280" height="720"></video>
    </div>
  </div>
</section>
<section class="section">
  <div class="container stack-lg">
    <div class="section-head"><span class="eyebrow">Go deeper</span><h2 class="h2">Every scene has <span class="accent">a full service page.</span></h2></div>
    <div class="related" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${SERVICES.map((s) => `<a class="card" href="${r}services/${s.slug}.html" style="padding:0;overflow:hidden"><img src="${r}assets/img/scenes/${s.key}-s.jpg" alt="" loading="lazy" style="aspect-ratio:16/10;object-fit:cover;width:100%;border-bottom:1px solid var(--line)"><div style="padding:18px"><span class="num">${s.num}</span><h3>${s.name}</h3></div></a>`).join('')}
    </div>
  </div>
</section>
${ctaBand(r)}
`,
};

/* ---------- about ---------- */
const about = {
  path: 'about.html',
  title: 'About',
  description: 'Mimar AI was founded by Shamroze Nasir, a facility engineer in Karachi, to build practical AI for the buildings people already run.',
  active: 'about',
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>About</span></div>
    <span class="eyebrow">About Mimar AI</span>
    <h1 class="display" style="max-width:17ch">We build AI for the buildings <span class="accent">people already run.</span></h1>
    <p class="lede">Mimar means architect. We are a small team in Karachi that designs practical tools for facility teams, starting from the cameras, drawings and data a building already has.</p>
  </div>
</section>
<section class="section">
  <div class="container founder" data-reveal>
    <div class="mark photo"><img src="${r}assets/img/shamroze-nasir.jpg" alt="Shamroze Nasir, founder of Mimar AI" width="720" height="720" loading="lazy"></div>
    <div class="stack-lg" style="gap:18px">
      <span class="eyebrow">Our story</span>
      <h2 class="h2" style="font-size:clamp(28px,3.2vw,42px)">Founded by a facility engineer, <span class="accent">built from site walks.</span></h2>
      <p style="font-weight:600;color:var(--ink)">Shamroze Nasir · Founder, Mimar AI · <a href="https://shamroze.vercel.app/" target="_blank" rel="noopener">View portfolio →</a></p>
      <p class="lede" style="font-size:18px">After years inside plant rooms and on site walks, the same problems kept coming back: ACs cooling empty rooms, drawings nobody could find, quotations nobody had time to check, and maintenance that lived on sticky notes.</p>
      <p class="lede" style="font-size:18px">None of them needed a new building. They needed someone to connect what was already there. That is what Mimar AI does.</p>
    </div>
  </div>
</section>
<section class="section section-white">
  <div class="container stack-lg">
    <div class="section-head"><span class="eyebrow">How we think</span><h2 class="h2">Four rules <span class="accent">we build by.</span></h2></div>
    <div class="grid-4">
      <div class="card" data-reveal="0"><div class="ic-tile">${I.layers}</div><h3>Use what’s there</h3><p>Start from existing cameras, drawings, bills and processes before adding anything new.</p></div>
      <div class="card" data-reveal="1"><div class="ic-tile air">${I.userCheck}</div><h3>A person stays in charge</h3><p>Our systems alert, check and recommend. People make the decisions and approve the spend.</p></div>
      <div class="card" data-reveal="2"><div class="ic-tile amber">${I.chart}</div><h3>Show the money</h3><p>Every system reports what it caught and what it saved, in rupees your finance team recognises.</p></div>
      <div class="card" data-reveal="3"><div class="ic-tile">${I.doc}</div><h3>Build in the open</h3><p>We publish build logs: what worked, what broke and what it cost.</p></div>
    </div>
  </div>
</section>
<section class="section">
  <div class="container stack-lg">
    <div class="section-head"><span class="eyebrow">What we do</span><h2 class="h2">Five services, <span class="accent">one team.</span></h2></div>
    <div class="related" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${SERVICES.map((s) => `<a class="card" href="${r}services/${s.slug}.html"><div class="ic-tile">${I[s.icon]}</div><span class="num">${s.num}</span><h3>${s.name}</h3></a>`).join('')}
    </div>
  </div>
</section>
${ctaBand(r, 'Let’s walk your building together.', 'Tell us where you are and what costs you most. We’ll set up a site walk.')}
`,
};

/* ---------- build logs ---------- */
const logs = {
  path: 'logs.html',
  title: 'Build logs',
  description: 'Build logs from Mimar AI: how our systems work in real buildings, what broke and what it cost.',
  active: 'logs',
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>Build logs</span></div>
    <span class="eyebrow">Build logs</span>
    <h1 class="display" style="max-width:16ch">What worked, what broke, <span class="accent">and what it cost.</span></h1>
    <p class="lede">Notes from building AI for real buildings. No hype, just how things work.</p>
  </div>
</section>
<section class="section">
  <article class="container article" id="log-01">
    <span class="eyebrow">Log 01 · Computer vision</span>
    <h2 class="h2" style="margin-top:14px;font-size:clamp(32px,4vw,48px)">How EnergyCam decides a room is really empty</h2>
    <p class="small" style="margin-top:12px">6 min read</p>
    <figure><img src="${r}assets/img/scenes/vision-p.jpg" alt="3D scene of an empty office with the AC still running" loading="lazy"><figcaption>The problem EnergyCam solves: the room is empty, the AC is still on.</figcaption></figure>
    <p>EnergyCam has one job: notice when a room is empty but an AC is still running, and tell someone. That sounds simple. Doing it without false alarms is the interesting part.</p>
    <h2>1. Read the camera you already have</h2>
    <p>EnergyCam connects to the room’s IP camera over RTSP, the same stream your CCTV recorder uses. If the stream drops, it releases the connection, waits two seconds and reconnects by itself, so a flaky camera never needs a person to restart the system.</p>
    <h2>2. Count people, check the ACs</h2>
    <p>Every frame goes through <code>YOLOv8</code>, a fast object-detection model. We only ask it about two things: people and phones. The number of people tells us if the room is occupied. Separately, a small check looks at each AC unit in view, left and right, and decides whether it is on.</p>
    <h2>3. Don’t trust a single frame</h2>
    <p>One frame can lie. Someone bends behind a desk, a reflection hits the lens, a frame arrives corrupted. So EnergyCam keeps the last four readings for each signal and takes a vote: a room only counts as occupied, or an AC as on, if at least half of the recent frames agree. Corrupted frames are skipped entirely.</p>
    <div class="callout"><strong>The rule:</strong> the room must be empty and at least one AC on for 10 seconds straight. Only then does an alert go out.</div>
    <h2>4. One alert, then a “resolved” email</h2>
    <p>When the rule fires, EnergyCam picks the clearest recent frame (it skips near-blank ones) and emails it to the facilities team with the room name and which AC is on. It sends one alert per event, not one every few seconds.</p>
    <p>When someone walks back in, or the AC is switched off, and that holds for 3 seconds, a second email says the alert is resolved and how many minutes the waste lasted.</p>
    <h2>5. Log everything, show the rupees</h2>
    <p>Every 30 seconds EnergyCam writes a row to a PostgreSQL database: room status, each AC’s status, the number of people and phones, and whether an alert went out. Every 30 minutes it writes a heartbeat, so we can see the system itself is alive.</p>
    <p>A live dashboard reads those rows. Each room gets a card with a running waste timer and a cost ticker in rupees, plus month-on-month waste cost and the CO2 impact.</p>
    <figure><img src="${r}assets/img/scenes/vision-s.jpg" alt="3D scene of the same office after EnergyCam sends an alert and the AC is switched off" loading="lazy"><figcaption>The fix: the camera spots the empty room, the team is alerted, the AC goes off.</figcaption></figure>
    <h2>What’s next</h2>
    <p>We are running EnergyCam on more rooms and will share real numbers here as they come in. If you want it on your cameras, <a href="${wa('Hi Mimar AI, I read the EnergyCam build log and want to try it.')}" target="_blank" rel="noopener">message us on WhatsApp</a>.</p>
  </article>
</section>
<section class="section section-white" id="coming">
  <div class="container stack-lg">
    <div class="section-head"><span class="eyebrow">Coming next</span><h2 class="h2">In the works.</h2></div>
    <div class="grid-2">
      <div class="card log-card"><div class="cover"><img src="${r}assets/img/scenes/twin-s.jpg" alt="" loading="lazy"></div><div class="in"><span class="meta">Log 02 · Digital twins</span><h3>From a PDF floor plan to a 3D building</h3><span class="soon">Coming soon</span></div></div>
      <div class="card log-card"><div class="cover"><img src="${r}assets/img/scenes/agents-s.jpg" alt="" loading="lazy"></div><div class="in"><span class="meta">Log 03 · AI agents</span><h3>What an AI catches in vendor quotations</h3><span class="soon">Coming soon</span></div></div>
    </div>
  </div>
</section>
${ctaBand(r)}
`,
};

/* ---------- contact ---------- */
const contact = {
  path: 'contact.html',
  title: 'Contact',
  description: `Talk to Mimar AI on WhatsApp (${SITE.whatsappDisplay}) or by email (${SITE.email}). Book a site walk for your building.`,
  active: 'contact',
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>Contact</span></div>
    <span class="eyebrow">Contact</span>
    <h1 class="display" style="max-width:14ch">Tell us about <span class="accent">your building.</span></h1>
    <p class="lede">WhatsApp is the fastest way to reach us. Prefer email? Fill in the form and send it from your own email app.</p>
  </div>
</section>
<section class="section">
  <div class="container contact-grid">
    <div style="display:flex;flex-direction:column;gap:14px">
      <a class="contact-card wa" href="${wa()}" target="_blank" rel="noopener"><span class="ic">${I.chat}</span><span><span class="k">WhatsApp</span><span class="v">${SITE.whatsappDisplay}</span></span></a>
      <div class="contact-card"><span class="ic">${I.mail}</span><span><span class="k">Email</span><a class="v" href="mailto:${SITE.email}">${SITE.email}</a></span><button class="copy" type="button" data-copy="${SITE.email}">Copy</button></div>
      <div class="contact-card"><span class="ic">${I.pin}</span><span><span class="k">Based in</span><span class="v">${SITE.city}</span></span></div>
      <div class="card" style="margin-top:8px;box-shadow:none">
        <h3>What happens next</h3>
        <ul class="checklist" style="margin-top:14px">
          <li>${I.check}<span>We reply and ask a few questions about your site.</span></li>
          <li>${I.check}<span>We set up a short site walk, in person or on a call.</span></li>
          <li>${I.check}<span>You get a clear proposal for a small pilot.</span></li>
        </ul>
      </div>
    </div>
    <form class="form" id="contact-form" novalidate>
      <div class="row">
        <div class="field"><label for="f-name">Your name</label><input id="f-name" name="name" autocomplete="name" required placeholder="Full name"></div>
        <div class="field"><label for="f-company">Company or building</label><input id="f-company" name="company" autocomplete="organization" placeholder="e.g. Clifton office tower"></div>
      </div>
      <div class="row">
        <div class="field"><label for="f-email">Email</label><input id="f-email" name="email" type="email" autocomplete="email" placeholder="you@company.com"></div>
        <div class="field"><label for="f-phone">Phone or WhatsApp</label><input id="f-phone" name="phone" type="tel" autocomplete="tel" placeholder="+92"></div>
      </div>
      <div class="field"><label for="f-building">Building type</label>
        <select id="f-building" name="building"><option value="">Choose one</option><option>Office</option><option>Bank or branch network</option><option>Hospital or clinic</option><option>School or university</option><option>Factory or warehouse</option><option>Hotel or mall</option><option>Other</option></select>
      </div>
      <fieldset class="checks field"><legend>Interested in</legend>
        ${SERVICES.map((s, i) => `<label class="check"><input type="checkbox" name="services" value="${s.name}" id="f-s${i}"><span>${s.name}</span></label>`).join('')}
      </fieldset>
      <div class="field"><label for="f-msg">What’s the problem?</label><textarea id="f-msg" name="message" placeholder="e.g. 3 floors, about 40 ACs, and the bill keeps rising"></textarea></div>
      <div class="form-actions">
        <button class="btn btn-mint btn-lg" type="submit">${I.chat}Send on WhatsApp</button>
        <button class="btn btn-ghost btn-lg" type="button" id="send-email">${I.mail}Send by email</button>
      </div>
      <p class="form-note">Both buttons open your own WhatsApp or email app with the message filled in. Nothing is sent until you press send there.</p>
      <p class="form-status" id="form-status" role="status" aria-live="polite"></p>
    </form>
  </div>
</section>
`,
};

/* ---------- privacy ---------- */
const privacy = {
  path: 'privacy.html',
  title: 'Privacy',
  description: 'How the Mimar AI website handles your information.',
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>Privacy</span></div>
    <h1 class="display" style="font-size:clamp(40px,5vw,64px)">Privacy</h1>
    <p class="lede">Last updated 28 September 2026.</p>
  </div>
</section>
<section class="section">
  <div class="container article">
    <h2 style="margin-top:0">This website</h2>
    <p>This website does not use advertising or tracking cookies, and it does not store the details you type into the contact form. The form opens WhatsApp or your email app with your message filled in; nothing is sent until you press send there.</p>
    <h2>When you contact us</h2>
    <p>If you message us on WhatsApp or by email, we use your name, contact details and message only to reply to you and to discuss your project. We don’t sell or share them.</p>
    <h2>Our systems in your building</h2>
    <p>Project data, such as camera events, drawings, quotations and maintenance records, belongs to you. How it is stored and who can access it is agreed with you in writing for each project.</p>
    <h2>Questions</h2>
    <p>Email <a href="mailto:${SITE.email}">${SITE.email}</a> or message us on WhatsApp at ${SITE.whatsappDisplay}.</p>
  </div>
</section>
`,
};

/* ---------- 404 ---------- */
const notFound = {
  path: '404.html',
  root: '/',
  title: 'Page not found',
  description: 'This page does not exist.',
  body: (r) => `
<section class="page-hero blueprint" style="border-bottom:0">
  <div class="container" style="align-items:flex-start;padding-block:120px">
    <span class="eyebrow">Error 404</span>
    <h1 class="display">This room <span class="accent">is empty.</span></h1>
    <p class="lede">The page you’re looking for isn’t here. It may have moved, or the link may be wrong.</p>
    <div class="hero-actions"><a class="btn btn-primary btn-lg" href="${r}index.html">Go to the homepage</a><a class="btn btn-ghost btn-lg" href="${r}services.html">See our services</a></div>
  </div>
</section>
`,
};

const terms = {
  path: 'terms.html',
  title: 'Terms',
  description: 'Terms of use for the Mimar AI website.',
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>Terms</span></div>
    <h1 class="display" style="font-size:clamp(40px,5vw,64px)">Terms of use</h1>
    <p class="lede">Last updated 28 September 2026.</p>
  </div>
</section>
<section class="section">
  <div class="container article">
    <h2 style="margin-top:0">Using this website</h2>
    <p>This website describes the services of Mimar AI, based in ${SITE.city}. You may browse it, share its pages and contact us through it.</p>
    <h2>Information on this site</h2>
    <p>We keep the content accurate and up to date, but it is general information, not a quote or a contract. The 3D scenes and the figures shown in them are illustrations. Every project is agreed separately in writing, with its own scope, price and terms.</p>
    <h2>Brand and content</h2>
    <p>The Mimar AI name, the Tower M logo, the 3D scenes, videos and text on this site belong to Mimar AI. Please ask before reusing them.</p>
    <h2>Links</h2>
    <p>Links to other websites, such as WhatsApp, open services that have their own terms.</p>
    <h2>Contact</h2>
    <p>Questions about these terms: <a href="mailto:${SITE.email}">${SITE.email}</a> or WhatsApp ${SITE.whatsappDisplay}.</p>
  </div>
</section>
`,
};

export default [experience, about, logs, contact, privacy, terms, notFound];
