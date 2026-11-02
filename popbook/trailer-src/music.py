import numpy as np, wave, sys
SR = 44100; DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 62.0
n = int(SR * DUR); L = np.zeros(n); R = np.zeros(n)
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def add(buf, start, sig, gain=1.0):
    i = int(start * SR); j = min(n, i + len(sig))
    if i < n: buf[i:j] += sig[:j - i] * gain
def bell(m, dur=1.6, dec=3.2):
    t = np.arange(int(SR * dur)) / SR; f = hz(m)
    s = np.sin(2*np.pi*f*t) + .45*np.sin(2*np.pi*2.0*f*t)*np.exp(-t*4) + .25*np.sin(2*np.pi*3.01*f*t)*np.exp(-t*7) + .1*np.sin(2*np.pi*4.2*f*t)*np.exp(-t*10)
    env = np.exp(-t*dec) * np.minimum(1, t / .004); return s * env
def pad(ms, dur):
    t = np.arange(int(SR * dur)) / SR; s = sum(np.sin(2*np.pi*hz(m)*t + k) for k, m in enumerate(ms)) / len(ms)
    env = np.minimum(1, t / .8) * np.minimum(1, (dur - t) / .8); return s * env * (1 + .15*np.sin(2*np.pi*.5*t))
bpm = 92; beat = 60 / bpm; bar = 4 * beat
chords = [(62, [62, 66, 69]), (57, [61, 64, 69]), (59, [62, 66, 71]), (55, [59, 62, 67])]  # D A Bm G
melody = [[78, 76, 74, 76], [76, 73, 69, 73], [74, 78, 81, 78], [79, 78, 76, 74]]
nbars = int(DUR / bar) + 1
for b in range(nbars):
    t0 = b * bar; root, tri = chords[b % 4]
    add(L, t0, pad([root - 12] + tri, bar + .6), .05); add(R, t0, pad([root - 12] + tri, bar + .6), .05)
    add(L, t0, bell(root - 12, 2.5, 1.6), .18); add(R, t0, bell(root - 12, 2.5, 1.6), .18)
    arp = [tri[0], tri[1], tri[2], tri[0] + 12, tri[2], tri[1], tri[2], tri[0] + 12]
    for k, m in enumerate(arp):
        s = bell(m + 12, 1.2, 4.5); g = .07 if b > 0 else .05; add(L, t0 + k * beat / 2, s, g * (1.1 if k % 2 else .9)); add(R, t0 + k * beat / 2, s, g * (.9 if k % 2 else 1.1))
    if b >= 2:
        for k, m in enumerate(melody[b % 4]):
            s = bell(m, 1.8, 2.6); add(L, t0 + k * beat, s, .11); add(R, t0 + k * beat, s, .11)
def sparkle(t0, up=True):
    for k in range(8):
        m = 88 + (k if up else -k) * 2; s = bell(m, .7, 6)
        add(L, t0 + k * .05, s, .05); add(R, t0 + k * .05 + .01, s, .05)
for t0 in (2.9, 3.5, 4.1): sparkle(t0)
sparkle(4.6); sparkle(DUR - 4.6)
mix = np.stack([L, R], 1); fade = np.ones(n); fi = int(SR * 1.0); fo = int(SR * 3.5)
fade[:fi] = np.linspace(0, 1, fi); fade[-fo:] = np.linspace(1, 0, fo); mix *= fade[:, None]
mix = np.tanh(mix * 1.2) / np.tanh(1.2); mix *= .85 / np.abs(mix).max()
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok', DUR)
