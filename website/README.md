# Mimar AI website

The public website for Mimar AI: a light, fast, static site with interactive 3D scenes built on three.js.

- **13 pages:** home, services overview, 5 service pages, 3D experience, about, build logs, contact, privacy, 404
- **Interactive 3D:** a hero building with a hotspot for each service, and a problem → solution scene for every service
- **No backend and no build dependencies.** The finished site is plain HTML, CSS and JS in `dist/`, so it can be hosted anywhere for free.

## Folder layout

```
website/
├── build.mjs              # builds src/ into dist/ (Node 18+, no npm install needed)
├── src/
│   ├── site.mjs           # contact details, service copy, industries, icons, logo
│   ├── layout.mjs         # <head>, header with the services menu, footer, CTA band
│   ├── pages/             # home, services (+ one page per service), other pages
│   └── assets/
│       ├── css/site.css   # the design system
│       ├── js/site.js     # menu, mobile drawer, reveal on scroll, contact form
│       ├── js/mimar3d.js  # the 3D engine (scenes + hero building)
│       ├── img/           # logo, icons, social image, 3D scene posters
│       └── video/         # EnergyCam promo and the 3D services film
└── dist/                  # the built site: deploy this folder
```

## Change the content

1. Edit `src/site.mjs` for WhatsApp, email, city and all service copy (titles, steps, features, FAQs).
2. Edit a page in `src/pages/` for page-specific sections.
3. Rebuild:

```bash
cd website
node build.mjs
```

## Preview locally

```bash
cd website/dist
python3 -m http.server 8080
# open http://localhost:8080
```

## Deploy (pick one)

- **Netlify (easiest):** go to app.netlify.com/drop and drag the `website/dist` folder onto the page.
- **Vercel or Cloudflare Pages:** import this repository, set the root directory to `website`, the build command to `node build.mjs`, and the output directory to `dist`.
- **GitHub Pages:** publish the contents of `website/dist` (for example with a Pages workflow, or by copying `dist` to a `gh-pages` branch).

Once you have a domain, set `url` in `src/site.mjs` (for example `https://mimar.ai`) and rebuild. That adds canonical links, an absolute social-share image URL and a `sitemap.xml`.

## Before launch

- Add the founder's name and photo on the About page and the homepage founder block (`src/pages/other.mjs`, `src/pages/home.mjs`).
- Add real client logos or results once you have permission to show them.
- Add LinkedIn and X links to the footer in `src/layout.mjs`.
- The contact form opens WhatsApp or the visitor's email app with the message filled in. To receive form submissions directly, connect a form service such as Formspree and point the form at it.

## About the 3D

`mimar3d.js` needs three.js r147, loaded from jsDelivr on pages that use 3D. Scenes start only when they scroll into view, pause when off screen, respect reduced-motion settings, and show a poster image if WebGL is not available. The figures shown inside the scenes are illustrations, and the site labels them as such.
