"""Trilha sonora + efeitos sonoros gerados por código (100% originais, sem direitos autorais).

Uso pelo reel.py (automático no render). Teste isolado:
  python3 engine/audio.py demo <saida.wav> [segundos] [seed]

No spec.json (opcional):
  "audio": {"seed": 7, "music": true, "sfx": true, "music_volume": 1.0}
  item com "sfx": "none" | "pop" | "notif" | "success" | "whoosh" | "logo" para trocar o efeito padrão.
"""
import hashlib
import json
import subprocess
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000


# ---------- utilidades ----------
def _sos(kind, f, order=2):
    return butter(order, f, kind, fs=SR, output="sos")


def lp(x, f, o=2): return sosfilt(_sos("low", f, o), x, axis=0)
def hp(x, f, o=2): return sosfilt(_sos("high", f, o), x, axis=0)
def bp(x, lo, hi, o=2): return sosfilt(_sos("band", [lo, hi], o), x, axis=0)
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def tt(n): return np.arange(n) / SR


def pan(x, p):
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1)


def add(buf, x, pos):
    i = int(round(pos * SR))
    if x.ndim == 1: x = pan(x, 0.0)
    if i < 0: x = x[-i:]; i = 0
    if i >= len(buf): return
    n = min(len(x), len(buf) - i)
    buf[i:i + n] += x[:n]


def fade(n, a, r):
    e = np.ones(n); na = max(1, int(a * SR)); nr = max(1, min(n, int(r * SR)))
    e[:na] *= np.linspace(0, 1, na); e[n - nr:] *= np.linspace(1, 0, nr)
    return e


def make_ir(dur=1.3, tone=5500, seed=3):
    r = np.random.default_rng(seed); n = int(dur * SR)
    ir = r.standard_normal((n, 2)) * np.exp(-tt(n) / (dur / 6.9))[:, None]
    ir = lp(ir, tone)
    k = int(0.015 * SR); ir[:k] *= np.linspace(0, 1, k)[:, None]
    return ir / np.sqrt((ir ** 2).sum(0)).max()


def reverb(x, ir, wet):
    y = np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1)
    return x + wet * y


# ---------- instrumentos ----------
def kick():
    n = int(0.42 * SR); t = tt(n)
    f = 46 + 80 * np.exp(-t / 0.032)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.17)
    click = lp(np.random.default_rng(1).standard_normal(n) * np.exp(-t / 0.0025), 3500) * 0.3
    return np.tanh(1.6 * (x + click)) * 0.95


def clap(r):
    n = int(0.45 * SR); t = tt(n); e = np.zeros(n)
    for d in (0.0, 0.010, 0.021):
        i = int(d * SR); e[i:] += np.exp(-t[:n - i] / 0.006)
    i = int(0.021 * SR); e[i:] += 0.55 * np.exp(-t[:n - i] / 0.10)
    x = bp(r.standard_normal(n) * e, 950, 7000)
    body = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.035) * 0.35
    return (x * 0.9 + body) * 0.8


def hat(r, open_=False):
    n = int((0.28 if open_ else 0.06) * SR); t = tt(n)
    x = hp(r.standard_normal(n), 7500, 4) * np.exp(-t / (0.075 if open_ else 0.013))
    return x * 0.55


def shaker(r):
    n = int(0.07 * SR); t = tt(n)
    e = np.minimum(1, t / 0.012) * np.exp(-t / 0.03)
    return bp(r.standard_normal(n), 4500, 11000) * e * 0.35


def bass(f, dur):
    n = int((dur + 0.05) * SR); t = tt(n)
    x = np.sin(2 * np.pi * f * t) + 0.32 * np.sin(4 * np.pi * f * t) + 0.1 * np.sin(6 * np.pi * f * t)
    e = fade(n, 0.006, 0.05) * (0.72 + 0.28 * np.exp(-t / 0.14))
    return np.tanh(1.3 * x * e) * 0.5


def epiano(f, dur):
    n = int((dur + 0.7) * SR); t = tt(n)
    idx = 1.7 * np.exp(-t / 0.22) + 0.22
    car = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    tine = np.sin(2 * np.pi * f * 7.0 * t) * np.exp(-t / 0.018) * 0.12
    e = np.exp(-t / 1.5) * fade(n, 0.003, 0.01)
    i = int(dur * SR); e[i:] *= np.exp(-tt(n - i) / 0.13)
    return (car + tine) * e * 0.16


def pluck(f, dur, r):
    N = int(round(SR / f)); n = int((dur + 0.35) * SR)
    out = np.zeros(n + 2 * N + 2)
    seed = r.uniform(-1, 1, N); seed = np.convolve(seed, np.ones(3) / 3, "same")
    out[:N] = seed; out[N] = seed[0]
    d = 0.9965
    i = N + 1
    while i < n + N:
        out[i:i + N] = d * 0.5 * (out[i - N:i] + out[i - N - 1:i - 1]); i += N
    out = out[:n]
    f0 = SR / (N + 0.5)  # afinação exata (corrige o atraso inteiro)
    pos = np.arange(n) * (f / f0)
    y = np.interp(pos, np.arange(n), out, right=0.0)
    t = tt(n)
    y = y + 0.35 * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.25)
    e = fade(n, 0.002, 0.02); k = int(dur * SR); e[k:] *= np.exp(-tt(n - k) / 0.08)
    return y * e * 0.28


# ---------- música ----------
SCALE = [0, 2, 4, 5, 7, 9, 11]
PROGS = [[0, 4, 5, 3], [5, 3, 0, 4], [0, 5, 3, 4], [3, 0, 4, 5], [0, 3, 5, 4]]
RHY = [[0, 2, 3, 5, 6, 8, 10, 11, 13], [0, 1, 2, 4, 6, 8, 9, 10, 12],
       [1, 2, 4, 5, 7, 9, 10, 12, 14], [0, 3, 4, 6, 8, 11, 12, 14]]


def chord_pcs(key, deg, ext=(0, 2, 4, 6, 8)):
    return [key + SCALE[(deg + e) % 7] + 12 * ((deg + e) // 7) for e in ext]


def into(m, lo, hi):
    while m < lo: m += 12
    while m > hi: m -= 12
    return m


def music(T, seed=0):
    r = np.random.default_rng(seed)
    bpm = [100, 104, 108, 112, 116][seed % 5]
    key = [60, 62, 63, 65, 67, 57][(seed // 5) % 6]
    prog = PROGS[(seed // 2) % len(PROGS)]
    rhy = RHY[(seed // 3) % len(RHY)]
    beat = 60 / bpm; bar = 4 * beat
    bars = int(np.ceil(T / bar)) + 1
    n = int((T + 2) * SR)
    drums = np.zeros((n, 2)); keys = np.zeros((n, 2)); lead = np.zeros((n, 2)); low = np.zeros((n, 2))
    K = kick(); swing = 0.035 * beat
    kicks = []

    # melodia: 4 compassos (frase A + resposta B), repetida
    penta = [0, 2, 4, 7, 9]
    pool = [key + 12 + o + p for o in (0, 12) for p in penta]
    pool = [m for m in pool if 69 <= m <= 88]
    mel = []; prev = pool[len(pool) // 2]
    for half in range(2):
        for k, on in enumerate(rhy):
            b = half * 2 + on // 8
            ct = set(x % 12 for x in chord_pcs(key, prog[b], (0, 2, 4)))
            strong = on % 2 == 0
            cand = [m for m in pool if abs(m - prev) <= 5] or pool
            w = np.array([(3.0 if (m % 12) in ct and strong else 1.0) / (1 + abs(m - prev)) for m in cand])
            if half == 1 and k == len(rhy) - 1:
                cand = [m for m in pool if m % 12 == (key + SCALE[[0, 2][seed % 2]]) % 12] or cand
                w = np.ones(len(cand))
            m = cand[r.choice(len(cand), p=w / w.sum())]
            nxt = rhy[k + 1] if k + 1 < len(rhy) else 16
            mel.append((half * 16 + on, m, max(1, nxt - on)))
            prev = m

    for b in range(bars):
        t0 = b * bar; deg = prog[b % 4]
        # bateria
        for kb in (0, 2, 2.5):
            add(drums, K * (1.0 if kb != 2.5 else 0.7), t0 + kb * beat); kicks.append(t0 + kb * beat)
        for cb in (1, 3): add(drums, pan(clap(r), 0.0), t0 + cb * beat)
        for e8 in range(8):
            off = (e8 % 2) * swing
            if e8 == 7 and b % 2 == 1: add(drums, pan(hat(r, True) * 0.8, 0.3), t0 + e8 * beat / 2 + off)
            else: add(drums, pan(hat(r) * (0.9 if e8 % 2 == 0 else 0.55) * r.uniform(0.85, 1.0), 0.3), t0 + e8 * beat / 2 + off)
        for s16 in range(16):
            add(drums, pan(shaker(r) * (0.9 if s16 % 4 == 2 else 0.45) * r.uniform(0.8, 1.0), -0.35), t0 + s16 * beat / 4 + (s16 % 2) * swing * 0.5)
        # baixo
        root = into(key + SCALE[deg], 36, 47)
        for bb, d, o in ((0, 0.9, 0), (1.5, 0.4, 0), (2, 0.9, 0), (3, 0.4, 0), (3.5, 0.4, 12)):
            add(low, bass(hz(root + o), d * beat), t0 + bb * beat)
        # piano elétrico (acordes sem fundamental, com 9ª)
        notes = sorted(into(m, 58, 75) for m in chord_pcs(key, deg, (2, 4, 6, 8)))
        for cb, d, v in ((0, 1.4, 1.0), (1.5, 0.45, 0.75), (2.5, 1.4, 0.9)):
            for j, m in enumerate(notes):
                x = epiano(hz(m), d * beat) * v * r.uniform(0.9, 1.0)
                add(keys, pan(x, [-0.35, -0.1, 0.15, 0.35][j % 4]), t0 + cb * beat + j * 0.007)
        # melodia a partir do 2º compasso
        if b >= 1:
            cyc = (b - 1) % 4
            for on, m, d8 in mel:
                if on // 8 != cyc: continue
                pos = t0 + (on % 8) * beat / 2 + (on % 2) * swing
                v = (0.95 if on % 2 == 0 else 0.75) * r.uniform(0.88, 1.0)
                add(lead, pan(pluck(hz(m), d8 * beat / 2, r) * v, 0.18), pos)

    # sidechain do bumbo (efeito "pump")
    duck = np.ones(n)
    for k in kicks:
        i = int(k * SR)
        if i >= n: continue
        m = min(n - i, int(0.35 * SR))
        duck[i:i + m] = np.minimum(duck[i:i + m], 1 - 0.4 * np.exp(-tt(m) / 0.11))
    ir = make_ir()
    keys = reverb(lp(keys, 9000), ir, 0.22) * duck[:, None]
    lead = reverb(lead, ir, 0.35) * duck[:, None]
    low = lp(low, 900) * duck[:, None]
    drums = reverb(drums, make_ir(0.6, 7000, 5), 0.08)
    mix = drums * 0.7 + keys * 1.15 + lead * 1.35 + low * 0.6
    mix = hp(mix[:int(T * SR)], 38)
    mix = np.tanh(1.2 * mix / (np.abs(mix).max() + 1e-9)) / np.tanh(1.2)
    return mix, bpm


# ---------- efeitos ----------
def _bell(freqs, gap, tau, partials=((1, 1), (2.76, 0.25), (5.4, 0.08))):
    n = int((gap * len(freqs) + tau * 5) * SR); out = np.zeros(n)
    for k, f in enumerate(freqs):
        i = int(k * gap * SR); m = n - i; t = tt(m)
        x = sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t / (tau / p ** 0.5)) for p, a in partials)
        out[i:] += x * np.minimum(1, t / 0.002)
    return out


def sfx(name, r=None):
    r = r or np.random.default_rng(11)
    if name == "notif":
        x = _bell([hz(88), hz(93)], 0.085, 0.13)
        return reverb(pan(x * 0.5, 0.15), make_ir(0.8, 8000, 7), 0.25)
    if name == "success":
        x = _bell([hz(84), hz(88), hz(91), hz(96)], 0.065, 0.16, ((1, 1), (2, 0.2), (3, 0.08)))
        return reverb(pan(x * 0.42, -0.1), make_ir(1.0, 8000, 8), 0.3)
    if name == "pop":
        n = int(0.12 * SR); t = tt(n)
        f = 380 + 900 * (1 - np.exp(-t / 0.018))
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.028) * np.minimum(1, t / 0.001)
        return pan(x * 0.55, 0.0)
    if name == "whoosh":
        n = int(0.6 * SR); t = tt(n)
        u = t / t[-1]; env = np.sin(np.pi * u ** 0.8) ** 2
        noise = r.standard_normal(n)
        fc = 350 + 3800 * np.sin(np.pi * u) ** 1.5
        y = np.zeros(n); low_, band = 0.0, 0.0; q = 0.6
        for i in range(n):  # filtro de estado variável com corte variando (o "vuush")
            fq = 2 * np.sin(np.pi * fc[i] / SR)
            low_ += fq * band; hi_ = noise[i] - low_ - q * band; band += fq * hi_; y[i] = band
        y = y / (np.abs(y).max() + 1e-9) * env
        return np.stack([y * (1 - 0.6 * u), y * (0.4 + 0.6 * u)], 1) * 0.42
    if name == "logo":
        n = int(1.8 * SR); t = tt(n)
        f = 52 + 70 * np.exp(-t / 0.05)
        boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.35) * 0.7
        hit = lp(r.standard_normal(n) * np.exp(-t / 0.02), 2500) * 0.25
        sh = sum(np.sin(2 * np.pi * fr * t + r.uniform(0, 6.28)) for fr in (hz(96), hz(100), hz(103), hz(108)))
        sh = sh * np.minimum(1, t / 0.06) * np.exp(-t / 0.55) * (0.8 + 0.2 * np.sin(2 * np.pi * 7 * t)) * 0.08
        x = pan(boom + hit, 0.0) + np.stack([sh, np.roll(sh, 240)], 1)
        return reverb(x, make_ir(1.6, 7000, 9), 0.35) * 0.8
    raise ValueError(name)


# ---------- trilha do vídeo ----------
def soundtrack(events, T, opts):
    seed = int(opts.get("seed", 0))
    out = np.zeros((int(T * SR) + SR, 2))
    if opts.get("music", True):
        m, _ = music(T, seed)
        m = m * 0.30 * float(opts.get("music_volume", 1.0))
        m *= fade(len(m), 0.25, 1.6)[:, None]
        out[:len(m)] += m
    if opts.get("sfx", True):
        cache = {}; r = np.random.default_rng(seed + 100)
        for t, name in events:
            if name in (None, "none"): continue
            if name not in cache: cache[name] = sfx(name, r)
            add(out, cache[name], t)
    return out[:int(T * SR)]


def write_wav(path, x):
    peak = np.abs(x).max()
    if peak > 0.98: x = x * (0.98 / peak)
    wavfile.write(path, SR, (x * 32767).astype(np.int16))


def mux(video, wav, out):
    """Junta vídeo + áudio, com volume padrão de Reels (-14 LUFS)."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    j = json.loads(p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1])
    af = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:measured_I={input_i}:measured_TP={input_tp}:"
          "measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}").format(**j)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", af, "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", out], check=True)


def seed_from(text):
    return int(hashlib.md5(text.encode()).hexdigest()[:6], 16) % 997


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "demo":
        T = float(sys.argv[3]) if len(sys.argv) > 3 else 20
        s = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        ev = [(1.0, "pop"), (2.0, "notif"), (3.0, "success"), (3.9, "whoosh"), (5.0, "logo")]
        write_wav(sys.argv[2], soundtrack(ev, T, {"seed": s}))
        print("ok", sys.argv[2])
    else:
        print(__doc__)
