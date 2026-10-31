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


def wrap(src: str) -> str:
    return HEAD + src.strip() + TAIL


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


README = '''# The Fox of the First Snow (pop-up storybook)

A static site: no build step and no server code. Three.js and the fonts load from public CDNs.

## Put it on Vercel

1. Unzip this folder.
2. Go to vercel.com > Add New > Project, and drag the unzipped folder in
   (or run `npx vercel` inside the folder and accept the defaults).
3. Framework preset: **Other**. Build command: none. Output directory: `.` (the folder itself).
4. Deploy. Your book is at `https://<your-project>.vercel.app/`, and the Alice demo at `/alice/`.

## How it behaves on your own site

- **Make your own:** builds a child's book; the link is copied automatically and opens that
  child's book on any phone.
- **English / Urdu:** button at the top, or Aa > Language.
- **Family voice:** on your own site the microphone works, so each page has a Record button.
  Recordings are saved **on the device that recorded them** (in the browser's storage). To let a
  child on another phone hear them, the voices need online storage (for example Vercel Blob or
  Supabase); that is the next step to add.
'''


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'alice').mkdir(parents=True)
    (OUT / 'index.html').write_text(storybook((HERE / 'first-snow.html').read_text()))
    (OUT / 'alice' / 'index.html').write_text(wrap((HERE / 'index.html').read_text()))
    (OUT / 'README.md').write_text(README)
    print('built', OUT)


if __name__ == '__main__':
    main()
