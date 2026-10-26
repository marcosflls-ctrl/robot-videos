"""Estilo «lienzo» para los Shorts de Zona Leonida.

En vez de pasar de escena en escena, todo vive en un mismo espacio oscuro con un hilo de luz
vertical. Cada frase coloca algo nuevo en el hilo (una tarjeta, una etiqueta, un titular, dos
tarjetas enfrentadas, una imagen...) y la cámara viaja hasta allí sin cortes: baja, se acerca,
se aleja para enseñar varias cosas a la vez. Cada 1–2 s pasa algo (un destello, una grieta,
un «×3», un candado), y los subtítulos van de 2 en 2 o de 3 en 3 palabras con la clave en color.

Uso:  montar(beats, audio, sr, tiempos_palabras, salida)   (ver demo al final del archivo)
"""
import math
import random
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BS = 2.0  # las piezas se dibujan al doble para que el zoom no las emborrone
FUENTES = Path(__file__).resolve().parent.parent / "fuentes"

# Paleta Zona Leonida: noche de Vice City
FONDO_A = (14, 8, 22)
FONDO_B = (40, 22, 48)
BLANCO = (250, 244, 250)
SUAVE = (190, 176, 196)
ROSA = (255, 92, 170)
CIAN = (90, 220, 255)
AMBAR = (255, 196, 70)
ROJO = (255, 70, 90)
SUBT_Y = 1400
CENTRO_Y = 780  # donde cae el foco de la cámara (por encima de los subtítulos)


@lru_cache(maxsize=256)
def fuente(nombre, tam):
    archivo = {"anton": "Anton.ttf", "num": "Inter-ExtraBold.ttf", "bold": "Inter-Bold.ttf",
               "label": "SpaceGrotesk-Bold.ttf", "txt": "SpaceGrotesk-Medium.ttf"}[nombre]
    return ImageFont.truetype(str(FUENTES / archivo), max(6, int(tam)))


def suave(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def entrada(x):  # salida con un pequeño rebote
    x = min(1.0, max(0.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def texto_espaciado(d, xy, texto, f, fill, espacio=0, anchor="mm"):
    """Texto con separación entre letras (para titulares tipo «HACKERS»)."""
    if not espacio:
        d.text(xy, texto, font=f, fill=fill, anchor=anchor)
        return
    anchos = [f.getlength(c) for c in texto]
    total = sum(anchos) + espacio * (len(texto) - 1)
    x = xy[0] - total / 2 if anchor[0] == "m" else xy[0]
    for c, a in zip(texto, anchos):
        d.text((x, xy[1]), c, font=f, fill=fill, anchor="l" + anchor[1])
        x += a + espacio


# =====================================================================
#  Piezas: cada una sabe dibujarse (a escala BS) en un momento dado
# =====================================================================

def _coeficientes(destino, origen):
    """Coeficientes de Image.PERSPECTIVE que llevan los 4 puntos `destino` a `origen`."""
    A, B = [], []
    for (x, y), (u, v) in zip(destino, origen):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, dtype=float), np.array(B, dtype=float)).tolist()


def perspectiva(im, giro_y=0.0, giro_x=0.0):
    """Gira una imagen en 3D (grados) alrededor de su eje vertical y horizontal, con perspectiva."""
    if abs(giro_y) < 0.3 and abs(giro_x) < 0.3:
        return im, 0, 0
    w, h = im.size
    f = 1.8 * max(w, h)
    ay, ax = math.radians(giro_y), math.radians(giro_x)
    pts = []
    for x, y in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        x1, z1 = x * math.cos(ay), x * math.sin(ay)          # giro vertical
        y2, z2 = y * math.cos(ax) - z1 * math.sin(ax), y * math.sin(ax) + z1 * math.cos(ax)  # giro horizontal
        k = f / (f + z2)
        pts.append((x1 * k, y2 * k))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    ow, oh = max(1, int(max(xs) - x0)), max(1, int(max(ys) - y0))
    destino = [(px - x0, py - y0) for px, py in pts]
    coef = _coeficientes(destino, [(0, 0), (w, 0), (w, h), (0, h)])
    salida = im.transform((ow, oh), Image.PERSPECTIVE, coef, Image.BICUBIC)
    # desplazamiento del centro respecto al original
    return salida, (x0 + ow / 2), (y0 + oh / 2)


class Pieza:
    ancho, alto = 400, 200
    brillo = BLANCO  # color del halo
    dur_entrada = 0.45
    giro_entrada = 0.0   # grados con los que entra girada (0 = sin giro)
    balanceo = 0.0       # grados de vaivén mientras está en pantalla

    def giro(self, t):
        lt = t - self.t0
        gy = self.giro_entrada * (1 - entrada(lt / max(0.3, self.dur_entrada * 1.4)))
        gy += self.balanceo * math.sin(lt * 1.1 + self.x * 0.01)
        gx = 0.4 * self.balanceo * math.sin(lt * 0.8 + 1.3)
        return gy, gx

    def __init__(self, x, y, t0, **kw):
        self.x, self.y, self.t0 = x, y, t0
        self.kw = kw
        self._cache = None
        self.estado = "normal"
        self.t_estado = 1e9

    def animada(self, t):
        return t - self.t0 < self.dur_entrada + 0.1 or 0 <= t - self.t_estado < 1.2

    def sprite(self, t):
        if not self.animada(t) and self._cache is not None:
            return self._cache
        im = Image.new("RGBA", (int(self.ancho * BS), int(self.alto * BS)), (0, 0, 0, 0))
        self.dibujar(ImageDraw.Draw(im), im, t)
        if not self.animada(t):
            self._cache = im
        return im

    def escala_entrada(self, t):
        return 0.86 + 0.14 * entrada((t - self.t0) / self.dur_entrada)

    def opacidad(self, t):
        return suave((t - self.t0) / (self.dur_entrada * 0.6))

    def dibujar(self, d, im, t):
        raise NotImplementedError


class Tarjeta(Pieza):
    """Tarjeta de cristal: etiqueta pequeña, cifra grande, subtítulo, barra y check."""

    def __init__(self, x, y, t0, grande, etiqueta="", sub="", ancho=420, alto=440, barra=True, **kw):
        super().__init__(x, y, t0, **kw)
        self.grande, self.etiqueta, self.sub, self.barra = grande, etiqueta, sub, barra
        self.ancho, self.alto = ancho, alto
        rnd = random.Random(f"{grande}{etiqueta}")
        # Grieta: ramas que salen de un punto (se dibujan poco a poco si se rompe)
        cx, cy = ancho * rnd.uniform(0.35, 0.65), alto * rnd.uniform(0.3, 0.5)
        self.grietas = []
        for _ in range(9):
            ang = rnd.uniform(0, 2 * math.pi)
            pts, px, py = [(cx, cy)], cx, cy
            for _ in range(rnd.randint(4, 8)):
                ang += rnd.uniform(-0.6, 0.6)
                paso = rnd.uniform(14, 34)
                px, py = px + math.cos(ang) * paso, py + math.sin(ang) * paso
                pts.append((px, py))
            self.grietas.append(pts)
        self.centro_grieta = (cx, cy)

    def romper(self, t):
        self.estado, self.t_estado = "rota", t

    def iluminar(self, t, color=ROJO):
        self.estado, self.t_estado, self.color_estado = "roja", t, color

    @property
    def brillo(self):
        return ROJO if self.estado in ("rota", "roja") else (255, 225, 240)

    def dibujar(self, d, im, t):
        s = BS
        lt = t - self.t0
        borde = self.brillo + (int(230 * self.opacidad(t)),)
        rojo = self.estado in ("rota", "roja")
        relleno = (60, 20, 30, 120) if rojo else (255, 255, 255, 16)
        r = 34 * s
        d.rounded_rectangle([2 * s, 2 * s, (self.ancho - 2) * s, (self.alto - 2) * s], r, fill=relleno,
                            outline=borde, width=int(2.4 * s))
        # brillo superior del cristal
        d.rounded_rectangle([10 * s, 10 * s, (self.ancho - 10) * s, (self.alto * 0.45) * s], r * 0.8,
                            fill=(255, 255, 255, 8))
        a = int(255 * self.opacidad(t))
        if self.etiqueta:
            d.text((34 * s, 40 * s), self.etiqueta.upper(), font=fuente("label", 17 * s), fill=SUAVE + (a,), anchor="lm")
            d.ellipse([(self.ancho - 46) * s, 34 * s, (self.ancho - 34) * s, 46 * s], fill=BLANCO + (a,))
        tam = min(150, 0.36 * self.alto, 1.25 * self.ancho / max(2.5, len(self.grande) * 0.62))
        d.text((self.ancho / 2 * s, self.alto * 0.44 * s), self.grande, font=fuente("num", tam * s),
               fill=BLANCO + (a,), anchor="mm")
        if self.sub:
            d.text((self.ancho / 2 * s, self.alto * 0.62 * s), self.sub.upper(), font=fuente("label", 22 * s),
                   fill=BLANCO + (int(a * 0.85),), anchor="mm")
        if self.barra:
            y = self.alto * 0.83
            x0, x1 = 50, self.ancho - 50
            d.rounded_rectangle([x0 * s, (y - 3) * s, x1 * s, (y + 3) * s], 3 * s, fill=(255, 255, 255, 40))
            p = suave((lt - 0.2) / 0.9)
            if p > 0:
                d.rounded_rectangle([x0 * s, (y - 3) * s, (x0 + (x1 - x0) * p) * s, (y + 3) * s], 3 * s,
                                    fill=(ROJO if rojo else BLANCO) + (a,))
            if p >= 1:
                cx, cy = self.ancho / 2, self.alto * 0.72
                d.line([((cx - 9) * s, cy * s), ((cx - 2) * s, (cy + 7) * s), ((cx + 11) * s, (cy - 8) * s)],
                       fill=BLANCO + (a,), width=int(3 * s))
        if self.estado == "rota":
            p = suave((t - self.t_estado) / 0.5)
            for rama in self.grietas:
                n = max(2, int(len(rama) * p))
                d.line([(px * s, py * s) for px, py in rama[:n]], fill=(255, 235, 240, 235), width=int(2 * s))
            if t - self.t_estado < 0.35:  # chispa del impacto
                cx, cy = self.centro_grieta
                rr = (14 + 60 * (t - self.t_estado)) * s
                d.ellipse([cx * s - rr, cy * s - rr, cx * s + rr, cy * s + rr],
                          fill=(255, 120, 140, int(220 * (1 - (t - self.t_estado) / 0.35))))


class Pastilla(Pieza):
    """Etiqueta redondeada: «• 19 NOV», «SE DICE», «RUMOR»..."""
    dur_entrada = 0.3

    def __init__(self, x, y, t0, texto, color=None, punto=True, **kw):
        super().__init__(x, y, t0, **kw)
        self.texto, self.color, self.punto = texto.upper(), color or ROSA, punto
        f = fuente("label", 22)
        self.ancho = int(f.getlength(self.texto) + (64 if punto else 40))
        self.alto = 46
        self.brillo = self.color

    def dibujar(self, d, im, t):
        s, a = BS, int(255 * self.opacidad(t))
        d.rounded_rectangle([1 * s, 1 * s, (self.ancho - 1) * s, (self.alto - 1) * s], 23 * s,
                            fill=(20, 12, 26, int(a * 0.9)), outline=self.color + (a,), width=int(2 * s))
        x = 22
        if self.punto:
            d.ellipse([(x - 5) * s, (self.alto / 2 - 5) * s, (x + 5) * s, (self.alto / 2 + 5) * s], fill=self.color + (a,))
            x += 16
        d.text((x * s, self.alto / 2 * s), self.texto, font=fuente("label", 22 * s), fill=BLANCO + (a,), anchor="lm")


class Titular(Pieza):
    """Palabra grande con letras separadas que se juntan al entrar."""
    dur_entrada = 0.6

    def __init__(self, x, y, t0, texto, color=None, tam=120, **kw):
        super().__init__(x, y, t0, **kw)
        self.texto, self.color, self.tam = texto.upper(), color or BLANCO, tam
        f = fuente("num", tam)
        self.ancho = int(f.getlength(self.texto) + 22 * len(self.texto) + 120)
        self.alto = int(tam * 1.5)
        self.brillo = self.color

    def dibujar(self, d, im, t):
        s, p = BS, suave((t - self.t0) / self.dur_entrada)
        espacio = (10 + 40 * (1 - p)) * s
        texto_espaciado(d, (self.ancho / 2 * s, self.alto / 2 * s), self.texto, fuente("num", self.tam * s),
                        self.color + (int(255 * p),), espacio)


class Multiplicador(Pieza):
    """«×3» que salta junto a una tarjeta."""
    dur_entrada = 0.35

    def __init__(self, x, y, t0, texto="×3", **kw):
        super().__init__(x, y, t0, **kw)
        self.texto = texto
        self.ancho, self.alto = 220, 150
        self.brillo = BLANCO

    def escala_entrada(self, t):
        return 0.4 + 0.6 * entrada((t - self.t0) / self.dur_entrada)

    def dibujar(self, d, im, t):
        s = BS
        d.text((self.ancho / 2 * s, self.alto / 2 * s), self.texto, font=fuente("num", 110 * s),
               fill=BLANCO + (int(255 * self.opacidad(t)),), anchor="mm")


class Candado(Pieza):
    """Candado que se cierra (algo bloqueado, «todavía no»)."""
    dur_entrada = 0.6

    def __init__(self, x, y, t0, color=None, **kw):
        super().__init__(x, y, t0, **kw)
        self.ancho, self.alto = 120, 150
        self.color = color or BLANCO
        self.brillo = self.color

    def dibujar(self, d, im, t):
        s, a = BS, int(255 * self.opacidad(t))
        cierre = suave((t - self.t0 - 0.25) / 0.3)
        sube = (1 - cierre) * 22
        d.arc([28 * s, (14 - sube) * s, 92 * s, (90 - sube) * s], 180, 360, fill=self.color + (a,), width=int(11 * s))
        d.line([(33.5 * s, (52 - sube) * s), (33.5 * s, 72 * s)], fill=self.color + (a,), width=int(11 * s))
        d.line([(86.5 * s, (52 - sube) * s), (86.5 * s, 72 * s)], fill=self.color + (a,), width=int(11 * s))
        d.rounded_rectangle([14 * s, 68 * s, 106 * s, 146 * s], 14 * s, fill=self.color + (a,))
        d.ellipse([52 * s, 94 * s, 68 * s, 110 * s], fill=FONDO_A + (a,))
        d.rectangle([57 * s, 104 * s, 63 * s, 124 * s], fill=FONDO_A + (a,))


class Imagen(Pieza):
    """Imagen en una tarjeta con borde de luz (fotograma del tráiler o ilustración)."""
    dur_entrada = 0.5

    def __init__(self, x, y, t0, imagen=None, ancho=760, alto=430, etiqueta="", **kw):
        super().__init__(x, y, t0, **kw)
        self.ancho, self.alto, self.etiqueta = ancho, alto, etiqueta
        self.foto = imagen if imagen is not None else _postal_vice_city(int(ancho * BS), int(alto * BS))
        self.brillo = (255, 200, 230)

    def dibujar(self, d, im, t):
        s, a = BS, self.opacidad(t)
        foto = self.foto.convert("RGBA").resize((int((self.ancho - 8) * s), int((self.alto - 8) * s)))
        mascara = Image.new("L", foto.size, 0)
        ImageDraw.Draw(mascara).rounded_rectangle([0, 0, foto.size[0], foto.size[1]], 28 * s, fill=int(255 * a))
        im.paste(foto, (int(4 * s), int(4 * s)), mascara)
        d.rounded_rectangle([2 * s, 2 * s, (self.ancho - 2) * s, (self.alto - 2) * s], 30 * s,
                            outline=(255, 230, 245, int(220 * a)), width=int(2.4 * s))
        if self.etiqueta:
            d.text((self.ancho / 2 * s, (self.alto - 34) * s), self.etiqueta.upper(), font=fuente("anton", 40 * s),
                   fill=BLANCO + (int(255 * a),), anchor="mm", stroke_width=int(3 * s), stroke_fill=(0, 0, 0, int(160 * a)))


def _postal_vice_city(w, h):
    """Imagen de relleno sin marcas: atardecer con palmeras (para el prototipo)."""
    y = np.linspace(0, 1, h)[:, None]
    arriba, abajo = np.array([40, 16, 80]), np.array([255, 120, 90])
    cielo = (arriba * (1 - y) + abajo * y)[:, :, None].repeat(1, 2) if False else None
    img = np.zeros((h, w, 3))
    for c in range(3):
        img[:, :, c] = arriba[c] * (1 - y[:, 0])[:, None] + abajo[c] * y[:, 0][:, None]
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.ellipse([w * 0.38, h * 0.42, w * 0.62, h * 0.42 + w * 0.24], fill=(255, 210, 120))
    d.rectangle([0, h * 0.72, w, h], fill=(30, 12, 50))
    for k in range(18):
        x0 = k * w / 18
        alto = h * (0.12 + 0.18 * ((k * 37) % 7) / 7)
        d.rectangle([x0, h * 0.72 - alto, x0 + w / 22, h * 0.72], fill=(26, 10, 44))
    for px, ph in [(0.12, 0.62), (0.86, 0.7)]:
        bx, by = w * px, h * 0.75
        d.line([(bx, by), (bx + w * 0.02, by - h * ph)], fill=(14, 6, 24), width=int(w * 0.012))
        tx, ty = bx + w * 0.02, by - h * ph
        for ang in range(0, 360, 40):
            d.line([(tx, ty), (tx + math.cos(math.radians(ang)) * w * 0.09, ty + math.sin(math.radians(ang)) * h * 0.12 + h * 0.04)],
                   fill=(14, 6, 24), width=int(w * 0.008))
    return im


class Conector(Pieza):
    """Curva que une el hilo con dos tarjetas enfrentadas (bifurcación)."""
    dur_entrada = 0.5

    def __init__(self, x, y, t0, separacion=480, alto=200, **kw):
        super().__init__(x, y, t0, **kw)
        self.sep, self.ancho, self.alto = separacion, separacion + 40, alto
        self.brillo = ROSA

    def dibujar(self, d, im, t):
        s, p = BS, suave((t - self.t0) / self.dur_entrada)
        cx = self.ancho / 2
        for lado in (-1, 1):
            pts = []
            for k in range(41):
                u = k / 40 * p
                x = cx + lado * (self.sep / 2) * (1 - (1 - u) ** 2)
                y = self.alto - self.alto * u ** 1.2
                pts.append((x * s, y * s))
            d.line(pts, fill=(255, 210, 235, 220), width=int(2.4 * s))


class Recorte(Pieza):
    """Objeto real recortado (sin fondo), con sombra; opcionalmente con escudo de energía:
    óvalo de luz, rayos que chisporrotean y bolas de luz dando vueltas."""
    dur_entrada = 0.6
    giro_entrada = 0.0
    balanceo = 3.0

    def __init__(self, x, y, t0, imagen, alto=700, escudo=False, t_escudo=None, color=None, **kw):
        super().__init__(x, y, t0, **kw)
        im = imagen.convert("RGBA")
        caja = im.getbbox()
        if caja:
            im = im.crop(caja)
        esc = alto / im.height
        self.foto = im.resize((max(1, int(im.width * esc * BS)), max(1, int(alto * BS))), Image.LANCZOS)
        self.escudo = escudo
        self.t_escudo = t0 + 0.8 if t_escudo is None else t_escudo
        self.color = color or (255, 150, 220)
        self.ancho = int(im.width * esc + (380 if escudo else 80))
        self.alto = int(alto + (260 if escudo else 80))
        self.brillo = self.color

    def animada(self, t):
        return True if self.escudo else super().animada(t)

    def escala_entrada(self, t):
        return 0.8 + 0.2 * entrada((t - self.t0) / self.dur_entrada)

    def dibujar(self, d, im, t):
        s = BS
        a = self.opacidad(t)
        cx, cy = self.ancho / 2 * s, self.alto / 2 * s
        # sombra suave debajo
        sombra = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sombra).ellipse([cx - self.foto.width * 0.45, cy + self.foto.height * 0.44,
                                        cx + self.foto.width * 0.45, cy + self.foto.height * 0.52],
                                       fill=(0, 0, 0, int(150 * a)))
        im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(14 * s)))
        foto = self.foto
        if a < 1:
            foto = foto.copy()
            foto.putalpha(foto.getchannel("A").point(lambda v: int(v * a)))
        im.alpha_composite(foto, (int(cx - foto.width / 2), int(cy - foto.height / 2)))
        if self.escudo and t >= self.t_escudo:
            self._escudo(im, t - self.t_escudo, cx, cy)

    def _escudo(self, im, lt, cx, cy):
        s = BS
        p = suave(lt / 0.5)
        rx, ry = (self.ancho / 2 - 40) * s * (0.85 + 0.15 * p), (self.alto / 2 - 40) * s * (0.85 + 0.15 * p)
        capa = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=self.color + (int(26 * p),),
                  outline=self.color + (int(170 * p),), width=int(2 * s))
        # rayos: cambian cada 3 fotogramas
        rnd = random.Random(int(lt * 10))
        for _ in range(int(8 * p)):
            ang = rnd.uniform(0, 2 * math.pi)
            x, y = cx + math.cos(ang) * rx, cy + math.sin(ang) * ry
            pts = [(x, y)]
            dir_ = ang + math.pi + rnd.uniform(-0.6, 0.6)
            for _ in range(rnd.randint(4, 7)):
                paso = rnd.uniform(12, 30) * s
                dir_ += rnd.uniform(-0.9, 0.9)
                x, y = x + math.cos(dir_) * paso, y + math.sin(dir_) * paso
                pts.append((x, y))
            d.line(pts, fill=(255, 210, 240, int(220 * p)), width=int(1.6 * s))
        # bolas de luz que dan vueltas
        for k in range(3):
            ang = lt * (1.2 + 0.3 * k) + k * 2.1
            x, y = cx + math.cos(ang) * rx, cy + math.sin(ang) * ry
            for rr, al in [(26, 40), (14, 110), (6, 255)]:
                d.ellipse([x - rr * s, y - rr * s, x + rr * s, y + rr * s], fill=(255, 235, 250, int(al * p)))
        im.alpha_composite(capa.filter(ImageFilter.GaussianBlur(1.2 * s)))
        im.alpha_composite(capa)


class Portada(Imagen):
    """Imagen (portada, fotograma del tráiler) que entra girando en 3D, con un reflejo que la cruza."""
    dur_entrada = 0.7
    giro_entrada = 75.0
    balanceo = 5.0

    def animada(self, t):
        return True

    def dibujar(self, d, im, t):
        super().dibujar(d, im, t)
        lt = t - self.t0
        fase = (lt * 0.45) % 1.6  # un reflejo cada ~3,5 s
        if fase < 1:
            s = BS
            capa = Image.new("RGBA", im.size, (0, 0, 0, 0))
            dd = ImageDraw.Draw(capa)
            x = (-0.3 + 1.6 * fase) * self.ancho * s
            dd.polygon([(x, 0), (x + 70 * s, 0), (x - 120 * s, self.alto * s), (x - 190 * s, self.alto * s)],
                       fill=(255, 255, 255, 46))
            mascara = Image.new("L", im.size, 0)
            ImageDraw.Draw(mascara).rounded_rectangle([4 * s, 4 * s, (self.ancho - 4) * s, (self.alto - 4) * s], 28 * s, fill=255)
            im.paste(Image.alpha_composite(im, capa), (0, 0), mascara)


class Lluvia(Pieza):
    """Copias de una imagen que salen volando y girando alrededor de un punto (p. ej. «piratería»)."""
    dur_entrada = 1.2

    def __init__(self, x, y, t0, imagen, n=7, tam=(280, 350), radio=520, **kw):
        super().__init__(x, y, t0, **kw)
        self.ancho, self.alto = radio * 2 + 400, radio * 2 + 400
        rnd = random.Random(n)
        foto = imagen.convert("RGBA").resize((int(tam[0] * BS * 0.5), int(tam[1] * BS * 0.5)))
        m = Image.new("L", foto.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, foto.width, foto.height], 16, fill=255)
        foto.putalpha(m)
        self.foto = foto
        self.cartas = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.55, 1.0) * radio, rnd.uniform(-1, 1),
                        rnd.uniform(0, 0.4)) for _ in range(n)]

    def animada(self, t):
        return True

    def escala_entrada(self, t):
        return 1.0

    def dibujar(self, d, im, t):
        s = BS
        lt = t - self.t0
        cx, cy = self.ancho / 2 * s, self.alto / 2 * s
        for ang, r, giro, retraso in self.cartas:
            p = entrada((lt - retraso) / 0.9)
            if p <= 0:
                continue
            a = ang + lt * 0.15 * giro
            x, y = cx + math.cos(a) * r * s * p, cy + math.sin(a) * r * s * p * 0.8
            carta, _, _ = perspectiva(self.foto, 50 * math.sin(lt * 1.5 * giro + ang), 25 * giro)
            carta = carta.copy()
            carta.putalpha(carta.getchannel("A").point(lambda v: int(v * min(1, p) * 0.8)))
            im.alpha_composite(carta, (int(x - carta.width / 2), int(y - carta.height / 2)))


class Titular3D(Pieza):
    """Palabra grande cuyas letras entran una a una girando sobre sí mismas."""
    dur_entrada = 1.0

    def __init__(self, x, y, t0, texto, color=None, tam=120, **kw):
        super().__init__(x, y, t0, **kw)
        self.texto, self.color, self.tam = texto.upper(), color or BLANCO, tam
        f = fuente("num", tam)
        self.esp = 16
        self.ancho = int(f.getlength(self.texto) + self.esp * len(self.texto) + 80)
        self.alto = int(tam * 1.6)

    def escala_entrada(self, t):
        return 1.0

    def dibujar(self, d, im, t):
        s = BS
        f = fuente("num", self.tam * s)
        anchos = [f.getlength(c) for c in self.texto]
        total = sum(anchos) + self.esp * s * (len(self.texto) - 1)
        x = im.width / 2 - total / 2
        for k, (c, a) in enumerate(zip(self.texto, anchos)):
            p = suave((t - self.t0 - k * 0.06) / 0.45)
            if p > 0 and c.strip():
                letra = Image.new("RGBA", (int(a + 20 * s), int(self.tam * 1.5 * s)), (0, 0, 0, 0))
                ImageDraw.Draw(letra).text((letra.width / 2, letra.height / 2), c, font=f,
                                           fill=self.color + (int(255 * p),), anchor="mm")
                girada, dx, dy = perspectiva(letra, 90 * (1 - p), 0)
                im.alpha_composite(girada, (int(x + a / 2 - girada.width / 2), int(im.height / 2 - girada.height / 2)))
            x += a + self.esp * s


def _vineta():
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.6)) ** 2)
    a = np.clip((r - 0.65) * 1.6, 0, 1) * 200
    im = np.zeros((H, W, 4), dtype=np.uint8)
    im[:, :, 3] = a.astype(np.uint8)
    return Image.fromarray(im, "RGBA")


def flash(te):
    """Efecto para «efectos»: fogonazo blanco (para cambiar de tema)."""
    def fn(_):
        pass
    fn.flash = True
    return (te, fn)


def preparar_fondo(foto, oscurecer=0.55, desenfoque=5):
    """Foto de fondo: recortada a vertical (con margen para moverse), desenfocada y oscurecida."""
    fw, fh = int(W * 1.15), int(H * 1.15)
    im = foto.convert("RGB")
    esc = max(fw / im.width, fh / im.height)
    im = im.resize((int(im.width * esc), int(im.height * esc)), Image.LANCZOS)
    x0, y0 = (im.width - fw) // 2, (im.height - fh) // 2
    im = im.crop((x0, y0, x0 + fw, y0 + fh)).filter(ImageFilter.GaussianBlur(desenfoque))
    arr = np.array(im).astype(np.float32) * (1 - oscurecer)
    tinte = np.array([30, 10, 45], dtype=np.float32)
    arr = arr * 0.85 + tinte * 0.15
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


# =====================================================================
#  Fondo, hilo, partículas, subtítulos
# =====================================================================

def fondo():
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / H) ** 2)
    m = np.clip(1 - r * 1.6, 0, 1)[:, :, None]
    img = np.array(FONDO_A) * (1 - m) + np.array(FONDO_B) * m
    return Image.fromarray(img.astype(np.uint8)).convert("RGBA")


class Polvo:
    def __init__(self, n=70, semilla=3):
        rnd = np.random.default_rng(semilla)
        self.p = rnd.uniform([0, 0, 0.3, 1], [W, H, 1.0, 3.2], size=(n, 4))
        self.v = rnd.uniform(-6, 6, size=(n, 2))

    def dibujar(self, capa, t, cam_dy):
        d = ImageDraw.Draw(capa)
        for (x, y, luz, r), (vx, vy) in zip(self.p, self.v):
            px = (x + vx * t) % W
            py = (y + vy * t - cam_dy * 0.15 * r) % H
            a = int(90 * luz * (0.6 + 0.4 * math.sin(t * 1.3 + x)))
            d.ellipse([px - r, py - r, px + r, py + r], fill=(255, 220, 240, a))


def trozos_de_subtitulo(palabras, claves=()):
    """Agrupa las palabras [(texto, ini, fin)] de 2 en 2 o de 3 en 3, cortando en la puntuación
    y sin separar dos palabras clave seguidas («VICE CITY»)."""
    trozos, actual = [], []
    for i, w in enumerate(palabras):
        actual.append(w)
        fin_frase = w[0][-1:] in ".,:;?!"
        sigue_clave = (i + 1 < len(palabras) and _norm(w[0]) in claves and _norm(palabras[i + 1][0]) in claves
                       and not fin_frase)
        if sigue_clave and len(actual) < 4:
            continue
        if len(actual) >= 3 or (len(actual) >= 2 and fin_frase) or (fin_frase and len(w[0]) > 6):
            trozos.append(actual)
            actual = []
    if actual:
        trozos.append(actual)
    return trozos


def dibujar_subtitulo(capa, trozo, t, claves):
    """Subtítulo de 2–3 palabras: entra girando (como una tarjeta que se voltea), la palabra clave
    en ámbar y la que está sonando un poco más grande."""
    if not trozo:
        return
    f = fuente("anton", 76)
    palabras = [w[0].strip(".,:;") for w in trozo]
    espacio = f.getlength(" ") + 12
    anchos = [f.getlength(p.upper()) for p in palabras]
    total = sum(anchos) + espacio * (len(palabras) - 1)
    lienzo = Image.new("RGBA", (int(total + 80), 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(lienzo)
    x = 40
    for p, a, w in zip(palabras, anchos, trozo):
        clave = _norm(p) in claves
        sonando = w[1] - 0.05 <= t <= w[2] + 0.05
        color = AMBAR if clave else BLANCO
        tam = 81 if sonando else 76
        fw = fuente("anton", tam)
        d.text((x + a / 2, 75), p.upper(), font=fw, fill=color + (255,), anchor="mm",
               stroke_width=6, stroke_fill=(10, 4, 14, 220))
        x += a + espacio
    lt = t - trozo[0][1] + 0.05
    p = suave(lt / 0.2)
    girado, dx, dy = perspectiva(lienzo, 0, -80 * (1 - p))
    if p < 1:
        girado = girado.copy()
        girado.putalpha(girado.getchannel("A").point(lambda v: int(v * p)))
    capa.alpha_composite(girado, (int(W / 2 + dx - girado.width / 2), int(SUBT_Y + dy - girado.height / 2)))


def _norm(p):
    import unicodedata
    p = unicodedata.normalize("NFD", p.lower())
    return "".join(c for c in p if c.isalnum() and unicodedata.category(c) != "Mn")


# =====================================================================
#  Montaje
# =====================================================================

def montar(beats, audio, sr, palabras, salida, claves=(), cierre=None):
    """beats: [{"ini": s, "piezas": [Pieza...], "foco": (x, y, zoom), "efectos": [(t, fn)]}]
    palabras: [(texto, ini, fin)] de toda la locución. claves: palabras que van en color."""
    duracion = len(audio) / sr
    claves = {_norm(c) for c in claves}
    piezas = [p for b in beats for p in b["piezas"]]
    efectos = sorted([e for b in beats for e in b.get("efectos", [])], key=lambda e: e[0])
    trozos = trozos_de_subtitulo(palabras, claves)
    base = fondo()
    polvo = Polvo()

    # Cámara: cada beat tiene un foco; se viaja hasta él con suavidad y luego deriva un poco
    focos = [(b["ini"], b["foco"]) for b in beats]
    fondos = [(b["ini"], b["fondo"]) for b in beats if "fondo" in b]
    vineta = _vineta()

    def camara(t):
        k = max(i for i, (t0, _) in enumerate(focos) if t0 <= t or i == 0)
        t0, (x1, y1, z1) = focos[k]
        x0, y0, z0 = focos[k - 1][1] if k > 0 else (x1, y1 - 300, z1 * 0.9)
        p = suave((t - t0) / 0.75)
        deriva = 1 + 0.02 * min(1.0, max(0.0, t - t0) / 3)
        return x0 + (x1 - x0) * p, y0 + (y1 - y0) * p, (z0 + (z1 - z0) * p) * deriva

    wav = Path(salida).with_suffix(".tmp.wav")
    import soundfile as sf
    sf.write(wav, audio, sr)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(salida)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(math.ceil(duracion * FPS))
    hilo_max = max(p.y + p.alto / 2 for p in piezas) + 600
    for i in range(n):
        t = i / FPS
        for te, fn in efectos:
            if te <= t and not getattr(fn, "_hecho", False):
                fn(te)
                fn._hecho = True
        cx, cy, z = camara(t)
        sacudida = 0.0
        for te, fn in efectos:
            if 0 <= t - te < 0.25 and getattr(fn, "golpe", False):
                sacudida = 10 * (1 - (t - te) / 0.25) * math.sin((t - te) * 90)

        def pantalla(x, y):
            return (x - cx) * z + W / 2 + sacudida, (y - cy) * z + CENTRO_Y

        frame = base.copy()
        # Fondo real (fotograma del tráiler...) del beat actual, con fundido y un poco de paralaje
        for k, (tb, fb) in enumerate(fondos):
            if fb is None or tb > t:
                continue
            fin = fondos[k + 1][0] if k + 1 < len(fondos) else 1e9
            if t > fin + 0.5:
                continue
            alfa = suave((t - tb) / 0.5) * (1 - suave((t - fin) / 0.5))
            ox = int((fb.width - W) / 2 + 30 * math.sin(t * 0.3))
            oy = int((fb.height - H) / 2 - 60 * suave((t - tb) / 6))
            trozo = fb.crop((ox, oy, ox + W, oy + H))
            if alfa < 1:
                trozo = trozo.copy()
                trozo.putalpha(int(255 * alfa))
            frame.alpha_composite(trozo)
        polvo.dibujar(frame, t, cy)
        capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        # Hilo de luz: crece hasta la última pieza visible
        visibles = [p for p in piezas if p.t0 <= t]
        y_fin = max([p.y for p in visibles] + [cy]) + 260
        sx, sy0 = pantalla(540, -2000)
        _, sy1 = pantalla(540, min(hilo_max, y_fin))
        d.line([(sx, sy0), (sx, sy1)], fill=(255, 225, 240, 150), width=max(2, int(2.2 * z)))
        # Piezas
        for p in visibles:
            sp = p.sprite(t)
            e = p.escala_entrada(t) * z / BS
            tw, th = max(1, int(sp.width * e)), max(1, int(sp.height * e))
            px, py = pantalla(p.x, p.y)
            if px + tw / 2 < -50 or px - tw / 2 > W + 50 or py + th / 2 < -50 or py - th / 2 > H + 50:
                continue
            im_p = sp.resize((tw, th), Image.LANCZOS)
            gy, gx = p.giro(t)
            im_p, dx, dy = perspectiva(im_p, gy, gx)
            capa.alpha_composite(im_p, (int(px + dx - im_p.width / 2), int(py + dy - im_p.height / 2)))
        # Halo: copia borrosa de las piezas (a un cuarto de tamaño), sumada en tono rosado
        peq = capa.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(7))
        r, g, bb, al = peq.split()
        halo = Image.merge("RGB", [ImageChops.multiply(c, al).point(lambda v, k=k: int(v * k))
                                   for c, k in zip((r, g, bb), (0.9, 0.55, 0.8))]).resize((W, H), Image.BILINEAR)
        frame = ImageChops.add(frame.convert("RGB"), halo).convert("RGBA")
        frame.alpha_composite(capa)
        frame.alpha_composite(vineta)
        # Destello de impacto / fogonazo blanco de transición
        for te, fn in efectos:
            if 0 <= t - te < 0.18 and getattr(fn, "golpe", False):
                frame.alpha_composite(Image.new("RGBA", (W, H), (255, 220, 235, int(70 * (1 - (t - te) / 0.18)))))
            if 0 <= t - te < 0.3 and getattr(fn, "flash", False):
                frame.alpha_composite(Image.new("RGBA", (W, H), (255, 252, 245, int(235 * (1 - (t - te) / 0.3) ** 1.5))))
        # Subtítulo
        actual = next((tr for tr in trozos if tr[0][1] - 0.05 <= t <= tr[-1][2] + 0.15), None)
        if cierre and t >= cierre["ini"]:
            actual = None
            cierre["dibujar"](frame, t - cierre["ini"])
        dibujar_subtitulo(frame, actual, t, claves)
        # Viñeta
        ff.stdin.write(np.array(frame.convert("RGB")).tobytes())
    ff.stdin.close()
    ff.wait()
    wav.unlink(missing_ok=True)


def cierre_comentarios(pregunta, comentario, marca="Zona Leonida"):
    """Pantalla final: pregunta grande y un comentario del canal invitando a responder."""
    f_p, f_c, f_m = fuente("anton", 92), fuente("bold", 34), fuente("label", 26)

    def dibujar(frame, lt):
        a = suave(lt / 0.4)
        velo = Image.new("RGBA", (W, H), (20, 8, 26, int(200 * a)))
        frame.alpha_composite(velo)
        d = ImageDraw.Draw(frame)
        y = 760 - 30 * (1 - a)
        d.text((W / 2, y), pregunta, font=f_p, fill=BLANCO + (int(255 * a),), anchor="mm",
               stroke_width=5, stroke_fill=(10, 4, 14, int(200 * a)))
        b = suave((lt - 0.5) / 0.4)
        if b > 0:
            x0, y0, x1, y1 = 110, 960 + 40 * (1 - b), W - 110, 1180 + 40 * (1 - b)
            d.rounded_rectangle([x0, y0, x1, y1], 26, fill=(32, 20, 40, int(235 * b)), outline=ROSA + (int(200 * b),), width=2)
            d.ellipse([x0 + 30, y0 + 30, x0 + 90, y0 + 90], fill=ROSA + (int(255 * b),))
            d.text((x0 + 60, y0 + 60), "ZL", font=fuente("anton", 30), fill=BLANCO + (int(255 * b),), anchor="mm")
            d.text((x0 + 110, y0 + 46), marca, font=f_m, fill=AMBAR + (int(255 * b),), anchor="lm")
            d.text((x0 + 110, y0 + 92), comentario, font=f_c, fill=BLANCO + (int(255 * b),), anchor="lm")
            d.text((x0 + 110, y0 + 160), "Responder", font=f_m, fill=SUAVE + (int(255 * b),), anchor="lm")
            d.rounded_rectangle([x1 - 230, y0 + 140, x1 - 30, y0 + 186], 23, fill=ROJO + (int(255 * b),))
            d.text((x1 - 130, y0 + 163), "COMENTAR", font=f_m, fill=BLANCO + (int(255 * b),), anchor="mm")

    return dibujar
