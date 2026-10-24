"""Canal de historia económica: monta el vídeo largo (horizontal) y sus Shorts a partir de un guion.

El guion es un archivo de guiones/ (por ejemplo guiones/corralito.yaml) con capítulos y escenas.
Cada escena tiene lo que dice la voz («voz») y lo que se ve («tipo» y sus datos).
Ver guiones/LEEME.md.

Genera en salida/:
    <guion>_largo.mp4          vídeo largo 1920x1080 para YouTube (calidad completa)
    <guion>_largo_movil.mp4    copia ligera para revisarlo en el móvil (Telegram)
    <guion>_largo.srt          subtítulos para subir a YouTube
    <guion>_descripcion.txt    título, descripción con capítulos (minutos), fuentes y créditos
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
from PIL import Image, ImageDraw, ImageFilter

import imagenes
import sonido
from historia_visuales import FPS, Contexto, _grano, alfa_capa, crear_pieza, duotono, envolver, pegar, recortar_a, rebote, suave

RAIZ = Path(__file__).resolve().parent.parent
GUIONES = RAIZ / "guiones"
SALIDA = Path("salida")
CACHE_VOZ = RAIZ / "cache_voz"

ANTES_VOZ = 0.35      # segundos de imagen antes de que hable la voz en cada escena
DESPUES_VOZ = 0.5     # y después
STING = 3.2           # cabecera del canal
TARJETA_CAP = 2.8     # tarjeta de cada capítulo
FINAL_SHORT = 2.8     # pantalla final de cada Short
FUNDIDO = 0.35        # fundido entre escenas

HORIZONTAL = {"W": 1920, "H": 1080, "y_sub": 985, "ancho_sub": 1500}
VERTICAL = {"W": 1080, "H": 1920, "y_sub": 1500, "ancho_sub": 940}


# =====================================================================
#  Canal y guion
# =====================================================================

def cargar_canal():
    canal = yaml.safe_load((RAIZ / "canal_historia.yaml").read_text(encoding="utf-8"))
    canal["tema"] = {k: tuple(v) for k, v in canal["colores"].items()}
    return canal


def _lista(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


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
            if e.get("tipo") in ("foto", "boceto") and not (e.get("imagen") or e.get("buscar_imagen")):
                errores.append(f"{donde}, escena {i}: una escena «{e.get('tipo')}» necesita «imagen» o «buscar_imagen»")

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


def todas_las_escenas(g):
    """[(escena, capítulo o None)] en orden de lectura."""
    salida = [(e, None) for e in g.get("gancho") or []]
    for c, cap in enumerate(g["capitulos"]):
        salida += [(e, c) for e in _lista(cap.get("gancho_short"))]
        salida += [(e, c) for e in cap["escenas"]]
    salida += [(e, None) for e in g.get("cierre") or []]
    return salida


# =====================================================================
#  Imágenes (Wikimedia Commons o carpeta propia)
# =====================================================================

def preparar_imagenes(g):
    hay = 0
    for e, _ in todas_las_escenas(g):
        if e.get("imagen") or e.get("buscar_imagen"):
            e["_img"], e["_credito"] = imagenes.conseguir(e, GUIONES)
            hay += e["_img"] is not None
    m = g.get("miniatura") or {}
    if m.get("imagen") or m.get("buscar_imagen"):
        m["_img"], _ = imagenes.conseguir(m, GUIONES)
    print(f"Imágenes: {hay} listas")


def creditos_imagenes(g):
    vistos, salida = set(), []
    for e, _ in todas_las_escenas(g):
        info = e.get("_commons")
        if info and info["titulo"] not in vistos:
            vistos.add(info["titulo"])
            salida.append(f"{info['titulo'].replace('File:', '')} — {info['autor']} ({info['licencia']}) — {info['pagina']}")
        elif e.get("_img") is not None and e.get("credito") and e["credito"] not in vistos:
            vistos.add(e["credito"])
            salida.append(str(e["credito"]))
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
            e["_audio"] = np.zeros(int(sr * max(2.0, len(str(e["voz"]).split()) / 2.5)), dtype=np.float32)
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
    extra = float(e.get("pausa", 0) or 0)  # segundos de más para que la imagen respire
    return {"tipo": "escena", "escena": e, "cap": cap, "ini": t, "fin": t + ANTES_VOZ + dur_voz + DESPUES_VOZ + extra,
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
    bloques.append({"tipo": "final", "ini": t, "fin": t + float(canal.get("pantalla_final", 12)), "cap": None})
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
    def __init__(self, trozos, geo, ctx):
        self.trozos, self.geo, self.ctx = trozos, geo, ctx
        self.f = ctx.f("txt_b", 60 if ctx.vertical else 42)
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
            d.rectangle((0, 0, w - 1, h - 1), fill=self.ctx.c("fondo", 215))
            for k, l in enumerate(lineas):
                d.text(((w - self.f.getlength(l)) / 2, 10 + k * alto_l), l, font=self.f, fill=self.ctx.c("texto"))
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
#  Fondo, grano y pantallas fijas (cabecera, capítulo, final)
# =====================================================================

def fondo_base(ctx, semilla=0):
    W, H, tema = ctx.W, ctx.H, ctx.tema
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(-1, 1, W)[None, :, None]
    c1, c2 = np.array(tema["fondo2"], np.float32), np.array(tema["fondo"], np.float32)
    col = np.broadcast_to(c1 * (1 - y) + c2 * y, (H, W, 3)).copy()
    col *= 1 - 0.2 * (x ** 2 + (y - 0.5) ** 2 * 1.4)
    col += _grano(W, H, 8, semilla)[..., None]
    return Image.fromarray(col.clip(0, 255).astype(np.uint8)).convert("RGBA")


class Grano:
    """Grano de película que cambia 12 veces por segundo (da textura sin distraer)."""

    def __init__(self, W, H, n=6, fuerza=22):
        self.capas = []
        for k in range(n):
            g = _grano(W, H, 1.0, 100 + k)
            a = (np.abs(g) * fuerza * 2).clip(0, 255).astype(np.uint8)
            claro = (g > 0)
            rgb = np.where(claro[..., None], 255, 0).astype(np.uint8)
            capa = Image.fromarray(np.dstack([np.broadcast_to(rgb, (H, W, 3)), a]), "RGBA")
            self.capas.append(capa)

    def en(self, t):
        return self.capas[int(t * 12) % len(self.capas)]


class Pantallas:
    """Cabecera del canal, tarjeta de capítulo y pantallas finales."""

    def __init__(self, ctx, canal, g):
        self.ctx, self.canal, self.g = ctx, canal, g
        self.W, self.H = ctx.W, ctx.H

    def sting(self, base, t, dur):
        ctx = self.ctx
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        f, lineas, tam = ctx.ajustar(self.canal["marca"].title() if not ctx.vertical else self.canal["marca"].title(),
                                     "tit", 150 if not ctx.vertical else 130, W - 2 * ctx.m, 3, 50)
        alto = tam * 1.05 * len(lineas)
        y0 = H / 2 - alto / 2 - 30
        for k, l in enumerate(lineas):
            a = suave((t - 0.15 - 0.15 * k) / 0.6)
            d.text((W / 2, y0 + k * tam * 1.05 + 30 * (1 - a)), l, font=f, fill=ctx.c("texto", int(255 * a)), anchor="ma")
        r = suave((t - 0.6) / 0.8)
        yb = y0 + alto + 36
        d.rectangle((W / 2 - 160 * r, yb, W / 2 + 160 * r, yb + 6), fill=ctx.c("acento"))
        b = suave((t - 1.0) / 0.5)
        d.text((W / 2, yb + 40), str(self.canal.get("lema", "")).upper(), font=ctx.f("txt_b", 30),
               fill=ctx.c("acento2", int(255 * b)), anchor="ma")
        salida = suave((t - (dur - 0.4)) / 0.4)
        if salida > 0:
            img = Image.blend(img, base, salida)
        return img

    def capitulo(self, base, t, dur, c):
        ctx = self.ctx
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        a = suave(t / 0.5)
        num = f"{c + 1:02d}"
        fn = ctx.f("num", 420 if ctx.vertical else 400)
        if ctx.vertical:
            d.text((W / 2, H * 0.38 + 40 * (1 - a)), num, font=fn, fill=ctx.c("acento", int(255 * a)), anchor="mm")
            x0, ancho, y0 = ctx.m, W - 2 * ctx.m, H * 0.52
            centro = True
        else:
            d.text((W * 0.30 - 40 * (1 - a), H / 2), num, font=fn, fill=ctx.c("acento", int(255 * a)), anchor="rm")
            x0, ancho, y0 = W * 0.36, W * 0.54, None
            centro = False
            d.line((W * 0.33, H * 0.3, W * 0.33, H * 0.3 + H * 0.4 * suave((t - 0.1) / 0.6)), fill=ctx.c("linea"), width=3)
        f, lineas, tam = ctx.ajustar(str(self.g["capitulos"][c]["titulo"]), "tit", 104, ancho, 3, 44)
        alto = tam * 1.08 * len(lineas)
        if y0 is None:
            y0 = H / 2 - alto / 2 + 20
        b = suave((t - 0.25) / 0.5)
        kick = f"CAPÍTULO {c + 1}"
        fk = ctx.f("txt_b", 28)
        if centro:
            d.text((W / 2, y0 - 60), kick, font=fk, fill=ctx.c("acento2", int(255 * b)), anchor="ma")
        else:
            d.text((x0, y0 - 60), kick, font=fk, fill=ctx.c("acento2", int(255 * b)))
        for k, l in enumerate(lineas):
            q = suave((t - 0.3 - 0.1 * k) / 0.5)
            if centro:
                d.text((W / 2, y0 + k * tam * 1.08 + 20 * (1 - q)), l, font=f, fill=ctx.c("texto", int(255 * q)), anchor="ma")
            else:
                d.text((x0 + 30 * (1 - q), y0 + k * tam * 1.08), l, font=f, fill=ctx.c("texto", int(255 * q)))
        return img

    def final(self, base, t, dur):
        ctx = self.ctx
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        a = suave(t / 0.6)
        d.text((W / 2, H * 0.11 + 20 * (1 - a)), "Gracias por ver", font=ctx.f("tit", 88), fill=ctx.c("texto", int(255 * a)), anchor="ma")
        b = suave((t - 0.3) / 0.5)
        d.text((W / 2, H * 0.11 + 130), "FUENTES, DATOS Y CRÉDITOS EN LA DESCRIPCIÓN", font=ctx.f("txt_b", 28),
               fill=ctx.c("acento2", int(255 * b)), anchor="ma")
        q = suave((t - 0.6) / 0.6)
        for x in (W * 0.27, W * 0.73):  # huecos para los vídeos de la pantalla final de YouTube
            d.rectangle((x - 400, H * 0.40, x + 400, H * 0.40 + 450), outline=ctx.c("linea", int(255 * q)), width=3)
        d.text((W / 2, H - 70), self.canal["marca"], font=ctx.f("txt_b", 28), fill=ctx.c("suave", int(255 * a)), anchor="mm")
        return img

    def final_short(self, base, t, dur):
        ctx = self.ctx
        img = base.copy()
        d = ImageDraw.Draw(img)
        W, H = self.W, self.H
        a = rebote(min(1, t / 0.5))
        f, lineas, tam = ctx.ajustar("La historia completa, en el canal", "tit", 110, W - 2 * ctx.m, 4, 50)
        y0 = H * 0.34
        for k, l in enumerate(lineas):
            d.text((W / 2, y0 + k * tam * 1.08), l, font=f, fill=ctx.c("texto", int(255 * min(1, a))), anchor="ma")
        yb = y0 + len(lineas) * tam * 1.08 + 50
        d.rectangle((W / 2 - 120, yb, W / 2 + 120, yb + 6), fill=ctx.c("acento"))
        d.text((W / 2, yb + 50), self.canal["marca"], font=ctx.f("txt_b", 36), fill=ctx.c("acento2", int(255 * min(1, a))), anchor="ma")
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
    woosh = [sonido.whoosh(dur=0.5, semilla=k) * 0.4 for k in range(4)]

    def poner(pista, seg, s):
        a = int(seg * sonido.SR)
        b = min(n, a + len(s))
        if 0 <= a < n:
            pista[a:b] += s[: b - a]

    for i, b in enumerate(bloques):
        if b["tipo"] == "escena":
            poner(voz, b["voz_ini"], _a_48k(b["escena"]["_audio"], sr))
            if b["escena"].get("tipo") == "cifra":
                poner(fx, b["ini"] + 0.1, sonido.pop() * 0.5)
        if b["tipo"] in ("sting", "capitulo"):
            poner(fx, b["ini"], sonido.golpe() * 0.7)
        if i > 0:
            poner(fx, max(0, b["ini"] - 0.2), woosh[i % 4])
    musica = sonido.musica(n / sonido.SR, "datos", bpm=80)[:n]
    v = np.abs(voz)
    ventana = int(0.4 * sonido.SR)
    cs = np.cumsum(np.concatenate([[0.0], v]))
    env = (cs[ventana:] - cs[:-ventana]) / ventana
    env = np.concatenate([env, np.full(len(v) - len(env), env[-1] if len(env) else 0)])
    env = env / (env.max() + 1e-9)
    musica = musica * 0.28 * (1 - 0.7 * np.clip(env * 4, 0, 1))
    mezcla = (voz + fx * 0.5 + musica)[: int(duracion * sonido.SR)]
    mezcla = mezcla / max(1.0, float(np.abs(mezcla).max()) / 0.95)
    bruto, final = carpeta / "mezcla.wav", carpeta / "mezcla_norm.wav"
    sf.write(bruto, mezcla.astype(np.float32), sonido.SR)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(bruto), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(final)], check=True)
    return final


# =====================================================================
#  Montaje
# =====================================================================

def montar(g, canal, bloques, sr, geo, salida, subtitulos=False):
    """Monta un vídeo (largo o Short) a partir de sus bloques."""
    from pexels import buscar_clip

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    carpeta = Path(tempfile.mkdtemp())
    W, H = geo["W"], geo["H"]
    ctx = Contexto(W, H, canal["tema"], canal["fuentes"], semilla=g["_nombre"])
    vertical = ctx.vertical
    duracion = bloques[-1]["fin"]
    n_frames = int(math.ceil(duracion * FPS))
    audio = mezclar_audio(bloques, sr, duracion, carpeta)

    base = fondo_base(ctx, semilla=len(g["titulo"]))
    grano = Grano(W, H)
    pantallas = Pantallas(ctx, canal, g)
    trozos = trozos_subtitulos(bloques, 5 if vertical else 9, 30 if vertical else 60)
    subs = Subtitulos(trozos, geo, ctx) if subtitulos else None

    marca_f = ctx.f("txt_b", 28 if vertical else 24)
    caps_cache, fuente_cache = {}, {}
    f_fuente = ctx.f("txt", 24 if vertical else 21)

    def etiqueta_cap(c):
        if c not in caps_cache:
            if vertical:
                f, lineas, tam = ctx.ajustar(str(g["capitulos"][c]["titulo"]), "tit", 50, W - 2 * ctx.m, 2, 30)
                capa = Image.new("RGBA", (W, int(tam * 1.15 * len(lineas)) + 20), (0, 0, 0, 0))
                dd = ImageDraw.Draw(capa)
                for k, l in enumerate(lineas):
                    dd.text((W / 2, k * tam * 1.15), l, font=f, fill=ctx.c("acento2"), anchor="ma")
            else:
                texto = f"{c + 1:02d} · {str(g['capitulos'][c]['titulo']).upper()}"
                f = ctx.f("txt", 21)
                capa = Image.new("RGBA", (int(f.getlength(texto)) + 4, 34), (0, 0, 0, 0))
                ImageDraw.Draw(capa).text((0, 4), texto, font=f, fill=ctx.c("suave"))
            caps_cache[c] = capa
        return caps_cache[c]

    def etiqueta_fuente(txt):
        if txt not in fuente_cache:
            lineas = envolver(txt, f_fuente, W - 2 * ctx.m)
            capa = Image.new("RGBA", (W, int(f_fuente.size * 1.3 * len(lineas)) + 8), (0, 0, 0, 0))
            dd = ImageDraw.Draw(capa)
            for k, l in enumerate(lineas):
                if vertical:
                    dd.text((W / 2, k * f_fuente.size * 1.3), l, font=f_fuente, fill=ctx.c("suave", 220), anchor="ma")
                else:
                    dd.text((72, k * f_fuente.size * 1.3), l, font=f_fuente, fill=ctx.c("suave", 220))
            fuente_cache[txt] = capa
        return fuente_cache[txt]

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
                ctx.semilla = f"{g['_nombre']}-{bi}"
                pieza = crear_pieza(e, ctx, b["fin"] - b["ini"], imagen=e.get("_img"), credito=e.get("_credito", ""), clip=clip)
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
            capa = pieza.cuadro(tl)
            if pieza.opaca:
                lienzo = capa.copy()
            else:
                lienzo = base.copy()
                lienzo.alpha_composite(capa)
            if b["fuente"]:
                capa_f = etiqueta_fuente(b["fuente"])
                lienzo.alpha_composite(capa_f, (0, int((H - 120 if vertical else H - 46) - capa_f.height / 2)))

        # Cabecera fija: marca y capítulo
        d = ImageDraw.Draw(lienzo)
        if b["tipo"] not in ("sting", "final", "final_short"):
            if vertical:
                tw = marca_f.getlength(canal["marca"])
                d.rectangle((W / 2 - tw / 2 - 26, 98, W / 2 - tw / 2 - 14, 122), fill=ctx.c("acento"))
                d.text((W / 2 + 0, 110), canal["marca"], font=marca_f, fill=ctx.c("texto"), anchor="mm")
                if b.get("cap") is not None and b["tipo"] != "capitulo":
                    lienzo.alpha_composite(etiqueta_cap(b["cap"]), (0, 165))
            else:
                d.rectangle((72, 58, 84, 82), fill=ctx.c("acento"))
                d.text((100, 70), canal["marca"], font=marca_f, fill=ctx.c("texto"), anchor="lm")
                if b.get("cap") is not None and b["tipo"] != "capitulo":
                    capa_c = etiqueta_cap(b["cap"])
                    lienzo.alpha_composite(capa_c, (W - 72 - capa_c.width, 54))
        if subs:
            subs.dibujar(lienzo, t)

        # Barra de progreso (en el largo, con las marcas de los capítulos)
        if vertical:
            d.rectangle((0, 0, int(W * t / duracion), 8), fill=ctx.c("acento"))
        else:
            d.rectangle((0, H - 5, W, H), fill=ctx.c("panel"))
            d.rectangle((0, H - 5, int(W * t / duracion), H), fill=ctx.c("acento"))
            for x in inicios_cap:
                xx = int(W * x / duracion)
                d.rectangle((xx - 2, H - 5, xx + 2, H), fill=ctx.c("fondo"))

        # Fundido corto con la escena anterior
        if anterior is not None and tl < FUNDIDO and bi > 0:
            lienzo = Image.blend(anterior, lienzo, suave(tl / FUNDIDO))
        ultimo = lienzo
        salida_img = lienzo.copy()
        salida_img.alpha_composite(grano.en(t))
        ffmpeg.stdin.write(salida_img.convert("RGB").tobytes())
        if nf % (FPS * 30) == 0:
            print(f"  {salida.name}: {t:.0f}/{duracion:.0f} s de vídeo ({time.time() - inicio:.0f} s montando)")

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
    creditos = creditos_imagenes(g)
    if creditos:
        lineas.append("Imágenes:")
        lineas += creditos
        lineas.append("")
    if clips:
        lineas.append("Clips de archivo de Pixabay / Pexels (licencia libre).")
    lineas.append("Gráficos, mapas (datos de Natural Earth) y música: originales del canal.")
    lineas.append("")
    if g.get("hashtags"):
        lineas.append(str(g["hashtags"]))
    return "\n".join(lineas)


def _primera_imagen(g):
    m = g.get("miniatura") or {}
    if m.get("_img") is not None:
        return m["_img"]
    for e, _ in todas_las_escenas(g):
        if e.get("_img") is not None:
            return e["_img"]
    return None


def miniatura(g, canal, ruta):
    ctx = Contexto(1280, 720, canal["tema"], canal["fuentes"])
    img = fondo_base(ctx, semilla=3)
    foto = _primera_imagen(g)
    if foto is not None:
        f = recortar_a(duotono(foto, canal["tema"], contraste=1.3, grano=10), 760, 720, (0.5, 0.3))
        m = np.ones((720, 760), np.float32)
        r = np.linspace(0, 1, 340) ** 1.4
        m[:, :340] *= r[None, :]
        f.putalpha(Image.fromarray((m * 255).astype(np.uint8)))
        img.alpha_composite(f, (520, 0))
    d = ImageDraw.Draw(img)
    mi = g.get("miniatura") or {}
    texto = str(mi.get("texto") or g["titulo"])
    resaltar = {p.strip(".,:;¿?¡!").lower() for p in str(mi.get("resaltar") or "").split()}
    f, lineas, tam = ctx.ajustar(texto, "tit", 120, 700 if foto is not None else 1100, 3, 50)
    alto_l = tam * 1.02
    y0 = 360 - alto_l * len(lineas) / 2 - (30 if mi.get("cifra") else 0)
    for k, l in enumerate(lineas):
        x = 56
        for p in l.split():
            col = ctx.c("acento2") if p.strip(".,:;¿?¡!").lower() in resaltar else ctx.c("texto")
            d.text((x, y0 + k * alto_l), p, font=f, fill=col, stroke_width=3, stroke_fill=ctx.c("fondo"))
            x += f.getlength(p + " ")
    if mi.get("cifra"):
        fc = ctx.f("num", 110)
        yc = y0 + len(lineas) * alto_l + 10
        d.rectangle((56, yc, 56 + fc.getlength(str(mi["cifra"])) + 40, yc + 130), fill=ctx.c("acento"))
        d.text((76, yc + 65), str(mi["cifra"]), font=fc, fill=ctx.c("texto"), anchor="lm")
    d.rectangle((56, 50, 66, 72), fill=ctx.c("acento"))
    d.text((80, 61), canal["marca"], font=ctx.f("txt_b", 22), fill=ctx.c("texto"), anchor="lm")
    img.convert("RGB").save(ruta)


def copia_ligera(entrada, salida, duracion, max_mb=45):
    """Copia que cabe en Telegram (límite de 50 MB para bots)."""
    if Path(entrada).stat().st_size < max_mb * 1024 * 1024:  # ya cabe: se manda tal cual
        import shutil
        shutil.copyfile(entrada, salida)
        return True
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
    preparar_imagenes(g)
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
            notas = ["✅ Más de 1 minuto: vale para el programa de pagos de TikTok" if dur > 61
                     else "⚠️ Menos de 1 minuto: TikTok no lo paga (alarga el capítulo si quieres cobrar allí)",
                     "✅ Vale para YouTube Shorts (hasta 3 minutos)" if dur <= 180
                     else "⚠️ Pasa de 3 minutos: YouTube no lo trataría como Short"]
            titulo = str(cap.get("titulo_short") or cap["titulo"])
            texto = f"{titulo}\n\nLa historia completa, en el canal.\n\n{g.get('hashtags', '')}\n\n— Dura {dur:.0f} s\n" + "\n".join(notas)
            base.with_suffix(".txt").write_text(texto, encoding="utf-8")
    print(f"Todo listo en {(time.time() - inicio) / 60:.1f} minutos")


if __name__ == "__main__":
    main()
