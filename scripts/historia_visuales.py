"""Piezas visuales del canal de historia económica (estilo «Editorial»).

Cada pieza dibuja una capa del tamaño de la pantalla, sirve igual para el vídeo largo
(1920x1080) y para los Shorts (1080x1920), y se anima con el tiempo t de su escena.

Tipos de escena (campo «tipo» del guion; ver guiones/LEEME.md):
    titulo, cifra, comparar, linea, barras, fecha, cita, lista,
    foto, boceto, mapa, esquema, archivo
"""
import functools
import json
import math
import random
import subprocess
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "fuentes"
MAPAS = RAIZ / "mapas"
FPS = 30
SS = 2  # supersampling: las formas se dibujan al doble y se reducen (bordes suaves)


# =====================================================================
#  Utilidades
# =====================================================================

@functools.lru_cache(maxsize=512)
def _fuente(ruta, tam):
    return ImageFont.truetype(ruta, max(8, int(tam)))


def suave(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def suave2(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def rebote(x):
    if x >= 1:
        return 1.0
    x = max(0.0, x)
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2


def numero(valor, decimales=0, prefijo="", sufijo=""):
    """Número a la española: 1.250.000 · 4,9 · 166,386 (las cifras de 4 dígitos, sin punto)."""
    txt = f"{abs(valor):,.{decimales}f}" if abs(valor) >= 10000 else f"{abs(valor):.{decimales}f}"
    txt = txt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{prefijo}{'−' if valor < 0 else ''}{txt}{sufijo}"


def envolver(texto, f, ancho):
    lineas, actual = [], ""
    for p in str(texto).split():
        prueba = (actual + " " + p).strip()
        if f.getlength(prueba) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    return lineas + ([actual] if actual else [])


def alfa_capa(capa, a):
    if a >= 0.999:
        return capa
    capa = capa.copy()
    capa.putalpha(capa.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return capa


def pegar(base, capa, x, y, alfa=1.0, centro=True):
    if alfa <= 0.01:
        return
    capa = alfa_capa(capa, alfa)
    if centro:
        x, y = x - capa.width / 2, y - capa.height / 2
    base.alpha_composite(capa, (int(round(x)), int(round(y))))


def normalizar(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())


def _grano(w, h, fuerza, semilla):
    rng = np.random.default_rng(semilla)
    n = rng.normal(0, 1, (max(1, h // 2), max(1, w // 2))).astype(np.float32)
    n = np.array(Image.fromarray(((n * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR),
                 np.float32) / 255 - 0.5
    return n * fuerza


def duotono(img, tema, contraste=1.15, grano=16):
    """Foto en dos tonos del canal (sombras oscuras cálidas, luces crema) con grano de película."""
    g = np.array(ImageOps.grayscale(img), np.float32) / 255
    lo, hi = np.percentile(g, 2), np.percentile(g, 98)
    g = ((g - lo) / max(hi - lo, 1e-3)).clip(0, 1)
    g = ((g - 0.5) * contraste + 0.5).clip(0, 1)
    a, b = np.array(tema["sombra_foto"], np.float32), np.array(tema["luz_foto"], np.float32)
    col = a * (1 - g[..., None]) + b * g[..., None]
    if grano:
        col += _grano(img.width, img.height, grano, 3)[..., None]
    return Image.fromarray(col.clip(0, 255).astype(np.uint8)).convert("RGBA")


def recortar_a(img, w, h, foco=(0.5, 0.4)):
    """Recorta la imagen para que llene w x h, centrando en el foco (x, y de 0 a 1)."""
    r = max(w / img.width, h / img.height)
    img = img.resize((max(w, int(img.width * r + 0.5)), max(h, int(img.height * r + 0.5))), Image.LANCZOS)
    x = int((img.width - w) * foco[0])
    y = int((img.height - h) * foco[1])
    return img.crop((x, y, x + w, y + h))


# =====================================================================
#  Contexto: tamaño de pantalla, colores y fuentes
# =====================================================================

class Contexto:
    def __init__(self, W, H, tema, fuentes, semilla=""):
        self.W, self.H, self.tema, self.semilla = W, H, tema, semilla
        self.vertical = H > W
        self.rutas = {k: str(FUENTES / v) for k, v in fuentes.items()}
        if self.vertical:
            self.m = 70                       # margen lateral
            self.arriba, self.abajo = 330, 1400  # zona útil (deja sitio a cabecera y subtítulos)
        else:
            self.m = 120
            self.arriba, self.abajo = 150, 960

    def f(self, rol, tam):
        return _fuente(self.rutas[rol], tam)

    def c(self, nombre, a=255):
        col = self.tema.get(nombre, nombre) if isinstance(nombre, str) else nombre
        return tuple(col[:3]) + (a,)

    def ajustar(self, texto, rol, tam, ancho, max_lineas=3, minimo=26):
        while True:
            f = self.f(rol, tam)
            lineas = envolver(texto, f, ancho)
            if (len(lineas) <= max_lineas and all(f.getlength(l) <= ancho for l in lineas)) or tam <= minimo:
                return f, lineas, tam
            tam -= 3


# =====================================================================
#  Pieza base
# =====================================================================

class Pieza:
    opaca = False        # True si tapa el fondo entero (fotos a pantalla completa, mapas...)
    entrada = 1.2

    def __init__(self, d, ctx, dur):
        self.d, self.ctx, self.dur = d, ctx, dur
        self.W, self.H = ctx.W, ctx.H
        self.rnd = random.Random(f"{ctx.semilla}")
        self._quieto = None

    def lienzo(self):
        return Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))

    def fin_animacion(self):
        return self.entrada

    def movil(self):
        """True si la pieza sigue moviéndose después de su entrada (fotos con zoom lento, clips...)."""
        return False

    def cuadro(self, t):
        if not self.movil() and t >= self.fin_animacion():
            if self._quieto is None:
                self._quieto = self.dibujar(self.fin_animacion() + 0.001)
            return self._quieto
        return self.dibujar(t)

    def dibujar(self, t):
        return self.lienzo()

    def cerrar(self):
        pass

    # Bloque de título + subtítulo arriba a la izquierda (gráficos, mapas, esquemas)
    def _cabecera_bloque(self, d, t, titulo, sub=None, x=None, y=None, ancho=None, tam=72):
        ctx = self.ctx
        x = ctx.m if x is None else x
        y = ctx.arriba if y is None else y
        ancho = ancho or (self.W - 2 * ctx.m)
        if not titulo:
            return y
        f, lineas, tam = ctx.ajustar(titulo, "tit", tam if not ctx.vertical else tam * 0.9, ancho, 3, 34)
        q = suave(t / 0.45)
        for i, l in enumerate(lineas):
            d.text((x, y + i * tam * 1.1 + 18 * (1 - q)), l, font=f, fill=ctx.c("texto", int(255 * q)))
        y += len(lineas) * tam * 1.1 + 6
        if sub:
            fs, ls, ts = ctx.ajustar(sub, "txt", 30, ancho, 2, 22)
            q2 = suave((t - 0.15) / 0.45)
            for i, l in enumerate(ls):
                d.text((x, y + i * ts * 1.3), l, font=fs, fill=ctx.c("suave", int(255 * q2)))
            y += len(ls) * ts * 1.3
        return y + 30


# =====================================================================
#  Titular
# =====================================================================

class Titulo(Pieza):
    def __init__(self, *a):
        super().__init__(*a)
        ctx, d = self.ctx, self.d
        resaltar = {normalizar(p.strip(".,:;¿?¡!«»")) for p in str(d.get("resaltar") or "").split()}
        ancho = self.W - 2 * ctx.m - (0 if ctx.vertical else 200)
        self.f, lineas, self.tam = ctx.ajustar(d["texto"], "tit", 128 if ctx.vertical else 118, ancho,
                                               5 if ctx.vertical else 3, 50)
        self.alto_l = self.tam * 1.08
        esp = self.f.getlength(" ")
        alto = self.alto_l * len(lineas)
        y0 = (ctx.arriba + ctx.abajo) / 2 - alto / 2 + (30 if d.get("kicker") else 0)
        self.palabras = []
        for i, l in enumerate(lineas):
            x = (self.W - self.f.getlength(l)) / 2
            for p in l.split():
                self.palabras.append((p, x, y0 + i * self.alto_l, normalizar(p.strip(".,:;¿?¡!«»")) in resaltar))
                x += self.f.getlength(p) + esp
        self.y0 = y0
        self.kicker = str(d["kicker"]).upper() if d.get("kicker") else None
        self.entrada = 0.9 + 0.06 * len(self.palabras)

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        if self.kicker:
            fk = ctx.f("txt_b", 30)
            q = suave(t / 0.35)
            w = fk.getlength(self.kicker)
            x = self.W / 2 - w / 2
            d.text((x, self.y0 - 80), self.kicker, font=fk, fill=ctx.c("acento", int(255 * q)))
            d.rectangle((x - 30, self.y0 - 66, x - 14, self.y0 - 62 + 0), fill=ctx.c("acento", int(255 * q)))
            d.rectangle((x + w + 14, self.y0 - 66, x + w + 30, self.y0 - 62), fill=ctx.c("acento", int(255 * q)))
        for k, (p, x, y, res) in enumerate(self.palabras):
            q = suave((t - 0.1 - 0.06 * k) / 0.35)
            if q <= 0:
                continue
            dy = 22 * (1 - q)
            a = int(255 * q)
            d.text((x, y + dy), p, font=self.f, fill=ctx.c("acento" if res else "texto", a))
            if res:  # subrayado que se dibuja
                g = suave((t - 0.45 - 0.06 * k) / 0.4)
                yb = y + self.tam * 1.02
                w = self.f.getlength(p.rstrip(".,:;?!»"))
                d.rectangle((x, yb, x + w * g, yb + max(5, self.tam * 0.06)), fill=ctx.c("acento2", a))
        return img


# =====================================================================
#  Cifra que cuenta
# =====================================================================

class Cifra(Pieza):
    entrada = 1.8

    def __init__(self, *a):
        super().__init__(*a)
        ctx, d = self.ctx, self.d
        self.valor = float(d.get("valor", 0) or 0)
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.fijo = d.get("texto")
        self.col = d.get("color", "acento2")
        final = self.fijo or numero(self.valor, self.dec, self.pre, self.suf)
        tam = 300 if ctx.vertical else 290
        while ctx.f("num", tam).getlength(final) > self.W - 2 * ctx.m and tam > 60:
            tam -= 8
        self.fn, self.tam = ctx.f("num", tam), tam
        self.eti = None
        if d.get("etiqueta"):
            self.eti = ctx.ajustar(str(d["etiqueta"]), "txt", 46, min(1100, self.W - 2 * ctx.m), 3, 28)
        alto = tam + 60 + (len(self.eti[1]) * self.eti[2] * 1.3 if self.eti else 0)
        self.y = (ctx.arriba + ctx.abajo) / 2 - alto / 2

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        p = suave(t / 1.3)
        txt = self.fijo or numero(self.valor * p if p < 1 else self.valor, self.dec, self.pre, self.suf)
        a = suave(t / 0.3)
        d.text((self.W / 2, self.y + self.tam / 2 + 24 * (1 - a)), txt, font=self.fn,
               fill=ctx.c(self.col, int(255 * a)), anchor="mm")
        yb = self.y + self.tam + 22
        r = suave((t - 0.35) / 0.7)
        d.rectangle((self.W / 2 - 110 * r, yb, self.W / 2 + 110 * r, yb + 5), fill=ctx.c("texto", 200))
        if self.eti:
            f, lineas, tam = self.eti
            q = suave((t - 0.6) / 0.5)
            for i, l in enumerate(lineas):
                d.text((self.W / 2, yb + 50 + i * tam * 1.3 + 14 * (1 - q)), l, font=f,
                       fill=ctx.c("suave", int(255 * q)), anchor="ma")
        return img


# =====================================================================
#  Comparar dos valores
# =====================================================================

class Comparar(Pieza):
    entrada = 2.0

    def __init__(self, *a):
        super().__init__(*a)
        d = self.d
        self.lados = [d["izquierda"], d["derecha"]]
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.maximo = max(abs(float(x["valor"])) for x in self.lados) or 1

    def dibujar(self, t):
        ctx = self.ctx
        big = Image.new("RGBA", (self.W * SS, self.H * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        img = self.lienzo()
        di = ImageDraw.Draw(img)
        y_top = self._cabecera_bloque(di, t, self.d.get("titulo"), self.d.get("subtitulo"))
        base_y = ctx.abajo - 70
        alto_max = base_y - y_top - 130
        ancho = 240 if not ctx.vertical else 220
        fv = ctx.f("num", 84)
        fe = ctx.f("txt_b", 34)
        for k, (lado, cx) in enumerate(zip(self.lados, (self.W * 0.34, self.W * 0.66))):
            q = suave((t - 0.3 - 0.35 * k) / 1.1)
            v = float(lado["valor"])
            h = max(6, alto_max * abs(v) / self.maximo * q)
            col = ctx.c(lado.get("color", "linea" if k == 0 else "acento"))
            d.rectangle(((cx - ancho / 2) * SS, (base_y - h) * SS, (cx + ancho / 2) * SS, base_y * SS), fill=col)
            txt = lado.get("texto") or numero(v * q if q < 1 else v, self.dec, self.pre, self.suf)
            di.text((cx, base_y - h - 24), txt, font=fv, fill=ctx.c("texto", int(255 * min(1, q * 3))), anchor="mb")
            di.text((cx, base_y + 26), str(lado.get("etiqueta", "")).upper(), font=fe, fill=ctx.c("suave"), anchor="ma")
        d.line((self.W * 0.14 * SS, base_y * SS, self.W * 0.86 * SS, base_y * SS), fill=ctx.c("texto", 160), width=3 * SS)
        capa = big.resize((self.W, self.H), Image.LANCZOS)
        capa.alpha_composite(img)
        return capa


# =====================================================================
#  Gráficos de línea y de barras
# =====================================================================

def _paso_redondo(x):
    base = 10 ** math.floor(math.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if x <= m * base:
            return m * base
    return 10 * base


class Linea(Pieza):
    def __init__(self, *a):
        super().__init__(*a)
        ctx, d = self.ctx, self.d
        self.vals = [float(v) for v in d["valores"]]
        n = len(self.vals)
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.col = d.get("color", "acento")
        # Fondo fijo: título, ejes y etiquetas
        self.base = self.lienzo()
        bd = ImageDraw.Draw(self.base)
        y_top = self._cabecera_bloque(bd, 9, d.get("titulo"), d.get("subtitulo"))
        x0, x1 = ctx.m + (90 if ctx.vertical else 110), self.W - ctx.m - (110 if ctx.vertical else 150)
        y0, y1 = y_top + 70, ctx.abajo - 60
        lo, hi = min(self.vals), max(self.vals)
        if d.get("desde_cero", lo >= 0):
            lo = min(0, lo)
        paso = _paso_redondo((hi - lo) / 4 or 1)
        lo = math.floor(lo / paso) * paso
        hi = math.ceil(hi * 1.04 / paso) * paso
        dec_eje = 0 if paso >= 1 else (1 if paso >= 0.1 else 2)
        fe = ctx.f("txt", 28)
        k = 0
        while lo + paso * k <= hi + 1e-9:
            v = lo + paso * k
            y = y1 - (y1 - y0) * (v - lo) / (hi - lo)
            bd.line((x0, y, x1, y), fill=ctx.c("linea"), width=2 if k else 3)
            bd.text((x0 - 18, y), numero(v, dec_eje) + (self.suf.strip() if self.suf.strip() == "%" else ""),
                    font=fe, fill=ctx.c("suave"), anchor="rm")
            k += 1
        etis = d.get("etiquetas") or {}
        if isinstance(etis, list):
            salto = max(1, math.ceil(len(etis) / (5 if ctx.vertical else 9)))
            etis = {i: e for i, e in enumerate(etis) if i % salto == 0 or i == len(etis) - 1}
        for i, txt in etis.items():
            x = x0 + (x1 - x0) * int(i) / max(1, n - 1)
            bd.text((x, y1 + 22), str(txt), font=fe, fill=ctx.c("suave"), anchor="ma")
        self.pts = [(x0 + (x1 - x0) * i / max(1, n - 1), y1 - (y1 - y0) * (v - lo) / (hi - lo)) for i, v in enumerate(self.vals)]
        self.y0, self.y1 = y0, y1
        self.marcas = [(int(m["indice"]), str(m["texto"]).upper(), m.get("color", "acento2")) for m in d.get("marcas") or []]

    def fin_animacion(self):
        return min(3.4, max(1.8, self.dur * 0.6)) + 0.6

    def dibujar(self, t):
        ctx = self.ctx
        img = self.base.copy()
        r = suave2(t / (self.fin_animacion() - 0.6))
        n = len(self.pts)
        pos = r * (n - 1)
        k = int(pos)
        pts = self.pts[:k + 1]
        if k + 1 < n:
            a, b = self.pts[k], self.pts[k + 1]
            f = pos - k
            pts = pts + [(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)]
        big = Image.new("RGBA", (self.W * SS, self.H * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        P = [(x * SS, y * SS) for x, y in pts]
        if len(P) >= 2:
            d.polygon(P + [(P[-1][0], self.y1 * SS), (P[0][0], self.y1 * SS)], fill=ctx.c(self.col, 40))
            d.line(P, fill=ctx.c(self.col), width=8 * SS, joint="curve")
        for i, txt, col in self.marcas:
            if pos >= i:
                x, y = self.pts[i]
                q = suave((pos - i) / 0.5)
                d.line((x * SS, (self.y0 - 10) * SS, x * SS, self.y1 * SS), fill=ctx.c(col, int(200 * q)), width=3 * SS)
                rr = 12 * SS
                d.ellipse((x * SS - rr, y * SS - rr, x * SS + rr, y * SS + rr), fill=ctx.c(col, int(255 * q)))
        xe, ye = P[-1]
        rr = 13 * SS
        d.ellipse((xe - rr, ye - rr, xe + rr, ye + rr), fill=ctx.c(self.col))
        capa = big.resize((self.W, self.H), Image.LANCZOS)
        img.alpha_composite(capa)
        d2 = ImageDraw.Draw(img)
        for i, txt, col in self.marcas:
            if pos >= i:
                x, _ = self.pts[i]
                q = suave((pos - i) / 0.5)
                fb = ctx.f("txt_b", 26)
                w = fb.getlength(txt)
                xc = min(max(x, ctx.m + w / 2 + 20), self.W - ctx.m - w / 2 - 20)
                d2.rectangle((xc - w / 2 - 16, self.y0 - 62, xc + w / 2 + 16, self.y0 - 18), fill=ctx.c(col, int(255 * q)))
                d2.text((xc, self.y0 - 40), txt, font=fb, fill=ctx.c("fondo", int(255 * q)), anchor="mm")
        vi = min(n - 1, int(round(pos)))
        txt = numero(self.vals[vi], self.dec, self.pre, self.suf)
        d2.text((pts[-1][0] + 24, pts[-1][1] - 14), txt, font=ctx.f("num", 56), fill=ctx.c("texto"), anchor="lb")
        return img


class Barras(Pieza):
    def __init__(self, *a):
        super().__init__(*a)
        d = self.d
        self.vals = [float(v) for v in d["valores"]]
        self.etis = [str(e) for e in (d.get("etiquetas") or [""] * len(self.vals))]
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.destacar = {int(i) for i in (d.get("destacar") or [])}
        self.entrada = 0.6 + 0.12 * len(self.vals) + 1.0

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        y_top = self._cabecera_bloque(d, t, self.d.get("titulo"), self.d.get("subtitulo"))
        n = len(self.vals)
        x0, x1 = ctx.m, self.W - ctx.m
        y1 = ctx.abajo - 60
        alto_max = y1 - y_top - 90
        top = max(abs(v) for v in self.vals) or 1
        paso = (x1 - x0) / n
        ancho = paso * 0.6
        fv = ctx.f("num", 50 if n <= 6 else 36)
        fe = ctx.f("txt", 30 if n <= 6 else 24)
        for i, v in enumerate(self.vals):
            q = suave((t - 0.3 - 0.12 * i) / 0.9)
            cx = x0 + paso * (i + 0.5)
            h = max(3, alto_max * abs(v) / top * q)
            col = ctx.c("acento" if i in self.destacar else ("linea" if self.destacar else "acento"))
            d.rectangle((cx - ancho / 2, y1 - h, cx + ancho / 2, y1), fill=col)
            if q > 0.05:
                d.text((cx, y1 - h - 14), numero(v * q if q < 1 else v, self.dec, self.pre, self.suf), font=fv,
                       fill=ctx.c("texto", int(255 * min(1, q * 2))), anchor="mb")
            d.text((cx, y1 + 18), self.etis[i] if i < len(self.etis) else "", font=fe, fill=ctx.c("suave"), anchor="ma")
        d.line((x0, y1, x1, y1), fill=ctx.c("texto", 160), width=3)
        return img


# =====================================================================
#  Fecha, cita y lista
# =====================================================================

class Fecha(Pieza):
    entrada = 1.8

    def __init__(self, *a):
        super().__init__(*a)
        ctx = self.ctx
        self.f, self.lineas, self.tam = ctx.ajustar(str(self.d["fecha"]), "num", 200, self.W - 2 * ctx.m, 2, 70)

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        yl = ctx.arriba + (ctx.abajo - ctx.arriba) * 0.66
        q = suave(t / 1.0)
        desp = (1 - q) * self.W * 0.4
        d.line((0, yl, self.W, yl), fill=ctx.c("linea"), width=3)
        for k in range(-14, 15):
            x = self.W / 2 + k * 100 + desp
            if 0 <= x <= self.W:
                h = 16 if k % 5 else 34
                d.line((x, yl - h / 2, x, yl + h / 2), fill=ctx.c("linea"), width=3)
        p = rebote(min(1, max(0, (t - 0.6) / 0.5)))
        r = 16 * p
        if r > 1:
            d.ellipse((self.W / 2 - r, yl - r, self.W / 2 + r, yl + r), fill=ctx.c("acento"))
            if t < 1.6:
                an = 16 + 46 * ((t - 0.6) % 1.0)
                d.ellipse((self.W / 2 - an, yl - an, self.W / 2 + an, yl + an), outline=ctx.c("acento", int(150 * (1 - (t - 0.6) % 1.0))), width=3)
        a = suave((t - 0.3) / 0.5)
        alto_l = self.tam * 1.05
        y0 = yl - 60 - alto_l * len(self.lineas)
        for i, l in enumerate(self.lineas):
            d.text((self.W / 2, y0 + i * alto_l + 26 * (1 - a)), l, font=self.f, fill=ctx.c("texto", int(255 * a)), anchor="ma")
        if self.d.get("lugar"):
            b = suave((t - 0.8) / 0.4)
            d.text((self.W / 2, yl + 50), str(self.d["lugar"]).upper(), font=ctx.f("txt_b", 34), fill=ctx.c("acento", int(255 * b)), anchor="ma")
        return img


class Cita(Pieza):
    def __init__(self, *a):
        super().__init__(*a)
        ctx = self.ctx
        ancho = self.W - 2 * ctx.m - (60 if ctx.vertical else 360)
        self.f, self.lineas, self.tam = ctx.ajustar(str(self.d["texto"]), "tit2", 64 if ctx.vertical else 62, ancho,
                                                    8 if ctx.vertical else 5, 30)
        autor = str(self.d.get("autor", ""))
        if self.d.get("fecha"):
            autor += f" · {self.d['fecha']}"
        self.autor = autor.upper()
        self.entrada = 0.5 + 0.16 * len(self.lineas) + 0.7

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        alto_l = self.tam * 1.32
        alto = alto_l * len(self.lineas) + 100
        y0 = (ctx.arriba + ctx.abajo) / 2 - alto / 2
        x0 = ctx.m + (20 if ctx.vertical else 180)
        q = suave(t / 0.4)
        if ctx.vertical:
            d.text((x0 - 10, y0 - 40), "“", font=ctx.f("tit", 200), fill=ctx.c("acento", int(255 * q)), anchor="lb")
        else:
            d.text((x0 - 20, y0 - 30), "“", font=ctx.f("tit", 240), fill=ctx.c("acento", int(255 * q)), anchor="rt")
        for i, l in enumerate(self.lineas):
            a = suave((t - 0.2 - 0.16 * i) / 0.45)
            d.text((x0 + 18 * (1 - a), y0 + i * alto_l), l, font=self.f, fill=ctx.c("texto", int(255 * a)))
        a = suave((t - 0.3 - 0.16 * len(self.lineas)) / 0.45)
        ya = y0 + alto_l * len(self.lineas) + 34
        d.rectangle((x0, ya + 16, x0 + 40 * a, ya + 20), fill=ctx.c("acento2", int(255 * a)))
        d.text((x0 + 60, ya), self.autor, font=ctx.f("txt_b", 32), fill=ctx.c("acento2", int(255 * a)))
        return img


class Lista(Pieza):
    def __init__(self, *a):
        super().__init__(*a)
        ctx = self.ctx
        self.puntos = [str(p) for p in self.d["puntos"]]
        n = len(self.puntos)
        tam = 58 if n <= 3 else (48 if n <= 5 else 40)
        self.f, self.tam = ctx.f("txt", tam), tam
        self.lineas = [envolver(p, self.f, self.W - 2 * ctx.m - 140) for p in self.puntos]

    def _momentos(self):
        tramo = max(0.6, self.dur * 0.75 / max(1, len(self.puntos)))
        return [0.4 + i * tramo for i in range(len(self.puntos))]

    def fin_animacion(self):
        return self._momentos()[-1] + 0.6

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        alto_l = self.tam * 1.3
        total = sum(len(ls) * alto_l + 46 for ls in self.lineas)
        y = self._cabecera_bloque(d, t, self.d.get("titulo"), None)
        y = max(y, (ctx.arriba + ctx.abajo) / 2 - total / 2) if not self.d.get("titulo") else y + 10
        fn = ctx.f("num", self.tam * 1.15)
        for i, (ls, m) in enumerate(zip(self.lineas, self._momentos())):
            q = suave((t - m) / 0.45)
            if q > 0:
                a = int(255 * q)
                dx = 30 * (1 - q)
                d.text((ctx.m + dx, y - self.tam * 0.12), f"{i + 1:02d}", font=fn, fill=ctx.c("acento", a))
                for j, l in enumerate(ls):
                    d.text((ctx.m + 130 + dx, y + j * alto_l), l, font=self.f, fill=ctx.c("texto", a))
                d.line((ctx.m + 130 + dx, y + len(ls) * alto_l + 14, self.W - ctx.m, y + len(ls) * alto_l + 14),
                       fill=ctx.c("linea", a), width=2)
            y += len(ls) * alto_l + 46
        return img


# =====================================================================
#  Foto de época
# =====================================================================

class Foto(Pieza):
    """Foto de archivo en tono sepia con zoom lento.

    diseno: sangre (foto a un lado y texto al otro) · completa (pantalla entera con rótulo) · marco (foto enmarcada)
    """

    def __init__(self, *a, imagen=None, credito=""):
        super().__init__(*a)
        ctx, d = self.ctx, self.d
        self.diseno = d.get("diseno", "sangre")
        self.credito = credito
        foco = tuple(d.get("foco") or (0.5, 0.35))
        W, H = self.W, self.H
        self.falta = imagen is None
        if imagen is None:  # sin imagen: textura neutra para que el vídeo no se rompa
            imagen = Image.new("RGB", (1600, 1000), ctx.tema["fondo2"])
        tratada = duotono(imagen.convert("RGB"), ctx.tema) if d.get("color") is not True else imagen.convert("RGBA")
        if self.diseno == "completa":
            self.caja = (0, 0, W, H)
        elif self.diseno == "marco":
            if ctx.vertical:
                self.caja = (ctx.m, 360, W - ctx.m, 360 + int((W - 2 * ctx.m) * 1.15))
            else:
                self.caja = (W - ctx.m - 900, 170, W - ctx.m, 170 + 700)
        else:  # sangre
            self.caja = (0, 0, W, int(H * 0.56)) if ctx.vertical else (int(W * 0.36), 0, W, H)
        bw, bh = self.caja[2] - self.caja[0], self.caja[3] - self.caja[1]
        self.zoom = 1.12
        self.foto = recortar_a(tratada, int(bw * self.zoom), int(bh * self.zoom), foco)
        self.dir = self.rnd.choice([(-1, 0), (1, 0), (0, -1), (0.6, 0.6), (-0.6, 0.4)])
        # Máscara de fundido con el fondo (sangre) y velo para que se lea el rótulo (completa)
        self.mascara = None
        if self.diseno == "sangre":
            m = np.ones((bh, bw), np.float32)
            if ctx.vertical:
                r = np.linspace(1, 0, int(bh * 0.35)) ** 1.5
                m[bh - len(r):, :] *= r[:, None]
            else:
                r = np.linspace(0, 1, int(bw * 0.42)) ** 1.6
                m[:, : len(r)] *= r[None, :]
            self.mascara = Image.fromarray((m * 255).astype(np.uint8))
        self.velo = None
        if self.diseno == "completa":
            y = np.linspace(0, 1, H)[:, None]
            a = 0.15 + 0.75 * np.clip((y - 0.5) / 0.5, 0, 1) ** 1.3 + 0.35 * np.clip((0.15 - y) / 0.15, 0, 1)
            self.velo = Image.new("RGBA", (W, H), ctx.c("fondo"))
            self.velo.putalpha(Image.fromarray((np.broadcast_to(a, (H, W)).clip(0, 1) * 255).astype(np.uint8)))
        self.textos = self._preparar_textos()

    def movil(self):
        return True

    def _preparar_textos(self):
        ctx, d = self.ctx, self.d
        capa = self.lienzo()
        dd = ImageDraw.Draw(capa)
        bloques = []
        if self.diseno == "sangre":
            if ctx.vertical:
                x, y, ancho = ctx.m, int(self.H * 0.56) - 40, self.W - 2 * ctx.m
            else:
                x, y, ancho = ctx.m, None, int(self.W * 0.40)
        elif self.diseno == "marco":
            x, y, ancho = (ctx.m, self.caja[3] + 110, self.W - 2 * ctx.m) if ctx.vertical else (ctx.m, None, self.caja[0] - ctx.m - 80)
        else:
            x, y, ancho = ctx.m, None, int(self.W * (0.86 if ctx.vertical else 0.62))
        partes = []
        if d.get("kicker"):
            partes.append(("kicker", str(d["kicker"]).upper(), ctx.f("txt_b", 28), 28))
        if d.get("texto"):
            f, ls, tam = ctx.ajustar(str(d["texto"]), "tit", 92 if self.diseno != "completa" else 96, ancho, 4, 40)
            partes.append(("tit", ls, f, tam))
        if d.get("sub"):
            f, ls, tam = ctx.ajustar(str(d["sub"]), "txt", 34, ancho, 3, 24)
            partes.append(("sub", ls, f, tam))
        alto = 0
        for tipo, txt, f, tam in partes:
            alto += (tam * 1.6) if tipo == "kicker" else len(txt) * tam * (1.08 if tipo == "tit" else 1.35) + 16
        if y is None:
            y = (self.H * 0.82 - alto) if self.diseno == "completa" else ((ctx.arriba + ctx.abajo) / 2 - alto / 2)
        for tipo, txt, f, tam in partes:
            if tipo == "kicker":
                bloques.append((tipo, [(x + 24, y)], txt, f))
                y += tam * 1.6
            else:
                coords = []
                for i, l in enumerate(txt):
                    coords.append((x, y + i * tam * (1.08 if tipo == "tit" else 1.35)))
                bloques.append((tipo, coords, txt, f))
                y += len(txt) * tam * (1.08 if tipo == "tit" else 1.35) + 16
        return bloques

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        x0, y0, x1, y1 = self.caja
        bw, bh = x1 - x0, y1 - y0
        # Zoom lento y desplazamiento (Ken Burns)
        av = min(1.0, t / max(self.dur, 0.1))
        z = self.zoom - (self.zoom - 1.0) * 0.75 * av
        w, h = int(bw * z), int(bh * z)
        mx, my = (self.foto.width - w) / 2, (self.foto.height - h) / 2
        cx = mx + mx * self.dir[0] * (av - 0.5) * 0.9
        cy = my + my * self.dir[1] * (av - 0.5) * 0.9
        foto = self.foto.crop((int(cx), int(cy), int(cx) + w, int(cy) + h)).resize((bw, bh), Image.BILINEAR)
        entra = suave(t / 0.8)
        if self.diseno == "marco":
            borde = 14
            d = ImageDraw.Draw(img)
            sombra = Image.new("RGBA", (bw + 120, bh + 120), (0, 0, 0, 0))
            ImageDraw.Draw(sombra).rectangle((60, 70, 60 + bw, 70 + bh), fill=(0, 0, 0, 150))
            img.alpha_composite(alfa_capa(sombra.filter(ImageFilter.GaussianBlur(24)), entra), (x0 - 60, y0 - 50))
            d.rectangle((x0 - borde, y0 - borde, x1 + borde, y1 + borde + 46), fill=ctx.c("luz_foto", int(255 * entra)))
            img.alpha_composite(alfa_capa(foto, entra), (x0, y0))
            if self.credito:
                d.text((x1, y1 + borde + 24), self.credito, font=ctx.f("txt", 18), fill=ctx.c("sombra_foto", int(220 * entra)), anchor="rm")
        else:
            if self.mascara is not None:
                foto.putalpha(self.mascara)
            img.alpha_composite(alfa_capa(foto, entra), (x0, y0))
            if self.velo is not None:
                img.alpha_composite(self.velo)
        d = ImageDraw.Draw(img)
        if self.credito and self.diseno != "marco":
            xc = self.W - ctx.m if not ctx.vertical else self.W - ctx.m
            yc = self.H - 48 if not ctx.vertical else int(self.H * 0.56) - 70
            d.text((xc, yc), self.credito, font=ctx.f("txt", 19), fill=ctx.c("luz_foto", int(190 * entra)), anchor="rm")
        # Textos escalonados
        k = 0
        for tipo, coords, txt, f in self.textos:
            q = suave((t - 0.35 - 0.18 * k) / 0.5)
            k += 1
            if q <= 0:
                continue
            a = int(255 * q)
            if tipo == "kicker":
                x, y = coords[0]
                d.rectangle((x - 24, y - 2, x - 18, y + 30), fill=ctx.c("acento", a))
                d.text((x, y), txt, font=f, fill=ctx.c("acento", a))
            else:
                for (x, y), l in zip(coords, txt):
                    d.text((x + 20 * (1 - q), y), l, font=f, fill=ctx.c("texto" if tipo == "tit" else "suave", a))
        return img


# =====================================================================
#  Boceto: la figura se dibuja a trazos
# =====================================================================

def _trazar_esqueleto(esq):
    """Convierte un esqueleto (píxeles de 1 de ancho) en trazos: listas de puntos (x, y)."""
    ys, xs = np.nonzero(esq)
    pix = set(zip(xs.tolist(), ys.tolist()))
    vecinos = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

    def grado(p):
        return sum((p[0] + dx, p[1] + dy) in pix for dx, dy in vecinos)

    inicios = [p for p in pix if grado(p) == 1] + list(pix)
    visto, trazos = set(), []
    for p in inicios:
        if p in visto:
            continue
        trazo = [p]
        visto.add(p)
        actual = p
        while True:
            sig = None
            for dx, dy in vecinos:
                q = (actual[0] + dx, actual[1] + dy)
                if q in pix and q not in visto:
                    sig = q
                    break
            if sig is None:
                break
            trazo.append(sig)
            visto.add(sig)
            actual = sig
        if len(trazo) >= 8:
            trazos.append(trazo)
    return trazos


def _suavizar(trazo, paso=2):
    a = np.array(trazo, np.float32)
    if len(a) >= 5:
        k = np.ones(5) / 5
        a = np.stack([np.convolve(np.pad(a[:, i], 2, mode="edge"), k, mode="valid") for i in range(2)], axis=1)
    return a[::paso] if len(a) > 2 * paso else a


class Boceto(Pieza):
    """A partir de una imagen (un retrato, un edificio...) dibuja su silueta a trazos, como un esbozo a lápiz.

    detalle: bajo · medio · alto      revelar: true = al final aparece la foto debajo del dibujo
    """

    def __init__(self, *a, imagen=None, credito=""):
        super().__init__(*a)
        ctx, d = self.ctx, self.d
        self.credito = credito
        W, H = self.W, self.H
        # Caja del dibujo
        if ctx.vertical:
            self.caja = (ctx.m, 330, W - ctx.m, 1180)
        else:
            self.caja = (int(W * 0.40), 130, W - ctx.m, H - 110) if (d.get("nombre") or d.get("texto")) else (ctx.m + 200, 130, W - ctx.m - 200, H - 110)
        bw, bh = self.caja[2] - self.caja[0], self.caja[3] - self.caja[1]
        self.falta = imagen is None
        self.trazos, self.total = [], 1.0
        self.foto = None
        if imagen is not None:
            img = imagen.convert("RGB")
            r = min(bw / img.width, bh / img.height)
            img = img.resize((max(1, int(img.width * r)), max(1, int(img.height * r))), Image.LANCZOS)
            self.ox = self.caja[0] + (bw - img.width) // 2
            self.oy = self.caja[1] + (bh - img.height) // 2
            self.iw, self.ih = img.size
            self.trazos = self._extraer(img, str(d.get("detalle", "medio")))
            self.total = sum(self._largo(tr) for tr in self.trazos) or 1.0
            self.foto = duotono(img, ctx.tema, grano=10)
            w, h = img.size
            yy, xx = np.mgrid[0:h, 0:w]
            borde = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy]).astype(np.float32)
            plumilla = np.clip(borde / (0.12 * min(w, h)), 0, 1) ** 1.5
            self.foto.putalpha(Image.fromarray((plumilla * 255).astype(np.uint8)))
            self.sombreado = self._sombreado(img)
        self.lienzo_trazos = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        self.dibujado = 0.0
        self.t_dibujo = max(2.0, min(self.dur * 0.7, 6.0))
        self.textos = None

    @staticmethod
    def _largo(tr):
        return float(np.sum(np.hypot(*np.diff(tr, axis=0).T))) if len(tr) > 1 else 0.0

    def _extraer(self, img, detalle):
        from skimage import feature, filters, morphology
        g = np.array(ImageOps.grayscale(img), np.float32) / 255
        escala = 900 / max(g.shape)
        if escala < 1:
            g = np.array(Image.fromarray((g * 255).astype(np.uint8)).resize(
                (int(g.shape[1] * escala), int(g.shape[0] * escala)), Image.LANCZOS), np.float32) / 255
        else:
            escala = 1.0
        g = filters.gaussian(g, 1.0)
        sigma = {"bajo": 3.2, "medio": 2.3, "alto": 1.6}.get(detalle, 2.3)
        bordes = feature.canny(g, sigma=sigma, low_threshold=0.04, high_threshold=0.12)
        esq = morphology.skeletonize(bordes)
        trazos = _trazar_esqueleto(esq)
        trazos.sort(key=len, reverse=True)
        maximo = {"bajo": 260, "medio": 520, "alto": 900}.get(detalle, 520)
        trazos = trazos[:maximo]
        sx = self.iw / g.shape[1]
        sy = self.ih / g.shape[0]
        salida = []
        for tr in trazos:
            a = _suavizar(tr)
            a = a * [sx, sy] + [self.ox, self.oy]
            # un poco de pulso de mano
            a = a + np.array([[self.rnd.uniform(-0.6, 0.6), self.rnd.uniform(-0.6, 0.6)] for _ in range(len(a))])
            salida.append(a)
        # Orden: de arriba abajo por franjas, para que parezca que se dibuja a mano
        salida.sort(key=lambda a: (int(a[:, 1].min() // 120), -len(a)))
        return salida

    def _sombreado(self, img):
        """Rayado diagonal en las zonas oscuras (como un sombreado a lápiz)."""
        g = np.array(ImageOps.grayscale(img).filter(ImageFilter.GaussianBlur(4)), np.float32) / 255
        oscuro = np.clip((0.42 - g) / 0.25, 0, 1)
        h, w = g.shape
        yy, xx = np.mgrid[0:h, 0:w]
        rayas = ((xx + yy) % 14 < 2).astype(np.float32)
        a = (oscuro * rayas * 150).astype(np.uint8)
        capa = Image.new("RGBA", (w, h), self.ctx.c("suave"))
        capa.putalpha(Image.fromarray(a))
        return capa

    def fin_animacion(self):
        return self.t_dibujo + (2.2 if self.d.get("revelar") else 1.0)

    def _dibujar_hasta(self, objetivo):
        ctx = self.ctx
        d = ImageDraw.Draw(self.lienzo_trazos)
        acumulado = 0.0
        ancho = max(2, int(2.4 * SS))
        for tr in self.trazos:
            largo = self._largo(tr)
            ini, fin = acumulado, acumulado + largo
            acumulado = fin
            if fin <= self.dibujado:
                continue
            if ini >= objetivo:
                break
            # tramo de este trazo entre lo ya dibujado y el objetivo
            seg = np.hypot(*np.diff(tr, axis=0).T)
            cum = np.concatenate([[0], np.cumsum(seg)]) + ini
            a = max(self.dibujado, ini)
            b = min(objetivo, fin)
            sel = (cum >= a - 1e-6) & (cum <= b + 1e-6)
            idx = np.nonzero(sel)[0]
            if len(idx) == 0:
                continue
            i0 = max(0, idx[0] - 1)
            pts = [(float(x) * SS, float(y) * SS) for x, y in tr[i0: idx[-1] + 1]]
            if len(pts) >= 2:
                d.line(pts, fill=ctx.c("texto", 235), width=ancho, joint="curve")
        self.dibujado = max(self.dibujado, objetivo)

    def _preparar_textos(self):
        ctx, d = self.ctx, self.d
        partes = []
        if ctx.vertical:
            x, ancho, y = ctx.m, self.W - 2 * ctx.m, self.caja[3] + 20
        else:
            x, ancho, y = ctx.m, int(self.W * 0.34), None
        if d.get("kicker"):
            partes.append(("kicker", [str(d["kicker"]).upper()], ctx.f("txt_b", 28), 28))
        nombre = d.get("nombre") or d.get("texto")
        if nombre:
            f, ls, tam = ctx.ajustar(str(nombre), "tit", 96, ancho, 3, 40)
            partes.append(("tit", ls, f, tam))
        if d.get("sub"):
            f, ls, tam = ctx.ajustar(str(d["sub"]), "txt", 36, ancho, 3, 24)
            partes.append(("sub", ls, f, tam))
        alto = sum(tam * 1.6 if tp == "kicker" else len(ls) * tam * 1.15 + 16 for tp, ls, f, tam in partes)
        if y is None:
            y = (ctx.arriba + ctx.abajo) / 2 - alto / 2
        salida = []
        for tp, ls, f, tam in partes:
            for i, l in enumerate(ls):
                salida.append((tp, x, y + i * tam * 1.15, l, f))
            y += tam * 1.6 if tp == "kicker" else len(ls) * tam * 1.15 + 16
        return salida

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        if self.foto is not None:
            p = suave2(t / self.t_dibujo)
            self._dibujar_hasta(p * self.total)
            if self.d.get("revelar"):
                r = suave((t - self.t_dibujo) / 1.8)
                if r > 0:
                    img.alpha_composite(alfa_capa(self.foto, 0.75 * r), (self.ox, self.oy))
            s = suave((t - self.t_dibujo * 0.6) / 1.2) * (1 - 0.7 * suave((t - self.t_dibujo) / 1.8) if self.d.get("revelar") else 1)
            if s > 0:
                img.alpha_composite(alfa_capa(self.sombreado, s), (self.ox, self.oy))
            img.alpha_composite(self.lienzo_trazos.resize((self.W, self.H), Image.LANCZOS))
        if self.textos is None:
            self.textos = self._preparar_textos()
        d = ImageDraw.Draw(img)
        for k, (tp, x, y, l, f) in enumerate(self.textos):
            q = suave((t - 0.3 - 0.12 * k) / 0.5)
            if q <= 0:
                continue
            a = int(255 * q)
            if tp == "kicker":
                d.rectangle((x, y - 2, x + 6, y + 30), fill=ctx.c("acento", a))
                d.text((x + 24, y), l, font=f, fill=ctx.c("acento", a))
            else:
                d.text((x + 18 * (1 - q), y), l, font=f, fill=ctx.c("texto" if tp == "tit" else "suave", a))
        if self.credito:
            q = suave((t - 0.5) / 0.5)
            d.text((self.caja[2], self.caja[3] + (14 if not ctx.vertical else -10)), self.credito, font=ctx.f("txt", 18),
                   fill=ctx.c("suave", int(200 * q)), anchor="ra")
        return img


# =====================================================================
#  Mapa animado
# =====================================================================

REGIONES = {
    "europa": (-12, 32, 34.5, 61),
    "espana": (-9.8, 4.6, 35.6, 44.1),
    "peninsula": (-10, 4.6, 35.6, 44.2),
    "mediterraneo": (-8, 37, 29, 47),
    "latinoamerica": (-118, -33, -56, 33),
    "america_sur": (-83, -33, -56, 13.5),
    "centroamerica": (-118, -59, 6, 33),
    "america": (-170, -30, -56, 72),
    "mundo": (-170, 180, -58, 80),
    "asia": (25, 150, -10, 60),
    "africa": (-20, 55, -36, 38),
}


@functools.lru_cache(maxsize=1)
def _paises():
    datos = json.loads((MAPAS / "paises.geojson").read_text(encoding="utf-8"))
    salida = []
    for f in datos["features"]:
        p = f["properties"]
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        nombres = {normalizar(p.get(k) or "") for k in ("NAME", "NAME_ES", "ADMIN", "ISO_A3")} - {""}
        salida.append({"nombres": nombres, "nombre_es": p.get("NAME_ES") or p.get("NAME"),
                       "polys": [poly[0] for poly in polys], "centro": (p.get("LABEL_X"), p.get("LABEL_Y"))})
    return salida


ALIAS = {"eeuu": "estados unidos", "ee uu": "estados unidos", "usa": "estados unidos", "reino unido": "reino unido",
         "holanda": "paises bajos", "chequia": "republica checa", "gran bretana": "reino unido"}


def _buscar_pais(nombre):
    n = normalizar(nombre)
    n = ALIAS.get(n, n)
    for p in _paises():
        if n in p["nombres"]:
            return p
    raise SystemExit(f"::error::País desconocido en el mapa: «{nombre}» (escríbelo en español o en inglés)")


class Mapa(Pieza):
    """Mapa con zoom de entrada, países que se colorean por grupos y etiquetas.

    region: europa, espana, latinoamerica, america_sur, mundo... o caja: [lon_min, lon_max, lat_min, lat_max]
    grupos: [{paises: [...], color: acento, leyenda: "..."}]   etiquetas: [{pais o lon/lat, texto}]
    """
    opaca = True

    def __init__(self, *a):
        super().__init__(*a)
        ctx, d = self.ctx, self.d
        W, H = self.W, self.H
        caja = d.get("caja") or REGIONES.get(normalizar(d.get("region", "europa")).replace(" ", "_"))
        if not caja:
            raise SystemExit(f"::error::Región desconocida: «{d.get('region')}». Hay: {', '.join(REGIONES)}")
        lo0, lo1, la0, la1 = caja
        # Zona del mapa en pantalla
        if ctx.vertical:
            self.zona = (0, 300, W, 1400)
        else:
            self.zona = (int(W * 0.34), 0, W, H) if (d.get("titulo") or d.get("grupos")) else (0, 0, W, H)
        zx0, zy0, zx1, zy1 = self.zona
        zw, zh = zx1 - zx0, zy1 - zy0
        # Proyección: equirectangular corregida por la latitud media
        self.k = math.cos(math.radians((la0 + la1) / 2))
        mw, mh = (lo1 - lo0) * self.k, (la1 - la0)
        # Ajusta la caja al formato de la zona (sin deformar)
        if mw / mh > zw / zh:
            extra = (mw * zh / zw - mh) / 2
            la0, la1 = la0 - extra, la1 + extra
        else:
            extra = (mh * zw / zh - mw) / 2 / self.k
            lo0, lo1 = lo0 - extra, lo1 + extra
        self.final = (lo0, lo1, la0, la1)
        # Vista inicial más abierta (zoom de entrada)
        cx, cy = (lo0 + lo1) / 2, (la0 + la1) / 2
        f = 1.0 if d.get("sin_zoom") else 1.45
        self.inicio = (cx - (cx - lo0) * f, cx + (lo1 - cx) * f, cy - (cy - la0) * f, cy + (la1 - cy) * f)
        # Se dibuja una vez, grande, la extensión inicial
        self.res = max(zw, zh) * 1.45 * 1.25 / max((self.inicio[1] - self.inicio[0]) * self.k, self.inicio[3] - self.inicio[2])
        self.ext = self.inicio
        RW = int((self.ext[1] - self.ext[0]) * self.k * self.res)
        RH = int((self.ext[3] - self.ext[2]) * self.res)
        self.RW, self.RH = RW, RH
        self.grupos = []
        for i, g in enumerate(d.get("grupos") or []):
            self.grupos.append({"paises": [_buscar_pais(p) for p in g["paises"]], "color": g.get("color", "acento" if i == 0 else "acento2"),
                                "leyenda": g.get("leyenda")})
        self.base = self._render(None)
        self.capas = [self._render(g) for g in self.grupos]
        n = max(1, len(self.grupos))
        self.t_zoom = 0 if d.get("sin_zoom") else 1.8
        self.momentos = [0.5 + i * max(0.7, (self.dur * 0.7 - 0.5) / n) for i in range(len(self.grupos))]
        self.etiquetas = []
        for e in d.get("etiquetas") or []:
            if e.get("pais"):
                p = _buscar_pais(e["pais"])
                lon, lat = p["centro"]
            else:
                lon, lat = e["lon"], e["lat"]
            self.etiquetas.append((lon, lat, str(e["texto"]), e.get("color", "texto")))
        self.t_etiquetas = (self.momentos[-1] + 0.6) if self.momentos else self.t_zoom + 0.3
        self.cache_quieto = None

    def _px(self, lon, lat):
        return ((lon - self.ext[0]) * self.k * self.res, (self.ext[3] - lat) * self.res)

    def _render(self, grupo):
        ctx = self.ctx
        img = Image.new("RGBA", (self.RW, self.RH), (0, 0, 0, 0) if grupo else ctx.c("fondo"))
        d = ImageDraw.Draw(img)
        lo0, lo1, la0, la1 = self.ext
        margen = 20
        lista = grupo["paises"] if grupo else _paises()
        for p in lista:
            for anillo in p["polys"]:
                if not any(lo0 - margen < x < lo1 + margen and la0 - margen < y < la1 + margen for x, y in anillo[::4] or anillo):
                    continue
                pts = [self._px(x, y) for x, y in anillo]
                if len(pts) < 3:
                    continue
                if grupo:
                    d.polygon(pts, fill=ctx.c(grupo["color"]), outline=ctx.c("fondo"), width=3)
                else:
                    d.polygon(pts, fill=ctx.c("panel"), outline=ctx.c("fondo"), width=3)
        return img

    def movil(self):
        return False

    def fin_animacion(self):
        return max(self.t_zoom, self.t_etiquetas + 0.8)

    def _vista(self, t):
        q = suave2(t / self.t_zoom) if self.t_zoom else 1.0
        return tuple(a + (b - a) * q for a, b in zip(self.inicio, self.final))

    def dibujar(self, t):
        ctx = self.ctx
        img = Image.new("RGBA", (self.W, self.H), ctx.c("fondo"))
        zx0, zy0, zx1, zy1 = self.zona
        zw, zh = zx1 - zx0, zy1 - zy0
        mapa = self.base.copy()
        for g, capa, m in zip(self.grupos, self.capas, self.momentos):
            q = suave((t - m) / 0.6)
            if q > 0:
                mapa.alpha_composite(alfa_capa(capa, q))
        v = self._vista(t)
        x0, y0 = self._px(v[0], v[3])
        x1, y1 = self._px(v[1], v[2])
        recorte = mapa.crop((int(x0), int(y0), int(x1), int(y1))).resize((zw, zh), Image.BILINEAR)
        img.alpha_composite(recorte, (zx0, zy0))
        # Fundido de los bordes del mapa con el fondo
        img.alpha_composite(self._bordes())
        d = ImageDraw.Draw(img)

        def a_pantalla(lon, lat):
            return (zx0 + (lon - v[0]) / (v[1] - v[0]) * zw, zy0 + (v[3] - lat) / (v[3] - v[2]) * zh)

        fe = ctx.f("txt_b", 30)
        for k, (lon, lat, txt, col) in enumerate(self.etiquetas):
            q = suave((t - self.t_etiquetas - 0.25 * k) / 0.5)
            if q <= 0:
                continue
            x, y = a_pantalla(lon, lat)
            a = int(255 * q)
            d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=ctx.c("texto", a))
            lineas = txt.split("\n")
            w = max(fe.getlength(l) for l in lineas) + 36
            h = 44 * len(lineas) + 14
            lado = -1 if x > zx0 + zw * 0.6 else 1
            bx = x + lado * 60 + (0 if lado > 0 else -w)
            bx = min(max(bx, 20), self.W - w - 20)
            by = min(max(y - h - 30, 110), self.H - h - 80)
            d.line((x, y, bx + (0 if lado > 0 else w), by + h), fill=ctx.c("texto", a), width=3)
            d.rectangle((bx, by, bx + w, by + h), fill=ctx.c("fondo", int(235 * q)), outline=ctx.c(col if col != "texto" else "acento2", a), width=3)
            for i, l in enumerate(lineas):
                d.text((bx + 18, by + 12 + 44 * i), l, font=fe, fill=ctx.c("texto", a))
        # Título y leyenda
        if ctx.vertical:
            y = self._cabecera_bloque(d, t, self.d.get("titulo"), self.d.get("subtitulo"), y=250, tam=70)
            y_ley = 1330
        else:
            y = self._cabecera_bloque(d, t, self.d.get("titulo"), self.d.get("subtitulo"), y=300, ancho=int(self.W * 0.30), tam=84)
            y_ley = y + 10
        fl = ctx.f("txt", 30)
        x = ctx.m
        for g, m in zip(self.grupos, self.momentos):
            if not g["leyenda"]:
                continue
            q = suave((t - m) / 0.5)
            if q <= 0:
                continue
            a = int(255 * q)
            d.rectangle((x, y_ley, x + 32, y_ley + 32), fill=ctx.c(g["color"], a))
            d.text((x + 50, y_ley + 16), str(g["leyenda"]), font=fl, fill=ctx.c("suave", a), anchor="lm")
            if ctx.vertical:
                x += 50 + fl.getlength(str(g["leyenda"])) + 50
            else:
                y_ley += 54
        return img

    @functools.lru_cache(maxsize=1)
    def _bordes(self):
        ctx = self.ctx
        zx0, zy0, zx1, zy1 = self.zona
        a = np.zeros((self.H, self.W), np.float32)
        yy = np.arange(self.H)[:, None]
        xx = np.arange(self.W)[None, :]
        a = np.maximum(a, np.clip((zy0 + 160 - yy) / 160, 0, 1) * (1 if zy0 > 0 else 0.85))
        a = np.maximum(a, np.clip((yy - (zy1 - 160)) / 160, 0, 1) * (1 if zy1 < self.H else 0.85))
        if zx0 > 0:
            a = np.maximum(a, np.clip((zx0 + 260 - xx) / 260, 0, 1))
        a = np.clip(a, 0, 1)
        capa = Image.new("RGBA", (self.W, self.H), ctx.c("fondo"))
        capa.putalpha(Image.fromarray((a * 255).astype(np.uint8)))
        return capa


# =====================================================================
#  Esquema: cajas y flechas
# =====================================================================

class Esquema(Pieza):
    """Cajas que aparecen una a una unidas por flechas.

    modo: cadena (A → B → C) · causas (varias cajas que llevan a un resultado)
    nodos: [{etiqueta, texto, destacar}]   flechas: textos opcionales sobre las flechas (cadena)
    resultado: {etiqueta, texto} (causas)    nota: frase que sale al final
    """

    def __init__(self, *a):
        super().__init__(*a)
        d = self.d
        self.modo = d.get("modo", "cadena")
        self.nodos = d["nodos"]
        self.flechas = d.get("flechas") or []
        self.resultado = d.get("resultado")
        n = len(self.nodos) + (1 if self.resultado else 0)
        self.paso = max(0.55, (self.dur * 0.72 - 0.6) / max(1, n))
        self.entrada = 0.6 + n * self.paso + (0.8 if d.get("nota") else 0.2)
        self.cajas = self._colocar()

    def _colocar(self):
        ctx = self.ctx
        W = self.W
        img = self.lienzo()
        y_top = self._cabecera_bloque(ImageDraw.Draw(img), 9, self.d.get("titulo"), self.d.get("subtitulo"))
        cajas = []
        if self.modo == "causas":
            n = len(self.nodos)
            if ctx.vertical:
                aw, ah, gap = W - 2 * ctx.m, 150, 30
                y0 = y_top + 20
                for i in range(n):
                    cajas.append((ctx.m, y0 + i * (ah + gap), ctx.m + aw, y0 + i * (ah + gap) + ah))
                yr = y0 + n * (ah + gap) + 90
                cajas.append((ctx.m + 80, yr, W - ctx.m - 80, yr + 190))
            else:
                aw, ah, gap = 560, 150, 36
                total = n * ah + (n - 1) * gap
                y0 = max(y_top + 10, (ctx.arriba + ctx.abajo) / 2 - total / 2 + 40)
                for i in range(n):
                    cajas.append((ctx.m, y0 + i * (ah + gap), ctx.m + aw, y0 + i * (ah + gap) + ah))
                yc = y0 + total / 2
                cajas.append((W - ctx.m - 560, yc - 130, W - ctx.m, yc + 130))
        else:
            n = len(self.nodos)
            if ctx.vertical or n > 5:
                aw, ah, gap = W - 2 * ctx.m - (0 if ctx.vertical else 400), 160, 80
                total = n * ah + (n - 1) * gap
                y0 = max(y_top + 10, (ctx.arriba + ctx.abajo) / 2 - total / 2 + 30)
                x0 = (W - aw) / 2
                for i in range(n):
                    cajas.append((x0, y0 + i * (ah + gap), x0 + aw, y0 + i * (ah + gap) + ah))
            else:
                gap = 200 if self.flechas else 110
                aw = (W - 2 * ctx.m - (n - 1) * gap) / n
                ah = 250
                y0 = max(y_top + 40, (ctx.arriba + ctx.abajo) / 2 - ah / 2 + 30)
                for i in range(n):
                    x = ctx.m + i * (aw + gap)
                    cajas.append((x, y0, x + aw, y0 + ah))
        return cajas

    def _caja(self, d, caja, nodo, q, destacar):
        ctx = self.ctx
        x0, y0, x1, y1 = caja
        a = int(255 * q)
        dy = 20 * (1 - q)
        if destacar:
            d.rectangle((x0, y0 + dy, x1, y1 + dy), fill=ctx.c("acento", a))
            col_e, col_t = ctx.c("fondo", int(a * 0.8)), ctx.c("fondo", a)
        else:
            d.rectangle((x0, y0 + dy, x1, y1 + dy), fill=ctx.c("panel", a), outline=ctx.c("linea", a), width=2)
            d.rectangle((x0, y0 + dy, x0 + 6, y1 + dy), fill=ctx.c("acento", a))
            col_e, col_t = ctx.c("suave", a), ctx.c("texto", a)
        pad = 28
        if nodo.get("etiqueta"):
            d.text((x0 + pad, y0 + dy + 24), str(nodo["etiqueta"]).upper(), font=ctx.f("txt_b", 22), fill=col_e)
        texto = str(nodo.get("texto", ""))
        ancho = x1 - x0 - 2 * pad
        alto_disp = (y1 - y0) - (70 if nodo.get("etiqueta") else 40)
        es_num = len(texto) <= 12 and any(ch.isdigit() for ch in texto)
        rol = "num" if es_num else "tit2"
        tam = 84 if es_num else 46
        while True:
            f = ctx.f(rol, tam)
            ls = envolver(texto, f, ancho)
            if (len(ls) * tam * 1.15 <= alto_disp and all(f.getlength(l) <= ancho for l in ls)) or tam <= 22:
                break
            tam -= 3
        yt = y0 + dy + (60 if nodo.get("etiqueta") else 20) + (alto_disp - len(ls) * tam * 1.15) / 2
        for i, l in enumerate(ls):
            d.text((x0 + pad, yt + i * tam * 1.15), l, font=f, fill=col_t)

    @staticmethod
    def _flecha(d, a, b, col, ancho, punta):
        d.line((a, b), fill=col, width=ancho)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        p1 = (b[0] - punta * math.cos(ang - 0.45), b[1] - punta * math.sin(ang - 0.45))
        p2 = (b[0] - punta * math.cos(ang + 0.45), b[1] - punta * math.sin(ang + 0.45))
        d.polygon([b, p1, p2], fill=col)

    def dibujar(self, t):
        ctx = self.ctx
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        self._cabecera_bloque(d, t, self.d.get("titulo"), self.d.get("subtitulo"))
        big = Image.new("RGBA", (self.W * SS, self.H * SS), (0, 0, 0, 0))
        db = ImageDraw.Draw(big)
        nodos = list(self.nodos) + ([self.resultado] if self.resultado else [])
        momentos = [0.6 + i * self.paso for i in range(len(nodos))]
        if self.modo == "causas":
            momentos[-1] = 0.6 + len(self.nodos) * self.paso
        # Flechas (se dibujan creciendo justo antes de la caja siguiente)
        pares = []
        if self.modo == "causas":
            r = self.cajas[-1]
            for i in range(len(self.nodos)):
                c = self.cajas[i]
                if ctx.vertical:
                    a = ((c[0] + c[2]) / 2, c[3])
                    b = ((r[0] + r[2]) / 2, r[1] - 10)
                    if i < len(self.nodos) - 1:
                        continue
                else:
                    a = (c[2] + 14, (c[1] + c[3]) / 2)
                    b = (r[0] - 16, (r[1] + r[3]) / 2)
                pares.append((a, b, momentos[-1] - 0.45, None))
        else:
            for i in range(len(self.nodos) - 1):
                c, e = self.cajas[i], self.cajas[i + 1]
                if abs(c[1] - e[1]) < 1:  # en fila
                    a, b = (c[2] + 14, (c[1] + c[3]) / 2), (e[0] - 16, (e[1] + e[3]) / 2)
                else:  # en columna
                    a, b = ((c[0] + c[2]) / 2, c[3] + 10), ((e[0] + e[2]) / 2, e[1] - 12)
                pares.append((a, b, momentos[i + 1] - 0.4, self.flechas[i] if i < len(self.flechas) else None))
        for a, b, m, etiqueta in pares:
            q = suave((t - m) / 0.4)
            if q <= 0:
                continue
            bb = (a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q)
            self._flecha(db, (a[0] * SS, a[1] * SS), (bb[0] * SS, bb[1] * SS), ctx.c("acento2"), 5 * SS, 22 * SS)
            if etiqueta:
                fe = ctx.f("txt_b", 24)
                xm, ym = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                if abs(a[1] - b[1]) < 1:
                    txt = str(etiqueta).upper()
                    while fe.getlength(txt) > abs(b[0] - a[0]) + 20 and fe.size > 14:
                        fe = ctx.f("txt_b", fe.size - 2)
                    d.text((xm, ym - 26), txt, font=fe, fill=ctx.c("acento2", int(255 * q)), anchor="mb")
                else:
                    d.text((xm + 30, ym), str(etiqueta).upper(), font=fe, fill=ctx.c("acento2", int(255 * q)), anchor="lm")
        img.alpha_composite(big.resize((self.W, self.H), Image.LANCZOS))
        d = ImageDraw.Draw(img)
        for i, (nodo, caja, m) in enumerate(zip(nodos, self.cajas, momentos)):
            q = suave((t - m) / 0.45)
            if q > 0:
                destacar = nodo.get("destacar", self.resultado is not None and i == len(nodos) - 1)
                self._caja(d, caja, nodo, q, destacar)
        if self.d.get("nota"):
            q = suave((t - momentos[-1] - 0.6) / 0.5)
            if q > 0:
                y = max(c[3] for c in self.cajas) + 60
                f, ls, tam = ctx.ajustar(str(self.d["nota"]), "txt_b", 40, self.W - 2 * ctx.m, 2, 26)
                for k, l in enumerate(ls):
                    d.text((self.W / 2, y + k * tam * 1.3), l, font=f, fill=ctx.c("acento", int(255 * q)), anchor="ma")
        return img


# =====================================================================
#  Clip de vídeo de archivo (Pixabay/Pexels)
# =====================================================================

class Archivo(Pieza):
    opaca = True
    entrada = 0.8

    def __init__(self, *a, clip=None):
        super().__init__(*a)
        ctx, d = self.ctx, self.d
        W, H = self.W, self.H
        self.proc, self.ultimo, self.base = None, None, None
        if clip:
            margen = max(0.0, clip["duracion"] - self.dur - 0.5)
            ini = self.rnd.uniform(0, margen) if margen > 0 else 0
            sepia = (f"colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,"
                     if d.get("color") is not True else "")
            filtro = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                      f"{sepia}eq=brightness=-0.06:saturation=0.9:contrast=1.08,noise=alls=10:allf=t,format=rgb24")
            cmd = ["ffmpeg", "-loglevel", "error"]
            if clip["duracion"] < self.dur + 0.5:
                cmd += ["-stream_loop", "-1"]
            cmd += ["-threads", "2", "-ss", f"{ini:.2f}", "-i", clip["ruta"], "-t", f"{self.dur + 0.5:.2f}", "-vf", filtro,
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        y = np.linspace(0, 1, H)[:, None]
        a = 0.2 + 0.7 * np.clip((y - 0.5) / 0.5, 0, 1) ** 1.2 + 0.3 * np.clip((0.15 - y) / 0.15, 0, 1)
        self.velo = Image.new("RGBA", (W, H), ctx.c("fondo"))
        self.velo.putalpha(Image.fromarray((np.broadcast_to(a, (H, W)).clip(0, 1) * 255).astype(np.uint8)))
        self.rot = None
        if d.get("texto"):
            self.rot = ctx.ajustar(str(d["texto"]), "tit", 92, int(W * (0.86 if ctx.vertical else 0.62)), 3, 40)

    def movil(self):
        return True

    def dibujar(self, t):
        ctx = self.ctx
        W, H = self.W, self.H
        img = None
        if self.proc:
            datos = self.proc.stdout.read(W * H * 3)
            if len(datos) == W * H * 3:
                self.ultimo = Image.frombytes("RGB", (W, H), datos).convert("RGBA")
            if self.ultimo is not None:
                img = self.ultimo.copy()
        if img is None:
            img = Image.new("RGBA", (W, H), ctx.c("fondo2"))
        img.alpha_composite(self.velo)
        d = ImageDraw.Draw(img)
        y = H * (0.80 if not ctx.vertical else 0.70)
        if self.rot:
            f, ls, tam = self.rot
            y -= len(ls) * tam * 1.08
            if self.d.get("sub"):
                q = suave((t - 0.1) / 0.4)
                d.rectangle((ctx.m, y - 52, ctx.m + 6, y - 22), fill=ctx.c("acento", int(255 * q)))
                d.text((ctx.m + 24, y - 54), str(self.d["sub"]).upper(), font=ctx.f("txt_b", 28), fill=ctx.c("acento", int(255 * q)))
            q = suave((t - 0.25) / 0.5)
            for i, l in enumerate(ls):
                d.text((ctx.m + 20 * (1 - q), y + i * tam * 1.08), l, font=f, fill=ctx.c("texto", int(255 * q)))
        return img

    def cerrar(self):
        if self.proc:
            self.proc.stdout.close()
            self.proc.kill()
            self.proc = None


TIPOS = {"titulo": Titulo, "cifra": Cifra, "comparar": Comparar, "linea": Linea, "barras": Barras,
         "fecha": Fecha, "cita": Cita, "lista": Lista, "foto": Foto, "boceto": Boceto, "mapa": Mapa,
         "esquema": Esquema, "archivo": Archivo}


def crear_pieza(d, ctx, dur, imagen=None, credito="", clip=None):
    tipo = d.get("tipo", "titulo")
    if tipo not in TIPOS:
        raise SystemExit(f"::error::Tipo de escena desconocido: «{tipo}». Hay: {', '.join(TIPOS)}")
    if tipo in ("foto", "boceto"):
        return TIPOS[tipo](d, ctx, dur, imagen=imagen, credito=credito)
    if tipo == "archivo":
        return Archivo(d, ctx, dur, clip=clip)
    return TIPOS[tipo](d, ctx, dur)
