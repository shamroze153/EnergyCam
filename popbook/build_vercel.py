"""Build a stand-alone static site (for Vercel or any static host) from the artifact pages.

The artifact files are written for claude.ai, which wraps them in a document skeleton at
publish time. This script adds that skeleton, swaps the claude.ai "Share menu" wording for a
built-in copy-link step, and writes the site to ./vercel-site.

    python3 build_vercel.py
"""
import pathlib, shutil

HERE = pathlib.Path(__file__).parent
OUT = HERE / 'vercel-site'

HEAD = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#10152a">
{META}
<style>
*,*::before,*::after{box-sizing:border-box}
:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
html,body{margin:0}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
img{max-width:100%}
[hidden]{display:none!important}
</style>
</head>
<body>
'''
TAIL = '\n</body>\n</html>\n'


META = {
    'book': ('The Fox of the First Snow', 'A 3D pop-up storybook where your child is the hero. Swipe the pages, hear it in English or Urdu, even in your own voice.', '/og-image.png', '/favicon.svg'),
    'alice': ('Alice Pop-Up Edition', 'An interactive 3D pop-up edition of Alice’s Adventures in Wonderland.', '/og-image.png', '/favicon.svg'),
}


def wrap(src: str, kind: str = 'book') -> str:
    import re
    title, desc, img, icon = META[kind]
    src = re.sub(r'^<title>.*?</title>\n', '', src.strip(), count=1)
    src = re.sub(r'^<meta name="description"[^>]*>\n', '', src, count=1, flags=re.M)
    meta = (f'<title>{title}</title>\n<meta name="description" content="{desc}">\n'
            f'<link rel="icon" href="{icon}" type="image/svg+xml">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:title" content="{title}">\n'
            f'<meta property="og:description" content="{desc}">\n<meta property="og:image" content="{img}">\n'
            f'<meta name="twitter:card" content="summary_large_image">')
    return HEAD.replace('{META}', meta) + src + TAIL


def storybook(src: str) -> str:
    swaps = [
        ('<p class="bShare"><b>To share it:</b> after you create it, use this page’s <b>Share</b> menu and copy the link. That link opens this child’s own book.</p>',
         '<p class="bShare"><b>To share it:</b> when you create the book its link is copied for you. Paste it into WhatsApp or a message; that link opens this child’s own book.</p>'),
        ("  CFG = sanitize({ ...draft, n: draft.n.trim(), g: draft.g.trim() }); const code = encCfg(CFG);",
         "  CFG = sanitize({ ...draft, n: draft.n.trim(), g: draft.g.trim() }); const code = encCfg(CFG);\n"
         "  const shareUrl = location.href.split('#')[0] + '#book-' + code; let copied = false;\n"
         "  try { navigator.clipboard?.writeText(shareUrl).then(() => { copied = true; }, () => { }); } catch (e) { }"),
        ("  toast(`${tn(CFG)}’s book is ready. Use Share › Copy link to send it.`);",
         "  toast(`${tn(CFG)}’s book is ready. Its link is copied: paste it in WhatsApp to send it.`, 6000);"),
    ]
    for a, b in swaps:
        assert src.count(a) == 1, a[:80]
        src = src.replace(a, b)
    return wrap(src)


README = '''# The Fox of the First Snow

An interactive 3D pop-up storybook where the child is the hero. Static site: plain HTML,
no build step and no server code. Three.js and the fonts load from public CDNs.

- `/` the storybook (English and Urdu, character builder, family voice)
- `/alice` the Alice in Wonderland pop-up demo

## 1. Put it on GitHub

1. Go to github.com, click **New repository**, give it a name (for example `fox-storybook`),
   keep it Public or Private, and click **Create repository**.
2. On the new repository page click **uploading an existing file**.
3. Drag in **everything inside this folder** (`index.html`, `alice`, `favicon.svg`,
   `og-image.png`, `vercel.json`, `README.md`) and click **Commit changes**.

Or with git:

```
git init
git add .
git commit -m "First version"
git branch -M main
git remote add origin https://github.com/<you>/fox-storybook.git
git push -u origin main
```

## 2. Deploy from GitHub to Vercel

1. Go to vercel.com and sign in with GitHub.
2. Click **Add New > Project**, find `fox-storybook`, and click **Import**.
3. Framework Preset: **Other**. Leave Build Command and Output Directory empty.
4. Click **Deploy**. In about a minute the book is live at `https://<project>.vercel.app/`.

Every time you push a change to GitHub, Vercel publishes it again by itself.

## 3. After the first deploy

- **WhatsApp link preview:** open `index.html` and `alice/index.html`, and change
  `content="/og-image.png"` to the full address, for example
  `content="https://fox-storybook.vercel.app/og-image.png"`. WhatsApp and Facebook need the
  full address to show the cover picture.
- **Your own domain:** in Vercel open the project > Settings > Domains and add it.

## How it works on your site

- **Make your own:** builds a child's book; the link is copied automatically and opens that
  child's book on any phone.
- **English / Urdu:** button at the top, or Aa > Language.
- **Family voice:** on your own site the microphone works, so each page has a Record button.
  Recordings are saved on the device that recorded them (in the browser's storage). For a
  child on another phone to hear them, the voices need online storage (for example
  Vercel Blob or Supabase); that is the next thing to add.
'''


FAVICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1c2a5e"/><circle cx="20" cy="40" r="12" fill="#ffc867" opacity=".35"/><path d="M14 44c4-10 14-12 22-10l4-12 4 9 6 1-4 6c2 6-2 12-10 14H22c-6 0-10-3-8-8z" fill="#e8742c"/><path d="M12 46c-2-6 2-12 10-12" stroke="#fff4e6" stroke-width="4" fill="none" stroke-linecap="round"/><circle cx="44" cy="30" r="1.8" fill="#1d1410"/></svg>'''

VERCEL = '''{
  "cleanUrls": true,
  "trailingSlash": false,
  "headers": [
    { "source": "/(.*)", "headers": [
      { "key": "Permissions-Policy", "value": "microphone=(self)" },
      { "key": "X-Content-Type-Options", "value": "nosniff" }
    ] }
  ]
}
'''


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'alice').mkdir(parents=True)
    (OUT / 'index.html').write_text(storybook((HERE / 'first-snow.html').read_text()))
    (OUT / 'alice' / 'index.html').write_text(wrap((HERE / 'index.html').read_text(), 'alice'))
    (OUT / 'favicon.svg').write_text(FAVICON)
    (OUT / 'vercel.json').write_text(VERCEL)
    (OUT / '.gitignore').write_text('.vercel\n.DS_Store\nnode_modules\n')
    og = HERE / 'og-image.png'
    if og.exists():
        shutil.copy(og, OUT / 'og-image.png')
    (OUT / 'README.md').write_text(README)
    print('built', OUT)


if __name__ == '__main__':
    main()
