"""Montaje por escenas: cada frase es una escena distinta, con cortes rápidos.

Qué hace en cada vídeo:
  - Gancho: la primera cifra o titular entra a pantalla completa con un golpe de sonido.
  - Una escena por frase, y un corte extra en cada coma: el fondo cambia cada 2–3 s.
  - Fondo: clip de Pexels (si hay clave) o fondo animado propio.
  - Transiciones rápidas (barrido, zoom, destello) con un «whoosh».
  - Subtítulos palabra a palabra, con la palabra que suena resaltada.
  - Música de fondo suave generada por código, que baja cuando habla la voz.

    montar_escenas(frases, audios, sr, escenas, estilo, salida, trozos_voz, semilla)

escenas: una por frase -> {"visual": {...}, "buscar": "consulta para Pexels"}
Visuales: cifra, titular, grafico, nada, cierre (ver _dibujar_visual).
"""
import math
import random
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import sonido
from pexels import buscar_clip
from video import ANCHO, ALTO, FPS, _brillo, _degradado, _pegar, _rebote, _salida_suave, _texto

FUENTES = Path(__file__).resolve().parent.parent / "fuentes"
F = {
    "anton": str(FUENTES / "Anton.ttf"),
    "inter": str(FUENTES / "Inter-ExtraBold.ttf"),
    "serif": str(FUENTES / "IBMPlexSerif-SemiBold.ttf"),
    "sans_b": str(FUENTES / "IBMPlexSans-Bold.ttf"),
    "sans_s": str(FUENTES / "IBMPlexSans-SemiBold.ttf"),
}

INICIO = 0.15        # la voz empieza casi de inmediato (gancho)
PAUSA = 0.22         # entre frases
COLA = 1.6           # pantalla de cierre
MAX_DURACION = 0  # 0 = nunca acelerar la voz (acelerarla la hacía sonar robótica)
TRANSICION = 0.22    # duración de cada transición (s)
CORTE_MIN = 1.3      # no cortar el fondo si quedan menos de estos segundos

ESTILO_GTA = {
    "nombre": "gta", "marca": "ZONA LEONIDA", "web": "zonaleonida.com",
    "imagenes": next((str(c) for c in [Path(__file__).resolve().parent.parent / "privado" / "imagenes_gta",
                                         Path(__file__).resolve().parent.parent / "imagenes_gta"] if c.is_dir()), ""),
    "credito": "Imagen: Rockstar Games",
    "grande": F["anton"], "titular": F["anton"], "subtitulo": F["inter"], "mayusculas": True,
    "acento": (255, 214, 92), "acento2": (255, 70, 170), "tinte": (60, 10, 70),
    "cielos": [
        [(18, 6, 38), (74, 12, 92), (214, 38, 120), (255, 132, 64)],
        [(6, 10, 40), (20, 40, 110), (0, 160, 190), (120, 240, 220)],
        [(25, 4, 30), (120, 10, 70), (255, 60, 110), (255, 190, 90)],
    ],
}
ESTILO_AFDM = {
    "nombre": "datos", "marca": "Al Final de Mes", "web": "alfinaldemes.com",
    "grande": F["sans_b"], "titular": F["serif"], "subtitulo": F["sans_b"], "mayusculas": False,
    "acento": (240, 178, 60), "acento2": (11, 93, 75), "tinte": (8, 68, 54),
    "fondos": [[(8, 68, 54), (11, 93, 75)], [(28, 32, 36), (8, 68, 54)], [(11, 93, 75), (6, 40, 32)]],
}
ESTILO_DEC = {
    "nombre": "datos", "marca": "Dinero en Claro", "web": "dineroenclaro.com",
    "grande": F["sans_b"], "titular": F["serif"], "subtitulo": F["sans_b"], "mayusculas": False,
    "acento": (240, 178, 60), "acento2": (31, 78, 121), "tinte": (22, 58, 92),
    "fondos": [[(22, 58, 92), (31, 78, 121)], [(28, 32, 36), (22, 58, 92)], [(31, 78, 121), (12, 30, 50)]],
}


# =====================================================================
#  Audio y tiempos
# =====================================================================

def _linea_de_tiempo(frases, audios, sr, trozos_voz, carpeta):
    """Une la voz y devuelve: wav de la voz, tiempos de frases, palabras con su tiempo, duración."""
    pausa = np.zeros(int(PAUSA * sr), dtype=np.float32)
    partes = [np.zeros(int(INICIO * sr), dtype=np.float32)]
    t = INICIO
    tiempos_frase, piezas = [], []
    for i, (frase, a) in enumerate(zip(frases, audios)):
        dur = len(a) / sr
        tiempos_frase.append((t, t + dur))
        trozos = (trozos_voz or [None] * len(frases))[i] or [(frase, 0.0, dur)]
        for txt, ini, fin in trozos:
            piezas.append((txt, t + ini, t + fin))
        partes += [a, pausa]
        t += dur + PAUSA
    voz = np.concatenate(partes)
    total = len(voz) / sr
    factor = min(1.15, max(1.0, total / (MAX_DURACION - COLA))) if MAX_DURACION else 1.0
    if factor > 1.0:
        bruto, rapido = carpeta / "voz_bruta.wav", carpeta / "voz_rapida.wav"
        sf.write(bruto, voz, sr)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(bruto), "-af", f"atempo={factor:.4f}",
                        "-ar", str(sr), "-ac", "1", str(rapido)], check=True)
        voz, _ = sf.read(rapido, dtype="float32")
        print(f"Voz acelerada x{factor:.2f} para no pasar de {MAX_DURACION:.0f} s")
    tiempos_frase = [(a / factor, b / factor) for a, b in tiempos_frase]
    piezas = [(txt, a / factor, b / factor) for txt, a, b in piezas]

    # Palabras con su tiempo, repartiendo cada trozo por letras
    palabras = []
    for txt, a, b in piezas:
        ps = _palabras(txt)
        letras = sum(len(p) + 1 for p in ps) or 1
        x = a
        for p in ps:
            d = (b - a) * (len(p) + 1) / letras
            palabras.append((p, x, x + d))
            x += d
    duracion = len(voz) / sr + COLA
    return voz, tiempos_frase, piezas, palabras, duracion


def _palabras(texto):
    """Separa en palabras sin despegar % € $ de su cifra."""
    t = texto.replace(" %", "\x00%").replace(" €", "\x00€").replace(" $", "\x00$")
    return [p.replace("\x00", " ") for p in t.split(" ") if p]


# =====================================================================
#  Fondos
# =====================================================================

class Fondo:
    """Fondo de un tramo: clip de Pexels (decodificado con ffmpeg) o animación propia."""

    def __init__(self, clip, dur, estilo, variante, semilla):
        self.estilo, self.variante, self.proc, self.ultimo = estilo, variante, None, None
        self.rnd = random.Random(semilla)
        if clip:
            margen = max(0.0, clip["duracion"] - dur - 0.5)
            ini = self.rnd.uniform(0, margen) if margen > 0 else 0
            paneo = self.rnd.choice(["sin(t*0.5)", "-sin(t*0.5)", "(t/8)", "-(t/8)"])
            filtro = (f"scale=1240:2204:force_original_aspect_ratio=increase,crop=1240:2204,"
                      f"crop=1080:1920:x='(in_w-out_w)/2*(1+0.9*{paneo})':y='(in_h-out_h)/2',"
                      f"fps={FPS},eq=brightness=-0.07:saturation=1.12:contrast=1.05,format=rgb24")
            cmd = ["ffmpeg", "-loglevel", "error"]
            if clip["duracion"] < dur + 0.5:
                cmd += ["-stream_loop", "-1"]
            cmd += ["-threads", "2", "-ss", f"{ini:.2f}", "-i", clip["ruta"], "-t", f"{dur + 0.5:.2f}", "-vf", filtro,
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        else:
            self.base = self._base_propia()

    def _base_propia(self):
        if self.estilo["nombre"] == "gta":
            cielo = self.estilo["cielos"][self.variante % len(self.estilo["cielos"])]
            img = Image.fromarray(_degradado(ALTO, cielo).astype(np.uint8)).convert("RGBA")
            d = ImageDraw.Draw(img)
            r = 260 + 40 * (self.variante % 3)
            cx = ANCHO // 2 + (-200, 0, 200)[self.variante % 3]
            cy = int(ALTO * 0.62)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 214, 92, 255))
            for k in range(6):
                y = cy + 20 + k * 36
                d.rectangle((cx - r, y, cx + r, y + 5 + 3 * k), fill=cielo[2] + (255,))
            img = img.filter(ImageFilter.GaussianBlur(1))
            return img
        c1, c2 = self.estilo["fondos"][self.variante % len(self.estilo["fondos"])]
        img = Image.fromarray(_degradado(ALTO, [c1, c2]).astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(img)
        for k in range(-10, 30):  # líneas diagonales muy suaves
            x = k * 90
            d.line((x, 0, x + 900, ALTO), fill=(255, 255, 255, 14), width=2)
        return img

    def cuadro(self, t):
        if self.proc:
            datos = self.proc.stdout.read(ANCHO * ALTO * 3)
            if len(datos) == ANCHO * ALTO * 3:
                self.ultimo = Image.frombytes("RGB", (ANCHO, ALTO), datos).convert("RGBA")
            if self.ultimo is not None:
                return self.ultimo.copy()
            self.base = self._base_propia()
            self.proc = None
        # Fondo propio con zoom lento (Ken Burns)
        z = 1.0 + 0.06 * t
        w, h = int(ANCHO / z), int(ALTO / z)
        x, y = (ANCHO - w) // 2, (ALTO - h) // 2
        img = self.base.crop((x, y, x + w, y + h)).resize((ANCHO, ALTO), Image.BILINEAR)
        if self.estilo["nombre"] == "gta":
            d = ImageDraw.Draw(img)
            horizonte = int(ALTO * 0.70)
            d.rectangle((0, horizonte, ANCHO, ALTO), fill=(14, 4, 30, 255))
            for i in range(-12, 13):
                d.line((ANCHO / 2 + i * 60, horizonte, ANCHO / 2 + i * 380, ALTO), fill=(255, 70, 170, 150), width=3)
            avance = (t * 0.6) % 1.0
            for k in range(14):
                zz = (k + avance) / 14
                yy = horizonte + (ALTO - horizonte) * zz ** 2.2
                d.line((0, yy, ANCHO, yy), fill=(255, 70, 170, int(60 + 140 * zz)), width=2 + int(3 * zz))
        return img

    def cerrar(self):
        if self.proc:
            self.proc.stdout.close()
            self.proc.kill()


def _capa_legibilidad(estilo):
    """Oscurece arriba y abajo, y tiñe un poco con el color de la marca, para que se lea todo."""
    a = np.zeros((ALTO, 1), dtype=np.float32)
    y = np.arange(ALTO) / ALTO
    a[:, 0] = 0.28 + 0.45 * np.clip((0.22 - y) / 0.22, 0, 1) + 0.55 * np.clip((y - 0.62) / 0.38, 0, 1)
    alfa = (np.repeat(a, ANCHO, axis=1) * 255).astype(np.uint8)
    capa = Image.new("RGBA", (ANCHO, ALTO), estilo["tinte"] + (0,))
    capa.putalpha(Image.fromarray(alfa))
    return capa


# =====================================================================
#  Visuales de cada escena
# =====================================================================

def _caja_texto(texto, fuente, tam, color, fondo=None, max_ancho=ANCHO - 120, pad=(34, 16)):
    f = ImageFont.truetype(fuente, tam)
    while f.getlength(texto) > max_ancho - 2 * pad[0] and tam > 30:
        tam -= 4
        f = ImageFont.truetype(fuente, tam)
    c = f.getbbox(texto)
    w, h = c[2] - c[0] + 2 * pad[0], c[3] - c[1] + 2 * pad[1]
    capa = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    if fondo:
        sombra = Image.new("RGBA", capa.size, (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rounded_rectangle((26, 30, 20 + w, 24 + h), radius=18, fill=(0, 0, 0, 120))
        capa = Image.alpha_composite(capa, sombra.filter(ImageFilter.GaussianBlur(8)))
        d = ImageDraw.Draw(capa)
        d.rounded_rectangle((20, 20, 20 + w, 20 + h), radius=18, fill=fondo + (255,))
    d.text((20 + pad[0] - c[0], 20 + pad[1] - c[1]), texto, font=f, fill=color + (255,),
           stroke_width=0 if fondo else 5, stroke_fill=(0, 0, 0, 255))
    return capa


class Visuales:
    def __init__(self, estilo):
        self.e = estilo
        self.cache = {}

    def _c(self, clave, fabrica):
        if clave not in self.cache:
            self.cache[clave] = fabrica()
        return self.cache[clave]

    def dibujar(self, lienzo, v, t, dur, cy=760, escala=1.0):
        tipo = v.get("tipo", "nada")
        e = self.e
        if tipo == "cifra":
            p = min(1, t / 0.45)
            esc = _rebote(p) * (1 + 0.02 * math.sin(t * 5))
            if v.get("valor") is not None and v.get("formato"):
                q = _salida_suave(min(1, t / 0.9))
                texto = v["formato"](v["valor"] * q if q < 1 else v["valor"])
            else:
                texto = v["texto"]
            capa = self._c(("cifra", texto), lambda: _brillo(
                _texto(texto, e["grande"], 400 if len(texto) <= 4 else 260, (255, 255, 255, 255), max_ancho=ANCHO - 100),
                e["acento2"], 36))
            _pegar(lienzo, capa, ANCHO / 2, cy - 40 * escala, escala=max(0.01, esc * escala), opacidad=min(1, p * 2))
            if v.get("sub"):
                s = self._c(("sub", v["sub"]), lambda: _caja_texto(v["sub"].upper() if e["mayusculas"] else v["sub"],
                                                                     e["titular"], 72, (20, 20, 20), e["acento"]))
                q = _salida_suave(min(1, max(0, (t - 0.25) / 0.35)))
                _pegar(lienzo, s, ANCHO / 2 + 300 * (1 - q), cy + 230 * escala, opacidad=q)

        elif tipo == "titular":
            palabras = v["texto"].upper().split() if e["mayusculas"] else v["texto"].split()
            resaltar = set((v.get("resaltar") or "").upper().split() if e["mayusculas"] else (v.get("resaltar") or "").split())
            # Agrupa en líneas de máximo 2-3 palabras, que entran una a una
            lineas, actual = [], []
            for p in palabras:
                actual.append(p)
                if len(" ".join(actual)) > (11 if e["mayusculas"] else 15):
                    lineas.append(actual)
                    actual = []
            if actual:
                lineas.append(actual)
            alto_l = 150 if e["mayusculas"] else 135
            y0 = cy - alto_l * (len(lineas) - 1) / 2
            k = 0
            for i, linea in enumerate(lineas):
                texto = " ".join(linea)
                destacado = any(p.strip(".,:;!?¿¡") in resaltar for p in linea)
                capa = self._c(("tit", texto, destacado), lambda: _caja_texto(
                    texto, e["titular"], 128 if e["mayusculas"] else 108,
                    (20, 20, 20) if destacado else (255, 255, 255), e["acento"] if destacado else None))
                q = min(1, max(0, (t - 0.12 * k) / 0.25))
                _pegar(lienzo, capa, ANCHO / 2, y0 + i * alto_l, escala=max(0.01, _rebote(q)), opacidad=min(1, q * 2))
                k += 1

        elif tipo == "grafico":
            from video_datos import _grafico
            g = v["grafico"]
            tarjeta = self._c(("graf", id(g)), lambda: _grafico(g, ANCHO - 100, 640, e["acento2"]))
            r = _salida_suave(min(1, max(0, (t - 0.15) / 1.0)))
            base = Image.new("RGBA", tarjeta.size, (0, 0, 0, 0))
            ImageDraw.Draw(base).rounded_rectangle((0, 0, tarjeta.width - 1, tarjeta.height - 1), radius=28, fill=(255, 255, 255, 255))
            if g["tipo"] == "barras":
                h = max(1, int(tarjeta.height * r))
                base.alpha_composite(tarjeta.crop((0, tarjeta.height - h, tarjeta.width, tarjeta.height)), (0, tarjeta.height - h))
            else:
                w = max(1, int(tarjeta.width * r))
                base.alpha_composite(tarjeta.crop((0, 0, w, tarjeta.height)), (0, 0))
            q = _salida_suave(min(1, t / 0.3))
            _pegar(lienzo, base, ANCHO / 2, cy + 40 + 200 * (1 - q), opacidad=q)
            if v.get("titulo"):
                tt = self._c(("gt", v["titulo"]), lambda: _caja_texto(v["titulo"], e["titular"], 64, (255, 255, 255)))
                _pegar(lienzo, tt, ANCHO / 2, cy - 360, opacidad=q)

        elif tipo == "cierre":
            q = _rebote(min(1, t / 0.45))
            sig = self._c("sig", lambda: _caja_texto("SÍGUENOS" if e["mayusculas"] else "Síguenos", e["titular"], 80,
                                                     (20, 20, 20), e["acento"]))
            web = self._c("web", lambda: _brillo(_texto(e["web"], e["grande"], 120, (255, 255, 255, 255),
                                                        max_ancho=ANCHO - 100), e["acento2"], 30))
            _pegar(lienzo, sig, ANCHO / 2, cy - 120, escala=max(0.01, q))
            _pegar(lienzo, web, ANCHO / 2, cy + 60, escala=max(0.01, q))
            if v.get("aviso"):
                av = self._c("aviso", lambda: _caja_texto(v["aviso"], e["subtitulo"], 32, (235, 235, 235), (0, 0, 0)))
                _pegar(lienzo, av, ANCHO / 2, cy + 260, opacidad=min(1, q))


# =====================================================================
#  Tarjeta con imagen (solo GTA, si hay carpeta de imágenes)
# =====================================================================

TARJETA_W, TARJETA_H, TARJETA_Y = 960, 540, 580


class Tarjeta:
    """Imagen 16:9 enmarcada en la parte de arriba, con zoom lento por dentro y su crédito."""

    def __init__(self, ruta, credito, color, semilla):
        rnd = random.Random(semilla)
        img = Image.open(ruta).convert("RGB")
        self.grande = img.resize((int(TARJETA_W * 1.12), int(TARJETA_H * 1.12)), Image.LANCZOS)
        self.dir = rnd.choice([(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0)])
        self.mascara = Image.new("L", (TARJETA_W, TARJETA_H), 0)
        ImageDraw.Draw(self.mascara).rounded_rectangle((0, 0, TARJETA_W - 1, TARJETA_H - 1), radius=26, fill=255)
        marco = Image.new("RGBA", (TARJETA_W + 80, TARJETA_H + 80), (0, 0, 0, 0))
        d = ImageDraw.Draw(marco)
        d.rounded_rectangle((40, 48, 40 + TARJETA_W, 48 + TARJETA_H), radius=30, fill=(0, 0, 0, 150))
        self.sombra = marco.filter(ImageFilter.GaussianBlur(16))
        borde = Image.new("RGBA", (TARJETA_W + 12, TARJETA_H + 12), (0, 0, 0, 0))
        ImageDraw.Draw(borde).rounded_rectangle((0, 0, TARJETA_W + 11, TARJETA_H + 11), radius=32, fill=color + (255,))
        self.borde = borde
        f = ImageFont.truetype(F["inter"], 24)
        c = f.getbbox(credito)
        self.credito = Image.new("RGBA", (c[2] - c[0] + 24, c[3] - c[1] + 14), (0, 0, 0, 150))
        ImageDraw.Draw(self.credito).text((12 - c[0], 7 - c[1]), credito, font=f, fill=(255, 255, 255, 220))

    def dibujar(self, lienzo, t, dur):
        g = self.grande
        avance = min(1, t / max(dur, 0.1))
        z = 1.12 - 0.08 * avance
        w, h = int(TARJETA_W * z), int(TARJETA_H * z)
        mx, my = (g.width - w) // 2, (g.height - h) // 2
        x = mx + int(mx * self.dir[0] * (avance - 0.5))
        y = my + int(my * self.dir[1] * (avance - 0.5))
        foto = g.crop((x, y, x + w, y + h)).resize((TARJETA_W, TARJETA_H), Image.BILINEAR)
        capa = Image.new("RGBA", (TARJETA_W + 80, TARJETA_H + 80), (0, 0, 0, 0))
        capa.alpha_composite(self.sombra)
        capa.alpha_composite(self.borde, (34, 34))
        capa.paste(foto, (40, 40), self.mascara)
        capa.alpha_composite(self.credito, (40 + TARJETA_W - self.credito.width - 14, 40 + TARJETA_H - self.credito.height - 12))
        q = _rebote(min(1, t / 0.35))
        _pegar(lienzo, capa, ANCHO / 2, TARJETA_Y, escala=max(0.01, 0.85 + 0.15 * q), opacidad=min(1, t / 0.15))


def _imagenes(estilo, semilla, cuantas):
    """Elige imágenes distintas para cada escena (orden distinto cada día)."""
    carpeta = estilo.get("imagenes")
    if not carpeta or not Path(carpeta).is_dir():
        return []
    fotos = sorted(p for p in Path(carpeta).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if not fotos:
        return []
    random.Random(semilla).shuffle(fotos)
    return [fotos[i % len(fotos)] for i in range(cuantas)]


# =====================================================================
#  Subtítulos palabra a palabra
# =====================================================================

class Subtitulos:
    def __init__(self, palabras, estilo, por_grupo=3):
        self.e = estilo
        self.grupos = []  # (inicio, fin, [palabras], [(ini, fin)])
        grupo, tiempos = [], []
        for p, a, b in palabras:
            grupo.append(p)
            tiempos.append((a, b))
            if len(grupo) >= por_grupo or p[-1] in ".,:;?!":
                self.grupos.append((tiempos[0][0], tiempos[-1][1], grupo, tiempos))
                grupo, tiempos = [], []
        if grupo:
            self.grupos.append((tiempos[0][0], tiempos[-1][1], grupo, tiempos))
        self.f = ImageFont.truetype(estilo["subtitulo"], 82)
        self.cache = {}

    def capa(self, grupo, activa):
        clave = (" ".join(grupo), activa)
        if clave in self.cache:
            return self.cache[clave]
        e = self.e
        textos = [p.upper() if e["mayusculas"] else p for p in grupo]
        espacio = self.f.getlength(" ")
        anchos = [self.f.getlength(x) for x in textos]
        total = sum(anchos) + espacio * (len(textos) - 1)
        f = self.f
        if total > ANCHO - 100:
            f = ImageFont.truetype(e["subtitulo"], int(82 * (ANCHO - 100) / total))
            anchos = [f.getlength(x) for x in textos]
            espacio = f.getlength(" ")
            total = sum(anchos) + espacio * (len(textos) - 1)
        capa = Image.new("RGBA", (int(total) + 80, 160), (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        x = 40
        for i, (txt, w) in enumerate(zip(textos, anchos)):
            if i == activa:
                d.rounded_rectangle((x - 12, 22, x + w + 12, 138), radius=14, fill=e["acento"] + (255,))
                d.text((x, 30), txt, font=f, fill=(20, 20, 20, 255))
            else:
                d.text((x, 30), txt, font=f, fill=(255, 255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0, 255))
            x += w + espacio
        self.cache[clave] = capa
        return capa

    def dibujar(self, lienzo, t, y=1430):
        for ini, fin, grupo, tiempos in self.grupos:
            if ini <= t < fin + 0.05:
                activa = next((i for i, (a, b) in enumerate(tiempos) if a <= t < b), len(grupo) - 1)
                q = min(1, (t - ini) / 0.1)
                _pegar(lienzo, self.capa(grupo, activa), ANCHO / 2, y, escala=0.92 + 0.08 * q)
                return


# =====================================================================
#  Montaje
# =====================================================================

def montar_escenas(frases, audios, sr, escenas, estilo, salida, trozos_voz=None, semilla="", consultas_extra=None):
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    carpeta = Path(tempfile.mkdtemp())
    voz, tiempos_frase, piezas, palabras, duracion = _linea_de_tiempo(frases, audios, sr, trozos_voz, carpeta)
    n_frames = int(math.ceil(duracion * FPS))
    rnd = random.Random(semilla)

    # --- Escenas: una por frase (desde el inicio de su frase hasta el de la siguiente) + cierre
    bloques = []
    for i, esc in enumerate(escenas):
        ini = 0.0 if i == 0 else tiempos_frase[i][0] - 0.08
        fin = tiempos_frase[i + 1][0] - 0.08 if i + 1 < len(escenas) else tiempos_frase[-1][1] + 0.25
        # Cortes de fondo en las comas (si el tramo es lo bastante largo)
        cortes = [ini]
        for txt, a, b in piezas:
            if ini + CORTE_MIN < a - 0.05 < fin - CORTE_MIN and a - cortes[-1] > CORTE_MIN:
                cortes.append(a - 0.05)
        bloques.append({"ini": ini, "fin": fin, "visual": esc.get("visual", {"tipo": "nada"}),
                        "buscar": esc.get("buscar"), "cortes": cortes})
    bloques.append({"ini": bloques[-1]["fin"], "fin": duracion, "visual": {"tipo": "cierre", "aviso": estilo.get("aviso")},
                    "buscar": (consultas_extra or [None])[0], "cortes": [bloques[-1]["fin"]]})

    # --- Fondos (Pexels o propios), uno por tramo
    tramos = []
    variante = 0
    for bi, b in enumerate(bloques):
        for k, c0 in enumerate(b["cortes"]):
            c1 = b["cortes"][k + 1] if k + 1 < len(b["cortes"]) else b["fin"]
            consulta = b["buscar"]
            if isinstance(consulta, list):
                consulta = consulta[k % len(consulta)]
            clip = buscar_clip(consulta, semilla=f"{semilla}-{bi}-{k}") if consulta else None
            tramos.append({"ini": c0, "fin": c1, "bloque": bi, "corte": k > 0, "clip": clip,
                           "variante": variante})
            variante += 1
    hay_pexels = any(t["clip"] for t in tramos)
    print(f"Escenas: {len(bloques)} · cortes de fondo: {len(tramos)} · clips de Pexels: {sum(1 for t in tramos if t['clip'])}")

    # --- Audio: voz + whoosh en cada transición + golpe inicial + pop en las cifras + música
    efectos = [(0.0, sonido.golpe())]
    for i, b in enumerate(bloques[1:], 1):
        efectos.append((max(0, b["ini"] - 0.18), sonido.whoosh(semilla=i)))
    for b in bloques:
        if b["visual"].get("tipo") == "cifra":
            efectos.append((b["ini"] + 0.05, sonido.pop()))
    for tr in tramos:
        if tr["corte"]:
            efectos.append((max(0, tr["ini"] - 0.1), sonido.whoosh(dur=0.3, semilla=int(tr["ini"] * 100)) * 0.5))
    mezcla = sonido.mezclar(voz, sr, efectos, duracion, estilo["nombre"])
    audio = carpeta / "mezcla.wav"
    sf.write(audio, mezcla, sonido.SR)
    final_audio = carpeta / "mezcla_norm.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(audio), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(final_audio)], check=True)

    # --- Vídeo
    fotos = _imagenes(estilo, semilla, len(bloques) - 1)
    tarjetas = {}
    if fotos:
        print(f"Imágenes en tarjeta: {len(fotos)} (de {estilo['imagenes']})")
    leg = _capa_legibilidad(estilo)
    marca = _caja_texto(estilo["marca"], estilo["titular"], 40, (255, 255, 255), estilo["acento2"], pad=(22, 10))
    subs = Subtitulos(palabras, estilo)
    vis = Visuales(estilo)
    transiciones = ["barrido", "zoom", "destello", "barrido_v"]

    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
         "-i", str(final_audio),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{n_frames / FPS:.3f}", "-movflags", "+faststart", str(salida)],
        stdin=subprocess.PIPE,
    )

    fondo_actual, tramo_actual = None, -1
    anterior = None  # último cuadro del bloque anterior (para las transiciones)
    bloque_actual = -1
    for n in range(n_frames):
        t = n / FPS
        ti = next((i for i, tr in enumerate(tramos) if tr["ini"] <= t < tr["fin"]), len(tramos) - 1)
        tr = tramos[ti]
        if ti != tramo_actual:
            if fondo_actual:
                fondo_actual.cerrar()
            fondo_actual = Fondo(tr["clip"], tr["fin"] - tr["ini"], estilo, tr["variante"], f"{semilla}-{ti}")
            tramo_actual = ti
        b = bloques[tr["bloque"]]
        if tr["bloque"] != bloque_actual:
            bloque_actual = tr["bloque"]

        lienzo = fondo_actual.cuadro(t - tr["ini"])
        if tr["clip"] or estilo["nombre"] != "gta":
            lienzo.alpha_composite(leg)
        con_tarjeta = bool(fotos) and b["visual"].get("tipo") != "cierre"
        if con_tarjeta:
            bi = tr["bloque"]
            if bi not in tarjetas:
                tarjetas.clear()  # solo hace falta la de la escena actual
                tarjetas[bi] = Tarjeta(fotos[bi], estilo.get("credito", ""), estilo["acento2"], f"{semilla}-{bi}")
            tarjetas[bi].dibujar(lienzo, t - b["ini"], b["fin"] - b["ini"])
            vis.dibujar(lienzo, b["visual"], t - b["ini"], b["fin"] - b["ini"], cy=1150, escala=0.62)
        else:
            vis.dibujar(lienzo, b["visual"], t - b["ini"], b["fin"] - b["ini"])
        if b["visual"].get("tipo") != "cierre":
            subs.dibujar(lienzo, t, y=1560 if con_tarjeta else 1430)
        lienzo.alpha_composite(marca, (30, 50))
        d = ImageDraw.Draw(lienzo)
        d.rectangle((0, 0, int(ANCHO * t / duracion), 12), fill=estilo["acento"] + (255,))

        # Punch de zoom en los cortes dentro de una escena
        dt_corte = t - tr["ini"]
        if tr["corte"] and dt_corte < 0.25:
            z = 1 + 0.08 * (1 - dt_corte / 0.25)
            w, h = int(ANCHO / z), int(ALTO / z)
            lienzo = lienzo.crop(((ANCHO - w) // 2, (ALTO - h) // 2, (ANCHO - w) // 2 + w, (ALTO - h) // 2 + h)).resize((ANCHO, ALTO), Image.BILINEAR)

        # Transición entre escenas
        dt = t - b["ini"]
        if tr["bloque"] > 0 and dt < TRANSICION and anterior is not None:
            q = _salida_suave(dt / TRANSICION)
            tipo = transiciones[tr["bloque"] % len(transiciones)]
            mezcla_img = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 255))
            if tipo == "barrido":
                mezcla_img.alpha_composite(anterior, (int(-ANCHO * q), 0))
                mezcla_img.alpha_composite(lienzo, (int(ANCHO * (1 - q)), 0))
            elif tipo == "barrido_v":
                mezcla_img.alpha_composite(anterior, (0, int(-ALTO * q)))
                mezcla_img.alpha_composite(lienzo, (0, int(ALTO * (1 - q))))
            elif tipo == "zoom":
                z = 1 + 0.35 * (1 - q)
                w, h = int(ANCHO / z), int(ALTO / z)
                nuevo = lienzo.crop(((ANCHO - w) // 2, (ALTO - h) // 2, (ANCHO - w) // 2 + w, (ALTO - h) // 2 + h)).resize((ANCHO, ALTO), Image.BILINEAR)
                mezcla_img = Image.blend(anterior, nuevo, q)
            else:  # destello
                mezcla_img = Image.blend(anterior, lienzo, q)
                blanco = Image.new("RGBA", (ANCHO, ALTO), (255, 255, 255, int(200 * (1 - abs(2 * q - 1)))))
                mezcla_img.alpha_composite(blanco)
            lienzo = mezcla_img
        else:
            anterior = lienzo

        ffmpeg.stdin.write(lienzo.convert("RGB").tobytes())
        if n % (FPS * 5) == 0:
            print(f"  vídeo: {t:.0f}/{duracion:.0f} s")

    if fondo_actual:
        fondo_actual.cerrar()
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("::error::ffmpeg no pudo montar el vídeo")
    creditos = sorted({f"{tr['clip']['autor']} ({tr['clip']['url']})" for tr in tramos if tr["clip"]})
    print(f"Vídeo listo: {salida} ({duracion:.1f} s){' · clips de Pexels' if hay_pexels else ' · fondos propios'}")
    return {"duracion": duracion, "creditos": creditos}
