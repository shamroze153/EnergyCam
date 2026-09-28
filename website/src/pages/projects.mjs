import { I, svcByKey } from '../site.mjs';
import { PROJECTS } from '../projects.mjs';
import { ctaBand } from '../layout.mjs';

export const projectCard = (p, r) => `
      <article class="card proj" data-reveal id="${p.slug}">
        <div class="media"><span class="pill-3d">${p.status}</span><img src="${r}${p.image}" alt="${p.title}" loading="lazy" width="1600" height="1000"></div>
        <div class="in">
          <span class="meta">${p.year} · ${svcByKey[p.service] ? svcByKey[p.service].name : ''}</span>
          <h3>${p.title}</h3>
          <p>${p.summary}</p>
          ${p.points && p.points.length ? `<ul class="checklist">${p.points.map((x) => `<li>${I.check}<span>${x}</span></li>`).join('')}</ul>` : ''}
          ${p.tags && p.tags.length ? `<div class="tag-row">${p.tags.map((t) => `<span class="tag">${t}</span>`).join('')}</div>` : ''}
          <div class="links">${(p.links || []).map((l) => `<a class="link-arrow" href="${/^https?:/.test(l.href) ? l.href : r + l.href}"${/^https?:/.test(l.href) ? ' target="_blank" rel="noopener"' : ''}>${l.label} ${I.arrow}</a>`).join('')}</div>
        </div>
      </article>`;

export default {
  path: 'projects.html',
  title: 'Projects',
  description: 'Projects built by Mimar AI: computer vision, digital twins, AI agents and more, from real buildings.',
  active: 'projects',
  body: (r) => `
<section class="page-hero blueprint">
  <div class="container">
    <div class="crumbs"><a href="${r}index.html">Home</a><span>/</span><span>Projects</span></div>
    <span class="eyebrow">Projects · ${PROJECTS.length}</span>
    <h1 class="display" style="max-width:15ch">Things we’ve built, <span class="accent">and what they do.</span></h1>
    <p class="lede">Every project starts with a problem on site. This list grows as we build. For the full story behind each one, read the build logs.</p>
  </div>
</section>
<section class="section">
  <div class="container proj-grid">
    ${PROJECTS.map((p) => projectCard(p, r)).join('')}
  </div>
</section>
${ctaBand(r, 'Have a problem worth building for?', 'Tell us what keeps going wrong in your building. The next project on this page could be yours.')}
`,
};
