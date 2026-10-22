"""Vídeo vertical sobrio para las webs de datos (Al Final de Mes y Dinero en Claro).

Mismo sistema que video.py (voz por frases, subtítulos sincronizados), pero con el
estilo de cada web: sus colores, la tipografía IBM Plex y un gráfico de datos que
se dibuja poco a poco.

Tema (diccionario):
    marca, etiqueta, titular, cifra (número), formato (función número -> texto),
    unidad, grafico, nota (fuente del dato), web, colores (ver COLORES_*).
Gráficos:
    {"tipo": "barras", "valores": [...], "etiquetas": {indice: "texto"}, "colores": {indice: color}}
    {"tipo": "linea", "series": [[...], [...]], "nombres": ["...", "..."], "etiquetas": {indice: "texto"}}
    {"tipo": "ranking", "filas": [(nombre, valor, "texto valor"), ...]}
"""
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from video import ALTO, ANCHO, COLA, FPS, _pegar, _preparar_audio, _rebote, _salida_suave, _trozos

FUENTES = Path(__file__).resolve().parent.parent / "fuentes"
SERIF = str(FUENTES / "IBMPlexSerif-SemiBold.ttf")
SANS_B = str(FUENTES / "IBMPlexSans-Bold.ttf")
SANS_S = str(FUENTES / "IBMPlexSans-SemiBold.ttf")
SANS_M = str(FUENTES / "IBMPlexSans-Medium.ttf")

BLANCO = (255, 255, 255)
TINTA = (28, 32, 36)
GRIS = (91, 99, 107)
RAYA = (223, 227, 230)
VERDE = (46, 122, 78)
ROJO = (179, 67, 47)
OCRE = (196, 136, 28)

COLORES_AFDM = {"fondo": (8, 68, 54), "fondo2": (11, 93, 75), "marca": (11, 93, 75), "acento": OCRE}
COLORES_DEC = {"fondo": (22, 58, 92), "fondo2": (31, 78, 121), "marca": (31, 78, 121), "acento": OCRE}


def _f(ruta, tam):
    return ImageFont.truetype(ruta, tam)


def _envolver(texto, fuente, max_ancho):
    lineas, actual = [], ""
    for p in texto.split():
        prueba = (actual + " " + p).strip()
        if fuente.getlength(prueba) <= max_ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def _bloque(texto, ruta, tam, color, max_ancho, interlineado=1.18, centrado=True):
    """Texto en varias líneas como capa RGBA."""
    f = _f(ruta, tam)
    lineas = _envolver(texto, f, max_ancho)
    while len(lineas) > 3 and tam > 30:
        tam -= 4
        f = _f(ruta, tam)
        lineas = _envolver(texto, f, max_ancho)
    alto_l = int(tam * interlineado)
    capa = Image.new("RGBA", (max_ancho + 20, alto_l * len(lineas) + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    for i, l in enumerate(lineas):
        x = (capa.width - f.getlength(l)) / 2 if centrado else 10
        d.text((x, 10 + i * alto_l), l, font=f, fill=color + (255,))
    return capa


def _linea_texto(texto, ruta, tam, color):
    f = _f(ruta, tam)
    c = f.getbbox(texto)
    capa = Image.new("RGBA", (c[2] - c[0] + 20, c[3] - c[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((10 - c[0], 10 - c[1]), texto, font=f, fill=color + (255,))
    return capa


def _subtitulo(texto):
    f = _f(SANS_B, 66)
    lineas = _envolver(texto, f, ANCHO - 200)
    alto_l = 82
    w = int(max(f.getlength(l) for l in lineas)) + 70
    h = alto_l * len(lineas) + 36
    capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=22, fill=(0, 0, 0, 150))
    for i, l in enumerate(lineas):
        d.text(((w - f.getlength(l)) / 2, 14 + i * alto_l), l, font=f, fill=(255, 255, 255, 255))
    return capa


# ---------- gráficos (se dibujan una vez; luego se van descubriendo) ----------

def _grafico(g, ancho, alto, acento):
    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.rounded_rectangle((0, 0, ancho - 1, alto - 1), radius=28, fill=BLANCO + (255,))
    pad_x, pad_top, pad_bot = 50, 70, 70
    x0, x1, y0, y1 = pad_x, ancho - pad_x, pad_top, alto - pad_bot
    f_eti = _f(SANS_M, 30)
    if g.get("titulo"):
        d.text((pad_x, 22), g["titulo"], font=_f(SANS_S, 30), fill=GRIS)

    if g["tipo"] == "barras":
        v = g["valores"]
        top = max(v) * 1.1 or 1
        n = len(v)
        paso = (x1 - x0) / n
        for i, val in enumerate(v):
            h = (y1 - y0) * max(val, 0) / top
            color = g.get("colores", {}).get(i, (200, 206, 211))
            d.rounded_rectangle((x0 + i * paso + 4, y1 - h, x0 + (i + 1) * paso - 4, y1), radius=6, fill=color)
        for i, txt in g.get("etiquetas", {}).items():
            w = f_eti.getlength(txt)
            d.text((x0 + (i + 0.5) * paso - w / 2, y1 + 14), txt, font=f_eti, fill=GRIS)

    elif g["tipo"] == "linea":
        series = g["series"]
        todos = [x for s in series for x in s]
        lo, hi = min(todos), max(todos)
        margen = (hi - lo) * 0.12 or 1
        lo, hi = lo - margen, hi + margen
        y0 += 30
        for k in range(4):
            y = y0 + (y1 - y0) * k / 3
            d.line((x0, y, x1, y), fill=RAYA, width=2)
        colores = [acento, (160, 168, 175)]
        for si, s in reversed(list(enumerate(series))):
            n = len(s)
            pts = [(x0 + (x1 - x0) * i / max(1, n - 1), y1 - (y1 - y0) * (val - lo) / (hi - lo)) for i, val in enumerate(s)]
            d.line(pts, fill=colores[si % 2], width=8 if si == 0 else 6, joint="curve")
            if si == 0:
                xe, ye = pts[-1]
                d.ellipse((xe - 14, ye - 14, xe + 14, ye + 14), fill=colores[0])
        for i, txt in g.get("etiquetas", {}).items():
            n = len(series[0])
            x = x0 + (x1 - x0) * i / max(1, n - 1)
            w = f_eti.getlength(txt)
            d.text((min(max(x - w / 2, x0), x1 - w), y1 + 14), txt, font=f_eti, fill=GRIS)
        if g.get("nombres"):
            x = pad_x
            for si, nombre in enumerate(g["nombres"]):
                d.rounded_rectangle((x, 30 + (40 if g.get("titulo") else 0), x + 34, 40 + (40 if g.get("titulo") else 0)), radius=4, fill=colores[si % 2])
                d.text((x + 46, 18 + (40 if g.get("titulo") else 0)), nombre, font=f_eti, fill=TINTA)
                x += 46 + f_eti.getlength(nombre) + 50

    elif g["tipo"] == "ranking":
        filas = g["filas"]
        y0 = pad_top - 10 if g.get("titulo") else 40
        alto_f = (alto - y0 - 30) / len(filas)
        f_nom = _f(SANS_S, 38 if len(filas) <= 5 else 32)
        f_val = _f(SANS_B, 40 if len(filas) <= 5 else 34)
        maximo = max(abs(f[1]) for f in filas) or 1
        col_nom = 400
        for i, fila in enumerate(filas):
            nombre, val, txt = fila[:3]
            color = fila[3] if len(fila) > 3 else acento
            yc = y0 + alto_f * (i + 0.5)
            nom = nombre
            while f_nom.getlength(nom) > col_nom - 20 and len(nom) > 4:
                nom = nom[:-2]
            if nom != nombre:
                nom = nom.rstrip() + "…"
            d.text((pad_x, yc - 24), nom, font=f_nom, fill=TINTA)
            ancho_barra = (ancho - pad_x * 2 - col_nom - 190) * abs(val) / maximo
            d.rounded_rectangle((pad_x + col_nom, yc - 20, pad_x + col_nom + max(8, ancho_barra), yc + 20), radius=8, fill=color)
            d.text((pad_x + col_nom + max(8, ancho_barra) + 16, yc - 25), txt, font=f_val, fill=TINTA)
    return capa


# ---------- montaje ----------

def montar(frases, audios, sr, tema, salida, trozos_voz=None):
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    carpeta = Path(tempfile.mkdtemp())
    audio, tiempos, duracion = _preparar_audio(frases, audios, sr, carpeta, trozos_voz)
    n_frames = int(math.ceil(duracion * FPS))
    col = tema["colores"]

    # Fondo: color de la web con un degradado muy suave y una franja de acento
    fondo = Image.new("RGBA", (ANCHO, ALTO), col["fondo"] + (255,))
    d = ImageDraw.Draw(fondo)
    for y in range(0, ALTO, 4):
        t = y / ALTO
        c = tuple(int(col["fondo2"][k] * (1 - t) + col["fondo"][k] * t) for k in range(3))
        d.rectangle((0, y, ANCHO, y + 4), fill=c + (255,))
    d.rectangle((0, 0, ANCHO, 14), fill=col["acento"] + (255,))

    c_marca = _linea_texto(tema["marca"], SERIF, 58, BLANCO)
    c_etiqueta = _linea_texto(tema["etiqueta"].upper(), SANS_S, 34, col["acento"])
    c_titular = _bloque(tema["titular"], SERIF, 66, BLANCO, ANCHO - 140)
    c_unidad = _bloque(tema.get("unidad", ""), SANS_M, 44, (215, 225, 222), ANCHO - 160)
    c_graf = _grafico(tema["grafico"], ANCHO - 120, 560, col["marca"])
    c_nota = _bloque(tema.get("nota", ""), SANS_M, 28, (190, 205, 200), ANCHO - 160)
    c_web = _linea_texto(tema["web"], SANS_S, 46, BLANCO)
    c_cierre1 = _linea_texto("Todos los datos en", SANS_M, 54, (215, 225, 222))
    c_cierre2 = _linea_texto(tema["web"], SERIF, 96, BLANCO)
    c_aviso = _bloque(tema.get("aviso", ""), SANS_M, 34, (200, 212, 208), ANCHO - 200)

    y_tit = 330
    y_cifra = y_tit + c_titular.height // 2 + 170
    y_unidad = y_cifra + 150
    y_graf = y_unidad + c_unidad.height // 2 + 40 + c_graf.height // 2
    y_sub = y_graf + c_graf.height // 2 + 130

    subtitulos = []
    for ini, fin, frase in tiempos:
        trozos = _trozos(frase, max_palabras=6)
        letras = sum(len(x) for x in trozos)
        t = ini
        for x in trozos:
            dd = (fin - ini) * len(x) / letras
            subtitulos.append((t, t + dd, x))
            t += dd
    cache = {}

    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
         "-i", str(audio),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{n_frames / FPS:.3f}", "-movflags", "+faststart", str(salida)],
        stdin=subprocess.PIPE,
    )

    def entra(t, desde, dur=0.5):
        return _salida_suave(min(1, max(0, (t - desde) / dur)))

    inicio_cierre = duracion - COLA - 0.2
    ultima_cifra = None
    for n in range(n_frames):
        t = n / FPS
        lienzo = fondo.copy()
        if t < inicio_cierre:
            e = entra(t, 0)
            _pegar(lienzo, c_marca, ANCHO / 2, 110, opacidad=e)
            _pegar(lienzo, c_etiqueta, ANCHO / 2, 190, opacidad=e)
            e = entra(t, 0.15)
            _pegar(lienzo, c_titular, ANCHO / 2, y_tit + 30 * (1 - e), opacidad=e)

            # Cifra que cuenta desde 0 hasta el dato
            p = entra(t, 0.4, 1.1)
            valor = tema["cifra"] * p
            texto = tema["formato"](valor if p < 1 else tema["cifra"])
            if texto != ultima_cifra:
                c_cifra = _linea_texto(texto, SANS_B, 190, BLANCO)
                ultima_cifra = texto
            _pegar(lienzo, c_cifra, ANCHO / 2, y_cifra, escala=0.85 + 0.15 * _rebote(min(1, p * 1.2)), opacidad=min(1, p * 3))
            _pegar(lienzo, c_unidad, ANCHO / 2, y_unidad, opacidad=entra(t, 0.9))

            # Gráfico que se descubre
            r = entra(t, 1.0, 1.4)
            if r > 0:
                g = tema["grafico"]["tipo"]
                if g == "barras":
                    h = max(1, int(c_graf.height * r))
                    trozo = Image.new("RGBA", c_graf.size, (0, 0, 0, 0))
                    trozo.paste(c_graf.crop((0, c_graf.height - h, c_graf.width, c_graf.height)), (0, c_graf.height - h))
                    # fondo blanco completo y barras creciendo desde abajo
                    tarjeta = Image.new("RGBA", c_graf.size, (0, 0, 0, 0))
                    ImageDraw.Draw(tarjeta).rounded_rectangle((0, 0, c_graf.width - 1, c_graf.height - 1), radius=28, fill=BLANCO + (255,))
                    tarjeta.alpha_composite(trozo)
                else:
                    w = max(1, int(c_graf.width * r))
                    tarjeta = Image.new("RGBA", c_graf.size, (0, 0, 0, 0))
                    ImageDraw.Draw(tarjeta).rounded_rectangle((0, 0, c_graf.width - 1, c_graf.height - 1), radius=28, fill=BLANCO + (255,))
                    tarjeta.alpha_composite(c_graf.crop((0, 0, w, c_graf.height)), (0, 0))
                _pegar(lienzo, tarjeta, ANCHO / 2, y_graf + 40 * (1 - entra(t, 1.0, 0.4)), opacidad=entra(t, 1.0, 0.3))

            for a, b, txt in subtitulos:
                if a <= t < b:
                    if txt not in cache:
                        cache[txt] = _subtitulo(txt)
                    _pegar(lienzo, cache[txt], ANCHO / 2, y_sub, escala=0.94 + 0.06 * entra(t, a, 0.12))
                    break
            _pegar(lienzo, c_nota, ANCHO / 2, ALTO - 190, opacidad=0.9)
            _pegar(lienzo, c_web, ANCHO / 2, ALTO - 100)
        else:
            e = _rebote(min(1, (t - inicio_cierre) / 0.5))
            _pegar(lienzo, c_marca, ANCHO / 2, 110)
            _pegar(lienzo, c_cierre1, ANCHO / 2, 820, opacidad=min(1, e))
            _pegar(lienzo, c_cierre2, ANCHO / 2, 940, escala=max(0.01, e))
            if tema.get("aviso"):
                _pegar(lienzo, c_aviso, ANCHO / 2, 1120, opacidad=min(1, e))

        d = ImageDraw.Draw(lienzo)
        d.rectangle((0, ALTO - 10, int(ANCHO * t / duracion), ALTO), fill=col["acento"] + (255,))
        ffmpeg.stdin.write(lienzo.convert("RGB").tobytes())
        if n % (FPS * 5) == 0:
            print(f"  vídeo: {t:.0f}/{duracion:.0f} s")

    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("::error::ffmpeg no pudo montar el vídeo")
    print(f"Vídeo listo: {salida} ({duracion:.1f} s)")
    return duracion
