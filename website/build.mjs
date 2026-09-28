// Builds the static site into ./dist. No dependencies: run with `node build.mjs` (Node 18+).
import { mkdirSync, writeFileSync, cpSync, rmSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { page } from './src/layout.mjs';
import { SITE } from './src/site.mjs';
import home from './src/pages/home.mjs';
import services from './src/pages/services.mjs';
import other from './src/pages/other.mjs';
import projects from './src/pages/projects.mjs';

const root = dirname(fileURLToPath(import.meta.url));
const out = join(root, 'dist');
if (existsSync(out)) rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const pages = [home, ...services, projects, ...other];
for (const p of pages) {
  const file = join(out, p.path);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, page(p));
}

cpSync(join(root, 'src', 'assets'), join(out, 'assets'), { recursive: true });

writeFileSync(join(out, 'site.webmanifest'), JSON.stringify({
  name: SITE.name, short_name: SITE.name, description: SITE.tagline, start_url: './index.html', display: 'standalone',
  background_color: '#F6F8F7', theme_color: '#0B1A16',
  icons: [
    { src: 'assets/img/icon-192.png', sizes: '192x192', type: 'image/png' },
    { src: 'assets/img/icon-512.png', sizes: '512x512', type: 'image/png' },
  ],
}, null, 2));

writeFileSync(join(out, '_headers'), `/assets/*\n  Cache-Control: public, max-age=604800\n/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n`);
writeFileSync(join(out, 'robots.txt'), `User-agent: *\nAllow: /\n${SITE.url ? `Sitemap: ${SITE.url}/sitemap.xml\n` : ''}`);
if (SITE.url) {
  const urls = pages.filter((p) => p.path !== '404.html').map((p) => `  <url><loc>${SITE.url}/${p.path.replace(/index\.html$/, '')}</loc></url>`).join('\n');
  writeFileSync(join(out, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`);
}

console.log(`Built ${pages.length} pages into ${out}`);
