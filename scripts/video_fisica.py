"""Vídeo de física: explica un fenómeno con un esquema 3D que se mueve, zooms y voz.

Genera salida/fisica_<tema>_AAAA-MM-DD.mp4 y su .txt (texto para la publicación).
No publica nada: el robot solo te lo manda para revisarlo.

Variables:
    TEMA_FISICA   tema (por ahora: motor)
    SIN_VOZ=1     prueba sin voz (calcula los tiempos a ojo), para ver la animación rápido
"""
import importlib
import math
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

import sonido
from escena3d import Escena
from montaje import Subtitulos, _caja_texto, _linea_de_tiempo
from video import ALTO, ANCHO, FPS

FUENTES = Path(__file__).resolve().parent.parent / "fuentes"
F_TITULO = str(FUENTES / "Anton.ttf")
F_TEXTO = str(FUENTES / "Inter-ExtraBold.ttf")

TEMAS = {"motor": "fisica_motor"}
ESTILO = {
    "nombre": "datos", "marca": "FÍSICA EN 40 SEGUNDOS", "subtitulo": F_TEXTO, "mayusculas": True,
    "acento": (255, 214, 60), "acento2": (40, 120, 230), "titular": F_TITULO,
}
CENTRO = (540, 860)       # dónde va el centro del esquema en la pantalla
CAMBIO_CAMARA = 0.75      # segundos que tarda la cámara en viajar a la escena nueva
COLORES_ETIQUETA = {
    "normal": ((255, 255, 255), (20, 30, 50)), "campo": ((10, 30, 40), (90, 220, 255)),
    "corriente": ((30, 15, 0), (255, 150, 40)), "fuerza": ((20, 20, 20), (255, 214, 60)),
    "aviso": ((20, 20, 20), (255, 214, 60)),
}


# ---------------------------------------------------------------------
#  Fondo tipo plano técnico
# ---------------------------------------------------------------------

def _fondo():
    y = np.linspace(0, 1, ALTO)[:, None]
    x = np.linspace(-1, 1, ANCHO)[None, :]
    arriba, abajo = np.array([10, 22, 44]), np.array([4, 10, 24])
    col = arriba[None, None, :] * (1 - y[..., None]) + abajo[None, None, :] * y[..., None]
    vin = 1 - 0.35 * (x ** 2)[..., None] - 0.25 * ((y - 0.45) ** 2)[..., None] * 2
    img = Image.fromarray(np.clip(col * vin, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    for k in range(0, ANCHO + 1, 40):
        d.line((k, 0, k, ALTO), fill=(90, 150, 255, 26 if k % 200 else 46), width=1)
    for k in range(0, ALTO + 1, 40):
        d.line((0, k, ANCHO, k), fill=(90, 150, 255, 26 if k % 200 else 46), width=1)
    return img


# ---------------------------------------------------------------------
#  Textos
# ---------------------------------------------------------------------

class Textos:
    def __init__(self):
        self.cache = {}

    def etiqueta(self, texto, tipo):
        clave = ("e", texto, tipo)
        if clave not in self.cache:
            if tipo == "letra":
                f = ImageFont.truetype(F_TITULO, 96)
                c = f.getbbox(texto)
                capa = Image.new("RGBA", (c[2] + 30, c[3] + 30), (0, 0, 0, 0))
                ImageDraw.Draw(capa).text((15 - c[0] // 2, 10), texto, font=f, fill=(255, 255, 255, 255),
                                          stroke_width=4, stroke_fill=(0, 0, 0, 200))
            elif tipo == "pila":
                f = ImageFont.truetype(F_TEXTO, 34)
                c = f.getbbox(texto)
                capa = Image.new("RGBA", (c[2] + 20, c[3] + 20), (0, 0, 0, 0))
                ImageDraw.Draw(capa).text((10, 6), texto, font=f, fill=(255, 220, 120, 255))
            elif tipo == "fuerza":
                capa = _caja_texto(texto, F_TITULO, 84, (20, 20, 20), (255, 214, 60), pad=(26, 8))
            else:
                color, fondo = COLORES_ETIQUETA.get(tipo, COLORES_ETIQUETA["normal"])
                tam = 50 if tipo == "aviso" else 42
                capa = _caja_texto(texto, F_TEXTO, tam, color, fondo, pad=(22, 12))
            self.cache[clave] = capa
        return self.cache[clave]

    def kicker(self, texto):
        clave = ("k", texto)
        if clave not in self.cache:
            grande = texto.startswith("¿")
            self.cache[clave] = _caja_texto(texto, F_TITULO, 96 if grande else 64,
                                            (20, 20, 20) if grande else (255, 255, 255),
                                            (255, 214, 60) if grande else (40, 120, 230), pad=(30, 14))
        return self.cache[clave]


def _pegar_centro(lienzo, capa, x, y, alfa=1.0, escala=1.0):
    if alfa <= 0.01:
        return
    if escala != 1.0:
        capa = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))), Image.BILINEAR)
    if alfa < 0.99:
        capa = capa.copy()
        capa.putalpha(capa.getchannel("A").point(lambda v: int(v * alfa)))
    lienzo.alpha_composite(capa, (int(x - capa.width / 2), int(y - capa.height / 2)))


def _ease(q):
    q = max(0.0, min(1.0, q))
    return q * q * (3 - 2 * q)


def _zumbido(theta, dur, fps):
    """Zumbido del motor: más agudo y fuerte cuanto más rápido gira."""
    n = int(dur * sonido.SR)
    w = np.abs(np.diff(np.array(theta), prepend=theta[0])) * fps
    w = np.interp(np.arange(n) / sonido.SR, np.arange(len(w)) / fps, w)
    frec = 70 + 9 * w
    fase = 2 * np.pi * np.cumsum(frec) / sonido.SR
    s = (np.sin(fase) + 0.4 * np.sin(2 * fase) + 0.15 * np.sign(np.sin(3 * fase)))
    vol = np.clip(w / 11, 0, 1) * 0.07
    return (s * vol).astype(np.float32)


# ---------------------------------------------------------------------
#  Montaje
# ---------------------------------------------------------------------

def montar_fisica(tema, frases, audios, sr, salida, trozos_voz=None):
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    carpeta = Path(tempfile.mkdtemp())
    voz, tiempos_frase, piezas, palabras, duracion = _linea_de_tiempo(frases, audios, sr, trozos_voz, carpeta)
    n_frames = int(math.ceil(duracion * FPS))

    # Cada escena dura desde que empieza su frase hasta que empieza la siguiente
    tiempos_escena = []
    for i in range(len(frases)):
        a = 0.0 if i == 0 else tiempos_frase[i][0] - 0.1
        b = tiempos_frase[i + 1][0] - 0.1 if i + 1 < len(frases) else tiempos_frase[-1][1] + 0.3
        tiempos_escena.append((a, b))
    estado = tema.preparar(tiempos_escena, n_frames, FPS)

    # --- Audio: voz + golpe inicial + whoosh en cada cambio de escena + zumbido del motor + música
    efectos = [(0.0, sonido.golpe()), (0.0, _zumbido(estado["theta"], duracion, FPS))]
    for i, (a, _) in enumerate(tiempos_escena[1:], 1):
        efectos.append((max(0, a - 0.15), sonido.whoosh(semilla=i)))
    efectos.append((max(0, tiempos_escena[-1][1] - 0.15), sonido.whoosh(semilla=99)))
    mezcla = sonido.mezclar(voz, sr, efectos, duracion, ESTILO["nombre"])
    audio = carpeta / "mezcla.wav"
    sf.write(audio, mezcla, sonido.SR)
    final_audio = carpeta / "mezcla_norm.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(audio), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(final_audio)], check=True)

    # --- Vídeo
    fondo = _fondo()
    textos = Textos()
    subs = Subtitulos(palabras, ESTILO)
    marca = _caja_texto(ESTILO["marca"], F_TEXTO, 34, (255, 255, 255), ESTILO["acento2"], pad=(20, 10))
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
         "-i", str(final_audio),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{n_frames / FPS:.3f}", "-movflags", "+faststart", str(salida)],
        stdin=subprocess.PIPE,
    )
    fin_voz = tiempos_escena[-1][1]
    for n in range(n_frames):
        t = n / FPS
        i = next((k for k, (a, b) in enumerate(tiempos_escena) if t < b), len(tiempos_escena))
        ini = tiempos_escena[i][0] if i < len(tiempos_escena) else fin_voz
        fin = tiempos_escena[i][1] if i < len(tiempos_escena) else duracion
        tl, dur = t - ini, fin - ini

        # Cámara: viaja suave desde donde estaba al empezar la escena nueva
        cam = tema.camara_en(tiempos_escena, i, tl, dur)
        if i > 0 and tl < CAMBIO_CAMARA:
            pi_ = i - 1
            pini, pfin = tiempos_escena[pi_]
            previa = tema.camara_en(tiempos_escena, pi_, pfin - pini, pfin - pini)
            cam = previa.mezclar(cam, _ease(tl / CAMBIO_CAMARA))

        esc = Escena()
        etiquetas = tema.dibujar(esc, estado, n, t, i, tl, dur)
        nitida, brillo = esc.dibujar(cam, ANCHO, ALTO, CENTRO)
        lienzo = fondo.copy()
        lienzo.alpha_composite(nitida)
        lienzo.alpha_composite(brillo)

        # Etiquetas con línea guía
        d = ImageDraw.Draw(lienzo, "RGBA")
        for p3, texto, (dx, dy), alfa, tipo in etiquetas:
            if alfa <= 0.01:
                continue
            x, y, _ = esc.proyectar(cam, p3, CENTRO)
            if not (-200 < x < ANCHO + 200 and -200 < y < ALTO + 200):
                continue
            ex, ey = x + dx, y + dy
            ex = min(max(ex, 150), ANCHO - 150)
            if (dx or dy) and tipo not in ("letra", "pila"):
                d.line((x, y, ex, ey), fill=(255, 255, 255, int(200 * alfa)), width=3)
                d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(255, 255, 255, int(230 * alfa)))
            esc_pop = 0.85 + 0.15 * min(1.0, alfa * 1.5)
            _pegar_centro(lienzo, textos.etiqueta(texto, tipo), ex, ey, alfa, esc_pop)

        # Título de la escena arriba
        if i < len(tema.ESCENAS):
            q = _ease(tl / 0.35)
            _pegar_centro(lienzo, textos.kicker(tema.ESCENAS[i]["kicker"]), ANCHO / 2 - 60 * (1 - q), 230, q)
            subs.dibujar(lienzo, t, y=1480)
        else:
            q = _ease(tl / 0.4)
            _pegar_centro(lienzo, textos.kicker("¿TE HA GUSTADO?"), ANCHO / 2, 300, q, 0.8 + 0.2 * q)
            _pegar_centro(lienzo, _caja_texto("SÍGUENOS PARA MÁS FÍSICA", F_TITULO, 80, (255, 255, 255), (40, 120, 230),
                                              pad=(30, 14)), ANCHO / 2, 1500, q, 0.8 + 0.2 * q)
        lienzo.alpha_composite(marca, (30, 60))
        ImageDraw.Draw(lienzo).rectangle((0, 0, int(ANCHO * t / duracion), 12), fill=ESTILO["acento"] + (255,))

        # Golpe de zoom en cada cambio de escena
        if 0 < i and tl < 0.2:
            z = 1 + 0.06 * (1 - tl / 0.2)
            w, h = int(ANCHO / z), int(ALTO / z)
            lienzo = lienzo.crop(((ANCHO - w) // 2, (ALTO - h) // 2, (ANCHO - w) // 2 + w,
                                  (ALTO - h) // 2 + h)).resize((ANCHO, ALTO), Image.BILINEAR)

        ffmpeg.stdin.write(lienzo.convert("RGB").tobytes())
        if n % (FPS * 5) == 0:
            print(f"  vídeo: {t:.0f}/{duracion:.0f} s")
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("::error::ffmpeg no pudo montar el vídeo")
    print(f"Vídeo listo: {salida} ({duracion:.1f} s)")
    return duracion


if __name__ == "__main__":
    nombre = (os.environ.get("TEMA_FISICA") or "motor").strip()
    if nombre not in TEMAS:
        raise SystemExit(f"::error::Tema desconocido: {nombre}. Hay: {', '.join(TEMAS)}")
    tema = importlib.import_module(TEMAS[nombre])
    frases = tema.FRASES
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    inicio = time.time()

    if (os.environ.get("SIN_VOZ") or "").strip() == "1":
        sr = 24000
        audios = [np.zeros(int(sr * max(1.6, len(f.split()) / 2.7)), dtype=np.float32) for f in frases]
        trozos = None
        print("Prueba SIN VOZ: tiempos calculados a ojo")
    else:
        from motor_voz import crear_motor
        voz = crear_motor()
        audios, trozos = [], []
        for f in frases:
            audios.append(voz.decir(f))
            trozos.append(voz.ultimas_piezas)
        sr = voz.sr

    os.makedirs("salida", exist_ok=True)
    base = f"salida/fisica_{nombre}_{hoy}"
    duracion = montar_fisica(tema, frases, audios, sr, base + ".mp4", trozos)
    with open(base + ".txt", "w", encoding="utf-8") as fh:
        fh.write(f"{tema.TITULO} ⚡\n\nLa física explicada en menos de un minuto.\n\n{tema.HASHTAGS}\n")
    print(f"Listo en {round(time.time() - inicio)} s · vídeo de {duracion:.1f} s")
