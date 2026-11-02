"""Shorts de quiz (canal «Dale al Coco», antes TrivialXpress).

Lee un quiz de la carpeta quizzes/ (ver quizzes/LEEME.md) y monta un vídeo vertical de 40–60 s:

    gancho  ->  pregunta 1 (cuenta atrás, respuesta y dato)  ->  pregunta 2  ->  ...  ->  final con pregunta extra

- Voz: Gemini (canal_quiz.yaml -> voz). Las frases leídas se guardan en cache_voz/.
- Una ilustración por pregunta (Gemini). Se guardan en cache_imagenes/: no se vuelven a pagar.
- Gráficos, música y efectos hechos con código. Cada categoría tiene su color, su patrón y su música,
  y cada vídeo elige su forma de entrar en pantalla, para que no parezcan todos iguales.
- NO publica nada: deja el vídeo y su texto en salida/ (y en Telegram/Drive desde el robot).

Variables:
    QUIZ        nombre del quiz (archivo de quizzes/ sin .yaml). Vacío = el primero sin publicar de la
                categoría que toca hoy (canal_quiz.yaml -> plan_semana).
    SIN_VOZ=1   prueba sin voz ni imágenes (gratis), para ver el montaje.
    REMONTAR=1  volver a montar un quiz marcado «publicado: true».
    GEMINI_API_KEY, VOZ_QUIZ (otra voz), VELOCIDAD_VOZ.

    python quiz.py              monta el vídeo
    python quiz.py --drive      copia a Google Drive lo que haya en salida/ del quiz
"""
import datetime
import hashlib
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import marca_quiz
import sonido

RAIZ = Path(__file__).resolve().parent.parent
QUIZZES = RAIZ / "quizzes"
FUENTES = RAIZ / "fuentes"
CACHE_VOZ = RAIZ / "cache_voz"
SALIDA = Path(__file__).resolve().parent / "salida"
W, H, FPS = 1080, 1920, 30
# Columna de contenido: deja libre la franja derecha, donde YouTube pone los botones
X0, X1 = 60, 960
CX = (X0 + X1) // 2
LETRAS = "ABCD"
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def _env(n):
    return (os.environ.get(n) or "").strip()


def suave(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def rebote(x):
    if x >= 1:
        return 1.0
    x = max(0.0, x)
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2


_fuentes = {}


def F(nombre, tam):
    k = (nombre, int(tam))
    if k not in _fuentes:
        _fuentes[k] = ImageFont.truetype(str(FUENTES / nombre), max(8, int(tam)))
    return _fuentes[k]


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


def encajar_texto(texto, fuente, ancho, max_lineas, tam, minimo):
    """Busca el tamaño de letra más grande con el que el texto cabe en max_lineas."""
    while tam > minimo:
        f = F(fuente, tam)
        lineas = envolver(texto, f, ancho)
        if len(lineas) <= max_lineas and all(f.getlength(l) <= ancho for l in lineas):
            return f, lineas
        tam -= 3
    f = F(fuente, minimo)
    return f, envolver(texto, f, ancho)


def rgba(v, a=255):
    return tuple(int(x) for x in v[:3]) + (int(a),)


def mezcla_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# =====================================================================
#  Cargar el canal y el quiz
# =====================================================================

def cargar_canal():
    return yaml.safe_load((RAIZ / "canal_quiz.yaml").read_text(encoding="utf-8"))


def elegir_quiz(canal):
    nombre = _env("QUIZ")
    if nombre:
        return nombre
    hoy = DIAS[datetime.datetime.now().weekday()]
    cat = (canal.get("plan_semana") or {}).get(hoy)
    candidatos = []
    for ruta in sorted(QUIZZES.glob("*.yaml")):
        q = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        if q.get("publicado") or q.get("prueba"):
            continue
        candidatos.append((q.get("categoria") != cat, ruta.stem))
    if not candidatos:
        raise SystemExit("::error::No queda ningún quiz sin publicar en quizzes/. Escribe más (ver quizzes/LEEME.md).")
    candidatos.sort()
    if candidatos[0][0]:
        print(f"::warning::Hoy ({hoy}) toca «{cat}», pero no queda ninguno sin publicar: uso otro")
    return candidatos[0][1]


def cargar_quiz(nombre, canal):
    ruta = QUIZZES / f"{nombre}.yaml"
    if not ruta.exists():
        raise SystemExit(f"::error::No existe quizzes/{nombre}.yaml")
    q = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    q["_nombre"] = nombre
    cats = canal["categorias"]
    if q.get("categoria") not in cats:
        raise SystemExit(f"::error::{nombre}: categoría «{q.get('categoria')}» no existe. Hay: {', '.join(cats)}")
    errores = []
    for i, p in enumerate(q.get("preguntas") or [], 1):
        tipo = p.setdefault("tipo", "opciones")
        if tipo == "vf":
            p["opciones"] = ["Verdadero", "Falso"]
            c = str(p.get("correcta", "")).strip().lower()
            if c not in ("verdadero", "falso", "v", "f"):
                errores.append(f"pregunta {i}: en «vf», correcta tiene que ser verdadero o falso")
            p["_ok"] = 0 if c.startswith("v") else 1
        else:
            ops = p.get("opciones") or []
            if not 2 <= len(ops) <= 4:
                errores.append(f"pregunta {i}: tiene que tener de 2 a 4 opciones")
            c = str(p.get("correcta", "")).strip().upper()
            if len(c) != 1 or c not in LETRAS[:len(ops)]:
                errores.append(f"pregunta {i}: correcta tiene que ser una letra ({LETRAS[:len(ops)]})")
            else:
                p["_ok"] = LETRAS.index(c)
        if not p.get("pregunta"):
            errores.append(f"pregunta {i}: falta el texto")
    if not q.get("preguntas"):
        errores.append("no tiene preguntas")
    if errores:
        raise SystemExit(f"::error::{nombre}: " + "; ".join(errores))
    return q


# =====================================================================
#  Textos que se leen
# =====================================================================

NUM = ["una", "dos", "tres", "cuatro", "cinco", "seis"]


def frase_respuesta(p):
    texto = p["opciones"][p["_ok"]]
    if p["tipo"] == "vf":
        base = f"¡{texto}!"
    elif p.get("decir_respuesta"):
        base = str(p["decir_respuesta"])
    else:
        base = f"¡La {LETRAS[p['_ok']]}: {texto}!"
    dato = str(p.get("dato") or "").strip()
    return f"{base} {dato}".strip()


def frase_pregunta(p, i, total):
    intro = "Y la última." if i == total - 1 and total > 2 else ("Pregunta uno." if i == 0 else "Siguiente.")
    if p["tipo"] == "vf":
        return f"{intro} ¿Verdadero o falso? {p['pregunta']}"
    return f"{intro} {p.get('decir') or p['pregunta']}"


def frase_final(q, canal):
    extra = str(q.get("extra") or "").strip()
    cierre = str(q.get("cierre") or canal.get("cierre") or "").strip()
    texto = f"{cierre}."
    if extra:
        texto += f" Y una extra, sin respuesta: {extra} Te leo en comentarios."
    return texto


# =====================================================================
#  Voz
# =====================================================================

def _recortar(wav, sr):
    env = np.abs(wav)
    activo = np.where(env > 0.02 * (env.max() or 1))[0]
    if len(activo):
        wav = wav[max(0, activo[0] - int(0.03 * sr)): activo[-1] + int(0.08 * sr)]
    return wav.astype(np.float32)


def voces(textos, canal):
    """Devuelve (sr, [audio por texto]). Usa la caché; pide a Gemini solo lo nuevo."""
    if _env("SIN_VOZ") == "1":
        sr = 24000
        print("Prueba SIN VOZ: tiempos calculados a ojo")
        return sr, [np.zeros(int(sr * max(1.6, len(t.split()) / 2.7)), np.float32) for t in textos]
    os.environ["GEMINI_VOZ"] = _env("VOZ_QUIZ") or canal["voz"]
    os.environ["GEMINI_ESTILO"] = " ".join(str(canal["estilo_voz"]).split())
    os.environ.setdefault("VOZ_MOTOR", "gemini")
    from motor_voz import crear_motor
    motor = crear_motor()
    sr = motor.sr
    CACHE_VOZ.mkdir(exist_ok=True)
    firma = f"{type(motor).__name__}|{getattr(motor, 'modelo', '')}|{getattr(motor, 'voz', '')}|{getattr(motor, 'estilo', '')}"
    audios, pendientes = [None] * len(textos), []
    for k, t in enumerate(textos):
        ruta = CACHE_VOZ / (hashlib.sha1(f"{firma}|{t}".encode("utf-8")).hexdigest()[:20] + ".wav")
        if ruta.exists():
            audios[k], _ = sf.read(ruta, dtype="float32")
        else:
            pendientes.append((k, t, ruta))
    if pendientes:
        print(f"Voces por pedir: {len(pendientes)} de {len(textos)}")
    tandas = []
    try:
        import faster_whisper  # noqa: F401  (para cortar una petición con varias frases)
        from voz_tandas import cortar_tanda
        for i in range(0, len(pendientes), 5):
            tandas.append(pendientes[i:i + 5])
    except ImportError:
        cortar_tanda = None
        tandas = [[p] for p in pendientes]
    for tanda in tandas:
        trozos = None
        if len(tanda) > 1 and cortar_tanda and hasattr(motor, "decir_seguido"):
            wav, dichos = motor.decir_seguido([t for _, t, _ in tanda])
            cortes = cortar_tanda(wav, sr, dichos)
            if cortes:
                trozos = [_recortar(wav[a:b], sr) for a, b in cortes]
                letras = [max(1, len(d)) for d in dichos]
                largos = [len(x) for x in trozos]
                if min(largos) == 0 or any(not 0.5 <= (a / sum(largos)) / (l / sum(letras)) <= 2.0
                                           for a, l in zip(largos, letras)):
                    trozos = None
            if trozos is None:
                print("  ::warning::No se pudo cortar bien esta tanda: pido sus frases una a una")
        if trozos is None:
            trozos = [motor.decir(t) for _, t, _ in tanda]
        for (k, _, ruta), a in zip(tanda, trozos):
            sf.write(ruta, a, sr)
            audios[k] = a
    v = float(_env("VELOCIDAD_VOZ") or canal.get("velocidad_voz") or 1.0)
    if abs(v - 1.0) > 0.01:
        v = min(max(v, 0.8), 1.3)
        with tempfile.TemporaryDirectory() as tmp:
            ent, sal = Path(tmp) / "e.wav", Path(tmp) / "s.wav"
            for k, a in enumerate(audios):
                sf.write(ent, a, sr)
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(ent), "-filter:a", f"atempo={v:.3f}",
                                "-ar", str(sr), "-ac", "1", str(sal)], check=True)
                audios[k], _ = sf.read(sal, dtype="float32")
    return sr, audios


# =====================================================================
#  Ilustraciones
# =====================================================================

def imagenes(q, canal):
    cat = canal["categorias"][q["categoria"]]
    sin = _env("SIN_VOZ") == "1"
    import ilustraciones
    salida = []
    for p in q["preguntas"]:
        img = None
        escena = str(p.get("escena") or "").strip()
        if escena and not sin:
            img, _ = ilustraciones.generar({"escena": f"{escena}. Ambiente: {' '.join(str(cat.get('estilo', '')).split())}"},
                                           canal)
        salida.append(img)
    return salida


def imagen_provisional(cat, colores, i):
    """Tarjeta sin ilustración (pruebas o si falla la IA): degradado del color de la categoría y un «?»."""
    w, h = 900, 540
    img = Image.new("RGB", (w, h))
    a, b = mezcla_color(cat["color"], colores["fondo"], 0.25), mezcla_color(cat["color"], colores["fondo"], 0.75)
    arr = np.linspace(0, 1, h)[:, None, None]
    img = Image.fromarray((np.array(a) * (1 - arr) + np.array(b) * arr).repeat(w, axis=1).astype(np.uint8))
    d = ImageDraw.Draw(img)
    rnd = random.Random(i)
    for _ in range(14):
        x, y, r = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(20, 90)
        d.ellipse((x - r, y - r, x + r, y + r), outline=rgba(colores["texto"], 255), width=3)
    d.text((w / 2, h / 2), "?", font=F("Fredoka-SemiBold.ttf", 300), fill=(255, 255, 255), anchor="mm")
    return img


# =====================================================================
#  Fondo de cada categoría
# =====================================================================

def fondo(canal, cat, semilla):
    col = canal["colores"]
    arr = np.linspace(0, 1, H)[:, None, None]
    arriba, abajo = np.array(col["fondo2"], np.float32), np.array(col["fondo"], np.float32)
    base = arriba * (1 - arr) + abajo * arr
    # Halo del color de la categoría arriba
    yy, xx = np.mgrid[0:H, 0:W]
    halo = np.exp(-(((xx - W * 0.5) / (W * 0.7)) ** 2 + ((yy - H * 0.3) / (H * 0.35)) ** 2))[..., None]
    base = base * (1 - 0.28 * halo) + np.array(cat["color"], np.float32) * 0.28 * halo
    img = Image.fromarray(base.clip(0, 255).astype(np.uint8)).convert("RGBA")
    # Patrón (más alto que la pantalla, para poder desplazarlo despacio)
    patron = Image.new("RGBA", (W, H + 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(patron)
    tinte = rgba(mezcla_color(col["fondo2"], cat["color"], 0.35), 70)
    rnd = random.Random(semilla)
    tipo = cat.get("patron", "puntos")
    if tipo == "rejilla":
        for x in range(0, W + 1, 72):
            d.line([(x, 0), (x, H + 400)], fill=tinte, width=2)
        for y in range(0, H + 401, 72):
            d.line([(0, y), (W, y)], fill=tinte, width=2)
    elif tipo == "diagonales":
        for k in range(-H, W + H, 90):
            d.line([(k, 0), (k + H + 400, H + 400)], fill=tinte, width=14)
    elif tipo == "lineas":
        for y in range(0, H + 400, 64):
            d.line([(0, y), (W, y)], fill=tinte, width=3)
        d.line([(110, 0), (110, H + 400)], fill=rgba(cat["color"], 60), width=4)
    elif tipo == "curvas":
        for k in range(14):
            y0 = k * 160
            pts = [(x, y0 + 40 * math.sin(x / 140 + k)) for x in range(0, W + 20, 20)]
            d.line(pts, fill=tinte, width=4)
    elif tipo == "estrellas":
        for _ in range(60):
            x, y, r = rnd.randint(0, W), rnd.randint(0, H + 400), rnd.randint(8, 22)
            pts = [(x + (r if j % 2 == 0 else r * 0.45) * math.cos(math.pi * j / 5 - math.pi / 2),
                    y + (r if j % 2 == 0 else r * 0.45) * math.sin(math.pi * j / 5 - math.pi / 2)) for j in range(10)]
            d.polygon(pts, fill=tinte)
    elif tipo == "runas":
        for _ in range(55):
            x, y, s = rnd.randint(0, W), rnd.randint(0, H + 400), rnd.randint(22, 46)
            forma = rnd.randint(0, 3)
            if forma == 0:
                d.line([(x, y - s), (x, y + s)], fill=tinte, width=5)
                d.line([(x, y - s * 0.4), (x + s * 0.6, y - s)], fill=tinte, width=5)
            elif forma == 1:
                d.line([(x - s * .5, y + s), (x, y - s), (x + s * .5, y + s)], fill=tinte, width=5)
            elif forma == 2:
                d.polygon([(x, y - s), (x + s * .6, y), (x, y + s), (x - s * .6, y)], outline=tinte, width=5)
            else:
                d.line([(x, y - s), (x, y + s)], fill=tinte, width=5)
                d.line([(x - s * .5, y - s * .3), (x + s * .5, y + s * .3)], fill=tinte, width=5)
    else:
        for y in range(0, H + 400, 54):
            for x in range(0, W + 54, 54):
                xx = x + (27 if (y // 54) % 2 else 0)
                d.ellipse((xx - 5, y - 5, xx + 5, y + 5), fill=tinte)
    return img, patron


# =====================================================================
#  Piezas
# =====================================================================

def chip(texto, f, fondo_c, texto_c, pad=24, alto=None):
    tw = f.getlength(texto)
    alto = alto or int(f.size * 1.55)
    img = Image.new("RGBA", (int(tw + pad * 2), alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, img.width - 1, alto - 1), radius=alto // 2, fill=fondo_c)
    d.text((img.width / 2, alto / 2), texto, font=f, fill=texto_c, anchor="mm")
    return img


def redondear(img, r):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=r, fill=255)
    out = img.convert("RGBA")
    out.putalpha(m)
    return out


def sombra(caja, r, fuerza=110, blur=18):
    x0, y0, x1, y1 = caja
    pad = blur * 3
    s = Image.new("RGBA", (int(x1 - x0) + pad * 2, int(y1 - y0) + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle((pad, pad + 10, s.width - pad, s.height - pad + 10), radius=r, fill=(0, 0, 0, fuerza))
    return s.filter(ImageFilter.GaussianBlur(blur)), (int(x0) - pad, int(y0) - pad)


def pegar(base, capa, x, y, alfa=1.0, escala=1.0):
    """Pega una capa centrada en (x, y), con transparencia y escala."""
    if alfa <= 0.01 or escala <= 0.01:
        return
    if abs(escala - 1) > 0.005:
        capa = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))), Image.BILINEAR)
    if alfa < 0.999:
        capa = capa.copy()
        capa.putalpha(capa.getchannel("A").point(lambda v: int(v * alfa)))
    base.alpha_composite(capa, (int(x - capa.width / 2), int(y - capa.height / 2)))


def palomita(d, cx, cy, r, color, ancho):
    d.line([(cx - r * 0.5, cy + r * 0.02), (cx - r * 0.12, cy + r * 0.4), (cx + r * 0.55, cy - r * 0.4)],
           fill=color, width=ancho, joint="curve")


class Montador:
    def __init__(self, q, canal, imgs):
        self.q, self.canal = q, canal
        self.col = {k: tuple(v) for k, v in canal["colores"].items()}
        self.cat = canal["categorias"][q["categoria"]]
        self.cc = tuple(self.cat["color"])
        self.ft = canal["fuentes"]
        semilla = int(hashlib.sha1(q["_nombre"].encode()).hexdigest()[:8], 16)
        self.rnd = random.Random(semilla)
        self.entrada = self.rnd.choice(["deslizar", "zoom", "caer"])
        self.base, self.patron = fondo(canal, self.cat, semilla)
        self.dir_patron = self.rnd.choice([-1, 1])
        n = len(q["preguntas"])
        self.n = n
        # Tarjetas de imagen ya recortadas y redondeadas (con margen para el zoom lento)
        self.tarjetas = []
        for i, img in enumerate(imgs):
            if img is None:
                img = imagen_provisional(self.cat, self.col, i)
            self.tarjetas.append(img.convert("RGB"))
        self.mascotas = {g: marca_quiz.mascota(360, canal["colores"], gesto=g) for g in ("feliz", "sorpresa", "guino", "pensando")}
        self.mini = {g: m.resize((200, 200), Image.LANCZOS) for g, m in self.mascotas.items()}
        self.f_marca = F(self.ft["tit"], 34)
        self.f_chip = F(self.ft["txt_b"], 32)
        self.chip_marca = chip(canal["marca"], self.f_marca, rgba(self.col["tinta"], 220), rgba(self.col["acento"]), pad=26)
        self.chip_cat = chip(self.cat["nombre"].upper(), self.f_chip, rgba(self.cc), rgba(self.col["tinta"]), pad=22)
        self._cache = {}

    # ----- capas que no cambian dentro de una pregunta (se guardan) -----

    def _guardado(self, clave, hacer):
        if clave not in self._cache:
            self._cache[clave] = hacer()
        return self._cache[clave]

    def capa_pregunta(self, i):
        def hacer():
            p = self.q["preguntas"][i]
            texto = p["pregunta"]
            f, lineas = encajar_texto(texto, self.ft["tit"], X1 - X0 - 20, 4, 68, 40)
            alto = int(len(lineas) * f.size * 1.18)
            img = Image.new("RGBA", (X1 - X0, alto + 10), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            for k, l in enumerate(lineas):
                y = int(k * f.size * 1.18 + f.size * 0.6)
                d.text(((X1 - X0) / 2 + 3, y + 4), l, font=f, fill=(0, 0, 0, 120), anchor="mm")
                d.text(((X1 - X0) / 2, y), l, font=f, fill=rgba(self.col["texto"]), anchor="mm")
            return img
        return self._guardado(("preg", i), hacer)

    def cajas(self, i):
        """Posiciones de las respuestas: [(x0, y0, x1, y1)]."""
        p = self.q["preguntas"][i]
        n = len(p["opciones"])
        y0 = 1175
        if p["tipo"] == "vf":
            mitad = (X0 + X1) // 2
            return [(X0, y0, mitad - 14, y0 + 190), (mitad + 14, y0, X1, y0 + 190)]
        alto = 112 if n > 2 else 150
        hueco = 20 if n > 2 else 30
        return [(X0, y0 + k * (alto + hueco), X1, y0 + k * (alto + hueco) + alto) for k in range(n)]

    def capa_opcion(self, i, k, estado):
        """estado: normal, bien, mal."""
        def hacer():
            p = self.q["preguntas"][i]
            x0, y0, x1, y1 = self.cajas(i)[k]
            w, h = int(x1 - x0), int(y1 - y0)
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            if estado == "bien":
                relleno, borde, txt = self.col["correcto"], self.col["correcto"], (255, 255, 255)
            elif estado == "mal":
                relleno, borde, txt = mezcla_color(self.col["fondo2"], self.col["fondo"], 0.4), self.col["fondo2"], self.col["suave"]
            else:
                relleno, borde, txt = self.col["panel"], self.col["panel"], self.col["tinta"]
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=28, fill=rgba(relleno), outline=rgba(borde), width=4)
            texto = p["opciones"][k]
            if p["tipo"] == "vf":
                f, lineas = encajar_texto(texto.upper(), self.ft["tit"], w - 40, 1, 64, 36)
                d.text((w / 2, h / 2 - (14 if estado == "bien" else 0)), lineas[0], font=f, fill=rgba(txt), anchor="mm")
                if estado == "bien":
                    palomita(d, w / 2, h - 40, 34, (255, 255, 255), 9)
                return img
            # Círculo con la letra
            r = h * 0.34
            cx, cy = 22 + r, h / 2
            circulo = self.cc if estado == "normal" else ((255, 255, 255) if estado == "bien" else self.col["fondo2"])
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba(circulo))
            letra_c = self.col["tinta"] if estado != "bien" else self.col["correcto"]
            if estado == "bien":
                palomita(d, cx, cy, r * 0.9, rgba(letra_c), 8)
            else:
                d.text((cx, cy), LETRAS[k], font=F(self.ft["tit"], r * 1.25), fill=rgba(letra_c), anchor="mm")
            ancho = w - (cx + r + 26) - 26
            f, lineas = encajar_texto(texto, self.ft["txt_b"], ancho, 2, 46, 28)
            lh = f.size * 1.1
            y = h / 2 - (len(lineas) - 1) * lh / 2
            for l in lineas:
                d.text((cx + r + 24, y), l, font=f, fill=rgba(txt), anchor="lm")
                y += lh
            return img
        return self._guardado(("op", i, k, estado), hacer)

    def capa_dato(self, i):
        def hacer():
            p = self.q["preguntas"][i]
            dato = str(p.get("dato_pantalla") or p.get("dato") or "").strip()
            if not dato:
                return None
            w = X1 - X0
            f, lineas = encajar_texto(dato, self.ft["txt_b"], w - 70, 4, 40, 28)
            lh = int(f.size * 1.22)
            h = 92 + len(lineas) * lh + 20
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=30, fill=rgba(self.col["tinta"], 238),
                                outline=rgba(self.cc), width=4)
            et = chip("¿SABÍAS QUE…?", F(self.ft["txt_b"], 28), rgba(self.cc), rgba(self.col["tinta"]), pad=18)
            img.alpha_composite(et, (32, 26))
            y = 92
            for l in lineas:
                d.text((36, y), l, font=f, fill=rgba(self.col["texto"]))
                y += lh
            return img
        return self._guardado(("dato", i), hacer)

    def tarjeta(self, i, t):
        """Ilustración con zoom lento (Ken Burns), redondeada."""
        img = self.tarjetas[i]
        w, h = X1 - X0, 520
        z = 1.04 + 0.08 * min(1.0, t / 14)
        iw, ih = img.size
        # recorte con la proporción de la tarjeta
        prop = w / h
        if iw / ih > prop:
            cw, ch = ih * prop, ih
        else:
            cw, ch = iw, iw / prop
        cw, ch = cw / z, ch / z
        x0 = (iw - cw) * (0.5 + 0.35 * math.sin(t * 0.15 + i)) if iw - cw > 2 else 0
        y0 = (ih - ch) * 0.5
        recorte = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR)
        return redondear(recorte, 34)

    # ----- pantalla de fondo con cabecera -----

    def lienzo(self, t, total, i_preg=None, hechas=0):
        lz = self.base.copy()
        off = int((t * 18 * self.dir_patron) % 400)
        lz.alpha_composite(self.patron.crop((0, off, W, off + H)))
        d = ImageDraw.Draw(lz)
        # Barra de progreso
        d.rectangle((0, 0, int(W * min(1, t / total)), 10), fill=rgba(self.cc))
        # Cabecera
        pegar(lz, self.chip_marca, CX, 150)
        if i_preg is not None:
            pegar(lz, self.chip_cat, X0 + self.chip_cat.width / 2, 232)
            # Puntos: preguntas hechas
            for k in range(self.n):
                x = X1 - (self.n - 1 - k) * 44 - 16
                lleno = k < hechas
                actual = k == i_preg
                r = 15 if actual else 12
                d.ellipse((x - r, 232 - r, x + r, 232 + r), fill=rgba(self.cc if lleno or actual else self.col["fondo2"]),
                          outline=rgba(self.col["texto"], 200) if actual else None, width=3)
        return lz

    def entrar(self, capa, x, y, tl, lz, retraso=0.0, dur=0.32):
        """Entrada de una pieza según el estilo del vídeo."""
        a = suave((tl - retraso) / dur)
        if a <= 0:
            return
        if self.entrada == "deslizar":
            pegar(lz, capa, x + (1 - a) * 220, y, a)
        elif self.entrada == "caer":
            pegar(lz, capa, x, y - (1 - a) * 120, a)
        else:
            pegar(lz, capa, x, y, a, 0.85 + 0.15 * rebote((tl - retraso) / dur))

    # ----- pantallas -----

    def gancho(self, t, tl, total):
        lz = self.lienzo(t, total)
        d = ImageDraw.Draw(lz)
        # En el primer fotograma ya se ve todo (nada de esperar)
        m = self.mascotas["pensando" if tl < 1.2 else "sorpresa"]
        pegar(lz, m, CX, 560 + 12 * math.sin(tl * 3), 1, 1.25)
        f = F(self.ft["tit"], 120)
        n_txt = f"{self.n} PREGUNTAS"
        d.text((CX + 4, 915), n_txt, font=f, fill=(0, 0, 0, 120), anchor="mm")
        d.text((CX, 910), n_txt, font=f, fill=rgba(self.col["acento"]), anchor="mm")
        cat = chip(self.cat["nombre"].upper(), F(self.ft["txt_b"], 52), rgba(self.cc), rgba(self.col["tinta"]), pad=34)
        pegar(lz, cat, CX, 1050, 1, 1 + 0.04 * math.sin(tl * 6))
        gancho = str(self.q.get("gancho_pantalla") or self.q.get("gancho") or "")
        fg, lineas = encajar_texto(gancho, self.ft["tit"], X1 - X0 - 40, 4, 64, 40)
        y = 1200
        for l in lineas:
            d.text((CX, y), l, font=fg, fill=rgba(self.col["texto"]), anchor="mm")
            y += fg.size * 1.2
        # Escalera de dificultad
        y += 50
        for k, nivel in enumerate(["FÁCIL", "MEDIA", "DIFÍCIL"][: max(1, min(3, self.n))]):
            c = mezcla_color(self.col["correcto"], self.col["incorrecto"], k / 2)
            ch = chip(nivel, F(self.ft["txt_b"], 30), rgba(c), (255, 255, 255, 255), pad=20)
            pegar(lz, ch, CX + (k - 1) * 230, y, 1, 1 + 0.08 * max(0.0, 1 - abs(tl - 0.6 - 0.25 * k) / 0.15))
        return lz

    def pregunta(self, t, tl, total, i, tiempos):
        """tiempos: dict con voz_fin, cuenta (inicio), revela (inicio), opciones [aparición]."""
        p = self.q["preguntas"][i]
        lz = self.lienzo(t, total, i, hechas=i + (1 if tl >= tiempos["revela"] else 0))
        d = ImageDraw.Draw(lz)
        # Etiqueta «PREGUNTA 1/3» con dificultad
        dif = str(p.get("dificultad") or ["facil", "media", "dificil"][min(2, int(3 * i / max(1, self.n)))]).lower()
        dif_txt = {"facil": "FÁCIL", "media": "MEDIA", "dificil": "DIFÍCIL"}.get(dif, dif.upper())
        dif_c = {"facil": self.col["correcto"], "media": self.col["acento"], "dificil": self.col["incorrecto"]}.get(dif, self.cc)
        # Golpe de entrada: la etiqueta grande en el centro durante el primer instante
        if tl < 0.45:
            a = 1 - suave((tl - 0.3) / 0.15) if tl > 0.3 else 1
            et = chip(f"PREGUNTA {i + 1}", F(self.ft["tit"], 96), rgba(self.cc), rgba(self.col["tinta"]), pad=46)
            pegar(lz, et, CX, H * 0.42, a, rebote(tl / 0.25))
            return lz
        # Ilustración
        tar = self.tarjeta(i, tl)
        sb, pos = sombra((X0, 290, X1, 810), 34)
        lz.alpha_composite(sb, pos)
        self.entrar(tar, CX, 290 + tar.height / 2, tl, lz, 0.45)
        et = chip(f"{i + 1}/{self.n} · {dif_txt}", F(self.ft["txt_b"], 30), rgba(dif_c), (255, 255, 255, 255), pad=20)
        pegar(lz, et, X0 + 24 + et.width / 2, 290 + 40, suave((tl - 0.6) / 0.2))
        # Texto de la pregunta
        cp = self.capa_pregunta(i)
        self.entrar(cp, CX, 845 + cp.height / 2 + max(0, (300 - cp.height) / 2) - 20, tl, lz, 0.5)
        # Respuestas
        revela = tl >= tiempos["revela"]
        for k, caja in enumerate(self.cajas(i)):
            x0, y0, x1, y1 = caja
            ap = tiempos["opciones"][k]
            if tl < ap:
                continue
            if revela:
                estado = "bien" if k == p["_ok"] else "mal"
                ca = self.capa_opcion(i, k, estado)
                tr = tl - tiempos["revela"]
                esc = 1 + 0.07 * math.sin(min(1, tr / 0.35) * math.pi) if estado == "bien" else 1
                alfa = 1 if estado == "bien" else 0.55 + 0.45 * (1 - suave(tr / 0.3))
                pegar(lz, ca, (x0 + x1) / 2, (y0 + y1) / 2, alfa, esc)
            else:
                ca = self.capa_opcion(i, k, "normal")
                a = (tl - ap) / 0.22
                sb, pos = sombra(caja, 28, 90, 12)
                lz.alpha_composite(sb, pos)
                pegar(lz, ca, (x0 + x1) / 2, (y0 + y1) / 2, suave(a), 0.9 + 0.1 * rebote(a))
        # Cuenta atrás
        if tiempos["cuenta"] <= tl < tiempos["revela"]:
            self.cuenta(lz, tl - tiempos["cuenta"], tiempos["revela"] - tiempos["cuenta"])
        # Dato curioso sobre la ilustración
        if revela:
            cd = self.capa_dato(i)
            if cd is not None:
                tr = tl - tiempos["revela"] - 0.5
                if tr > 0:
                    pegar(lz, cd, CX, 810 - cd.height / 2 - 10 + (1 - suave(tr / 0.3)) * 60, suave(tr / 0.3))
            m = self.mini["feliz" if (tl - tiempos["revela"]) < 1.2 else "guino"]
            tr = tl - tiempos["revela"]
            pegar(lz, m, X1 - 95, 345 + (1 - rebote(tr / 0.4)) * 60, suave(tr / 0.2))
        return lz

    def cuenta(self, lz, tc, dur):
        d = ImageDraw.Draw(lz)
        cx, cy, r = X1 - 90, 330 + 10, 76
        falta = max(0.0, dur - tc)
        n = int(math.ceil(falta))
        frac = falta / dur
        color = mezcla_color(self.col["correcto"], self.col["incorrecto"], 1 - frac)
        d.ellipse((cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10), fill=rgba(self.col["tinta"], 235))
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * frac, fill=rgba(color), width=14)
        lat = 1 + 0.18 * max(0.0, 1 - ((tc % 1.0) / 0.25))
        f = F(self.ft["tit"], 84 * lat)
        d.text((cx, cy + 2), str(max(1, n)), font=f, fill=rgba(self.col["texto"]), anchor="mm")

    def final(self, t, tl, total):
        lz = self.lienzo(t, total)
        d = ImageDraw.Draw(lz)
        m = self.mascotas["feliz" if tl < 1.5 else "guino"]
        pegar(lz, m, CX, 470 + 10 * math.sin(tl * 3), 1, rebote(tl / 0.4))
        f = F(self.ft["tit"], 84)
        for k, l in enumerate(["¿Cuántas", "has acertado?"]):
            pegar(lz, self._texto(l, f, self.col["acento"]), CX, 745 + k * 96, suave((tl - 0.1) / 0.25))
        # Marcador 0/3 ... 3/3
        for k in range(self.n + 1):
            ch = chip(f"{k}/{self.n}", F(self.ft["tit"], 46), rgba(self.col["panel"]), rgba(self.col["tinta"]), pad=24)
            ancho = (self.n + 1) * 170
            pegar(lz, ch, CX - ancho / 2 + 85 + k * 170, 1000, suave((tl - 0.3 - 0.08 * k) / 0.2))
        extra = str(self.q.get("extra") or "").strip()
        if extra:
            w = X1 - X0
            fe, lineas = encajar_texto(extra, self.ft["tit"], w - 70, 4, 52, 34)
            lh = int(fe.size * 1.2)
            h = 110 + len(lineas) * lh + 30
            caja = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            dc = ImageDraw.Draw(caja)
            dc.rounded_rectangle((0, 0, w - 1, h - 1), radius=32, fill=rgba(self.cc))
            et = chip("PREGUNTA EXTRA", F(self.ft["txt_b"], 30), rgba(self.col["tinta"]), rgba(self.cc), pad=20)
            caja.alpha_composite(et, ((w - et.width) // 2, 28))
            y = 110
            for l in lineas:
                dc.text((w / 2, y + lh / 2), l, font=fe, fill=rgba(self.col["tinta"]), anchor="mm")
                y += lh
            pegar(lz, caja, CX, 1130 + h / 2, suave((tl - 0.9) / 0.3), 0.9 + 0.1 * rebote((tl - 0.9) / 0.3))
            fy = 1130 + h + 70
            a = suave((tl - 1.4) / 0.3)
            pegar(lz, self._texto("Respóndela en comentarios", F(self.ft["txt_b"], 44), self.col["texto"]), CX, fy, a)
            # flecha hacia abajo
            fy2 = fy + 70 + 10 * math.sin(tl * 6)
            if a > 0:
                d = ImageDraw.Draw(lz)
                d.polygon([(CX - 30, fy2 - 16), (CX + 30, fy2 - 16), (CX, fy2 + 22)], fill=rgba(self.col["acento"], int(255 * a)))
        return lz

    def _texto(self, texto, f, color):
        tw = int(f.getlength(texto)) + 20
        img = Image.new("RGBA", (tw, int(f.size * 1.4)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((tw / 2 + 3, img.height / 2 + 4), texto, font=f, fill=(0, 0, 0, 120), anchor="mm")
        d.text((tw / 2, img.height / 2), texto, font=f, fill=rgba(color), anchor="mm")
        return img


# =====================================================================
#  Línea de tiempo y audio
# =====================================================================

def linea_de_tiempo(q, canal, sr, audios):
    """Bloques [{tipo, ini, fin, ...}] y [(segundo, audio de voz)]."""
    cuenta = float(q.get("cuenta_atras") or canal.get("cuenta_atras") or 4)
    bloques, voz = [], []
    t = 0.0
    dur = len(audios[0]) / sr
    bloques.append({"tipo": "gancho", "ini": 0.0, "fin": max(2.4, dur + 0.35)})
    voz.append((0.1, audios[0]))
    t = bloques[-1]["fin"]
    k = 1
    for i, p in enumerate(q["preguntas"]):
        a_preg, a_resp = audios[k], audios[k + 1]
        k += 2
        ini = t
        voz_ini = 0.5
        voz_fin = voz_ini + len(a_preg) / sr
        n_op = len(p["opciones"])
        # Las respuestas aparecen mientras se lee la pregunta (desde la mitad), una detrás de otra
        primera = voz_ini + max(0.4, (voz_fin - voz_ini) * 0.45)
        paso = min(0.35, max(0.18, (voz_fin - primera) / max(1, n_op)))
        opciones = [primera + j * paso for j in range(n_op)]
        c_ini = max(voz_fin + 0.15, opciones[-1] + 0.3)
        revela = c_ini + cuenta
        fin = revela + len(a_resp) / sr + 0.75
        bloques.append({"tipo": "pregunta", "i": i, "ini": ini, "fin": ini + fin,
                        "tiempos": {"voz_fin": voz_fin, "cuenta": c_ini, "revela": revela, "opciones": opciones}})
        voz.append((ini + voz_ini, a_preg))
        voz.append((ini + revela + 0.25, a_resp))
        t = ini + fin
    a_fin = audios[k]
    bloques.append({"tipo": "final", "ini": t, "fin": t + len(a_fin) / sr + 1.2})
    voz.append((t + 0.3, a_fin))
    return bloques, voz


def tic(alto=False):
    n = int(0.07 * sonido.SR)
    tt = np.arange(n) / sonido.SR
    f = 1500 if alto else 1050
    return (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 70) * 0.5).astype(np.float32)


def acierto():
    a, b = sonido.pop(1047, 0.18), sonido.pop(1568, 0.3)
    s = np.zeros(int(0.45 * sonido.SR), np.float32)
    s[: len(a)] += a
    o = int(0.09 * sonido.SR)
    s[o: o + len(b)] += b[: len(s) - o]
    return s * 0.9


def audio(bloques, voz, sr, canal, cat, carpeta):
    dur = bloques[-1]["fin"]
    n = int(dur * sr)
    pista = np.zeros(n + sr, np.float32)
    for seg, a in voz:
        i = int(seg * sr)
        pista[i: i + len(a)] += a[: len(pista) - i]
    efectos = []
    for b in bloques:
        efectos.append((max(0, b["ini"] - 0.05), sonido.whoosh(0.4, int(b["ini"] * 10))))
        if b["tipo"] == "pregunta":
            ts = b["tiempos"]
            efectos.append((b["ini"] + 0.02, sonido.golpe(0.3)))
            for x in ts["opciones"]:
                efectos.append((b["ini"] + x, sonido.pop(880, 0.1)))
            c = ts["cuenta"]
            while c < ts["revela"] - 0.05:
                efectos.append((b["ini"] + c, tic(ts["revela"] - c < 1.05)))
                c += 1.0
            efectos.append((b["ini"] + ts["revela"], acierto()))
    estilo = (cat.get("musica") or {}).get("estilo", "datos")
    mezcla = sonido.mezclar(pista[:n], sr, efectos, dur, estilo, volumen_musica=0.5)
    bruto, final = carpeta / "mezcla.wav", carpeta / "mezcla_norm.wav"
    sf.write(bruto, mezcla, sonido.SR)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(bruto), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(final)], check=True)
    return final


# =====================================================================
#  Montaje
# =====================================================================

def montar(q, canal, bloques, ruta_audio, imgs, salida, solo=None):
    m = Montador(q, canal, imgs)
    total = bloques[-1]["fin"]
    n_frames = int(math.ceil(total * FPS))
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(ruta_audio), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{n_frames / FPS:.3f}",
           "-movflags", "+faststart", str(salida)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    inicio, anterior, bi_ant, corte_t, ultimo_bloque = time.time(), None, -1, 0.0, None
    for nf in range(n_frames):
        t = nf / FPS
        bi = next((k for k, b in enumerate(bloques) if b["ini"] <= t < b["fin"]), len(bloques) - 1)
        b = bloques[bi]
        tl = t - b["ini"]
        if b["tipo"] == "gancho":
            lz = m.gancho(t, tl, total)
        elif b["tipo"] == "pregunta":
            lz = m.pregunta(t, tl, total, b["i"], b["tiempos"])
        else:
            lz = m.final(t, tl, total)
        # Fundido rápido entre pantallas
        if bi != bi_ant:
            corte_t = t
            ultimo_bloque = anterior
        if bi > 0 and t - corte_t < 0.15 and ultimo_bloque is not None:
            lz = Image.blend(ultimo_bloque, lz, (t - corte_t) / 0.15)
        bi_ant = bi
        anterior = lz
        ff.stdin.write(lz.convert("RGB").tobytes())
        if solo is not None and nf in solo:
            lz.convert("RGB").save(SALIDA / f"{q['_nombre']}_fotograma_{nf:04d}.png")
        if nf % (FPS * 10) == 0:
            print(f"  {t:.0f}/{total:.0f} s ({time.time() - inicio:.0f} s montando)")
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("::error::ffmpeg no pudo montar el vídeo")
    print(f"Vídeo listo: {salida} ({total:.1f} s, {Path(salida).stat().st_size / 1e6:.1f} MB)")
    return total


def nombre_canal(canal):
    menores = {"de", "del", "la", "el", "al", "y", "a", "en"}
    return " ".join(p if (i and p in menores) else p.capitalize()
                    for i, p in enumerate(str(canal["marca"]).lower().split()))


def texto_publicacion(q, canal):
    cat = canal["categorias"][q["categoria"]]
    titulo = str(q.get("titulo") or q.get("gancho"))
    etiquetas = ["#quiz", "#trivia", "#cultura", "#" + cat["nombre"].split()[0].lower().replace("í", "i"), "#shorts"]
    lineas = [
        f"TÍTULO: {titulo}",
        "",
        "DESCRIPCIÓN:",
        f"{q.get('gancho', '')} ¿Cuántas aciertas? Déjalo en los comentarios.",
        "",
        f"Un quiz nuevo de {nombre_canal(canal)} cada día: mitología, historia, geografía, ciencia, arte y deporte.",
        "Ilustraciones generadas con IA.",
        "",
        " ".join(etiquetas + [f"#{e}" for e in (q.get("etiquetas") or [])]),
    ]
    resp = ["", "RESPUESTAS (para fijar un comentario, si quieres):"]
    for i, p in enumerate(q["preguntas"], 1):
        resp.append(f"{i}. {p['opciones'][p['_ok']]}")
    if q.get("fuentes"):
        resp += ["", "FUENTES (para comprobar las respuestas):"] + [f"- {f}" for f in q["fuentes"]]
    return "\n".join(lineas + resp) + "\n"


def subir_drive(nombre):
    """Copia el vídeo y su texto a Google Drive: Vídeos/Dale al Coco/<título>/."""
    if not _env("GDRIVE_REFRESH"):
        print("Google Drive no está configurado (falta GDRIVE_REFRESH): no copio nada.")
        return
    import subir_drive as sd
    canal = cargar_canal()
    q = cargar_quiz(nombre, canal)
    titulo = sd.limpio(q.get("titulo") or nombre, 80)
    archivos = [(SALIDA / f"{nombre}.mp4", f"Short - {titulo}.mp4"), (SALIDA / f"{nombre}.txt", "Texto para YouTube.txt")]
    archivos = [(r, n) for r, n in archivos if r.exists()]
    if not archivos:
        print("Drive: no hay archivos que copiar.")
        return
    try:
        d = sd.Drive()
        raiz = d.carpeta(sd.CARPETA_RAIZ, "root")
        destino = d.carpeta(titulo, d.carpeta(sd.limpio(nombre_canal(canal)), raiz))
        for ruta, nuevo in archivos:
            print(f"  {d.subir(ruta, nuevo, destino)}: {nuevo}")
    except Exception as e:  # nunca rompemos el robot por Drive
        print(f"::warning::No se pudo copiar a Google Drive: {str(e)[:300]}")


def main():
    canal = cargar_canal()
    nombre = elegir_quiz(canal)
    if "--drive" in sys.argv:
        return subir_drive(nombre)
    q = cargar_quiz(nombre, canal)
    if q.get("publicado") and _env("REMONTAR") != "1":
        raise SystemExit(f"::error::{nombre} ya está publicado. Para montarlo otra vez, marca «Volver a montar».")
    print(f"Quiz: {nombre} · {canal['categorias'][q['categoria']]['nombre']} · {len(q['preguntas'])} preguntas")
    SALIDA.mkdir(parents=True, exist_ok=True)
    textos = [str(q.get("decir_gancho") or q.get("gancho") or "")]
    for i, p in enumerate(q["preguntas"]):
        textos += [frase_pregunta(p, i, len(q["preguntas"])), frase_respuesta(p)]
    textos.append(frase_final(q, canal))
    sr, auds = voces(textos, canal)
    imgs = imagenes(q, canal)
    bloques, voz = linea_de_tiempo(q, canal, sr, auds)
    with tempfile.TemporaryDirectory() as tmp:
        ruta_audio = audio(bloques, voz, sr, canal, canal["categorias"][q["categoria"]], Path(tmp))
        solo = None
        if _env("FOTOGRAMAS"):
            solo = {int(float(x) * FPS) for x in _env("FOTOGRAMAS").split(",")}
        dur = montar(q, canal, bloques, ruta_audio, imgs, SALIDA / f"{nombre}.mp4", solo)
    (SALIDA / f"{nombre}.txt").write_text(texto_publicacion(q, canal), encoding="utf-8")
    if dur > 60:
        print(f"::warning::El Short dura {dur:.0f} s: más de 60 s se ve peor en Shorts. Quita una pregunta o acorta datos.")
    # Nombre del quiz para los pasos siguientes del robot (Telegram, Drive)
    if _env("GITHUB_OUTPUT"):
        with open(_env("GITHUB_OUTPUT"), "a") as f:
            f.write(f"quiz={nombre}\n")


if __name__ == "__main__":
    sys.exit(main())
