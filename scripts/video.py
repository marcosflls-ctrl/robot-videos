"""Monta un vídeo vertical (1080x1920) con gráficos propios, voz y subtítulos.

Todo se dibuja aquí con código (degradado, sol, rejilla en movimiento, cifra grande,
subtítulos). No usa imágenes ni vídeo de terceros.

    montar(frases, audios, sr, tema, "salida/video.mp4")

- frases: textos tal y como se ven en pantalla (uno por frase de la voz).
- audios: un array de audio por frase (mismo orden).
- tema: diccionario con la cifra grande, las etiquetas y los colores (ver TEMA_GTA).
"""
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ANCHO, ALTO, FPS = 1080, 1920, 30
PAUSA = 0.28        # silencio entre frases (s)
COLA = 1.2          # segundos al final, con la pantalla de cierre
MAX_DURACION = 40.0  # si la voz se pasa, se acelera un poco (sin cambiar el tono)

FUENTES = Path(__file__).resolve().parent.parent / "fuentes"
ANTON = str(FUENTES / "Anton.ttf")
INTER = str(FUENTES / "Inter-ExtraBold.ttf")

TEMA_GTA = {
    "marca": "ZONA LEONIDA",
    "etiqueta": "CUENTA ATRÁS",
    "cifra": "28",
    "bajo_cifra": "DÍAS PARA GTA 6",
    "dato": "19 · NOV · 2026",
    "web": "zonaleonida.com",
    "cielo": [(18, 6, 38), (74, 12, 92), (214, 38, 120), (255, 132, 64)],
    "suelo": (14, 4, 30),
    "rejilla": (255, 70, 170),
    "sol": [(255, 222, 89), (255, 92, 138)],
    "acento": (255, 214, 92),
}


# ---------- utilidades de dibujo ----------

def _degradado(alto, colores):
    """Degradado vertical por tramos, como array (alto, ANCHO, 3)."""
    t = np.linspace(0, 1, alto)[:, None]
    tramos = len(colores) - 1
    pos = t * tramos
    i = np.clip(pos.astype(int), 0, tramos - 1)
    f = pos - i
    c = np.array(colores, dtype=np.float32)
    col = c[i[:, 0]] * (1 - f) + c[i[:, 0] + 1] * f
    return np.repeat(col[:, None, :], ANCHO, axis=1)


def _texto(texto, fuente, tam, color, sombra=True, contorno=0, max_ancho=None):
    """Devuelve una imagen RGBA recortada con el texto (con brillo/sombra opcional)."""
    f = ImageFont.truetype(fuente, tam)
    if max_ancho:
        while f.getlength(texto) > max_ancho and tam > 20:
            tam -= 4
            f = ImageFont.truetype(fuente, tam)
    caja = f.getbbox(texto, stroke_width=contorno)
    w, h = caja[2] - caja[0] + 60, caja[3] - caja[1] + 60
    capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    xy = (30 - caja[0], 30 - caja[1])
    if sombra:
        s = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(s).text((xy[0] + 6, xy[1] + 8), texto, font=f, fill=(0, 0, 0, 170),
                               stroke_width=contorno, stroke_fill=(0, 0, 0, 170))
        capa = Image.alpha_composite(capa, s.filter(ImageFilter.GaussianBlur(8)))
        d = ImageDraw.Draw(capa)
    d.text(xy, texto, font=f, fill=color, stroke_width=contorno, stroke_fill=(0, 0, 0, 255))
    return capa


def _brillo(capa, color, radio=28):
    """Halo de color alrededor de una capa de texto."""
    margen = radio * 3  # espacio para que el halo no se corte en un recuadro
    grande = Image.new("RGBA", (capa.width + 2 * margen, capa.height + 2 * margen), (0, 0, 0, 0))
    grande.alpha_composite(capa, (margen, margen))
    capa = grande
    a = capa.split()[3]
    halo = Image.new("RGBA", capa.size, color + (0,))
    halo.putalpha(a.filter(ImageFilter.GaussianBlur(radio)))
    base = Image.new("RGBA", capa.size, (0, 0, 0, 0))
    base = Image.alpha_composite(base, halo)
    base = Image.alpha_composite(base, halo)
    return Image.alpha_composite(base, capa)


def _pegar(lienzo, capa, cx, cy, escala=1.0, opacidad=1.0):
    if escala != 1.0:
        capa = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))),
                           Image.LANCZOS)
    if opacidad < 1.0:
        a = capa.split()[3].point(lambda v: int(v * opacidad))
        capa = capa.copy()
        capa.putalpha(a)
    lienzo.alpha_composite(capa, (int(cx - capa.width / 2), int(cy - capa.height / 2)))


def _trozos(frase, max_palabras=4):
    """Parte una frase en trozos cortos para los subtítulos."""
    # Que el símbolo no se separe de su cifra ("0,28 %" va siempre junto)
    palabras = frase.replace(" %", "\x00%").replace(" €", "\x00€").replace(" $", "\x00$").split(" ")
    palabras = [p.replace("\x00", " ") for p in palabras if p]
    trozos, actual = [], []
    for p in palabras:
        actual.append(p)
        if len(actual) >= max_palabras or p[-1] in ".,:;?!":
            trozos.append(" ".join(actual))
            actual = []
    if actual:
        trozos.append(" ".join(actual))
    return trozos


def _salida_suave(x):
    return 1 - (1 - x) ** 3


def _rebote(x):
    """Entrada con un pequeño rebote (0 -> 1)."""
    if x >= 1:
        return 1.0
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2


# ---------- audio ----------

def _preparar_audio(frases, audios, sr, carpeta, trozos_voz=None):
    """Une las frases con pausas, ajusta la velocidad si hace falta y calcula los tiempos.

    trozos_voz: para cada frase, la lista [(texto, inicio, fin)] de los trozos que generó la
    voz (entre comas). Si está, los subtítulos siguen exactamente esos tiempos.
    """
    pausa = np.zeros(int(PAUSA * sr), dtype=np.float32)
    piezas, tiempos, t = [np.zeros(int(0.35 * sr), dtype=np.float32)], [], 0.35
    for i, (frase, a) in enumerate(zip(frases, audios)):
        dur = len(a) / sr
        trozos = (trozos_voz or [None] * len(frases))[i]
        if trozos:
            tiempos += [(t + ini, t + fin, txt) for txt, ini, fin in trozos]
        else:
            tiempos.append((t, t + dur, frase))
        piezas += [a, pausa]
        t += dur + PAUSA
    voz = np.concatenate(piezas)
    bruto = carpeta / "voz_bruta.wav"
    sf.write(bruto, voz, sr)

    total = len(voz) / sr
    factor = 1.0  # sin acelerar la voz
    filtros = ([f"atempo={factor:.4f}"] if factor > 1.0 else []) + ["loudnorm=I=-14:TP=-1.5:LRA=11", f"apad=pad_dur={COLA + 1}"]
    final = carpeta / "voz.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(bruto), "-af", ",".join(filtros),
                    "-ar", "48000", "-ac", "2", str(final)], check=True)
    tiempos = [(a / factor, b / factor, f) for a, b, f in tiempos]
    duracion = total / factor + COLA
    if factor > 1.0:
        print(f"Voz acelerada x{factor:.2f} para no pasar de {MAX_DURACION:.0f} s")
    return final, tiempos, duracion


# ---------- vídeo ----------

def montar(frases, audios, sr, tema, salida, trozos_voz=None):
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    carpeta = Path(tempfile.mkdtemp())
    audio, tiempos, duracion = _preparar_audio(frases, audios, sr, carpeta, trozos_voz)
    n_frames = int(math.ceil(duracion * FPS))

    # Fondo fijo: cielo, sol y suelo
    horizonte = int(ALTO * 0.70)
    fondo = np.zeros((ALTO, ANCHO, 3), dtype=np.float32)
    fondo[:horizonte] = _degradado(horizonte, tema["cielo"])
    fondo[horizonte:] = np.array(tema["suelo"], dtype=np.float32)
    fondo_img = Image.fromarray(fondo.astype(np.uint8)).convert("RGBA")

    radio_sol = 300
    sol = Image.new("RGBA", (radio_sol * 2, radio_sol * 2), (0, 0, 0, 0))
    grad = _degradado(radio_sol * 2, tema["sol"])[:, :radio_sol * 2]
    mascara = Image.new("L", sol.size, 0)
    md = ImageDraw.Draw(mascara)
    md.ellipse((0, 0, radio_sol * 2 - 1, radio_sol * 2 - 1), fill=255)
    for k in range(7):  # franjas horizontales en la mitad inferior del sol
        y = radio_sol + 30 + k * 40
        md.rectangle((0, y, radio_sol * 2, y + 6 + k * 3), fill=0)
    sol = Image.fromarray(grad.astype(np.uint8)).convert("RGBA")
    sol.putalpha(mascara)
    halo_sol = Image.new("RGBA", (radio_sol * 3, radio_sol * 3), (0, 0, 0, 0))
    ImageDraw.Draw(halo_sol).ellipse((radio_sol // 2, radio_sol // 2, radio_sol * 5 // 2, radio_sol * 5 // 2),
                                     fill=tema["sol"][1] + (120,))
    halo_sol = halo_sol.filter(ImageFilter.GaussianBlur(90))
    fondo_img.alpha_composite(halo_sol, (ANCHO // 2 - halo_sol.width // 2, horizonte - radio_sol - halo_sol.height // 2 + radio_sol))
    fondo_img.alpha_composite(sol, (ANCHO // 2 - radio_sol, horizonte - int(radio_sol * 1.35)))
    # El sol queda cortado por el horizonte
    fondo_img.paste(Image.new("RGBA", (ANCHO, ALTO - horizonte), tema["suelo"] + (255,)), (0, horizonte))

    # Capas de texto fijas
    acento = tema["acento"] + (255,)
    blanco = (255, 255, 255, 255)
    c_marca = _texto(tema["marca"], ANTON, 64, blanco)
    c_etiqueta = _texto(tema["etiqueta"], INTER, 40, acento, sombra=False)
    c_cifra = _brillo(_texto(tema["cifra"], ANTON, 560, blanco, max_ancho=ANCHO - 120), tema["rejilla"], 40)
    c_bajo = _texto(tema["bajo_cifra"], ANTON, 104, acento, max_ancho=ANCHO - 120)
    c_dato = _texto(tema["dato"], INTER, 46, blanco)
    c_web = _texto(tema["web"], INTER, 48, blanco)
    c_cierre = _brillo(_texto(tema["web"], ANTON, 120, blanco, max_ancho=ANCHO - 100), tema["rejilla"], 30)
    c_sigue = _texto("SÍGUENOS", INTER, 56, acento)

    # Subtítulos: cada frase en trozos, con su tiempo repartido por letras
    subtitulos = []
    for ini, fin, frase in tiempos:
        trozos = _trozos(frase)
        letras = sum(len(x) for x in trozos)
        t = ini
        for x in trozos:
            d = (fin - ini) * len(x) / letras
            subtitulos.append((t, t + d, x))
            t += d
    cache_sub = {}

    def capa_sub(txt):
        if txt not in cache_sub:
            cache_sub[txt] = _texto(txt.upper(), INTER, 78, blanco, contorno=6, max_ancho=ANCHO - 100)
        return cache_sub[txt]

    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
         "-i", str(audio),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{n_frames / FPS:.3f}", "-movflags", "+faststart", str(salida)],
        stdin=subprocess.PIPE,
    )

    rejilla_color = tema["rejilla"]
    inicio_cierre = duracion - COLA - 0.2
    for n in range(n_frames):
        t = n / FPS
        lienzo = fondo_img.copy()
        d = ImageDraw.Draw(lienzo)

        # Rejilla en perspectiva que avanza hacia la cámara
        alto_suelo = ALTO - horizonte
        for i in range(-12, 13):
            x_fondo = ANCHO / 2 + i * 60
            x_frente = ANCHO / 2 + i * 380
            d.line((x_fondo, horizonte, x_frente, ALTO), fill=rejilla_color + (150,), width=3)
        avance = (t * 0.55) % 1.0
        for k in range(14):
            z = (k + avance) / 14
            y = horizonte + alto_suelo * (z ** 2.2)
            d.line((0, y, ANCHO, y), fill=rejilla_color + (int(60 + 140 * z),), width=2 + int(3 * z))

        # Cabecera
        aparece = _salida_suave(min(1, t / 0.5))
        _pegar(lienzo, c_marca, ANCHO / 2, 150 - 40 * (1 - aparece), opacidad=aparece)
        _pegar(lienzo, c_etiqueta, ANCHO / 2, 232, opacidad=aparece)

        # Cifra grande con entrada en rebote y un latido suave
        if t < inicio_cierre:
            e = _rebote(min(1, max(0, (t - 0.15) / 0.7)))
            latido = 1 + 0.025 * math.sin(t * 2 * math.pi * 0.9)
            _pegar(lienzo, c_cifra, ANCHO / 2, 660, escala=max(0.01, e * latido), opacidad=min(1, e))
            e2 = _salida_suave(min(1, max(0, (t - 0.6) / 0.5)))
            _pegar(lienzo, c_bajo, ANCHO / 2, 1010 + 40 * (1 - e2), opacidad=e2)
            _pegar(lienzo, c_dato, ANCHO / 2, 1120, opacidad=e2)

            # Subtítulo actual
            for a, b, txt in subtitulos:
                if a <= t < b:
                    pop = _salida_suave(min(1, (t - a) / 0.12))
                    _pegar(lienzo, capa_sub(txt), ANCHO / 2, 1460, escala=0.9 + 0.1 * pop)
                    break
            _pegar(lienzo, c_web, ANCHO / 2, ALTO - 120, opacidad=0.85)
        else:
            # Pantalla de cierre
            e = _rebote(min(1, (t - inicio_cierre) / 0.5))
            _pegar(lienzo, c_sigue, ANCHO / 2, 820, opacidad=min(1, e))
            _pegar(lienzo, c_cierre, ANCHO / 2, 960, escala=max(0.01, e))

        # Barra de progreso arriba
        d.rectangle((0, 0, int(ANCHO * t / duracion), 10), fill=acento)

        ffmpeg.stdin.write(lienzo.convert("RGB").tobytes())
        if n % (FPS * 5) == 0:
            print(f"  vídeo: {t:.0f}/{duracion:.0f} s")

    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("::error::ffmpeg no pudo montar el vídeo")
    print(f"Vídeo listo: {salida} ({duracion:.1f} s)")
    return duracion
