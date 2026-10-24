"""Canal de historia económica: monta el vídeo largo (horizontal) y sus Shorts a partir de un guion.

El guion es un archivo de guiones/ (por ejemplo guiones/corralito.yaml) con capítulos y escenas.
Cada escena tiene lo que dice la voz («voz») y lo que se ve («tipo» y sus datos).
Ver guiones/LEEME.md.

Genera en salida/:
    <guion>_largo.mp4          vídeo largo 1920x1080 para YouTube (calidad completa)
    <guion>_largo_movil.mp4    copia ligera para revisarlo en el móvil (Telegram)
    <guion>_largo.srt          subtítulos para subir a YouTube
    <guion>_descripcion.txt    título, descripción con capítulos (minutos) y fuentes
    <guion>_miniatura.png      miniatura 1280x720
    <guion>_short_NN.mp4/.txt  un Short vertical por cada capítulo marcado con «short: true»

No publica nada.

Variables:
    GUION         nombre del guion (sin .yaml)
    QUE           todo | largo | shorts
    SIN_VOZ=1     prueba rápida sin voz (tiempos calculados a ojo)
    VOZ_HISTORIA  voz de Gemini (vacío = la de canal_historia.yaml)
"""
import hashlib
import math
import os
import random
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml
from PIL import Image, ImageDraw

import sonido
from historia_visuales import (F_NUM, F_TIT, F_TXT, F_TXT_B, F_TXT_M, FPS, ajustar, caja, color, crear_pieza,
                               envolver, fuente, pegar, rebote, suave)

RAIZ = Path(__file__).resolve().parent.parent
GUIONES = RAIZ / "guiones"
SALIDA = Path("salida")
CACHE_VOZ = RAIZ / "cache_voz"

ANTES_VOZ = 0.30      # segundos de imagen antes de que hable la voz en cada escena
DESPUES_VOZ = 0.45    # y después
STING = 3.0           # cabecera del canal
TARJETA_CAP = 2.6     # tarjeta de cada capítulo
FINAL_SHORT = 2.8     # pantalla final de cada Short
FUNDIDO = 0.3         # fundido entre escenas

HORIZONTAL = {"W": 1920, "H": 1080, "zona": (110, 130, 1700, 760), "y_sub": 972, "ancho_sub": 1500}
VERTICAL = {"W": 1080, "H": 1920, "zona": (50, 320, 980, 1030), "y_sub": 1490, "ancho_sub": 940}


# =====================================================================
#  Canal y guion
# =====================================================================

def cargar_canal():
    canal = yaml.safe_load((RAIZ / "canal_historia.yaml").read_text(encoding="utf-8"))
    canal["tema"] = {k: tuple(v) for k, v in canal["colores"].items()}
    return canal


def cargar_guion(nombre):
    ruta = GUIONES / f"{nombre}.yaml"
    if not ruta.exists():
        hay = ", ".join(sorted(p.stem for p in GUIONES.glob("*.yaml")))
        raise SystemExit(f"::error::No existe guiones/{nombre}.yaml. Hay: {hay}")
    g = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    errores = []
    if not g.get("titulo"):
        errores.append("falta «titulo»")
    if not g.get("capitulos"):
        errores.append("faltan «capitulos»")
    fuentes = {str(f["id"]): f for f in g.get("fuentes") or []}

    def revisar(escenas, donde):
        for i, e in enumerate(escenas or [], 1):
            if not str(e.get("voz") or "").strip():
                errores.append(f"{donde}, escena {i}: falta «voz»")
            for f in _lista(e.get("fuente")):
                if str(f) not in fuentes:
                    errores.append(f"{donde}, escena {i}: la fuente {f} no está en «fuentes»")

    revisar(g.get("gancho"), "gancho")
    for c, cap in enumerate(g.get("capitulos") or [], 1):
        if not cap.get("titulo"):
            errores.append(f"capítulo {c}: falta «titulo»")
        if not cap.get("escenas"):
            errores.append(f"capítulo {c}: no tiene escenas")
        revisar(cap.get("escenas"), f"capítulo {c}")
        revisar(_lista(cap.get("gancho_short")), f"capítulo {c} (gancho del Short)")
    revisar(g.get("cierre"), "cierre")
    if errores:
        raise SystemExit("::error::El guion tiene errores:\n  - " + "\n  - ".join(errores))
    g["_fuentes"] = fuentes
    g["_nombre"] = nombre
    return g


def _lista(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def todas_las_escenas(g):
    """[(escena, capítulo o None)] en orden de lectura."""
    salida = [(e, None) for e in g.get("gancho") or []]
    for c, cap in enumerate(g["capitulos"]):
        salida += [(e, c) for e in _lista(cap.get("gancho_short"))]
        salida += [(e, c) for e in cap["escenas"]]
    salida += [(e, None) for e in g.get("cierre") or []]
    return salida


# =====================================================================
#  Voz (con caché: si el texto no cambia, no se vuelve a pedir)
# =====================================================================

def generar_voces(g, canal):
    escenas = [e for e, _ in todas_las_escenas(g)]
    if (os.environ.get("SIN_VOZ") or "").strip() == "1":
        sr = 24000
        print("Prueba SIN VOZ: tiempos calculados a ojo")
        for e in escenas:
            e["_audio"] = np.zeros(int(sr * max(1.8, len(str(e["voz"]).split()) / 2.5)), dtype=np.float32)
        return sr

    os.environ["GEMINI_VOZ"] = (os.environ.get("VOZ_HISTORIA") or "").strip() or canal["voz"]
    os.environ["GEMINI_ESTILO"] = canal["estilo_voz"]
    os.environ.setdefault("VOZ_MOTOR", "gemini")
    from motor_voz import crear_motor
    motor = crear_motor()
    sr = motor.sr
    CACHE_VOZ.mkdir(exist_ok=True)
    firma = f"{type(motor).__name__}|{getattr(motor, 'modelo', '')}|{getattr(motor, 'voz', '')}|{getattr(motor, 'estilo', '')}"
    nuevas = 0
    for i, e in enumerate(escenas, 1):
        texto = str(e.get("pronunciar") or e["voz"]).strip()
        clave = hashlib.sha1(f"{firma}|{texto}".encode("utf-8")).hexdigest()[:20]
        ruta = CACHE_VOZ / f"{clave}.wav"
        if ruta.exists():
            e["_audio"], _ = sf.read(ruta, dtype="float32")
            continue
        print(f"Voz {i}/{len(escenas)}")
        audio = motor.decir(texto)
        sf.write(ruta, audio, sr)
        e["_audio"] = audio
        nuevas += 1
    print(f"Voces: {len(escenas)} escenas · {nuevas} nuevas · {len(escenas) - nuevas} de la caché")
    return sr


# =====================================================================
#  Bloques: la línea de tiempo del vídeo
# =====================================================================

def _fuente_corta(g, e):
    ids = _lista(e.get("fuente"))
    if not ids:
        return ""
    return "Fuente: " + " · ".join(str(g["_fuentes"][str(i)].get("corta") or g["_fuentes"][str(i)].get("cita", ""))
                                   for i in ids)


def _bloque_escena(g, e, cap, sr, t):
    dur_voz = len(e["_audio"]) / sr
    return {"tipo": "escena", "escena": e, "cap": cap, "ini": t, "fin": t + ANTES_VOZ + dur_voz + DESPUES_VOZ,
            "voz_ini": t + ANTES_VOZ, "dur_voz": dur_voz, "fuente": _fuente_corta(g, e)}


def bloques_largo(g, sr, canal):
    bloques, t = [], 0.0
    for e in g.get("gancho") or []:
        b = _bloque_escena(g, e, None, sr, t)
        bloques.append(b)
        t = b["fin"]
    bloques.append({"tipo": "sting", "ini": t, "fin": t + STING, "cap": None})
    t += STING
    for c, cap in enumerate(g["capitulos"]):
        bloques.append({"tipo": "capitulo", "ini": t, "fin": t + TARJETA_CAP, "cap": c})
        t += TARJETA_CAP
        for e in cap["escenas"]:
            b = _bloque_escena(g, e, c, sr, t)
            bloques.append(b)
            t = b["fin"]
    for e in g.get("cierre") or []:
        b = _bloque_escena(g, e, None, sr, t)
        bloques.append(b)
        t = b["fin"]
    fin = float(canal.get("pantalla_final", 12))
    bloques.append({"tipo": "final", "ini": t, "fin": t + fin, "cap": None})
    return bloques


def bloques_short(g, sr, c):
    """Short de un capítulo: su gancho propio (si lo tiene) + sus escenas + pantalla final."""
    bloques, t = [], 0.0
    cap = g["capitulos"][c]
    for e in _lista(cap.get("gancho_short")) + cap["escenas"]:
        b = _bloque_escena(g, e, c, sr, t)
        bloques.append(b)
        t = b["fin"]
    bloques.append({"tipo": "final_short", "ini": t, "fin": t + FINAL_SHORT, "cap": c})
    return bloques


# =====================================================================
#  Subtítulos
# =====================================================================

def trozos_subtitulos(bloques, max_palabras, max_letras):
    """[(inicio, fin, texto)] repartiendo cada frase por letras dentro de su voz."""
    trozos = []
    for b in bloques:
        if b["tipo"] != "escena" or b["dur_voz"] <= 0:
            continue
        palabras = str(b["escena"]["voz"]).split()
        grupos, actual = [], []
        for p in palabras:
            if actual and (len(actual) >= max_palabras or len(" ".join(actual + [p])) > max_letras):
                grupos.append(actual)
                actual = []
            actual.append(p)
            if p[-1] in ".:;?!":
                grupos.append(actual)
                actual = []
        if actual:
            grupos.append(actual)
        letras = sum(len(" ".join(x)) + 1 for x in grupos) or 1
        t = b["voz_ini"]
        for x in grupos:
            texto = " ".join(x)
            d = b["dur_voz"] * (len(texto) + 1) / letras
            trozos.append((t, t + d, texto))
            t += d
    return trozos


def escribir_srt(trozos, ruta):
    def hora(s):
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    lineas = []
    for i, (a, b, txt) in enumerate(trozos, 1):
        lineas += [str(i), f"{hora(a)} --> {hora(b)}", txt, ""]
    Path(ruta).write_text("\n".join(lineas), encoding="utf-8")


class Subtitulos:
    def __init__(self, trozos, geo, tema):
        self.trozos, self.geo, self.tema = trozos, geo, tema
        self.vertical = geo["H"] > geo["W"]
        self.f = fuente(F_TIT if self.vertical else F_TXT, 62 if self.vertical else 44)
        self.cache = {}
        self.i = 0

    def capa(self, texto):
        if texto not in self.cache:
            lineas = envolver(texto, self.f, self.geo["ancho_sub"] - 60)
            alto_l = int(self.f.size * 1.25)
            w = int(max(self.f.getlength(l) for l in lineas)) + 56
            h = alto_l * len(lineas) + 26
            capa = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(capa)
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(0, 0, 0, 170))
            for k, l in enumerate(lineas):
                d.text(((w - self.f.getlength(l)) / 2, 10 + k * alto_l), l, font=self.f, fill=(255, 255, 255, 255))
            self.cache[texto] = capa
        return self.cache[texto]

    def dibujar(self, lienzo, t):
        while self.i < len(self.trozos) and self.trozos[self.i][1] <= t:
            self.i += 1
        if self.i < len(self.trozos):
            a, b, txt = self.trozos[self.i]
            if a <= t < b:
                pegar(lienzo, self.capa(txt), self.geo["W"] / 2, self.geo["y_sub"])


# =====================================================================
#  Fondos y pantallas fijas (cabecera, capítulo, final)
# =====================================================================

def fondo_base(geo, tema, semilla=0):
    W, H = geo["W"], geo["H"]
    y = np.linspace(0, 1, H)[:, None, None]
    c1, c2 = np.array(tema["fondo2"], np.float32), np.array(tema["fondo"], np.float32)
    col = c1 * (1 - y) * 0.75 + c2 * (0.25 + 0.75 * y)
    img = Image.fromarray(np.repeat(col, W, axis=1).clip(0, 255).astype(np.uint8)).convert("RGBA")
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    rnd = random.Random(semilla)
    r = int(min(W, H) * 0.55)
    x, yy = rnd.choice([(W * 0.85, H * 0.1), (W * 0.1, H * 0.15), (W * 0.9, H * 0.9)])
    d.ellipse((x - r, yy - r, x + r, yy + r), fill=color(tema, "acento", 34))
    from PIL import ImageFilter
    img.alpha_composite(capa.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(img)
    paso = 48
    for gx in range(paso // 2, W, paso):
        for gy in range(paso // 2, H, paso):
            d.point((gx, gy), fill=color(tema, "linea", 110))
    return img


class Pantallas:
    """Cabecera del canal, tarjeta de capítulo y pantallas finales."""

    def __init__(self, geo, tema, canal, g):
        self.geo, self.tema, self.canal, self.g = geo, tema, canal, g
        self.W, self.H = geo["W"], geo["H"]

    def sting(self, base, t, dur):
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        # Línea que sube como un gráfico
        rnd = random.Random(7)
        pts, v = [], 0.0
        for k in range(40):
            v += rnd.uniform(-0.6, 1.0)
            pts.append((W * 0.08 + W * 0.84 * k / 39, H * 0.78 - v * H * 0.012))
        r = suave(t / 1.6)
        n = max(2, int(len(pts) * r))
        d.line(pts[:n], fill=color(self.tema, "acento"), width=8, joint="curve")
        xe, ye = pts[n - 1]
        d.ellipse((xe - 14, ye - 14, xe + 14, ye + 14), fill=color(self.tema, "acento"))
        f, lineas, tam = ajustar(self.canal["marca"], F_TIT, 120, W - 200, 2, 50)
        a = suave((t - 0.5) / 0.6)
        y0 = H * 0.42 - tam * 1.15 * len(lineas) / 2
        for k, l in enumerate(lineas):
            d.text(((W - f.getlength(l)) / 2, y0 + k * tam * 1.15 + 30 * (1 - a)), l, font=f,
                   fill=color(self.tema, "texto", int(255 * a)))
        b = suave((t - 1.0) / 0.5)
        lema = caja("HISTORIA ECONÓMICA, CON DATOS", F_TXT_B, 36, color(self.tema, "fondo"), color(self.tema, "acento2"),
                    pad=(20, 10), radio=8)
        pegar(img, lema, W / 2, y0 + len(lineas) * tam * 1.15 + 60, b)
        salida = suave((t - (dur - 0.35)) / 0.35)
        if salida > 0:
            img = Image.blend(img, base, salida)
        return img

    def capitulo(self, base, t, dur, c):
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        vertical = H > W
        numero = f"{c + 1:02d}"
        fn = fuente(F_NUM, 300 if vertical else 280)
        a = suave(t / 0.5)
        x_num = W / 2 if vertical else W * 0.27
        y_num = H * 0.36 if vertical else H * 0.5
        c_num = fn.getbbox(numero)
        capa = Image.new("RGBA", (c_num[2] + 40, c_num[3] + 40), (0, 0, 0, 0))
        ImageDraw.Draw(capa).text((20 - c_num[0], 20 - c_num[1]), numero, font=fn, fill=(0, 0, 0, 0),
                                  stroke_width=5, stroke_fill=color(self.tema, "acento"))
        pegar(img, capa, x_num - 60 * (1 - a), y_num, a)
        titulo = str(self.g["capitulos"][c]["titulo"])
        ancho = W - 160 if vertical else W * 0.5
        f, lineas, tam = ajustar(titulo, F_TIT, 96, ancho, 3, 44)
        b = suave((t - 0.25) / 0.5)
        x0 = (W - ancho) / 2 if vertical else W * 0.45
        y0 = (H * 0.55 if vertical else H * 0.5 - tam * 1.15 * len(lineas) / 2 + 20)
        etiqueta = caja("CAPÍTULO", F_TXT_B, 32, color(self.tema, "fondo"), color(self.tema, "acento"), pad=(16, 8), radio=6)
        pegar(img, etiqueta, x0 + (ancho / 2 - etiqueta.width / 2 if vertical else 0), y0 - 80, b, centro=False)
        for k, l in enumerate(lineas):
            x = x0 + ((ancho - f.getlength(l)) / 2 if vertical else 0)
            d.text((x + 40 * (1 - b), y0 + k * tam * 1.15), l, font=f, fill=color(self.tema, "texto", int(255 * b)))
        d.rounded_rectangle((x0, y0 + len(lineas) * tam * 1.15 + 20, x0 + 160 * suave((t - 0.5) / 0.6),
                             y0 + len(lineas) * tam * 1.15 + 28), radius=4, fill=color(self.tema, "acento2"))
        return img

    def final(self, base, t, dur):
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        a = suave(t / 0.6)
        f = fuente(F_TIT, 84)
        txt = "Gracias por ver"
        d.text(((W - f.getlength(txt)) / 2, H * 0.12 + 20 * (1 - a)), txt, font=f, fill=color(self.tema, "texto", int(255 * a)))
        sub = caja("FUENTES Y DATOS EN LA DESCRIPCIÓN", F_TXT_B, 34, color(self.tema, "fondo"), color(self.tema, "acento2"),
                   pad=(20, 10), radio=8)
        pegar(img, sub, W / 2, H * 0.12 + 150, suave((t - 0.3) / 0.5))
        # Huecos para los elementos de pantalla final de YouTube (otros vídeos y suscripción)
        q = suave((t - 0.6) / 0.6)
        for x in (W * 0.27, W * 0.73):
            d.rounded_rectangle((x - 400, H * 0.45, x + 400, H * 0.45 + 450), radius=24,
                                outline=color(self.tema, "linea", int(255 * q)), width=4)
        marca = fuente(F_TXT_B, 32)
        d.text(((W - marca.getlength(self.canal["marca"])) / 2, H - 70), self.canal["marca"], font=marca,
               fill=color(self.tema, "suave", int(255 * a)))
        return img

    def final_short(self, base, t, dur):
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        a = rebote(min(1, t / 0.5))
        f, lineas, tam = ajustar("Historia completa en el canal", F_TIT, 104, W - 140, 3, 50)
        y0 = H * 0.36
        for k, l in enumerate(lineas):
            d.text(((W - f.getlength(l)) / 2, y0 + k * tam * 1.15), l, font=f, fill=color(self.tema, "texto", int(255 * min(1, a))))
        marca = caja(self.canal["marca"], F_TXT_B, 40, color(self.tema, "fondo"), color(self.tema, "acento"), pad=(22, 12), radio=10)
        pegar(img, marca, W / 2, y0 + len(lineas) * tam * 1.15 + 90, min(1, a))
        return img


# =====================================================================
#  Audio
# =====================================================================

def _a_48k(x, sr):
    if sr == sonido.SR:
        return x.astype(np.float32)
    n = int(len(x) * sonido.SR / sr)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def mezclar_audio(bloques, sr, duracion, carpeta):
    n = int(duracion * sonido.SR) + sonido.SR
    voz = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    woosh = [sonido.whoosh(dur=0.5, semilla=k) * 0.45 for k in range(4)]

    def poner(pista, seg, s):
        a = int(seg * sonido.SR)
        b = min(n, a + len(s))
        if 0 <= a < n:
            pista[a:b] += s[: b - a]

    for i, b in enumerate(bloques):
        if b["tipo"] == "escena":
            poner(voz, b["voz_ini"], _a_48k(b["escena"]["_audio"], sr))
            if b["escena"].get("tipo") == "cifra":
                poner(fx, b["ini"] + 0.1, sonido.pop() * 0.6)
        if b["tipo"] in ("sting", "capitulo"):
            poner(fx, b["ini"], sonido.golpe() * 0.7)
        if i > 0:
            poner(fx, max(0, b["ini"] - 0.2), woosh[i % 4])
    musica = sonido.musica(n / sonido.SR, "datos", bpm=86)[:n]
    # La música baja cuando habla la voz (media móvil con suma acumulada: rápido aunque dure 15 min)
    v = np.abs(voz)
    ventana = int(0.4 * sonido.SR)
    cs = np.cumsum(np.concatenate([[0.0], v]))
    env = (cs[ventana:] - cs[:-ventana]) / ventana
    env = np.concatenate([env, np.full(len(v) - len(env), env[-1] if len(env) else 0)])
    env = env / (env.max() + 1e-9)
    musica = musica * 0.30 * (1 - 0.7 * np.clip(env * 4, 0, 1))
    mezcla = voz + fx * 0.5 + musica
    mezcla = mezcla[: int(duracion * sonido.SR)]
    mezcla = mezcla / max(1.0, float(np.abs(mezcla).max()) / 0.95)
    bruto, final = carpeta / "mezcla.wav", carpeta / "mezcla_norm.wav"
    sf.write(bruto, mezcla.astype(np.float32), sonido.SR)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(bruto), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(final)], check=True)
    return final


# =====================================================================
#  Montaje
# =====================================================================

def montar(g, canal, bloques, sr, geo, salida, subtitulos=False, titulo_arriba=None):
    """Monta un vídeo (largo o Short) a partir de sus bloques."""
    from pexels import buscar_clip

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    carpeta = Path(tempfile.mkdtemp())
    tema = canal["tema"]
    W, H = geo["W"], geo["H"]
    vertical = H > W
    duracion = bloques[-1]["fin"]
    n_frames = int(math.ceil(duracion * FPS))
    audio = mezclar_audio(bloques, sr, duracion, carpeta)

    base = fondo_base(geo, tema, semilla=len(g["titulo"]))
    pantallas = Pantallas(geo, tema, canal, g)
    zx, zy, zw, zh = geo["zona"]
    trozos = trozos_subtitulos(bloques, 5 if vertical else 9, 30 if vertical else 60)
    subs = Subtitulos(trozos, geo, tema) if subtitulos else None

    # Elementos fijos
    marca = caja(canal["marca"], F_TXT_B, 30 if vertical else 24, color(tema, "texto"), None, pad=(0, 0))
    punto = Image.new("RGBA", (26, 26), (0, 0, 0, 0))
    ImageDraw.Draw(punto).rounded_rectangle((0, 0, 25, 25), radius=6, fill=color(tema, "acento"))
    caps_cache = {}
    fuente_cache = {}
    f_fuente = fuente(F_TXT_M, 26 if vertical else 22)

    def etiqueta_cap(c):
        if c not in caps_cache:
            texto = f"CAPÍTULO {c + 1} · {str(g['capitulos'][c]['titulo']).upper()}"
            if vertical:
                f, lineas, tam = ajustar(str(g["capitulos"][c]["titulo"]), F_TIT, 52, W - 140, 2, 30)
                capa = Image.new("RGBA", (W, int(tam * 1.2 * len(lineas)) + 20), (0, 0, 0, 0))
                dd = ImageDraw.Draw(capa)
                for k, l in enumerate(lineas):
                    dd.text(((W - f.getlength(l)) / 2, k * tam * 1.2), l, font=f, fill=color(tema, "acento2"))
                caps_cache[c] = capa
            else:
                caps_cache[c] = caja(texto, F_TXT_B, 22, color(tema, "suave"), None, pad=(0, 0))
        return caps_cache[c]

    def etiqueta_fuente(txt):
        if txt not in fuente_cache:
            lineas = envolver(txt, f_fuente, (W - 120))
            capa = Image.new("RGBA", (W, int(f_fuente.size * 1.3 * len(lineas)) + 8), (0, 0, 0, 0))
            dd = ImageDraw.Draw(capa)
            for k, l in enumerate(lineas):
                x = (W - f_fuente.getlength(l)) / 2 if vertical else 60
                dd.text((x, k * f_fuente.size * 1.3), l, font=f_fuente, fill=color(tema, "suave", 230))
            fuente_cache[txt] = capa
        return fuente_cache[txt]

    # Marcas de capítulo en la barra de progreso
    inicios_cap = [b["ini"] for b in bloques if b["tipo"] == "capitulo"]

    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(audio),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{n_frames / FPS:.3f}", "-movflags", "+faststart", str(salida)],
        stdin=subprocess.PIPE,
    )

    bi, pieza, anterior, ultimo = -1, None, None, None
    clips_usados = []
    inicio = time.time()
    for nf in range(n_frames):
        t = nf / FPS
        while bi + 1 < len(bloques) and t >= bloques[bi + 1]["ini"]:
            bi += 1
            if pieza:
                pieza.cerrar()
            pieza = None
            anterior = ultimo
            b = bloques[bi]
            if b["tipo"] == "escena":
                e = b["escena"]
                clip = None
                if e.get("tipo") == "archivo" and e.get("buscar"):
                    clip = buscar_clip(str(e["buscar"]), semilla=f"{g['_nombre']}-{bi}", minimo_seg=4,
                                       orientacion="portrait" if vertical else "landscape")
                    if clip:
                        clips_usados.append(clip)
                pieza = crear_pieza(e, zw, zh, tema, f"{g['_nombre']}-{bi}", (W, H), clip=clip, dur=b["fin"] - b["ini"])
        b = bloques[bi]
        tl, dur = t - b["ini"], b["fin"] - b["ini"]

        if b["tipo"] == "sting":
            lienzo = pantallas.sting(base, tl, dur)
        elif b["tipo"] == "capitulo":
            lienzo = pantallas.capitulo(base, tl, dur, b["cap"])
        elif b["tipo"] == "final":
            lienzo = pantallas.final(base, tl, dur)
        elif b["tipo"] == "final_short":
            lienzo = pantallas.final_short(base, tl, dur)
        else:
            lienzo = pieza.fondo(tl) if pieza.fondo_propio else base.copy()
            capa = pieza.cuadro(tl, dur)
            if not pieza.fondo_propio:
                z = 1.0 + 0.025 * tl / max(dur, 0.1)  # zoom muy lento para que la imagen respire
                if z > 1.001:
                    nw, nh = int(zw * z), int(zh * z)
                    capa = capa.resize((nw, nh), Image.BILINEAR)
                    lienzo.alpha_composite(capa, (int(zx - (nw - zw) / 2), int(zy - (nh - zh) / 2)))
                else:
                    lienzo.alpha_composite(capa, (zx, zy))
            else:
                lienzo.alpha_composite(capa, (zx, zy))
            if b["fuente"]:
                capa_f = etiqueta_fuente(b["fuente"])
                lienzo.alpha_composite(capa_f, (0, (H - 150 if vertical else H - 50) - capa_f.height // 2))

        # Cabecera fija: marca y capítulo
        if b["tipo"] not in ("sting", "final", "final_short"):
            if vertical:
                pegar(lienzo, marca, W / 2 + 18, 110)
                lienzo.alpha_composite(punto, (int(W / 2 - marca.width / 2 - 24), 97))
                if b.get("cap") is not None:
                    lienzo.alpha_composite(etiqueta_cap(b["cap"]), (0, 170))
            else:
                lienzo.alpha_composite(punto, (60, 46))
                lienzo.alpha_composite(marca, (100, 48))
                if b.get("cap") is not None and b["tipo"] != "capitulo":
                    capa_c = etiqueta_cap(b["cap"])
                    lienzo.alpha_composite(capa_c, (W - 60 - capa_c.width, 50))
        if subs:
            subs.dibujar(lienzo, t)

        # Barra de progreso (en el largo, con las marcas de los capítulos)
        d = ImageDraw.Draw(lienzo)
        if vertical:
            d.rectangle((0, 0, int(W * t / duracion), 10), fill=color(tema, "acento"))
        else:
            d.rectangle((0, H - 6, W, H), fill=color(tema, "panel"))
            d.rectangle((0, H - 6, int(W * t / duracion), H), fill=color(tema, "acento"))
            for x in inicios_cap:
                xx = int(W * x / duracion)
                d.rectangle((xx - 2, H - 6, xx + 2, H), fill=color(tema, "fondo"))

        # Fundido corto con la escena anterior
        if anterior is not None and tl < FUNDIDO and bi > 0:
            lienzo = Image.blend(anterior, lienzo, suave(tl / FUNDIDO))
        ultimo = lienzo
        ffmpeg.stdin.write(lienzo.convert("RGB").tobytes())
        if nf % (FPS * 30) == 0:
            pasado = time.time() - inicio
            print(f"  {salida.name}: {t:.0f}/{duracion:.0f} s de vídeo ({pasado:.0f} s montando)")

    if pieza:
        pieza.cerrar()
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise SystemExit("::error::ffmpeg no pudo montar el vídeo")
    print(f"Vídeo listo: {salida} ({duracion:.1f} s) en {time.time() - inicio:.0f} s")
    return {"duracion": duracion, "trozos": trozos, "clips": clips_usados}


# =====================================================================
#  Textos de publicación, miniatura y copia ligera
# =====================================================================

def minutos(s):
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def descripcion(g, bloques, clips):
    lineas = [str(g["titulo"]), ""]
    if g.get("descripcion"):
        lineas += [str(g["descripcion"]).strip(), ""]
    lineas.append("Capítulos:")
    caps = [b for b in bloques if b["tipo"] == "capitulo"]
    hay_intro = caps and caps[0]["ini"] >= 10
    if hay_intro:
        lineas.append("0:00 Introducción")
    for k, b in enumerate(caps):
        t = 0 if (k == 0 and not hay_intro) else b["ini"]
        lineas.append(f"{minutos(t)} {g['capitulos'][b['cap']]['titulo']}")
    lineas.append("")
    if g["_fuentes"]:
        lineas.append("Fuentes:")
        for f in g["_fuentes"].values():
            linea = f"[{f['id']}] {f.get('cita') or f.get('corta')}"
            if f.get("url"):
                linea += f" — {f['url']}"
            lineas.append(linea)
        lineas.append("")
    if clips:
        lineas.append("Clips de archivo de Pixabay / Pexels (licencia libre). Gráficos y música: originales del canal.")
        lineas.append("")
    if g.get("hashtags"):
        lineas.append(str(g["hashtags"]))
    return "\n".join(lineas)


def miniatura(g, canal, ruta):
    tema = canal["tema"]
    geo = {"W": 1280, "H": 720}
    img = fondo_base(geo, tema, semilla=3)
    d = ImageDraw.Draw(img)
    m = g.get("miniatura") or {}
    texto = str(m.get("texto") or g["titulo"])
    resaltar = {p.strip(".,:;¿?¡!").lower() for p in str(m.get("resaltar") or "").split()}
    cifra = m.get("cifra")
    ancho = 700 if cifra else 1140
    f, lineas, tam = ajustar(texto.upper(), F_TIT, 110, ancho, 3, 50)
    alto_l = tam * 1.15
    y0 = (720 - alto_l * len(lineas)) / 2
    asc = f.getbbox("Á")[1]
    for k, l in enumerate(lineas):
        x = 60
        for p in l.split():
            w = f.getlength(p)
            if p.strip(".,:;¿?¡!").lower() in resaltar:
                d.rounded_rectangle((x - 10, y0 + k * alto_l + asc - 8, x + w + 10, y0 + k * alto_l + tam * 1.08),
                                    radius=10, fill=color(tema, "acento2"))
                d.text((x, y0 + k * alto_l), p, font=f, fill=color(tema, "fondo"))
            else:
                d.text((x, y0 + k * alto_l), p, font=f, fill=color(tema, "texto"), stroke_width=3, stroke_fill=(0, 0, 0, 200))
            x += w + f.getlength(" ")
    if cifra:
        tam_c = 230
        fc = fuente(F_NUM, tam_c)
        while fc.getlength(str(cifra)) > 480 and tam_c > 80:
            tam_c -= 10
            fc = fuente(F_NUM, tam_c)
        c = fc.getbbox(str(cifra))
        d.text((1280 - 60 - (c[2] - c[0]) - c[0], 360 - (c[3] - c[1]) / 2 - c[1]), str(cifra), font=fc,
               fill=color(tema, "acento"), stroke_width=4, stroke_fill=(0, 0, 0, 220))
    marca = caja(canal["marca"], F_TXT_B, 26, color(tema, "fondo"), color(tema, "acento"), pad=(14, 8), radio=6)
    img.alpha_composite(marca, (60, 720 - 60 - marca.height))
    img.convert("RGB").save(ruta)


def copia_ligera(entrada, salida, duracion, max_mb=45):
    """Copia en 720p que cabe en Telegram (límite de 50 MB para bots)."""
    total = max_mb * 8192 / max(duracion, 1)
    video = int(total - 96)
    if video < 180:
        print("::warning::El vídeo es demasiado largo para mandarlo por Telegram: descárgalo de GitHub (Artifacts)")
        return False
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(entrada), "-vf", "scale=1280:720",
                    "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{video}k", "-maxrate", f"{int(video * 1.4)}k",
                    "-bufsize", f"{video * 2}k", "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", str(salida)],
                   check=True)
    mb = Path(salida).stat().st_size / 1024 / 1024
    print(f"Copia ligera: {salida} ({mb:.1f} MB)")
    return mb < 49


# =====================================================================
#  Principal
# =====================================================================

def main():
    nombre = (os.environ.get("GUION") or "ejemplo").strip()
    que = (os.environ.get("QUE") or "todo").strip()
    canal = cargar_canal()
    g = cargar_guion(nombre)
    SALIDA.mkdir(exist_ok=True)
    inicio = time.time()
    sr = generar_voces(g, canal)

    if que in ("todo", "largo"):
        bloques = bloques_largo(g, sr, canal)
        print(f"Vídeo largo: {len(bloques)} bloques, {bloques[-1]['fin'] / 60:.1f} minutos")
        r = montar(g, canal, bloques, sr, HORIZONTAL, SALIDA / f"{nombre}_largo.mp4",
                   subtitulos=bool(canal.get("subtitulos_largo")))
        escribir_srt(r["trozos"], SALIDA / f"{nombre}_largo.srt")
        (SALIDA / f"{nombre}_descripcion.txt").write_text(descripcion(g, bloques, r["clips"]), encoding="utf-8")
        miniatura(g, canal, SALIDA / f"{nombre}_miniatura.png")
        copia_ligera(SALIDA / f"{nombre}_largo.mp4", SALIDA / f"{nombre}_largo_movil.mp4", r["duracion"])

    if que in ("todo", "shorts"):
        for c, cap in enumerate(g["capitulos"]):
            if not cap.get("short", True):
                continue
            bloques = bloques_short(g, sr, c)
            base = SALIDA / f"{nombre}_short_{c + 1:02d}"
            r = montar(g, canal, bloques, sr, VERTICAL, base.with_suffix(".mp4"),
                       subtitulos=bool(canal.get("subtitulos_shorts", True)))
            dur = r["duracion"]
            notas = []
            notas.append("✅ Más de 1 minuto: vale para el programa de pagos de TikTok" if dur > 61
                         else "⚠️ Menos de 1 minuto: TikTok no lo paga (alarga el capítulo si quieres cobrar allí)")
            notas.append("✅ Vale para YouTube Shorts (hasta 3 minutos)" if dur <= 180
                         else "⚠️ Pasa de 3 minutos: YouTube no lo trataría como Short")
            titulo = str(cap.get("titulo_short") or cap["titulo"])
            texto = f"{titulo}\n\nHistoria completa en el canal.\n\n{g.get('hashtags', '')}\n\n— Dura {dur:.0f} s\n" + "\n".join(notas)
            base.with_suffix(".txt").write_text(texto, encoding="utf-8")
    print(f"Todo listo en {(time.time() - inicio) / 60:.1f} minutos")


if __name__ == "__main__":
    main()
