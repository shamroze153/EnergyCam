"""Build popbook/frog-prince.html from the fox book's engine plus this book's art, story and Urdu."""
import pathlib, re, sys
HERE = pathlib.Path(__file__).parent  # this book's art, story and Urdu
SRC = HERE.parent / 'first-snow.html'
OUT = HERE.parent / 'frog-prince.html'
s = SRC.read_text()


def rep(a, b, n=1):
    global s
    c = s.count(a)
    assert c == n, (c, a[:90])
    s = s.replace(a, b)


def rep_block(start, end, new):
    global s
    i = s.index(start); j = s.index(end, i)
    s = s[:i] + new + s[j:]


TITLE = 'The Queen and the Frog'
rep('<title>The Fox of the First Snow</title>', f'<title>{TITLE}</title>')
rep('An original interactive 3D pop-up storybook, written by Shamroze for Princess Zainab.', 'An original interactive 3D pop-up storybook, written by Shamroze for Queen Zainab.')
rep('<style>\n', '<style>\n#mkBtn,#setMake{display:none!important}\n')
rep('<div class="chip"><b>The Fox of the First Snow</b><span>by Shamroze · for Princess Zainab</span></div>', f'<div class="chip"><b>{TITLE}</b><span>by Shamroze · for Queen Zainab</span></div>')
rep('<div id="capTitle">The Fox of the First Snow</div>', f'<div id="capTitle">{TITLE}</div>')
rep('The snow is beginning to fall…', 'The frog is warming up his ribbit…')

# who the book is for
rep("const DEFAULT_CFG = { p: 'fox', n: 'Zainab', nu: 'زینب', t: 'Princess', k: 'girl', s: '#dcab86', h: '#2b1a14', y: 'long', a: 'bow',",
    "const DEFAULT_CFG = { p: 'fox', n: 'Zainab', nu: 'زینب', t: 'Queen', k: 'girl', s: '#e6b994', h: '#2b1a14', y: 'long', a: 'crown',")
rep("  m: 'who makes the coldest nights feel warm.\\nMay you always find the light,\\nand always be the light\\nfor someone else.' };",
    "  m: 'who is kind to every creature,\\nbig or small.\\nMay you always see the prince\\nhiding inside every frog.' };")
rep("t: [['Princess', 'Princess'], ['Prince', 'Prince'], ['', 'Just the name']],", "t: [['Queen', 'Queen'], ['Princess', 'Princess'], ['Prince', 'Prince'], ['', 'Just the name']],")
rep("const UR_TITLE = { Princess: 'شہزادی', Prince: 'شہزادہ' };", "const UR_TITLE = { Queen: 'ملکہ', Princess: 'شہزادی', Prince: 'شہزادہ' };")
rep("const DEFAULT_UR_MSG = 'جس کی مسکراہٹ سرد ترین راتوں کو بھی گرم کر دیتی ہے۔\\nدعا ہے کہ تمہیں ہمیشہ روشنی ملے،\\nاور تم ہمیشہ کسی اور کے لیے روشنی بنو۔';",
    "const DEFAULT_UR_MSG = 'جو ہر چھوٹے بڑے جاندار سے پیار کرتی ہے۔\\nدعا ہے کہ تم ہمیشہ\\nہر مینڈک کے اندر چھپا شہزادہ دیکھ سکو۔';")
rep_block('const DICT = {', 'const TR = ', (HERE / 'dict.js').read_text())
rep_block('const UR_PARAS = [null,', 'function T(str) {', (HERE / 'ur.js').read_text())
for k in ["'fox-book'"]:
    rep(k, "'frog-book'", 2)
rep("'fox-prefs'", "'frog-prefs'", 2)
rep("indexedDB.open('fox-voices', 1)", "indexedDB.open('frog-voices', 1)")

# Shamroze: lantern optional, crown and golden ball optional
rep("function shamroze(g, cx, by, k = 1) {", "function shamroze(g, cx, by, k = 1, o = {}) {")
lan = """  stroke(g, '#2a2d44', .012 * k, g => { g.moveTo(X(.46), Y(1.02)); g.lineTo(X(.46), Y(.96)); }, false);
  cut(g, '#2a2d44', g => { poly(g, [X(.39), Y(.95), X(.53), Y(.95), X(.46), Y(1.0)]); rr(g, X(.39), Y(.78), .14 * k, .03 * k, .01 * k); });
  cut(g, '#ffd27a', g => rr(g, X(.41), Y(.945), .1 * k, .165 * k, .02 * k), { sc: 'rgba(255,200,100,1)', blur: 14, oy: 0 });
}
function armArt"""
assert s.count(lan) == 1
s = s.replace(lan, """  if (o.crown) { cut(g, '#ffcf4a', g => poly(g, [X(-.1), Y(2.1), X(-.12), Y(2.3), X(-.05), Y(2.22), X(.01), Y(2.34), X(.07), Y(2.22), X(.14), Y(2.29), X(.12), Y(2.09)]), { blur: 3, oy: 1 }); dots(g, '#e2456f', [[X(.01), Y(2.16)]], .022 * k); }
  if (o.ball) { const r = .085 * k, bx = X(.46), byy = Y(1.0); cut(g, '#ffcf4a', g => circ(g, bx, byy, r), { sc: 'rgba(255,200,80,1)', blur: 14, oy: 0 }); cut(g, 'rgba(255,255,255,.8)', g => ell(g, bx - r * .35, byy - r * .4, r * .25, r * .13, -.6), { shadow: false }); }
  if (o.lantern !== false) {
""" + lan.replace("\n}\nfunction armArt", "\n  }\n}\nfunction armArt"))

# this book's art, then its story
rep('/* ================================================================== 3D helpers (glows, particles, aurora) */',
    (HERE / 'art.js').read_text() + '\n/* ================================================================== 3D helpers (glows, particles, aurora) */')
rep_block('/* ================================================================== the story (original text, written for this book) */\nconst SP = [',
          '/* ================================================================== textures for pages, cover, table */', (HERE / 'sp.js').read_text() + '\n')

# page furniture
rep("g.fillText(T('پہلی برف {f:کی|کا} {ua}'), cx, 98);", "g.fillText('ملکہ اور مینڈک', cx, 98);")
rep("g.fillText(T('THE {AU} OF THE FIRST SNOW'), cx, 92);", "g.fillText('THE QUEEN AND THE FROG', cx, 92);")
rep("function pxFlake(g, x, y, r, col, lw) { g.save(); g._u = 1; flake(g, x, y, r, col, lw); g.restore(); }",
    "function pxFlake(g, x, y, r, col, lw) { g.save(); g._u = 1; stroke(g, col, lw, g => { g.moveTo(x, y - r); g.quadraticCurveTo(x, y, x + r, y); g.quadraticCurveTo(x, y, x, y + r); g.quadraticCurveTo(x, y, x - r, y); g.quadraticCurveTo(x, y, x, y - r); g.closePath(); }, false); dots(g, col, [[x, y]], r * .2); g.restore(); }")
rep("bg.addColorStop(0, '#1c2a5e'); bg.addColorStop(1, '#141d44');", "bg.addColorStop(0, '#1f5a44'); bg.addColorStop(1, '#123a2c');")
rep("silver.addColorStop(0, '#f4f7ff'); silver.addColorStop(.5, '#a9b6d6'); silver.addColorStop(1, '#eef2ff');", "silver.addColorStop(0, '#fff6dc'); silver.addColorStop(.5, '#e2c98a'); silver.addColorStop(1, '#fff3d0');")
rep("g.fillText('پہلی برف', cx, 235); g.fillText(T('{f:کی|کا} {ua}'), cx, 365);", "g.fillText('ملکہ', cx, 235); g.fillText('اور مینڈک', cx, 365);")
rep("g.fillText(T('The {A} of'), cx, 240); g.fillText('the First Snow', cx, 340);", "g.fillText('The Queen', cx, 240); g.fillText('and the Frog', cx, 340);")
rep("tg.save(); tg.translate(.38, 1.92); tailArt(tg); tg.restore(); fox(tg, 1.65, 2.62, 2.0);",
    "frogArt(tg, 1.3, 2.62, 2.5); tg.beginPath(); circ(tg, 2.45, 2.36, .22); tg.fillStyle = '#fff'; tg.fill();")
rep("const gl = g.createRadialGradient(cx - 90, 760, 10, cx - 90, 760, 160); gl.addColorStop(0, 'rgba(255,200,103,.45)'); gl.addColorStop(1, 'rgba(255,200,103,0)'); g.fillStyle = gl; g.fillRect(cx - 260, 600, 340, 320);",
    "const gl = g.createRadialGradient(cx + 137, 805, 10, cx + 137, 805, 130); gl.addColorStop(0, 'rgba(255,200,103,.55)'); gl.addColorStop(1, 'rgba(255,200,103,0)'); g.fillStyle = gl; g.fillRect(cx - 10, 670, 300, 280);")
rep("g.fillStyle = '#1f2d63'; g.fillRect(0, 0, 512, 512); for (let y = 0; y < 512; y += 64) for (let x = 0; x < 512; x += 64) pxFlake(g, x + ((y / 64) % 2 ? 32 : 0) + 16, y + 32, 11, 'rgba(210,222,255,.35)', 1.6);",
    "g.fillStyle = '#1f4a3a'; g.fillRect(0, 0, 512, 512); for (let y = 0; y < 512; y += 64) for (let x = 0; x < 512; x += 64) pxFlake(g, x + ((y / 64) % 2 ? 32 : 0) + 16, y + 32, 11, 'rgba(255,225,150,.4)', 1.6);")
rep("const cloth = lam({ color: '#1b2758' })", "const cloth = lam({ color: '#1b4a38' })")

rep('const t = tweens[i], p = Math.min(1, (now - t.t0) / t.d);', 'const t = tweens[i], p = clamp((now - t.t0) / t.d, 0, 1);')

# lighting for a sunny garden and under the water
rep("  twilight: { bg: '#15132a',", "  day: { bg: '#18221c', sky: '#fffbe8', gnd: '#4a5a3a', hi: 1.7, sun: '#fff4d6', si: 2.9, fi: .55 },\n  deep: { bg: '#0d2230', sky: '#c6f1ff', gnd: '#1f4a5a', hi: 1.45, sun: '#d6f4ff', si: 2.1, fi: .35 },\n  twilight: { bg: '#15132a',")

# the falling snow becomes petals, fireflies, bubbles and magic dust
rep("let snowTarget = 0;", "let snowTarget = 0, snowDir = 1;")
rep("for (let i = 0; i < SNOWN; i++) { const j = i * 3; snowPos[j + 1] -= snowSpd[i] * dt; snowPos[j] += (Math.sin(t * .8 + snowPh[i]) * .12 + wind * (.6 + snowSpd[i])) * dt; if (snowPos[j] > 4.6) snowPos[j] = -.3; if (snowPos[j + 1] < Y0) { snowPos[j + 1] = Y0 + 4.4;",
    "for (let i = 0; i < SNOWN; i++) { const j = i * 3; snowPos[j + 1] -= snowSpd[i] * dt * snowDir * (snowDir < 0 ? .6 : 1); snowPos[j] += (Math.sin(t * .8 + snowPh[i]) * .12 + wind * (.6 + snowSpd[i])) * dt; if (snowPos[j] > 4.6) snowPos[j] = -.3; if (snowDir > 0 ? snowPos[j + 1] < Y0 : snowPos[j + 1] > Y0 + 4.4) { snowPos[j + 1] = snowDir > 0 ? Y0 + 4.4 : Y0;")
rep("snowTarget = c.kind === 'close' ? 0 : c.b.snow; }", "snowTarget = c.kind === 'close' ? 0 : c.b.snow; if (c.kind !== 'close') { snow.material.color.set(c.b.fall || '#ffffff'); snowDir = c.b.up ? -1 : 1; } }")

# sounds for this book
rep("    note(f) { tone(f, f * 1.002, .6, .06, 'triangle'); },",
    "    note(f) { tone(f, f * 1.002, .6, .06, 'triangle'); },\n"
    "    ribbit() { [0, .17].forEach(d => { tone(210, 120, .11, .13, 'square', d); tone(420, 260, .09, .03, 'sawtooth', d); }); },\n"
    "    splash() { burstN('lowpass', 2600, 280, .8, .32); burstN('highpass', 2200, 5200, .45, .08, .06); tone(320, 80, .3, .1); },\n"
    "    plip() { tone(1000, 320, .12, .08); burstN('bandpass', 1600, 600, .15, .05); },")

# the opening hook: golden sparkles and a frog on the table
rep("function flakeTex() { const c = mk(128, 128), g = c.getContext('2d'); g._u = 1; flake(g, 64, 64, 50, '#ffffff', 6); dots(g, '#ffffff', [[64, 64]], 9); return new THREE.CanvasTexture(c); }",
    "function flakeTex() { const c = mk(128, 128), g = c.getContext('2d'); g._u = 1; twinkle(g, 64, 64, 56, '#ffffff'); dots(g, '#ffffff', [[64, 64]], 10); return new THREE.CanvasTexture(c); }")
rep("function pawTex() { const c = mk(64, 64), g = c.getContext('2d'); g.fillStyle = '#fff'; g.beginPath(); ell(g, 32, 40, 13, 11); circ(g, 18, 24, 6); circ(g, 28, 17, 6); circ(g, 38, 17, 6); circ(g, 47, 24, 6); g.fill(); return new THREE.CanvasTexture(c); }",
    "function pawTex() { return frogPrint(); }")
rep("const halo = glow('#bfe0ff', 1.15, .7);", "const halo = glow('#ffd27a', 1.15, .7);")
rep("map: pt, color: '#ffc867',", "map: pt, color: '#a8f08a',")
rep("fg.save(); fg.translate(.02, .52); fg.scale(.62, .62); tailArt(fg); fg.restore(); fox(fg, .5, 1.0, .82); };", "frogArt(fg, .45, .98, 1.15); };")
rep("HOOK.foxGlow = glow('#ffb347', .7, .6); HOOK.foxGlow.position.set(-.2, .3, .05);", "HOOK.foxGlow = glow('#ffcf4a', .7, .45); HOOK.foxGlow.position.set(0, .7, .03);")
rep("burst(f.getWorldPosition(new THREE.Vector3()), '#dff0ff', 40, 1.4, .09, 1.2, -.4);", "burst(f.getWorldPosition(new THREE.Vector3()), '#ffe7a8', 40, 1.4, .09, 1.2, -.4);")
rep("spark(f.position.clone(), '#dff0ff',", "spark(f.position.clone(), '#ffe7a8',")
rep("if (ur) $('i1').append(T('{f:ایک ننھی|ایک ننھا} {ua} '), name, T(' کا انتظار کر {f:رہی|رہا} ہے…'));\n  else $('i1').append(T('A little {a} is waiting for '), name, '…');",
    "if (ur) $('i1').append('ایک ننھا مینڈک ', name, ' کا انتظار کر رہا ہے…');\n  else $('i1').append('A little frog is waiting for ', name, '…');")
rep("'کتاب کھولنے کے لیے تین چمکتے برف کے گالے پکڑیں' : 'Catch the 3 glowing snowflakes to open the book'", "'کتاب کھولنے کے لیے تین سنہری ستارے پکڑیں' : 'Catch the 3 golden sparkles to open the book'")
rep("bubble(LANG === 'ur' ? '“برف کے گالے پکڑو، {N}!”' : '“Catch the snowflakes, {N}!”', { grp: HOOK.fox }, 1.2, 2200); sfx.chime([784, 988]);",
    "bubble(LANG === 'ur' ? '“ٹرّ ٹرّ! سنہری ستارے پکڑو، {N}!”' : '“Ribbit! Catch the golden sparkles, {N}!”', { grp: HOOK.fox }, 1.2, 2200); sfx.ribbit();")
rep("bubble(LANG === 'ur' ? '“پہلے برف کے گالے پکڑیں ✨”' : '“Catch the snowflakes first!”'", "bubble(LANG === 'ur' ? '“پہلے سنہری ستارے پکڑیں ✨”' : '“Catch the sparkles first!”'")

# titles in the chrome
UR_T = 'ملکہ اور مینڈک'
rep("$('capTitle').textContent = closed ? T(LANG === 'ur' ? 'پہلی برف {f:کی|کا} {ua}' : 'The {A} of the First Snow') : T(TR(sp.title));",
    f"$('capTitle').textContent = closed ? (LANG === 'ur' ? '{UR_T}' : '{TITLE}') : T(TR(sp.title));")
rep("document.querySelector('.top .chip b').textContent = T('The {A} of the First Snow'); document.title = T('The {A} of the First Snow');",
    f"document.querySelector('.top .chip b').textContent = '{TITLE}'; document.title = '{TITLE}';")
rep("$('rTitle').textContent = sp.dedication ? T(LANG === 'ur' ? 'پہلی برف {f:کی|کا} {ua}' : 'The {A} of the First Snow') : T(TR(sp.title));",
    f"$('rTitle').textContent = sp.dedication ? (LANG === 'ur' ? '{UR_T}' : '{TITLE}') : T(TR(sp.title));")
rep("draw: { princess, fox, tailArt, castle, pine, drift, moon, flake, shamroze,", "draw: { princess, fox, tailArt, castle, pine, drift, moon, flake, shamroze, frogArt, prince, ballArt,")

left = [w for w in ['First Snow', 'snowflakes', 'tailArt(fg)'] if w in s]
print('leftovers:', left)
OUT.write_text(s)
print('wrote', OUT, len(s.splitlines()), 'lines')
