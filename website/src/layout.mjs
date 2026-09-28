import { SITE, SERVICES, I, LOGO, wa } from './site.mjs';

export const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const THREE_CDN = 'https://cdn.jsdelivr.net/npm/three@0.147.0/build/three.min.js';

function header(active, r) {
  const items = SERVICES.map((s) => `
          <a class="mega-item" href="${r}services/${s.slug}.html"><span class="ic">${I[s.icon]}</span><span><strong>${s.name}</strong><span>${s.menu}</span></span></a>`).join('');
  const cur = (k) => (active === k ? ' aria-current="page"' : '');
  return `
<div class="topbar"><div class="container"><span class="tag">NEW</span><span>See every service as a 3D problem and fix.</span><a href="${r}experience.html">Open the 3D experience →</a></div></div>
<header class="site-header">
  <div class="container">
    <a class="brand" href="${r}index.html" aria-label="Mimar AI home">${LOGO(38)}<span>Mimar <b>AI</b></span></a>
    <nav class="nav" aria-label="Main">
      <div class="nav-drop${active === 'services' ? ' current' : ''}">
        <button type="button" aria-expanded="false" aria-haspopup="true">Services ${I.chevron}</button>
        <div class="mega">
          <div class="mega-list">${items}
            <a class="mega-item all" href="${r}services.html"><span class="ic">${I.layers}</span><span><strong>All services</strong><span>Compare them and see where to start</span></span></a>
          </div>
          <a class="mega-promo" href="${r}experience.html"><img src="${r}assets/img/scenes/twin-s.jpg" alt="" loading="lazy"><strong>See all five in 3D</strong><span>Flip each scene from problem to solution.</span></a>
        </div>
      </div>
      <a href="${r}experience.html"${cur('experience')}>3D experience</a>
      <a href="${r}index.html#industries">Industries</a>
      <a href="${r}about.html"${cur('about')}>About</a>
      <a href="${r}logs.html"${cur('logs')}>Build logs</a>
    </nav>
    <div class="header-cta">
      <a class="btn btn-ghost btn-sm" href="${wa()}" target="_blank" rel="noopener">${I.chat}WhatsApp</a>
      <a class="btn btn-primary btn-sm" href="${r}contact.html">Book a site visit</a>
      <button class="burger" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="drawer">${I.menu}</button>
    </div>
  </div>
</header>
<div class="drawer" id="drawer" role="dialog" aria-modal="true" aria-label="Menu">
  <div class="drawer-top"><a class="brand" href="${r}index.html">${LOGO(34)}<span>Mimar <b>AI</b></span></a><button class="burger drawer-close" type="button" aria-label="Close menu" style="display:inline-flex">${I.close}</button></div>
  <nav aria-label="Mobile">
    <a href="${r}services.html">Services</a>
    <div class="sub">${SERVICES.map((s) => `<a href="${r}services/${s.slug}.html">${s.num} · ${s.name}</a>`).join('')}</div>
    <a href="${r}experience.html">3D experience</a>
    <a href="${r}index.html#industries">Industries</a>
    <a href="${r}about.html">About</a>
    <a href="${r}logs.html">Build logs</a>
    <a href="${r}contact.html">Contact</a>
  </nav>
  <div class="acts">
    <a class="btn btn-mint btn-lg" href="${wa()}" target="_blank" rel="noopener">${I.chat}Chat on WhatsApp</a>
    <a class="btn btn-primary btn-lg" href="${r}contact.html">Book a site visit</a>
  </div>
</div>`;
}

export function ctaBand(r, title = 'Tell us about your building.', text = 'Send a message with your building type and the problem that costs you most. We’ll suggest where to start.') {
  return `
<section class="section-tight"><div class="container">
  <div class="cta-band" data-reveal>
    <div><h2 class="h2">${title}</h2><p>${text}</p></div>
    <div class="acts">
      <a class="btn btn-primary btn-lg" href="${wa()}" target="_blank" rel="noopener">${I.chat}WhatsApp ${SITE.whatsappDisplay}</a>
      <a class="btn btn-ghost btn-lg" href="${r}contact.html">${I.mail}Send an enquiry</a>
      <span class="contact-line">${SITE.email}</span>
    </div>
  </div>
</div></section>`;
}

function footer(r) {
  return `
<footer class="site-footer">
  <div class="container">
    <div class="top">
      <div>
        <a class="brand" href="${r}index.html">${LOGO(38)}<span>Mimar <b>AI</b></span></a>
        <p class="about">AI for the buildings you already run. Founded by a facility engineer in ${SITE.city.split(',')[0]}.</p>
        <span class="hash">#AIforBuildings</span>
      </div>
      <div><h4>Services</h4><ul>${SERVICES.map((s) => `<li><a href="${r}services/${s.slug}.html">${s.name}</a></li>`).join('')}</ul></div>
      <div><h4>Company</h4><ul><li><a href="${r}about.html">About</a></li><li><a href="${r}experience.html">3D experience</a></li><li><a href="${r}logs.html">Build logs</a></li><li><a href="${r}contact.html">Contact</a></li></ul></div>
      <div><h4>Explore</h4><ul><li><a href="${r}services.html">All services</a></li><li><a href="${r}index.html#industries">Industries</a></li><li><a href="${r}index.html#process">How we work</a></li><li><a href="${r}privacy.html">Privacy</a></li></ul></div>
      <div><h4>Contact</h4><ul>
        <li><a href="${wa()}" target="_blank" rel="noopener">WhatsApp ${SITE.whatsappDisplay}</a></li>
        <li><a href="mailto:${SITE.email}">${SITE.email}</a></li>
        <li><span style="color:#DCE6E2;font-size:15px">${SITE.city}</span></li>
      </ul></div>
    </div>
    <div class="bottom"><span>© <span data-year>2026</span> Mimar AI. All rights reserved.</span><span><a href="${r}privacy.html">Privacy</a></span></div>
  </div>
</footer>
<a class="wa-float" href="${wa()}" target="_blank" rel="noopener" aria-label="Chat with Mimar AI on WhatsApp"><span class="dot">${I.chat}</span><span class="lbl">Chat with us</span></a>`;
}

export function page({ path, title, description, active = '', body, three = false, jsonld = null }) {
  const depth = path.split('/').length - 1;
  const r = '../'.repeat(depth);
  const fullTitle = title ? `${title} · Mimar AI` : 'Mimar AI · AI for the buildings you already run';
  const desc = description || SITE.description;
  const canonical = SITE.url ? `<link rel="canonical" href="${SITE.url}/${path.replace(/index\.html$/, '')}">` : '';
  const ogImg = SITE.url ? `${SITE.url}/assets/img/og.png` : `${r}assets/img/og.png`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${esc(fullTitle)}</title>
<meta name="description" content="${esc(desc)}">
<meta name="theme-color" content="#F6F8F7">
${canonical}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Mimar AI">
<meta property="og:title" content="${esc(fullTitle)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:image" content="${ogImg}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="${r}assets/img/favicon.svg" type="image/svg+xml">
<link rel="icon" href="${r}assets/img/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="${r}assets/img/apple-touch-icon.png">
<link rel="manifest" href="${r}site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@500;700;800&family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<link rel="stylesheet" href="${r}assets/css/site.css">
${jsonld ? `<script type="application/ld+json">${JSON.stringify(jsonld)}</script>` : ''}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
${header(active, r)}
<main id="main">
${body(r)}
</main>
${footer(r)}
${three ? `<script src="${THREE_CDN}" defer></script>\n<script src="${r}assets/js/mimar3d.js" defer></script>` : ''}
<script src="${r}assets/js/site.js" defer></script>
</body>
</html>
`;
}
