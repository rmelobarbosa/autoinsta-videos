#!/usr/bin/env python3
"""Motor de Reels do Auto Insta.

Uso:
  python3 engine/reel.py prep <screenshot.jpg> <saida.jpg>
      Ajusta uma captura de tela (qualquer tamanho, vertical) para 1080x1920,
      cortando a borda direita (barra de rolagem) e centralizando.
  python3 engine/reel.py check <spec.json> <contato.jpg>
      Gera um quadro de conferência com 1 frame de cada cena (rápido).
  python3 engine/reel.py render <spec.json> <saida.mp4>
      Renderiza o vídeo final (1080x1920, 30 fps, H.264 + trilha e efeitos).
  python3 engine/reel.py bg '<json do fundo>' <saida.jpg>
      Mostra como fica um fundo gráfico, ex.: '{"color":"#E4002B","accent":"#FFC72C","style":"rays"}'.

Formato do spec (JSON):
{
  "scenes": [
    {"image": "cenas/s1.jpg", "dur": 3.6, "zoom": [1.0, 1.10], "center": [[0.5,0.42],[0.5,0.40]], "vignette": true,
     "items": [
       {"type": "card", "lines": [[["Você também","ink"]], [["perde venda","grad"]]], "size": 92, "x": 70, "y": 120, "t": 0.1},
       {"type": "pill", "style": "notif", "text": "Nova mensagem", "x": "right", "y": 980, "t": 1.1},
       {"type": "pill", "style": "ok", "text": "respondido", "x": "center", "y": 1440, "t": 1.7}
     ]},
    {"bg": {"color": "#E4002B", "accent": "#FFC72C", "style": "rays"}, "dur": 3.8,
     "items": [
       {"type": "sticker", "text": "CURIOSIDADE", "bg": "accent", "fg": "ink", "x": 70, "y": 170, "t": 0.05, "angle": -4},
       {"type": "big", "lines": [[["POR QUE O","white"]], [["MÉQUI","accent"]], [["MUDOU DE NOME?","white"]]],
        "font": "Anton", "size": 170, "align": "center", "x": "center", "y": 330, "t": 0.2, "anim": "slam", "shadow": "#000000"}
     ]},
    {"end": true, "dur": 4.0, "title": "Comente QUERO", "subtitle": "e teste 7 dias grátis", "footer": "autoinsta.com.br"}
  ]
}
Cena com foto: "image". Cena gráfica (sem foto, não precisa de navegador): "bg" com
  "color" (cor do fundo), "accent" (cor de contraste) e "style": plain | rays | dots | stripes | grid | split | blob.
Estilos de texto em "lines": "ink" (quase preto), "grad" (degradê da marca), "white", "accent", "bg" ou uma cor "#RRGGBB".
Card: "align" left|center, "size" (padrão 80). Posição x: número, "center" ou "right". Posição y: número ou "below" (logo abaixo do item anterior).
Big (texto gigante sem card): "font" Anton | Archivo | Black | ExtraBold, "size", "align", "shadow" (cor da sombra dura, opcional),
  "anim" slam | pop | up, "stagger": 0.3 (cada linha entra separada, 0,3 s depois da outra).
Sticker (etiqueta inclinada): "text", "bg", "fg", "angle", "size".
Count (número que sobe animado): "to", "from" (0), "prefix", "suffix", "size" (260), "color" ("accent"), "shadow", "t", "dur" (1.2).
Barra de progresso no topo: ligada por padrão; "progress": false no spec para desligar.
Pill styles: "notif" (branca com bolinha rosa), "ok" (verde com check), "dark" (preta).
Fim: "bg" (cor sólida, opcional; sem ela usa o degradê da marca) e "accent".
Zona segura do Reels: texto entre y=110 e y=1500; nada colado na direita entre y=1100 e 1700.
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio  # trilha + efeitos (engine/audio.py)

W, H, FPS = 1080, 1920, 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")
LOGO = os.path.join(ROOT, "assets", "logo_horizontal.png")
INK = (17, 20, 23)
GRAD = [(255, 138, 0), (255, 61, 127), (162, 59, 240)]
GREEN = (10, 166, 83)


FONT_FILES = {"Anton": "Anton-Regular.ttf", "Archivo": "ArchivoBlack-Regular.ttf"}
_FCACHE = {}
def font(w, s):
    key = (w, s)
    if key not in _FCACHE:
        _FCACHE[key] = ImageFont.truetype(os.path.join(FONTS, FONT_FILES.get(w, f"Poppins-{w}.ttf")), s)
    return _FCACHE[key]


def rgb(c, default=(255, 255, 255)):
    """Cor em "#RRGGBB", lista [r,g,b] ou nome (ink, white, black)."""
    if isinstance(c, (list, tuple)): return tuple(int(v) for v in c[:3])
    if isinstance(c, str):
        if c.startswith("#") and len(c) == 7: return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
        return {"ink": INK, "white": (255, 255, 255), "black": (11, 11, 11)}.get(c, default)
    return default


def luma(c):
    r, g, b = rgb(c); return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def shade(c, k):
    """k<0 escurece, k>0 clareia."""
    r, g, b = rgb(c)
    if k < 0: return tuple(int(v * (1 + k)) for v in (r, g, b))
    return tuple(int(v + (255 - v) * k) for v in (r, g, b))


def ease_out(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3


def ease_back(t):
    t = max(0.0, min(1.0, t)); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


_GCACHE = {}
def gradient(w, h):
    key = (w, h)
    if key in _GCACHE: return _GCACHE[key]
    row = Image.new("RGB", (w, 1)); px = row.load()
    for x in range(w):
        u = x / max(1, w - 1)
        a, b, k = (GRAD[0], GRAD[1], u / 0.5) if u < 0.5 else (GRAD[1], GRAD[2], (u - 0.5) / 0.5)
        px[x, 0] = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
    g = row.resize((w, h)); _GCACHE[key] = g
    return g


def text_line(parts, size, weight="ExtraBold", palette=None):
    f = font(weight, size)
    palette = palette or {}
    widths = [f.getlength(t) for t, _ in parts]
    asc, desc = f.getmetrics()
    lw, lh = int(sum(widths)) + 4, asc + desc
    img = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    x = 0
    for (t, st), wd in zip(parts, widths):
        st = palette.get(st, st)
        if st == "grad":
            mask = Image.new("L", (lw, lh), 0)
            ImageDraw.Draw(mask).text((x, 0), t, font=f, fill=255)
            layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
            layer.paste(gradient(int(wd) + 2, lh).convert("RGBA"), (int(x), 0))
            layer.putalpha(mask)
            img = Image.alpha_composite(img, layer)
        else:
            ImageDraw.Draw(img).text((x, 0), t, font=f, fill=rgb(st) + (255,))
        x += wd
    return img


def big(lines, size=150, align="center", weight="Anton", shadow=None, palette=None, gap=None):
    """Texto gigante sem card (estilo manchete), com sombra dura opcional."""
    imgs = [text_line([tuple(p) for p in l], size, weight, palette) for l in lines]
    if weight == "Anton":  # Anton tem respiro grande em cima e embaixo: corta para as linhas ficarem juntas
        imgs = [i.crop((0, int(i.height * 0.10), i.width, int(i.height * 0.92))) for i in imgs]
    gap = int(size * 0.02) if gap is None else gap
    off = max(6, size // 14) if shadow else 0
    w = max(i.width for i in imgs) + off
    h = sum(i.height for i in imgs) + gap * (len(imgs) - 1) + off
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0)); y = 0
    for i in imgs:
        x = 0 if align == "left" else (w - off - i.width) // 2
        txt.alpha_composite(i, (x, y)); y += i.height + gap
    if not shadow: return txt
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), rgb(shadow) + (255,)); sh.putalpha(txt.getchannel("A"))
    out.alpha_composite(sh, (off, off)); out.alpha_composite(txt)
    return out


def sticker(text, bg="#FFC72C", fg="ink", size=46, angle=-4, weight="Archivo", palette=None):
    """Etiqueta inclinada (ex.: CURIOSIDADE, EM ALTA, URGENTE)."""
    palette = palette or {}
    bgc, fgc = rgb(palette.get(bg, bg)), rgb(palette.get(fg, fg))
    f = font(weight, size); asc, desc = f.getmetrics()
    tw = int(f.getlength(text)); padx, pady = int(size * 0.7), int(size * 0.38)
    w, h = tw + padx * 2, asc + desc + pady * 2
    tag = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0)); d = ImageDraw.Draw(tag)
    d.rounded_rectangle((10, 10, w + 10, h + 10), 14, fill=(0, 0, 0, 110))
    d.rounded_rectangle((2, 2, w + 2, h + 2), 14, fill=bgc + (255,))
    d.text((2 + padx, 2 + pady), text, font=f, fill=fgc + (255,))
    return tag.rotate(angle, resample=Image.BICUBIC, expand=True) if angle else tag


def make_bg(b, seed=1, size=None):
    """Fundo gráfico de alto contraste (sem foto). b = {"color","accent","style"}."""
    import random
    import numpy as np
    rnd = random.Random(seed)
    SW, SH = size or (int(W * 1.35), int(H * 1.35))
    col, acc = rgb(b.get("color", "#E4002B")), rgb(b.get("accent", "#FFC72C"))
    style = b.get("style", "plain")
    im = Image.new("RGB", (SW, SH), col); d = ImageDraw.Draw(im, "RGBA")
    cx, cy = SW / 2, SH * 0.45
    dark = luma(col) < 0.5
    tone = shade(col, 0.10 if dark else -0.10)
    if style == "rays":
        n = 28; R = SW * 2
        import math
        for k in range(n):
            if k % 2: continue
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=tone + (255,))
    elif style == "dots":
        step = 64
        for yy in range(0, SH + step, step):
            for xx in range((yy // step % 2) * step // 2, SW + step, step):
                r = 4 + 16 * (yy / SH)
                d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=acc + (90,))
    elif style == "stripes":
        wdt = 110
        for k in range(-SH, SW + SH, wdt * 2):
            d.polygon([(k, 0), (k + wdt, 0), (k + wdt + SH * 0.6, SH), (k + SH * 0.6, SH)], fill=tone + (255,))
    elif style == "grid":
        step = 90; c = acc + (55,)
        for xx in range(0, SW, step): d.line([(xx, 0), (xx, SH)], fill=c, width=3)
        for yy in range(0, SH, step): d.line([(0, yy), (SW, yy)], fill=c, width=3)
    elif style == "split":
        d.polygon([(0, SH * 0.62), (SW, SH * 0.38), (SW, SH), (0, SH)], fill=acc + (255,))
    elif style == "blob":
        layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0)); dl = ImageDraw.Draw(layer)
        for _ in range(5):
            r = rnd.uniform(0.25, 0.5) * SW; x, y = rnd.uniform(0, SW), rnd.uniform(0, SH)
            dl.ellipse((x - r, y - r, x + r, y + r), fill=acc + (110,))
        im.paste(layer.filter(ImageFilter.GaussianBlur(140)), (0, 0), layer.filter(ImageFilter.GaussianBlur(140)))
    # luz suave no centro + granulado leve (tira a cara de "cor chapada")
    glow = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(glow).ellipse((cx - SW * 0.55, cy - SW * 0.55, cx + SW * 0.55, cy + SW * 0.55), fill=60)
    im = Image.composite(Image.new("RGB", (SW, SH), shade(col, 0.25)), im, glow.filter(ImageFilter.GaussianBlur(200)))
    a = np.asarray(im).astype(np.int16)
    noise = np.random.default_rng(seed).integers(-7, 8, size=(SH, SW, 1))
    return Image.fromarray(np.clip(a + noise, 0, 255).astype(np.uint8))


def card(lines, size=80, align="left"):
    pad, radius, gap, sh = (54, 40), 44, 6, 30
    imgs = [text_line([tuple(p) for p in l], size) for l in lines]
    cw = max(i.width for i in imgs) + pad[0] * 2
    ch = sum(i.height for i in imgs) + gap * (len(imgs) - 1) + pad[1] * 2
    out = Image.new("RGBA", (cw + sh * 2, ch + sh * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((sh, sh + 10, sh + cw, sh + ch + 10), radius, fill=(0, 0, 0, 70))
    out = Image.alpha_composite(out, shadow.filter(ImageFilter.GaussianBlur(16)))
    ImageDraw.Draw(out).rounded_rectangle((sh, sh, sh + cw, sh + ch), radius, fill=(255, 255, 255, 242))
    y = sh + pad[1]
    for i in imgs:
        x = sh + pad[0] if align == "left" else sh + (cw - i.width) // 2
        out.alpha_composite(i, (x, y)); y += i.height + gap
    return out


def pill(text, style="dark", size=44):
    if style == "notif": bg, fg, dot, check = (255, 255, 255, 250), INK, (255, 61, 127), False
    elif style == "ok": bg, fg, dot, check = GREEN + (255,), (255, 255, 255), None, True
    else: bg, fg, dot, check = INK + (255,), (255, 255, 255), None, False
    f = font("SemiBold", size)
    padx, pady = 42, 19
    tw = int(f.getlength(text)); asc, desc = f.getmetrics(); th = asc + desc
    extra = (size + 14) if (dot or check) else 0
    w, h, sh = tw + padx * 2 + extra, th + pady * 2, 20
    out = Image.new("RGBA", (w + sh * 2, h + sh * 2), (0, 0, 0, 0))
    s = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle((sh, sh + 6, sh + w, sh + h + 6), h // 2, fill=(0, 0, 0, 60))
    out = Image.alpha_composite(out, s.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((sh, sh, sh + w, sh + h), h // 2, fill=bg)
    x = sh + padx
    if dot:
        r = size // 2; d.ellipse((x, sh + h // 2 - r, x + 2 * r, sh + h // 2 + r), fill=dot); x += extra
    if check:
        cy, s_ = sh + h // 2, size
        d.line([(x + s_ * 0.08, cy + s_ * 0.02), (x + s_ * 0.38, cy + s_ * 0.30), (x + s_ * 0.92, cy - s_ * 0.32)],
               fill=fg, width=max(4, s_ // 8), joint="curve"); x += extra
    d.text((x, sh + pady), text, font=f, fill=fg)
    return out


def vignette():
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(v)
    for i in range(0, 520, 8):
        d.rectangle((0, i, W, i + 8), fill=(0, 0, 0, int(110 * (1 - i / 520) ** 2)))
    return v


def kenburns(src, u, z0, z1, c0, c1):
    z = z0 + (z1 - z0) * u
    cx = c0[0] + (c1[0] - c0[0]) * u; cy = c0[1] + (c1[1] - c0[1]) * u
    sw, sh = src.size; bw, bh = sw / z, sh / z
    x0 = min(max(cx * sw - bw / 2, 0), sw - bw); y0 = min(max(cy * sh - bh / 2, 0), sh - bh)
    return src.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))


def place(frame, layer, t, t0, x, y, anim="up", dur=0.45):
    if t < t0: return
    k = (t - t0) / dur
    if anim in ("pop", "slam"):
        if anim == "pop": s = 0.6 + 0.4 * ease_back(k); a = min(1, k * 2.5)
        else: s = 1.55 - 0.55 * ease_out(k * 1.4); a = min(1, k * 3.0)  # entra grande e "bate" no lugar
        lay = layer if abs(s - 1) < 1e-3 else layer.resize((max(1, int(layer.width * s)), max(1, int(layer.height * s))), Image.BILINEAR)
        px, py = int(x + (layer.width - lay.width) / 2), int(y + (layer.height - lay.height) / 2)
    else:
        e = ease_out(k); a = min(1, k * 1.6); lay = layer; px, py = int(x), int(y + (1 - e) * 60)
    if a < 1:
        lay = lay.copy(); lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
    frame.alpha_composite(lay, (px, py))


def resolve_x(x, layer):
    if x == "center": return (W - layer.width) // 2
    if x == "right": return W - layer.width - 150
    return int(x)


class Scene:
    def __init__(self, spec, base):
        self.s = spec; self.dur = float(spec.get("dur", 3.6)); self.end = spec.get("end", False)
        if self.end:
            logo = Image.open(LOGO).convert("RGBA"); lw = 620
            logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
            lc = Image.new("RGBA", (lw + 120, logo.height + 90), (0, 0, 0, 0))
            ImageDraw.Draw(lc).rounded_rectangle((0, 0, lc.width - 1, lc.height - 1), 48, fill=(255, 255, 255, 255))
            lc.alpha_composite(logo, (60, 45))
            self.logo = lc
            tc = "ink" if spec.get("bg") and luma(spec["bg"]) > 0.6 else "white"
            self.t1 = text_line([(spec.get("title", "Comente QUERO"), tc)], 104)
            self.t2 = text_line([(spec.get("subtitle", "e teste 7 dias grátis"), tc)], 66, "SemiBold")
            self.t3 = pill(spec.get("footer", "autoinsta.com.br"), "dark", 40)
            if spec.get("bg"):
                self.bg = make_bg({"color": spec["bg"], "accent": spec.get("accent", "#FFFFFF"), "style": spec.get("style", "rays")},
                                  7, (W, H)).convert("RGBA")
            else:
                self.bg = gradient(W, H).convert("RGBA")
            self.events = [(0.10, spec.get("sfx_logo", "logo")), (1.20, "pop")]
        else:
            if spec.get("image"):
                p = spec["image"]; p = p if os.path.isabs(p) else os.path.join(base, p)
                im = Image.open(p).convert("RGB")
                if im.size != (W, H): im = prep_image(im)
                self.src = im.resize((int(W * 1.35), int(H * 1.35)), Image.LANCZOS)
                vig_default = True; pal = {}
            else:  # cena gráfica: fundo gerado aqui mesmo, sem foto e sem navegador
                b = spec.get("bg", {})
                self.src = make_bg(b, int(spec.get("seed", 1)))
                vig_default = False
                pal = {"accent": b.get("accent", "#FFC72C"), "bg": b.get("color", "#E4002B")}
            self.zoom = spec.get("zoom", [1.0, 1.08]); c = spec.get("center", [[0.5, 0.5], [0.5, 0.5]])
            self.c0, self.c1 = c[0], c[1]
            self.vig = vignette() if spec.get("vignette", vig_default) else None
            self.items = []; last = None; self.events = []; self.counts = []
            for it in spec.get("items", []):
                if it["type"] == "big" and it.get("stagger"):
                    # cada linha entra separada, uma depois da outra (mais ritmo)
                    y = it.get("y", 120)
                    if y == "below": y = (last[0] + last[1] - 34) if last else 120
                    y = int(y); t0 = float(it.get("t", 0.1)); gap = int(it.get("size", 150) * 0.02)
                    for k, line in enumerate(it["lines"]):
                        lay = big([line], it.get("size", 150), it.get("align", "center"), it.get("font", "Anton"), it.get("shadow"), pal)
                        tk = t0 + k * float(it["stagger"])
                        self.items.append((lay, tk, resolve_x(it.get("x", "center"), lay), y, it.get("anim", "slam")))
                        self.events.append((tk + 0.02, it.get("sfx", "pop")))
                        y += lay.height + gap
                    last = (y - gap, 0)
                    continue
                if it["type"] == "count":
                    # número que sobe animado (só números que estão nas fontes!)
                    fmt = lambda v, it=it: it.get("prefix", "") + f"{int(round(v)):,}".replace(",", ".") + it.get("suffix", "")
                    mk = lambda txt, it=it: big([[(txt, it.get("color", "accent"))]], it.get("size", 260), "center",
                                                it.get("font", "Anton"), it.get("shadow"), pal)
                    final = mk(fmt(it["to"]))
                    y = it.get("y", 600)
                    if y == "below": y = (last[0] + last[1] - 34) if last else 600
                    y = int(y); last = (y, final.height)
                    cx = resolve_x(it.get("x", "center"), final) + final.width // 2
                    t0 = float(it.get("t", 0.2)); dur = float(it.get("dur", 1.2))
                    self.counts.append(dict(fmt=fmt, mk=mk, frm=float(it.get("from", 0)), to=float(it["to"]), t0=t0, dur=dur,
                                            cx=cx, y=y, cache={}))
                    self.events.append((t0 + 0.02, "whoosh")); self.events.append((t0 + dur, it.get("sfx", "success")))
                    continue
                if it["type"] == "card": lay = card(it["lines"], it.get("size", 80), it.get("align", "left")); anim = it.get("anim", "up")
                elif it["type"] == "big":
                    lay = big(it["lines"], it.get("size", 150), it.get("align", "center"), it.get("font", "Anton"),
                              it.get("shadow"), pal); anim = it.get("anim", "slam")
                elif it["type"] == "sticker":
                    lay = sticker(it["text"], it.get("bg", "accent"), it.get("fg", "ink"), it.get("size", 46),
                                  it.get("angle", -4), it.get("font", "Archivo"), pal); anim = it.get("anim", "pop")
                else: lay = pill(it["text"], it.get("style", "dark"), it.get("size", 44)); anim = it.get("anim", "pop")
                y = it.get("y", 120)
                if y == "below": y = (last[0] + last[1] - 34) if last else 120  # logo abaixo do item anterior
                y = int(y); last = (y, lay.height)
                self.items.append((lay, float(it.get("t", 0.1)), resolve_x(it.get("x", 70), lay), y, anim))
                padrao = {"notif": "notif", "ok": "success"}.get(it.get("style"), "pop") if it["type"] == "pill" else "pop"
                self.events.append((float(it.get("t", 0.1)) + 0.02, it.get("sfx", padrao)))

    def frame(self, i, N):
        t = i / FPS; u = i / max(1, N - 1)
        if self.end:
            f = self.bg.copy()
            sweep = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sx = int(-600 + (W + 1200) * ease_out(u))
            ImageDraw.Draw(sweep).polygon([(sx, 0), (sx + 220, 0), (sx - 380, H), (sx - 600, H)], fill=(255, 255, 255, 40))
            f.alpha_composite(sweep.filter(ImageFilter.GaussianBlur(30)))
            place(f, self.logo, t, 0.10, (W - self.logo.width) // 2, 520, "pop")
            place(f, self.t1, t, 0.55, (W - self.t1.width) // 2, 860)
            place(f, self.t2, t, 0.85, (W - self.t2.width) // 2, 1010)
            place(f, self.t3, t, 1.20, (W - self.t3.width) // 2, 1150, "pop", 0.4)
            return f.convert("RGB")
        f = kenburns(self.src, u, self.zoom[0], self.zoom[1], self.c0, self.c1).convert("RGBA")
        if self.vig: f.alpha_composite(self.vig)
        for lay, t0, x, y, anim in self.items:
            place(f, lay, t, t0, x, y, anim, 0.45 if anim == "up" else 0.35)
        for c in self.counts:
            if t < c["t0"]: continue
            v = c["frm"] + (c["to"] - c["frm"]) * ease_out((t - c["t0"]) / c["dur"])
            txt = c["fmt"](v)
            if txt not in c["cache"]: c["cache"][txt] = c["mk"](txt)
            lay = c["cache"][txt]
            place(f, lay, t, c["t0"], c["cx"] - lay.width // 2, c["y"], "pop", 0.3)
        return f.convert("RGB")


def prep_image(im):
    im = im.convert("RGB"); w, h = im.size
    usable = int(w * 0.985)  # tira a barra de rolagem da captura
    cw = usable; ch = int(cw * 16 / 9)
    if ch > h: ch = h; cw = int(ch * 9 / 16)
    x0 = (usable - cw) // 2; y0 = (h - ch) // 2
    return im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS)


def stitch(top_path, bottom_path, out, width=1080, height=1920):
    """Junta 2 capturas (topo e fim) do navegador na nuvem com a imagem em 100%."""
    import numpy as np
    a = np.asarray(Image.open(top_path).convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(bottom_path).convert("RGB")).astype(np.int16)
    # acha a faixa horizontal da imagem (fora o fundo escuro do visualizador e a barra de rolagem)
    col = a.mean(axis=(0, 2)); xs = np.where(col > 40)[0]
    x0 = int(xs[0]) if len(xs) else 0
    if x0 + width > a.shape[1]: x0 = max(0, a.shape[1] - width)
    a = a[:, x0:x0 + width]; b = b[:, x0:x0 + width]
    h = a.shape[0]; best, off = 1e9, height - h
    for o in range(max(1, height - h - 40), min(h, height - h + 40) + 1):  # confirma a sobreposição
        n = min(200, h - o); d = np.abs(a[o:o + n] - b[:n]).mean() if n >= 8 else 1e9
        if d < best: best, off = d, o
    full = np.concatenate([a[:off], b], 0)[:height]
    Image.fromarray(full.astype(np.uint8)).save(out, quality=95)
    print("ok", out, full.shape[1], "x", full.shape[0], "sobreposicao", off, "erro", round(float(best), 2))


def load(spec_path, with_spec=False):
    spec = json.load(open(spec_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(spec_path))
    scenes = [Scene(s, base) for s in spec["scenes"]]
    return (scenes, spec) if with_spec else scenes


def render(spec_path, out):
    scenes, spec = load(spec_path, True); stem = os.path.splitext(out)[0]; tmpdir = stem + "_parts"; os.makedirs(tmpdir, exist_ok=True)
    files = []
    total = sum(int(round(sc.dur * FPS)) for sc in scenes); done = 0
    bar = spec.get("progress", True)  # barrinha de progresso no topo: segura a pessoa até o fim
    for n, sc in enumerate(scenes):
        N = int(round(sc.dur * FPS)); fn = os.path.join(tmpdir, f"scene{n}.mp4"); part = os.path.join(tmpdir, f"scene{n}.tmp.mp4")
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                              "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), part], stdin=subprocess.PIPE)
        for i in range(N):
            fr = sc.frame(i, N)
            if bar and not sc.end:
                d = ImageDraw.Draw(fr); d.rectangle((0, 0, W, 11), fill=(0, 0, 0))
                d.rectangle((0, 0, int(W * (done + i + 1) / total), 11), fill=(255, 255, 255))
            p.stdin.write(fr.tobytes())
        done += N
        p.stdin.close()
        if p.wait() != 0: sys.exit(f"falhou na cena {n}")
        os.replace(part, fn); files.append(fn)
    lst = os.path.join(tmpdir, "list.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
    joined = os.path.join(tmpdir, "joined.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
    # trilha + efeitos sincronizados com as animações
    events, t = [], 0.0
    for n, sc in enumerate(scenes):
        if n > 0: events.append((t - 0.25, "whoosh"))
        events += [(t + a, b) for a, b in sc.events]
        t += int(round(sc.dur * FPS)) / FPS
    opts = dict(spec.get("audio", {})); opts.setdefault("seed", audio.seed_from(os.path.basename(out)))
    wav = os.path.join(tmpdir, "trilha.wav")
    audio.write_wav(wav, audio.soundtrack(events, t, opts))
    part = stem + ".tmp.mp4"
    audio.mux(joined, wav, part)
    os.replace(part, out)
    for f in files + [lst, joined, wav]: os.remove(f)
    os.rmdir(tmpdir)
    print("ok", out, round(sum(s.dur for s in scenes), 1), "s")


def check(spec_path, out):
    scenes = load(spec_path); thumbs = []
    for sc in scenes:
        N = int(round(sc.dur * FPS)); i = min(N - 1, int(2.4 * FPS))
        thumbs.append(sc.frame(i, N).resize((360, 640)))
    S = Image.new("RGB", (360 * len(thumbs), 640))
    for k, t in enumerate(thumbs): S.paste(t, (k * 360, 0))
    S.save(out, quality=85); print("ok", out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep": prep_image(Image.open(sys.argv[2])).save(sys.argv[3], quality=95); print("ok", sys.argv[3])
    elif cmd == "check": check(sys.argv[2], sys.argv[3])
    elif cmd == "stitch": stitch(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "render": render(sys.argv[2], sys.argv[3])
    elif cmd == "bg": make_bg(json.loads(sys.argv[2]), 1, (W, H)).save(sys.argv[3], quality=92); print("ok", sys.argv[3])
    else: print(__doc__)
