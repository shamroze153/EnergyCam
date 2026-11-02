"""Build popbook/where-hugs-go.html: the frog book's engine and art, with this book's foxes, story and stars (English only)."""
import pathlib
HERE = pathlib.Path(__file__).parent
SRC = HERE.parent / 'frog-prince.html'
OUT = HERE.parent / 'where-hugs-go.html'
s = SRC.read_text()


def rep(a, b, n=1):
    global s
    c = s.count(a); assert c == n, (c, a[:90]); s = s.replace(a, b)


def rep_block(start, end, new):
    global s
    i = s.index(start); j = s.index(end, i); s = s[:i] + new + s[j:]


T0, T1 = 'The Queen and the Frog', 'Where Do Hugs Go?'
rep(f'<title>{T0}</title>', f'<title>{T1}</title>')
rep('An original interactive 3D pop-up storybook, written by Shamroze for Queen Zainab.', 'An original interactive 3D pop-up storybook about where hugs go, written by Shamroze for every little one.')
rep('#mkBtn,#setMake{display:none!important}', '#mkBtn,#setMake,#langBtn,.setRow:has(#langSeg){display:none!important}')
rep(f'<b>{T0}</b><span>by Shamroze · for Queen Zainab</span>', f'<b>{T1}</b><span>by Shamroze · for every little one</span>')
rep(f'<div id="capTitle">{T0}</div>', f'<div id="capTitle">{T1}</div>')
rep('The frog is warming up his ribbit…', 'The stars are coming out…')
rep("n: 'Zainab', nu: 'زینب', t: 'Queen',", "n: 'every little one', nu: '', t: '',")
rep("  m: 'who is kind to every creature,\\nbig or small.\\nMay you always see the prince\\nhiding inside every frog.' };",
    "  m: 'and every grown-up\\nwho ever tucked one in.\\nGoodnight.\\nLook up.' };")
rep_block('const DICT = {', 'const TR = ', "const DICT = {};\n")
rep_block('const UR_PARAS = [null,', 'function T(str) {', "const UR_PARAS = new Proxy([], { get: (a, i) => SP[i]?.paras });\n")
rep("'frog-book'", "'hugs-book'", 2); rep("'frog-prefs'", "'hugs-prefs'", 2); rep("indexedDB.open('frog-voices', 1)", "indexedDB.open('hugs-voices', 1)")
rep('/* ================================================================== 3D helpers (glows, particles, aurora) */', (HERE / 'art.js').read_text() + '\n/* ================================================================== 3D helpers (glows, particles, aurora) */')
rep_block('/* ================================================================== loose pieces that travel through the scene (the ball, the frog) */',
          '/* ================================================================== textures for pages, cover, table */', (HERE / 'sp.js').read_text() + '\n')
rep("g.fillText('THE QUEEN AND THE FROG', cx, 92);", "g.fillText('WHERE DO HUGS GO?', cx, 92);")
rep("bg.addColorStop(0, '#1f5a44'); bg.addColorStop(1, '#123a2c');", "bg.addColorStop(0, '#2c2a6e'); bg.addColorStop(1, '#17163f');")
rep("g.fillText('The Queen', cx, 240); g.fillText('and the Frog', cx, 340);", "g.fillText('Where Do', cx, 240); g.fillText('Hugs Go?', cx, 340);")
rep("frogArt(tg, 1.3, 2.62, 2.5); tg.beginPath(); circ(tg, 2.45, 2.36, .22); tg.fillStyle = '#fff'; tg.fill();",
    "kit(tg, 1.15, 2.8, 1.45); kit(tg, 2.2, 2.8, .8, { flip: true }); tg.fillStyle = '#fff'; tg.beginPath(); heart(tg, 1.75, .75, .22); tg.fill(); [[.45, .5], [2.6, .45], [.3, 1.4], [2.75, 1.3], [1.2, .3], [2.25, .95]].forEach(([x, y], i) => { tg.beginPath(); circ(tg, x, y, .035 + (i % 3) * .015); tg.fill(); });")
rep("const gl = g.createRadialGradient(cx + 137, 805, 10, cx + 137, 805, 130);", "const gl = g.createRadialGradient(cx, 560, 10, cx, 560, 160);")
rep("g.fillRect(cx - 10, 670, 300, 280);", "g.fillRect(cx - 170, 400, 340, 330);")
rep("g.fillStyle = '#1f4a3a'; g.fillRect(0, 0, 512, 512);", "g.fillStyle = '#24204f'; g.fillRect(0, 0, 512, 512);")
rep("const cloth = lam({ color: '#1b4a38' })", "const cloth = lam({ color: '#2a2560' })")
rep("frogArt(fg, .45, .98, 1.15); };", "kit(fg, .55, .98, .75, { young: true }); };")
rep("if (ur) $('i1').append('ایک ننھا مینڈک ', name, ' کا انتظار کر رہا ہے…');\n  else $('i1').append('A little frog is waiting for ', name, '…');",
    "$('i1').append('A little fox has a question for ', Object.assign(document.createElement('b'), { textContent: 'you' }), '…');")
rep("'کتاب کھولنے کے لیے تین سنہری ستارے پکڑیں' : 'Catch the 3 golden sparkles to open the book'", "'کتاب کھولنے کے لیے تین ستارے پکڑیں' : 'Catch the 3 falling stars to open the book'")
rep("'“ٹرّ ٹرّ! سنہری ستارے پکڑو، {N}!”' : '“Ribbit! Catch the golden sparkles, {N}!”'", "'“ستارے پکڑو!”' : '“Catch the stars!”'")
rep("{ grp: HOOK.fox }, 1.2, 2200); sfx.ribbit();", "{ grp: HOOK.fox }, 1.2, 2200); sfx.chime([784, 988]);")
rep("'“پہلے سنہری ستارے پکڑیں ✨”' : '“Catch the sparkles first!”'", "'“پہلے ستارے پکڑیں ✨”' : '“Catch the stars first!”'")
rep(f"(LANG === 'ur' ? 'ملکہ اور مینڈک' : '{T0}')", f"'{T1}'", 2)
rep(f"textContent = '{T0}'; document.title = '{T0}';", f"textContent = '{T1}'; document.title = '{T1}';")
rep("frogArt, prince, ballArt,", "frogArt, prince, ballArt, kit,")
OUT.write_text(s)
print('wrote', OUT, len(s.splitlines()), 'lines', [w for w in ['Zainab', 'frog-book'] if w in s])
s = s.replace('placeholder="e.g. Zainab"', 'placeholder="e.g. Ava"').replace('(defaults: Zainab)', '(defaults: the reader)')
OUT.write_text(s)
