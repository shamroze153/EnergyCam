"""Original soundtrack + SFX for the Mimar AI PDF-to-3D promo.
120 BPM, A minor, 4-bar loop (Am9 - Fmaj7 - Cmaj7 - G6). Scene hits land on bar lines.
Usage: python3 music.py out.wav
"""
import sys, json
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 44100
DUR = 41.0
N = int(SR * DUR)
BPM = 120.0
BEAT = 60.0 / BPM          # 0.5 s
BAR = BEAT * 4             # 2.0 s
rng = np.random.default_rng(7)

L = np.zeros(N); R = np.zeros(N)          # dry bus
RL = np.zeros(N); RR = np.zeros(N)        # reverb send
SC = np.ones(N)                           # sidechain gain (ducked by kick)

def midi(m): return 440.0 * 2 ** ((m - 69) / 12)
def tt(n): return np.arange(n) / SR
def idx(t): return int(round(t * SR))

def add(buf_l, buf_r, sig, t0, pan=0.0, gain=1.0):
    i = idx(t0)
    if i >= N: return
    sig = sig[: N - i]
    gl = gain * np.sqrt(0.5 * (1 - pan)); gr = gain * np.sqrt(0.5 * (1 + pan))
    buf_l[i:i + len(sig)] += sig * gl
    buf_r[i:i + len(sig)] += sig * gr

def dry(sig, t0, pan=0, gain=1, send=0.0):
    add(L, R, sig, t0, pan, gain)
    if send: add(RL, RR, sig, t0, pan, gain * send)

def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR / 2 - 100) / (SR / 2), 'low', output='sos'), x)
def hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), 'high', output='sos'), x)
def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band', output='sos'), x)

def env_adsr(n, a, d, s, r, sus_len):
    t = tt(n)
    e = np.where(t < a, t / max(a, 1e-4), 1.0)
    e = np.where((t >= a) & (t < a + d), 1 - (1 - s) * (t - a) / d, e)
    e = np.where((t >= a + d), s, e)
    rel0 = a + d + sus_len
    e = np.where(t >= rel0, s * np.exp(-(t - rel0) / max(r, 1e-4) * 4), e)
    return e

def saw(f, n, detune=0.0):
    t = tt(n); ph = (f * (1 + detune)) * t
    return 2 * (ph - np.floor(ph + 0.5))

# ---------------- instruments ----------------
def kick(gain=1.0):
    n = idx(0.45); t = tt(n)
    f = 45 + 95 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 7.5)
    click = hp(rng.standard_normal(n), 3000) * np.exp(-t * 400) * 0.25
    return (s + click) * gain

def clap():
    n = idx(0.35); t = tt(n)
    nz = bp(rng.standard_normal(n), 900, 5000)
    e = np.zeros(n)
    for o in (0, 0.011, 0.022):
        e += np.where(t >= o, np.exp(-(t - o) * 60), 0)
    e += np.exp(-t * 14) * 0.5
    return nz * e * 0.5

def hat(open_=False):
    n = idx(0.25 if open_ else 0.06); t = tt(n)
    return hp(rng.standard_normal(n), 7000) * np.exp(-t * (18 if open_ else 90)) * 0.35

def pluck(m, length=0.35):
    n = idx(length + 0.4); t = tt(n); f = midi(m)
    s = 0.6 * np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) + 0.1 * saw(f, n)
    return lp(s * np.exp(-t * 9), 5000)

def bass(m, length):
    n = idx(length + 0.05); t = tt(n); f = midi(m)
    s = saw(f, n) * 0.6 + np.sin(2 * np.pi * f * t) * 0.8
    s = lp(s, 380)
    e = np.minimum(1, t / 0.005) * np.exp(-t * 3) * np.where(t > length, np.exp(-(t - length) * 60), 1)
    return s * e

def pad(notes, length, cutoff=1800):
    n = idx(length + 1.2); s = np.zeros(n)
    for m in notes:
        for dt in (-0.006, 0.0, 0.007):
            s += saw(midi(m), n, dt)
    s = lp(s / (len(notes) * 3), cutoff, 3)
    return s * env_adsr(n, 0.35, 0.4, 0.8, 1.0, length - 0.75)

def whoosh(length=1.0, up=True, gain=1.0):
    n = idx(length); t = tt(n); x = rng.standard_normal(n)
    out = np.zeros(n); seg = 512
    for i in range(0, n, seg):        # moving band-pass sweep
        u = i / n; u = u if up else 1 - u
        fc = 300 * (2 ** (u * 5.2))
        chunk = x[max(0, i - 2048): i + seg]
        y = bp(chunk, fc * 0.6, min(fc * 1.6, SR / 2 - 200))[-min(seg, n - i):]
        out[i:i + len(y)] = y
    e = (t / length) ** 2 if up else np.exp(-t / length * 5)
    if up: e = e * np.where(t > length * 0.92, np.exp(-(t - length * 0.92) * 60), 1)
    return out * e * gain

def impact(gain=1.0):
    n = idx(2.5); t = tt(n)
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-t * 10)) / SR) * np.exp(-t * 2.2)
    nz = lp(rng.standard_normal(n), 1200) * np.exp(-t * 6) * 0.4
    return (boom + nz) * gain

def blip(m, length=0.12, gain=0.3):
    n = idx(length + 0.25); t = tt(n); f = midi(m)
    s = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t)
    return s * np.exp(-t * 22) * gain

def click_sfx():
    n = idx(0.08); t = tt(n)
    return (hp(rng.standard_normal(n), 2500) * np.exp(-t * 250) * 0.6 + np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 120) * 0.4)

def paper(gain=0.5):
    n = idx(0.5); t = tt(n)
    return bp(rng.standard_normal(n), 1500, 8000) * np.exp(-t * 10) * (1 - np.exp(-t * 80)) * gain

def rumble(length, gain=0.6):
    n = idx(length); t = tt(n)
    x = lp(rng.standard_normal(n), 140, 3) * 3
    e = np.sin(np.pi * np.clip(t / length, 0, 1)) ** 0.7
    return x * e * gain

# ---------------- arrangement ----------------
CHORDS = [  # (bass root, pad voicing, arp tones)
    (45, [57, 60, 64, 67, 71], [69, 72, 76, 79, 83, 76]),   # Am9
    (41, [57, 60, 64, 65, 69], [65, 69, 72, 76, 77, 72]),   # Fmaj7
    (48, [55, 59, 60, 64, 67], [67, 71, 72, 76, 79, 72]),   # Cmaj7
    (43, [55, 59, 62, 64, 67], [67, 71, 74, 76, 79, 74]),   # G6
]
END = 35.0      # drums stop, final chord
bars = int(END / BAR)
for b in range(bars):
    t0 = b * BAR
    root, voicing, arp = CHORDS[b % 4]
    pad_cut = 900 if t0 < 4 else 2200
    dry(pad(voicing, BAR, pad_cut), t0, 0, 0.22, send=0.5)
    # arpeggio (16ths), sparse in intro
    for k in range(16):
        tk = t0 + k * BEAT / 4
        if t0 < 4 and k % 2: continue
        m = arp[(k * 5 + b) % len(arp)] + (12 if (k % 8 == 7 and t0 >= 13) else 0)
        g = 0.13 if t0 < 6 else 0.17
        dry(pluck(m), tk, pan=0.45 * np.sin(k * 1.3), gain=g, send=0.35)
        dry(pluck(m) * 0.5, tk + BEAT * 0.75, pan=-0.6 * np.sin(k * 1.3), gain=g * 0.5, send=0.4)  # ping-pong echo
    if t0 >= 4:
        for q in range(4):
            tb = t0 + q * BEAT
            dry(kick(), tb, 0, 0.95)
            i = idx(tb); m = min(N - i, idx(0.32))
            SC[i:i + m] = np.minimum(SC[i:i + m], 0.35 + 0.65 * (np.arange(m) / m) ** 0.7)
            # off-beat bass
            dry(bass(root, BEAT * 0.42), tb + BEAT / 2, 0, 0.55)
            if t0 >= 6:
                dry(hat(q == 3), tb + BEAT / 2, 0.25, 0.8)
                dry(hat() * 0.5, tb + BEAT / 4, -0.3, 0.6)
                dry(hat() * 0.5, tb + 3 * BEAT / 4, -0.3, 0.6)
            if t0 >= 13 and q in (1, 3):
                dry(clap(), tb, 0.05, 0.6, send=0.25)

# final chord ring-out (Am9 add high), no drums
dry(pad([45, 57, 60, 64, 67, 71, 76], 4.5, 2600), END, 0, 0.3, send=0.7)
for k, m in enumerate([69, 72, 76, 79, 83, 88]):
    dry(pluck(m, 0.6), END + k * 0.09, pan=(-1) ** k * 0.4, gain=0.18, send=0.6)

# ---------------- sound design (synced to picture) ----------------
cues = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
# scene transitions: riser into the bar line
for tb in (4.0, 6.0, 13.0, 20.0, 30.0, 35.0):
    ln = 1.2 if tb != 4.0 else 2.0
    dry(whoosh(ln, True, 0.22), tb - ln, 0, 1, send=0.4)
    dry(whoosh(0.8, False, 0.12), tb, 0, 1, send=0.5)
dry(impact(0.55), 4.0, 0, 1, send=0.3)
dry(impact(0.7), 35.0, 0, 1, send=0.5)
for t0, g in cues.get('paper', []):
    dry(paper(g), t0, pan=rng.uniform(-.5, .5), gain=1, send=0.3)
for t0, m in cues.get('blip', []):
    dry(blip(m), t0, pan=rng.uniform(-.4, .4), gain=0.8, send=0.45)
for t0 in cues.get('click', []):
    dry(click_sfx(), t0, 0.2, 0.8, send=0.2)
for t0, ln in cues.get('rumble', []):
    dry(rumble(ln), t0, 0, 1, send=0.2)
for t0, ln in cues.get('scan', []):
    dry(whoosh(ln, True, 0.10), t0, 0, 1, send=0.5)

# ---------------- mix ----------------
def reverb(x, secs=2.6):
    n = idx(secs); t = tt(n)
    ir = rng.standard_normal(n) * np.exp(-t / secs * 5.5)
    ir = lp(ir, 6000); ir /= np.sqrt(np.sum(ir ** 2))
    return fftconvolve(x, ir)[:N]
wetL = reverb(RL); wetR = reverb(RR)
mixL = L * np.where(SC < 1, 1, 1) + wetL * 0.9
mixR = R + wetR * 0.9
# sidechain the reverb/pad wash lightly for pump
mixL = L + wetL * 0.9 * SC; mixR = R + wetR * 0.9 * SC
mix = np.stack([mixL, mixR], 1)
mix = hp(mix.T, 25).T
# fades
ft = tt(N)
mix *= np.clip(ft / 0.05, 0, 1)[:, None]
mix *= np.clip((DUR - ft) / 2.5, 0, 1)[:, None]
# soft clip + normalize
mix = mix / np.max(np.abs(mix)) * 1.4
mix = np.tanh(mix)
mix = mix / np.max(np.abs(mix)) * 0.89
from scipy.io import wavfile
wavfile.write(sys.argv[1], SR, (mix * 32767).astype(np.int16))
print('ok', sys.argv[1], 'rms dB', 20 * np.log10(np.sqrt(np.mean(mix ** 2))))
