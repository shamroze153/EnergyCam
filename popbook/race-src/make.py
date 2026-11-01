"""Build popbook/zainab-runs.html: the frog book's engine and garden art, with this book's art, story and Urdu."""
import pathlib
HERE = pathlib.Path(__file__).parent
SRC = HERE.parent / 'frog-prince.html'
OUT = HERE.parent / 'zainab-runs.html'
s = SRC.read_text()


def rep(a, b, n=1):
    global s
    c = s.count(a); assert c == n, (c, a[:90]); s = s.replace(a, b)


def rep_block(start, end, new):
    global s
    i = s.index(start); j = s.index(end, i); s = s[:i] + new + s[j:]


T0, T1, UR0, UR1 = 'The Queen and the Frog', 'Queen Zainab Runs', 'ملکہ اور مینڈک', 'ملکہ زینب کی دوڑ'
rep(f'<title>{T0}</title>', f'<title>{T1}</title>')
rep('An original interactive 3D pop-up storybook, written by Shamroze for Queen Zainab.', 'An original interactive 3D pop-up storybook about a rainy-day race, written by Shamroze for Queen Zainab.')
rep(f'<b>{T0}</b>', f'<b>{T1}</b>'); rep(f'<div id="capTitle">{T0}</div>', f'<div id="capTitle">{T1}</div>')
rep('The frog is warming up his ribbit…', 'The rain is beginning to fall…')
rep("  m: 'who is kind to every creature,\\nbig or small.\\nMay you always see the prince\\nhiding inside every frog.' };",
    "  m: 'who never gives up,\\nwho always lends a hand,\\nand who shines brightest\\nwhen it pours.' };")
rep("const DEFAULT_UR_MSG = 'جو ہر چھوٹے بڑے جاندار سے پیار کرتی ہے۔\\nدعا ہے کہ تم ہمیشہ\\nہر مینڈک کے اندر چھپا شہزادہ دیکھ سکو۔';",
    "const DEFAULT_UR_MSG = 'جو کبھی ہمت نہیں ہارتی،\\nجو ہمیشہ دوسروں کا ہاتھ تھامتی ہے،\\nاور بارش میں سب سے زیادہ چمکتی ہے۔';")
rep_block('const DICT = {', 'const TR = ', (HERE / 'dict.js').read_text())
rep_block('const UR_PARAS = [null,', 'function T(str) {', (HERE / 'ur.js').read_text())
rep("'frog-book'", "'race-book'", 2); rep("'frog-prefs'", "'race-prefs'", 2); rep("indexedDB.open('frog-voices', 1)", "indexedDB.open('race-voices', 1)")
rep('/* ================================================================== 3D helpers (glows, particles, aurora) */', (HERE / 'art.js').read_text() + '\n/* ================================================================== 3D helpers (glows, particles, aurora) */')
rep_block('/* ================================================================== loose pieces that travel through the scene (the ball, the frog) */',
          '/* ================================================================== textures for pages, cover, table */', (HERE / 'sp.js').read_text() + '\n')

# page furniture and cover
rep(f"g.fillText('{UR0}', cx, 98);", f"g.fillText('{UR1}', cx, 98);")
rep("g.fillText('THE QUEEN AND THE FROG', cx, 92);", "g.fillText('QUEEN ZAINAB RUNS', cx, 92);")
rep("bg.addColorStop(0, '#1f5a44'); bg.addColorStop(1, '#123a2c');", "bg.addColorStop(0, '#2a5a8a'); bg.addColorStop(1, '#16345a');")
rep("g.fillText('ملکہ', cx, 235); g.fillText('اور مینڈک', cx, 365);", "g.fillText('ملکہ زینب', cx, 235); g.fillText('کی دوڑ', cx, 365);")
rep("g.fillText('The Queen', cx, 240); g.fillText('and the Frog', cx, 340);", "g.fillText('Queen Zainab', cx, 240); g.fillText('Runs', cx, 340);")
rep("frogArt(tg, 1.3, 2.62, 2.5); tg.beginPath(); circ(tg, 2.45, 2.36, .22); tg.fillStyle = '#fff'; tg.fill();",
    "zainabRunner(tg, 1.47, 2.85, 1.45); tg.fillStyle = '#fff'; [[.35, .7], [2.55, .55], [.5, 1.6], [2.5, 1.5], [.75, 2.4], [2.3, 2.45], [1.5, .2]].forEach(([x, y]) => { tg.beginPath(); tg.moveTo(x, y - .11); tg.quadraticCurveTo(x + .09, y + .03, x, y + .06); tg.quadraticCurveTo(x - .09, y + .03, x, y - .11); tg.fill(); });")
rep("const gl = g.createRadialGradient(cx + 137, 805, 10, cx + 137, 805, 130);", "const gl = g.createRadialGradient(cx, 640, 10, cx, 640, 150);")
rep("g.fillRect(cx - 10, 670, 300, 280);", "g.fillRect(cx - 160, 490, 320, 300);")
rep("g.fillStyle = '#1f4a3a'; g.fillRect(0, 0, 512, 512);", "g.fillStyle = '#1f3f63'; g.fillRect(0, 0, 512, 512);")
rep("const cloth = lam({ color: '#1b4a38' })", "const cloth = lam({ color: '#1b3a5c' })")

# rain: a grey-blue mood, fast falling drops, and weather sounds
rep("  deep: { bg: '#0d2230',", "  rain: { bg: '#131b25', sky: '#d6e4f0', gnd: '#3a4a5a', hi: 1.4, sun: '#e3ebf5', si: 2.0, fi: .4 },\n  deep: { bg: '#0d2230',")
rep("let snowTarget = 0, snowDir = 1;", "let snowTarget = 0, snowDir = 1, snowMul = 1;")
rep("snowPos[j + 1] -= snowSpd[i] * dt * snowDir * (snowDir < 0 ? .6 : 1);", "snowPos[j + 1] -= snowSpd[i] * dt * snowDir * (snowDir < 0 ? .6 : 1) * snowMul;")
rep("snowDir = c.b.up ? -1 : 1; }", "snowDir = c.b.up ? -1 : 1; snowMul = c.b.rain ? 7 : 1; snow.material.size = c.b.rain ? .05 : .075; }")
rep("    plip() {", "    whistle() { tone(2350, 2500, .55, .05, 'square'); tone(2450, 2300, .55, .03, 'sine', .04); },\n"
    "    thunder() { burstN('lowpass', 320, 50, 2.4, .45); tone(62, 38, 1.8, .16, 'sawtooth', .08); },\n"
    "    cheer() { for (let i = 0; i < 7; i++) burstN('bandpass', 700 + i * 160, 1300 + i * 110, .7, .05, i * .07); },\n"
    "    quack() { tone(620, 420, .12, .1, 'sawtooth'); tone(580, 400, .12, .08, 'sawtooth', .17); },\n"
    "    drum() { tone(130, 55, .3, .28); burstN('lowpass', 700, 150, .15, .15); },\n    plip() {")

# the opening hook: raindrops and a frog under an umbrella
rep("function flakeTex() { const c = mk(128, 128), g = c.getContext('2d'); g._u = 1; twinkle(g, 64, 64, 56, '#ffffff'); dots(g, '#ffffff', [[64, 64]], 10); return new THREE.CanvasTexture(c); }", "function flakeTex() { return dropTex(); }")
rep("function pawTex() { return frogPrint(); }", "function pawTex() { return bootPrint(); }")
rep("const halo = glow('#ffd27a', 1.15, .7);", "const halo = glow('#8fc8ff', 1.15, .7);")
rep("map: pt, color: '#a8f08a',", "map: pt, color: '#9fd0ff',")
rep("frogArt(fg, .45, .98, 1.15); };", "frogArt(fg, .4, .98, 1.0, 'sit', { crown: false }); stroke(fg, '#3a3a4a', .02, g => { g.moveTo(.62, .62); g.lineTo(.62, .32); }, false); umbrellaTop(fg, .62, .32, .27, ['#e2456f', '#ffcf4a', '#3d8fd8', '#5fbf6a']); };")
rep("burst(f.getWorldPosition(new THREE.Vector3()), '#ffe7a8', 40, 1.4, .09, 1.2, -.4);", "burst(f.getWorldPosition(new THREE.Vector3()), '#cfe6ff', 40, 1.4, .09, 1.2, -.4);")
rep("spark(f.position.clone(), '#ffe7a8',", "spark(f.position.clone(), '#cfe6ff',")
rep("if (ur) $('i1').append('ایک ننھا مینڈک ', name, ' کا انتظار کر رہا ہے…');\n  else $('i1').append('A little frog is waiting for ', name, '…');",
    "if (ur) $('i1').append('بارش کی دوڑ ', name, ' کا انتظار کر رہی ہے…');\n  else $('i1').append('The rain race is waiting for ', name, '…');")
rep("'کتاب کھولنے کے لیے تین سنہری ستارے پکڑیں' : 'Catch the 3 golden sparkles to open the book'", "'کتاب کھولنے کے لیے بارش کے تین قطرے پکڑیں' : 'Catch the 3 raindrops to open the book'")
rep("'“ٹرّ ٹرّ! سنہری ستارے پکڑو، {N}!”' : '“Ribbit! Catch the golden sparkles, {N}!”'", "'“ٹرّ ٹرّ! بارش کے قطرے پکڑو، {N}!”' : '“Ribbit! Catch the raindrops, {N}!”'")
rep("'“پہلے سنہری ستارے پکڑیں ✨”' : '“Catch the sparkles first!”'", "'“پہلے بارش کے قطرے پکڑیں 💧”' : '“Catch the raindrops first!”'")

# titles in the chrome
rep(f"(LANG === 'ur' ? '{UR0}' : '{T0}')", f"(LANG === 'ur' ? '{UR1}' : '{T1}')", 2)
rep(f"textContent = '{T0}'; document.title = '{T0}';", f"textContent = '{T1}'; document.title = '{T1}';")
rep("frogArt, prince, ballArt,", "frogArt, prince, ballArt, zainabRunner, mikaalRunner, shamUmb,")
OUT.write_text(s)
print('wrote', OUT, len(s.splitlines()), 'lines; frog/royal leftovers:', [w for w in ['Frog in the Pond', 'golden sparkles', 'ملکہ اور مینڈک'] if w in s])
