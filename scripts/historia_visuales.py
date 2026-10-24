"""Piezas visuales del canal de historia económica (estilo «datos moderno»).

Todo se dibuja con código y sirve igual para el vídeo largo (1920x1080) y para los
Shorts (1080x1920): cada pieza se dibuja dentro de una «zona» del tamaño que le den.

Tipos de escena (campo «tipo» en el guion):
    titulo     titular grande; «resaltar» marca palabras en color
    cifra      número que cuenta hasta su valor, con etiqueta
    comparar   dos barras: antes / después (o dos países, dos sueldos…)
    linea      gráfico de línea que se dibuja poco a poco, con marcas
    barras     gráfico de barras que crecen
    fecha      fecha grande sobre una línea de tiempo
    cita       cita textual con su autor
    lista      puntos que aparecen uno a uno
    archivo    clip de vídeo de archivo (Pixabay/Pexels) con un rótulo
"""
import functools
import math
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FUENTES = Path(__file__).resolve().parent.parent / "fuentes"
F_TIT = str(FUENTES / "Inter-ExtraBold.ttf")
F_NUM = str(FUENTES / "Inter-ExtraBold.ttf")
F_TXT = str(FUENTES / "IBMPlexSans-SemiBold.ttf")
F_TXT_B = str(FUENTES / "IBMPlexSans-Bold.ttf")
F_TXT_M = str(FUENTES / "IBMPlexSans-Medium.ttf")
F_SERIF = str(FUENTES / "IBMPlexSerif-SemiBold.ttf")
FPS = 30


@functools.lru_cache(maxsize=256)
def fuente(ruta, tam):
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


def color(tema, nombre, alfa=255):
    c = tema.get(nombre, nombre) if isinstance(nombre, str) else nombre
    return tuple(c[:3]) + (alfa,)


def numero(valor, decimales=0, prefijo="", sufijo=""):
    """Número a la española: 1.250.000 · 4,9 · 166,386 (los años y cifras de 4 dígitos sin punto)."""
    txt = f"{abs(valor):,.{decimales}f}" if abs(valor) >= 10000 else f"{abs(valor):.{decimales}f}"
    txt = txt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    signo = "−" if valor < 0 else ""
    return f"{prefijo}{signo}{txt}{sufijo}"


def _paso_redondo(x):
    """Paso «bonito» para los ejes: 1, 2, 2,5 o 5 por una potencia de 10."""
    base = 10 ** math.floor(math.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if x <= m * base:
            return m * base
    return 10 * base


def envolver(texto, f, ancho):
    lineas, actual = [], ""
    for p in texto.split():
        prueba = (actual + " " + p).strip()
        if f.getlength(prueba) <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def ajustar(texto, ruta, tam, ancho, max_lineas=3, minimo=28):
    """Baja el tamaño hasta que el texto quepa en max_lineas."""
    while True:
        f = fuente(ruta, tam)
        lineas = envolver(texto, f, ancho)
        if (len(lineas) <= max_lineas and all(f.getlength(l) <= ancho for l in lineas)) or tam <= minimo:
            return f, lineas, tam
        tam -= 4


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
    base.alpha_composite(capa, (int(x), int(y)))


def caja(texto, ruta, tam, tinta, fondo, pad=(22, 12), radio=12):
    f = fuente(ruta, tam)
    c = f.getbbox(texto)
    w, h = c[2] - c[0] + 2 * pad[0], c[3] - c[1] + 2 * pad[1]
    capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    if fondo:
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radio, fill=fondo)
    d.text((pad[0] - c[0], pad[1] - c[1]), texto, font=f, fill=tinta)
    return capa


# =====================================================================
#  Pieza base
# =====================================================================

class Pieza:
    """Una pieza visual. cuadro(t, dur) devuelve una imagen RGBA del tamaño de la zona."""
    entrada = 1.2          # segundos que dura su animación de entrada
    fondo_propio = False   # True si ocupa toda la pantalla (clips de archivo)

    def __init__(self, d, w, h, tema, semilla=""):
        self.d, self.w, self.h, self.tema = d, w, h, tema
        self.rnd = random.Random(str(semilla))
        self._quieto = None

    def lienzo(self):
        return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))

    def cuadro(self, t, dur):
        if t >= self.fin_animacion(dur):
            if self._quieto is None:
                self._quieto = self.dibujar(self.fin_animacion(dur) + 0.001, dur)
            return self._quieto
        return self.dibujar(t, dur)

    def fin_animacion(self, dur):
        return self.entrada

    def dibujar(self, t, dur):
        return self.lienzo()

    def cerrar(self):
        pass


# =====================================================================
#  Titular
# =====================================================================

class Titulo(Pieza):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        texto = self.d["texto"]
        resaltar = {p.strip(".,:;¿?¡!«»").lower() for p in str(self.d.get("resaltar") or "").split()}
        vertical = self.h > self.w
        self.f, lineas, self.tam = ajustar(texto, F_TIT, 112 if vertical else 104, self.w - 80, 4 if vertical else 3, 48)
        self.alto_l = int(self.tam * 1.22)
        esp = self.f.getlength(" ")
        extra = 18  # aire a cada lado de las palabras resaltadas, para que la caja no pise a las vecinas
        self.palabras = []  # (texto, x, y, resaltada)
        y0 = (self.h - self.alto_l * len(lineas)) / 2 + (30 if self.d.get("kicker") else 0)
        for i, l in enumerate(lineas):
            ps = l.split()
            marcadas = [p.strip(".,:;¿?¡!«»").lower() in resaltar for p in ps]
            ancho = self.f.getlength(l) + extra * 2 * sum(marcadas)
            x = (self.w - ancho) / 2
            for p, res in zip(ps, marcadas):
                if res:
                    x += extra
                self.palabras.append((p, x, y0 + i * self.alto_l, res))
                x += self.f.getlength(p) + esp + (extra if res else 0)
        self.kicker = None
        if self.d.get("kicker"):
            self.kicker = caja(str(self.d["kicker"]).upper(), F_TXT_B, 34, color(self.tema, "fondo"),
                               color(self.tema, "acento"), pad=(18, 8), radio=8)
            self.y_kicker = y0 - 70
        self.entrada = 0.65 + 0.07 * len(self.palabras)

    def dibujar(self, t, dur):
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        if self.kicker:
            q = suave(t / 0.35)
            pegar(img, self.kicker, self.w / 2 - 30 * (1 - q), self.y_kicker, q)
        asc = self.f.getbbox("Ág")[1]
        for k, (p, x, y, res) in enumerate(self.palabras):
            q = suave((t - 0.1 - 0.07 * k) / 0.32)
            if q <= 0:
                continue
            dy = 26 * (1 - q)
            a = int(255 * q)
            if res:
                ancho = self.f.getlength(p)
                g = suave((t - 0.25 - 0.07 * k) / 0.3)
                d.rounded_rectangle((x - 14, y + asc - 10 + dy, x - 14 + (ancho + 28) * g, y + self.tam * 1.08 + dy),
                                    radius=10, fill=color(self.tema, "acento2", a))
                d.text((x, y + dy), p, font=self.f, fill=color(self.tema, "fondo", a))
            else:
                d.text((x, y + dy), p, font=self.f, fill=color(self.tema, "texto", a))
        return img


# =====================================================================
#  Cifra que cuenta
# =====================================================================

class Cifra(Pieza):
    entrada = 1.7

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        d = self.d
        self.valor = float(d.get("valor", 0) or 0)
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.texto_fijo = d.get("texto")
        self.col = color(self.tema, d.get("color", "acento"))
        final = self.texto_fijo or numero(self.valor, self.dec, self.pre, self.suf)
        tam = 250 if self.h > self.w else 240
        while fuente(F_NUM, tam).getlength(final) > self.w - 60 and tam > 60:
            tam -= 8
        self.fn = fuente(F_NUM, tam)
        self.tam = tam
        self.etiqueta = None
        if d.get("etiqueta"):
            f, lineas, t2 = ajustar(str(d["etiqueta"]), F_TXT, 50, self.w - 120, 3, 30)
            capa = Image.new("RGBA", (self.w, int(t2 * 1.3 * len(lineas)) + 10), (0, 0, 0, 0))
            dd = ImageDraw.Draw(capa)
            for i, l in enumerate(lineas):
                dd.text(((self.w - f.getlength(l)) / 2, i * t2 * 1.3), l, font=f, fill=color(self.tema, "suave"))
            self.etiqueta = capa
        alto_total = tam * 1.05 + 40 + (self.etiqueta.height if self.etiqueta else 0)
        self.y_num = (self.h - alto_total) / 2
        self.y_raya = self.y_num + tam * 1.05 + 10
        self.y_eti = self.y_raya + 30

    def dibujar(self, t, dur):
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        p = suave(t / 1.2)
        if self.texto_fijo:
            txt = self.texto_fijo
        else:
            txt = numero(self.valor * p if p < 1 else self.valor, self.dec, self.pre, self.suf)
        aparece = suave(t / 0.3)
        c = self.fn.getbbox(txt)
        x = (self.w - (c[2] - c[0])) / 2 - c[0]
        d.text((x, self.y_num + 30 * (1 - aparece) - c[1] + self.tam * 0.05), txt, font=self.fn,
               fill=self.col[:3] + (int(255 * aparece),))
        r = suave((t - 0.3) / 0.8)
        ancho = 180 * r
        d.rounded_rectangle((self.w / 2 - ancho / 2, self.y_raya, self.w / 2 + ancho / 2, self.y_raya + 8), radius=4,
                            fill=color(self.tema, "acento2"))
        if self.etiqueta:
            q = suave((t - 0.5) / 0.5)
            pegar(img, self.etiqueta, 0, self.y_eti + 20 * (1 - q), q, centro=False)
        return img


# =====================================================================
#  Comparar dos valores
# =====================================================================

class Comparar(Pieza):
    entrada = 1.8

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        d = self.d
        self.izq, self.der = d["izquierda"], d["derecha"]
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.maximo = max(abs(float(self.izq["valor"])), abs(float(self.der["valor"]))) or 1
        self.titulo = None
        if d.get("titulo"):
            f, lineas, tam = ajustar(str(d["titulo"]), F_TIT, 52, self.w - 100, 2, 30)
            self.titulo = (f, lineas, tam)
        self.f_val = fuente(F_NUM, 76 if self.h > self.w else 72)
        self.f_eti = fuente(F_TXT, 40)

    def dibujar(self, t, dur):
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        y_top = 20
        if self.titulo:
            f, lineas, tam = self.titulo
            q = suave(t / 0.4)
            for i, l in enumerate(lineas):
                d.text(((self.w - f.getlength(l)) / 2, y_top + i * tam * 1.2), l, font=f,
                       fill=color(self.tema, "texto", int(255 * q)))
            y_top += len(lineas) * tam * 1.2 + 20
        base_y = self.h - 90
        alto_max = base_y - y_top - 170
        ancho_barra = min(300, self.w * 0.22)
        for k, (lado, cx) in enumerate([(self.izq, self.w * 0.32), (self.der, self.w * 0.68)]):
            q = suave((t - 0.2 - 0.25 * k) / 1.1)
            v = float(lado["valor"])
            h = max(6, alto_max * abs(v) / self.maximo * q)
            col = color(self.tema, lado.get("color", "suave" if k == 0 else "acento2"))
            d.rounded_rectangle((cx - ancho_barra / 2, base_y - h, cx + ancho_barra / 2, base_y), radius=14, fill=col)
            txt = lado.get("texto") or numero(v * q if q < 1 else v, self.dec, self.pre, self.suf)
            c = self.f_val.getbbox(txt)
            d.text((cx - (c[2] - c[0]) / 2 - c[0], base_y - h - 30 - c[3]), txt, font=self.f_val,
                   fill=color(self.tema, "texto", int(255 * min(1, q * 3))))
            eti = str(lado.get("etiqueta", ""))
            lw = self.f_eti.getlength(eti)
            d.text((cx - lw / 2, base_y + 18), eti, font=self.f_eti, fill=color(self.tema, "suave"))
        d.line((self.w * 0.12, base_y, self.w * 0.88, base_y), fill=color(self.tema, "linea"), width=3)
        return img


# =====================================================================
#  Gráficos: línea y barras
# =====================================================================

class Linea(Pieza):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        d = self.d
        self.vals = [float(v) for v in d["valores"]]
        n = len(self.vals)
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.col = color(self.tema, d.get("color", "acento"))
        vertical = self.h > self.w
        pad_l, pad_r = (120 if vertical else 150), (70 if vertical else 110)
        y_top = 30
        base = self.lienzo()
        bd = ImageDraw.Draw(base)
        if d.get("titulo"):
            f, lineas, tam = ajustar(str(d["titulo"]), F_TIT, 50, self.w - 80, 2, 28)
            for i, l in enumerate(lineas):
                bd.text((40, y_top + i * tam * 1.2), l, font=f, fill=color(self.tema, "texto"))
            y_top += len(lineas) * tam * 1.2 + 30
        x0, x1, y0, y1 = pad_l, self.w - pad_r, y_top + 100, self.h - 80
        lo, hi = min(self.vals), max(self.vals)
        if d.get("desde_cero", lo >= 0):
            lo = min(0, lo)
        paso = _paso_redondo((hi - lo) / 4 or 1)
        lo = math.floor(lo / paso) * paso
        hi = math.ceil(hi * 1.05 / paso) * paso
        f_eje = fuente(F_TXT_M, 30)
        dec_eje = 0 if paso >= 1 else (1 if paso >= 0.1 else 2)
        k = 0
        while lo + paso * k <= hi + 1e-9:
            v = lo + paso * k
            y = y1 - (y1 - y0) * (v - lo) / (hi - lo)
            bd.line((x0, y, x1, y), fill=color(self.tema, "linea"), width=2)
            txt = numero(v, dec_eje)
            bd.text((x0 - 16 - f_eje.getlength(txt), y - 18), txt, font=f_eje, fill=color(self.tema, "suave"))
            k += 1
        etiquetas = d.get("etiquetas") or {}
        if isinstance(etiquetas, list):
            paso = max(1, math.ceil(len(etiquetas) / (6 if vertical else 9)))
            etiquetas = {i: e for i, e in enumerate(etiquetas) if i % paso == 0 or i == len(etiquetas) - 1}
        for i, txt in etiquetas.items():
            i = int(i)
            x = x0 + (x1 - x0) * i / max(1, n - 1)
            w = f_eje.getlength(str(txt))
            bd.text((min(max(x - w / 2, x0 - 40), x1 - w + 40), y1 + 18), str(txt), font=f_eje, fill=color(self.tema, "suave"))
        self.base = base
        self.pts = [(x0 + (x1 - x0) * i / max(1, n - 1), y1 - (y1 - y0) * (v - lo) / (hi - lo)) for i, v in enumerate(self.vals)]
        self.y1 = y1
        self.marcas = []
        for m in d.get("marcas") or []:
            i = int(m["indice"])
            self.marcas.append((i, caja(str(m["texto"]), F_TXT_B, 32, color(self.tema, "fondo"),
                                        color(self.tema, m.get("color", "acento2")), pad=(16, 8), radio=8)))
        self.f_val = fuente(F_NUM, 44)

    def fin_animacion(self, dur):
        return min(3.2, max(1.6, dur * 0.6)) + 0.5

    def dibujar(self, t, dur):
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        r = suave2(t / (self.fin_animacion(dur) - 0.5))
        n = len(self.pts)
        pos = r * (n - 1)
        k = int(pos)
        f = pos - k
        pts = self.pts[:k + 1]
        if k + 1 < n:
            a, b = self.pts[k], self.pts[k + 1]
            pts = pts + [(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)]
        if len(pts) >= 2:
            relleno = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(relleno).polygon(pts + [(pts[-1][0], self.y1), (pts[0][0], self.y1)], fill=self.col[:3] + (40,))
            img.alpha_composite(relleno)
            d = ImageDraw.Draw(img)
            d.line(pts, fill=self.col, width=8, joint="curve")
        xe, ye = pts[-1]
        d.ellipse((xe - 13, ye - 13, xe + 13, ye + 13), fill=self.col)
        d.ellipse((xe - 6, ye - 6, xe + 6, ye + 6), fill=color(self.tema, "fondo"))
        # Valor en la punta
        vi = min(n - 1, int(round(pos)))
        txt = numero(self.vals[vi], self.dec, self.pre, self.suf)
        tw = self.f_val.getlength(txt)
        tx = min(xe + 22, self.w - tw - 10)
        d.text((tx, ye - 62), txt, font=self.f_val, fill=color(self.tema, "texto"))
        for i, capa in self.marcas:
            if pos >= i:
                q = suave((pos - i) / 0.6 if n > 2 else 1)
                x, y = self.pts[i]
                d.line((x, y, x, y - 70), fill=color(self.tema, "acento2", int(255 * q)), width=3)
                pegar(img, capa, min(max(x, capa.width / 2 + 10), self.w - capa.width / 2 - 10), y - 90, q)
        return img


class Barras(Pieza):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        d = self.d
        self.vals = [float(v) for v in d["valores"]]
        self.etis = [str(e) for e in (d.get("etiquetas") or [""] * len(self.vals))]
        self.dec = int(d.get("decimales", 0) or 0)
        self.pre, self.suf = str(d.get("prefijo", "") or ""), str(d.get("sufijo", "") or "")
        self.destacar = set(int(i) for i in (d.get("destacar") or []))
        self.titulo = None
        if d.get("titulo"):
            self.titulo = ajustar(str(d["titulo"]), F_TIT, 50, self.w - 80, 2, 28)
        n = len(self.vals)
        self.f_val = fuente(F_NUM, 44 if n <= 6 else 32)
        self.f_eti = fuente(F_TXT, 34 if n <= 6 else 26)
        self.entrada = 0.5 + 0.12 * n + 0.9

    def dibujar(self, t, dur):
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        y_top = 20
        if self.titulo:
            f, lineas, tam = self.titulo
            for i, l in enumerate(lineas):
                d.text((40, y_top + i * tam * 1.2), l, font=f, fill=color(self.tema, "texto"))
            y_top += len(lineas) * tam * 1.2 + 30
        n = len(self.vals)
        x0, x1 = 60, self.w - 60
        y1 = self.h - 70
        alto_max = y1 - y_top - 80
        top = max(abs(v) for v in self.vals) or 1
        paso = (x1 - x0) / n
        ancho = paso * 0.62
        for i, v in enumerate(self.vals):
            q = suave((t - 0.2 - 0.12 * i) / 0.9)
            cx = x0 + paso * (i + 0.5)
            h = max(4, alto_max * abs(v) / top * q)
            col = color(self.tema, "acento2" if i in self.destacar else "acento")
            d.rounded_rectangle((cx - ancho / 2, y1 - h, cx + ancho / 2, y1), radius=10, fill=col)
            if q > 0.05:
                txt = numero(v * q if q < 1 else v, self.dec, self.pre, self.suf)
                tw = self.f_val.getlength(txt)
                d.text((cx - tw / 2, y1 - h - 58), txt, font=self.f_val, fill=color(self.tema, "texto", int(255 * min(1, q * 2))))
            eti = self.etis[i] if i < len(self.etis) else ""
            ew = self.f_eti.getlength(eti)
            d.text((cx - ew / 2, y1 + 16), eti, font=self.f_eti, fill=color(self.tema, "suave"))
        d.line((x0, y1, x1, y1), fill=color(self.tema, "linea"), width=3)
        return img


# =====================================================================
#  Fecha, cita y lista
# =====================================================================

class Fecha(Pieza):
    entrada = 1.6

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        d = self.d
        self.f_fecha, lineas, self.tam = ajustar(str(d["fecha"]), F_NUM, 170, self.w - 80, 2, 60)
        self.lineas = lineas
        self.lugar = None
        if d.get("lugar"):
            self.lugar = caja(str(d["lugar"]).upper(), F_TXT_B, 36, color(self.tema, "fondo"),
                              color(self.tema, "acento"), pad=(20, 10), radio=8)

    def dibujar(self, t, dur):
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        y_linea = self.h * 0.66
        # Línea de tiempo que llega desde la derecha, con marcas de años
        q = suave(t / 0.9)
        desplaz = (1 - q) * self.w * 0.5
        d.line((0, y_linea, self.w, y_linea), fill=color(self.tema, "linea"), width=4)
        for k in range(-12, 13):
            x = self.w / 2 + k * 110 + desplaz
            if 0 <= x <= self.w:
                alto = 22 if k % 5 else 40
                d.line((x, y_linea - alto / 2, x, y_linea + alto / 2), fill=color(self.tema, "linea"), width=3)
        p = rebote(min(1, max(0, (t - 0.6) / 0.5)))
        r = 18 * p
        if r > 1:
            if t < 1.55:
                anillo = 18 + 50 * ((t - 0.6) % 1.0)
                a = int(160 * (1 - ((t - 0.6) % 1.0)))
                d.ellipse((self.w / 2 - anillo, y_linea - anillo, self.w / 2 + anillo, y_linea + anillo),
                          outline=color(self.tema, "acento", a), width=4)
            d.ellipse((self.w / 2 - r, y_linea - r, self.w / 2 + r, y_linea + r), fill=color(self.tema, "acento"))
        a = suave((t - 0.3) / 0.5)
        alto_l = self.tam * 1.12
        y0 = y_linea - 70 - alto_l * len(self.lineas)
        for i, l in enumerate(self.lineas):
            d.text(((self.w - self.f_fecha.getlength(l)) / 2, y0 + i * alto_l + 30 * (1 - a)), l,
                   font=self.f_fecha, fill=color(self.tema, "texto", int(255 * a)))
        if self.lugar:
            b = suave((t - 0.8) / 0.4)
            pegar(img, self.lugar, self.w / 2, y_linea + 80, b)
        return img


class Cita(Pieza):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        d = self.d
        vertical = self.h > self.w
        self.f, self.lineas, self.tam = ajustar(f"«{d['texto']}»", F_SERIF, 66 if vertical else 62, self.w - 200,
                                                7 if vertical else 5, 30)
        autor = "— " + str(d.get("autor", ""))
        if d.get("fecha"):
            autor += f", {d['fecha']}"
        self.autor = autor
        self.f_aut = fuente(F_TXT_B, 40)
        self.entrada = 0.4 + 0.18 * len(self.lineas) + 0.6

    def dibujar(self, t, dur):
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        alto_l = self.tam * 1.32
        alto = alto_l * len(self.lineas) + 90
        y0 = (self.h - alto) / 2
        x0 = 140
        q = suave(t / 0.4)
        d.rounded_rectangle((x0 - 50, y0 - 10, x0 - 40, y0 - 10 + (alto - 40) * q), radius=5, fill=color(self.tema, "acento"))
        for i, l in enumerate(self.lineas):
            a = suave((t - 0.2 - 0.18 * i) / 0.4)
            d.text((x0 + 20 * (1 - a), y0 + i * alto_l), l, font=self.f, fill=color(self.tema, "texto", int(255 * a)))
        a = suave((t - 0.3 - 0.18 * len(self.lineas)) / 0.4)
        d.text((x0, y0 + alto_l * len(self.lineas) + 24), self.autor, font=self.f_aut, fill=color(self.tema, "acento2", int(255 * a)))
        return img


class Lista(Pieza):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        d = self.d
        self.puntos = [str(p) for p in d["puntos"]]
        vertical = self.h > self.w
        self.titulo = ajustar(str(d["titulo"]), F_TIT, 56, self.w - 80, 2, 30) if d.get("titulo") else None
        n = len(self.puntos)
        tam = 60 if n <= 3 else (50 if n <= 5 else 40)
        self.f = fuente(F_TXT, tam)
        self.f_num = fuente(F_NUM, int(tam * 0.9))
        self.tam = tam
        self.lineas = [envolver(p, self.f, self.w - 220) for p in self.puntos]

    def _momentos(self, dur):
        n = len(self.puntos)
        tramo = max(0.6, dur * 0.8 / max(1, n))
        return [0.3 + i * tramo for i in range(n)]

    def fin_animacion(self, dur):
        return self._momentos(dur)[-1] + 0.6

    def dibujar(self, t, dur):
        img = self.lienzo()
        d = ImageDraw.Draw(img)
        alto_l = self.tam * 1.3
        total = sum(len(ls) * alto_l + 40 for ls in self.lineas)
        if self.titulo:
            f, lineas, tam = self.titulo
            total += len(lineas) * tam * 1.2 + 50
        y = max(10, (self.h - total) / 2)
        if self.titulo:
            for i, l in enumerate(lineas):
                d.text((60, y + i * tam * 1.2), l, font=f, fill=color(self.tema, "texto"))
            y += len(lineas) * tam * 1.2 + 50
        for i, (ls, m) in enumerate(zip(self.lineas, self._momentos(dur))):
            q = suave((t - m) / 0.45)
            if q > 0:
                a = int(255 * q)
                dx = 40 * (1 - q)
                r = self.tam * 0.75
                cx, cy = 60 + r + dx, y + alto_l / 2
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color(self.tema, "acento", a))
                num = str(i + 1)
                c = self.f_num.getbbox(num)
                d.text((cx - (c[2] - c[0]) / 2 - c[0], cy - (c[3] - c[1]) / 2 - c[1]), num, font=self.f_num,
                       fill=color(self.tema, "fondo", a))
                for j, l in enumerate(ls):
                    d.text((60 + 2 * r + 30 + dx, y + j * alto_l), l, font=self.f, fill=color(self.tema, "texto", a))
            y += len(ls) * alto_l + 40
        return img


# =====================================================================
#  Clip de archivo a pantalla completa
# =====================================================================

class Archivo(Pieza):
    """Clip de Pixabay/Pexels a pantalla completa (oscurecido) con un rótulo. Sin clip: fondo animado."""
    fondo_propio = True
    entrada = 0.8

    def __init__(self, d, w, h, tema, semilla="", pantalla=(1920, 1080), clip=None, dur=6.0):
        super().__init__(d, w, h, tema, semilla)
        self.W, self.H = pantalla
        self.proc, self.ultimo = None, None
        self.base = None
        self.clip = clip
        if clip:
            margen = max(0.0, clip["duracion"] - dur - 0.5)
            ini = self.rnd.uniform(0, margen) if margen > 0 else 0
            filtro = (f"scale={self.W}:{self.H}:force_original_aspect_ratio=increase,crop={self.W}:{self.H},"
                      f"fps={FPS},eq=brightness=-0.10:saturation=0.85:contrast=1.05,format=rgb24")
            cmd = ["ffmpeg", "-loglevel", "error"]
            if clip["duracion"] < dur + 0.5:
                cmd += ["-stream_loop", "-1"]
            cmd += ["-threads", "2", "-ss", f"{ini:.2f}", "-i", clip["ruta"], "-t", f"{dur + 0.5:.2f}", "-vf", filtro,
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        # Velo para que se lea el rótulo
        y = np.linspace(0, 1, self.H)[:, None]
        a = 0.35 + 0.5 * np.clip((y - 0.45) / 0.55, 0, 1)
        alfa = (np.repeat(a, self.W, axis=1) * 255).astype(np.uint8)
        self.velo = Image.new("RGBA", (self.W, self.H), color(tema, "fondo"))
        self.velo.putalpha(Image.fromarray(alfa))
        self.rotulo = None
        if d.get("texto"):
            f, lineas, tam = ajustar(str(d["texto"]), F_TIT, 84, self.w - 80, 3, 36)
            alto_l = int(tam * 1.2)
            capa = Image.new("RGBA", (self.w, alto_l * len(lineas) + 20), (0, 0, 0, 0))
            dd = ImageDraw.Draw(capa)
            for i, l in enumerate(lineas):
                dd.text((40, i * alto_l), l, font=f, fill=color(tema, "texto"), stroke_width=2, stroke_fill=(0, 0, 0, 160))
            self.rotulo = capa
        self.sub = None
        if d.get("sub"):
            self.sub = caja(str(d["sub"]).upper(), F_TXT_B, 32, color(tema, "fondo"), color(tema, "acento"), pad=(18, 8), radio=8)

    def fondo(self, t):
        if self.proc:
            datos = self.proc.stdout.read(self.W * self.H * 3)
            if len(datos) == self.W * self.H * 3:
                self.ultimo = Image.frombytes("RGB", (self.W, self.H), datos).convert("RGBA")
            if self.ultimo is not None:
                img = self.ultimo.copy()
                img.alpha_composite(self.velo)
                return img
        if self.base is None:
            self.base = _fondo_animado(self.W, self.H, self.tema, self.rnd)
        z = 1.0 + 0.04 * t
        w, h = int(self.W / z), int(self.H / z)
        x, y = (self.W - w) // 2, (self.H - h) // 2
        return self.base.crop((x, y, x + w, y + h)).resize((self.W, self.H), Image.BILINEAR)

    def dibujar(self, t, dur):
        img = self.lienzo()
        if self.sub:
            q = suave((t - 0.1) / 0.35)
            pegar(img, self.sub, 40 + 30 * (1 - q), self.h - (self.rotulo.height if self.rotulo else 0) - 90, q, centro=False)
        if self.rotulo:
            q = suave((t - 0.2) / 0.5)
            pegar(img, self.rotulo, 0, self.h - self.rotulo.height - 20 + 30 * (1 - q), q, centro=False)
        return img

    def cuadro(self, t, dur):
        return self.dibujar(t, dur)

    def cerrar(self):
        if self.proc:
            self.proc.stdout.close()
            self.proc.kill()
            self.proc = None


def _fondo_animado(W, H, tema, rnd):
    """Fondo propio cuando no hay clip: degradado con manchas de color difuminadas."""
    img = Image.new("RGBA", (W, H), color(tema, "fondo"))
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    for _ in range(4):
        r = rnd.randint(int(min(W, H) * 0.25), int(min(W, H) * 0.5))
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color(tema, rnd.choice(["acento", "fondo2", "acento2"]), 60))
    img.alpha_composite(capa.filter(ImageFilter.GaussianBlur(120)))
    return img


TIPOS = {"titulo": Titulo, "cifra": Cifra, "comparar": Comparar, "linea": Linea, "barras": Barras,
         "fecha": Fecha, "cita": Cita, "lista": Lista, "archivo": Archivo}


def crear_pieza(d, w, h, tema, semilla, pantalla, clip=None, dur=6.0):
    tipo = d.get("tipo", "titulo")
    if tipo not in TIPOS:
        raise SystemExit(f"::error::Tipo de escena desconocido: «{tipo}». Hay: {', '.join(TIPOS)}")
    if tipo == "archivo":
        return Archivo(d, w, h, tema, semilla, pantalla=pantalla, clip=clip, dur=dur)
    return TIPOS[tipo](d, w, h, tema, semilla)
