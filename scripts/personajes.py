"""Personajes que salen siempre iguales: el presentador de cada canal y los personajes de cada guion.

Cómo se consigue que un personaje sea siempre el mismo:
1. Se dibuja UNA vez su «ficha» (cuerpo entero, de frente) a partir de sus rasgos fijos.
2. Cada vez que sale, esa ficha se manda a Gemini como imagen de referencia junto a la escena.
Las fichas y las poses se guardan en la caché: el presentador de un canal se paga una sola vez
y después se reutiliza en todos los vídeos.

El presentador se dibuja sobre un fondo liso magenta, que luego se recorta, para poder animarlo
por capas encima de cualquier escena (entra, rebota, se mueve al hablar).

Nunca se dibuja a una persona real reconocible: los personajes se distinguen por sus rasgos
(un sombrero, una bufanda, unas gafas), no por parecerse a nadie.
"""
import math

import numpy as np
from PIL import Image, ImageFilter

import ilustraciones

MAGENTA = (255, 0, 255)

FONDO_RECORTE = ("Fondo totalmente liso de color magenta puro (#FF00FF), uniforme, sin degradados, sin suelo, "
                 "sin sombras, sin otros objetos ni decorado. El personaje entero, de cuerpo completo, centrado y "
                 "sin tocar los bordes, con un margen amplio alrededor. Un solo personaje. Ningún tono magenta o "
                 "rosa intenso en el personaje.")

# Gestos del presentador cuando el guion no dice ninguno (momentos clave automáticos)
GESTOS = {
    "gancho": "mira al espectador con cara de intriga y levanta un dedo, como diciendo «escucha esto»",
    "capitulo": "abre un brazo hacia un lado presentando lo que viene, con gesto amable",
    "cierre": "se rasca la barbilla pensativo y mira al espectador, como haciendo una pregunta",
    "final_short": "señala hacia abajo con el brazo extendido, invitando a seguir mirando",
}


def _ficha_texto(nombre, rasgos):
    return (f"Hoja de personaje de «{nombre}»: una sola figura de cuerpo entero, de frente, en postura neutra y "
            f"relajada, brazos a los lados. Rasgos fijos que lo identifican: {rasgos}. "
            f"Rasgos muy marcados y fáciles de reconocer a distancia. " + FONDO_RECORTE)


def recortar(img, umbral=110, suavizado=60):
    """Quita el fondo magenta: devuelve RGBA recortada a su contenido."""
    a = np.asarray(img.convert("RGB"), np.float32)
    dist = np.sqrt(((a - np.array(MAGENTA, np.float32)) ** 2).sum(axis=2))
    alfa = np.clip((dist - umbral) / suavizado, 0, 1)
    # Quitar el reflejo magenta de los bordes (despill): el verde no puede quedar muy por debajo de rojo y azul
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    tope = g + 30
    a[..., 0] = np.minimum(r, np.maximum(tope, g))
    a[..., 2] = np.minimum(b, np.maximum(tope, g))
    rgba = np.dstack([a.clip(0, 255), alfa * 255]).astype(np.uint8)
    out = Image.fromarray(rgba, "RGBA")
    # Limpia motas sueltas y suaviza el borde
    m = out.getchannel("A").filter(ImageFilter.MedianFilter(3))
    out.putalpha(m)
    caja = m.point(lambda v: 255 if v > 40 else 0).getbbox()
    return out.crop(caja) if caja else out


def ficha(nombre, rasgos, canal):
    """Imagen de referencia del personaje (RGB, con su fondo liso) o None."""
    return ilustraciones.generar_imagen(_ficha_texto(nombre, rasgos), canal, aspecto="3:4",
                                        aviso=f"ficha de {nombre}")


def pose(nombre, rasgos, gesto, canal, ref):
    """El personaje haciendo un gesto, recortado (RGBA), o None."""
    if ref is None:
        return None
    texto = (f"El mismo personaje de la imagen de referencia, «{nombre}», exactamente igual (mismos rasgos: "
             f"{rasgos}), de cuerpo entero. Ahora {gesto}. Expresivo, con la postura clara y fácil de leer. "
             + FONDO_RECORTE)
    img = ilustraciones.generar_imagen(texto, canal, referencias=[ref], aspecto="3:4", aviso=f"{nombre}: {gesto}")
    return recortar(img) if img is not None else None


def texto_con_personajes(descripcion, nombres, fichas_guion):
    """Añade a la descripción de una escena quién es quién en las imágenes de referencia."""
    partes = []
    for k, n in enumerate(nombres, 1):
        p = fichas_guion[n]
        partes.append(f"La imagen de referencia {k} es «{p['nombre']}»: debe salir exactamente igual "
                      f"(mismos rasgos: {p['rasgos']}).")
    return descripcion + "\n\nPersonajes de la escena: " + " ".join(partes) + \
        " No copies el fondo liso de las referencias: dibuja la escena completa."


# =====================================================================
#  El presentador en pantalla (capa animada encima de la escena)
# =====================================================================

def _poner(lienzo, img, x, y):
    """alpha_composite que admite coordenadas fuera del lienzo (recorta lo que sobra)."""
    x, y = int(x), int(y)
    izq, arr = max(0, -x), max(0, -y)
    der = min(img.width, lienzo.width - x)
    aba = min(img.height, lienzo.height - y)
    if der <= izq or aba <= arr:
        return
    lienzo.alpha_composite(img.crop((izq, arr, der, aba)), (x + izq, y + arr))


def _envolvente(audio, sr, fps):
    if audio is None or not len(audio):
        return np.zeros(1, np.float32)
    paso = max(1, int(sr / fps))
    n = len(audio) // paso
    if n == 0:
        return np.zeros(1, np.float32)
    v = np.abs(audio[: n * paso]).reshape(n, paso).mean(axis=1)
    v = np.convolve(v, np.ones(3) / 3, mode="same")
    return (v / (v.max() + 1e-9)).astype(np.float32)


class CapaPresentador:
    """Dibuja al presentador encima de un fotograma: entra rebotando y se mueve mientras habla la voz."""

    def __init__(self, recorte, W, H, vertical, lado="derecha", grande=False, audio=None, sr=24000, fps=30,
                 voz_ini=0.35):
        self.W, self.H, self.vertical, self.lado = W, H, vertical, lado
        alto = int(H * (0.46 if grande else 0.30)) if vertical else int(H * (0.78 if grande else 0.46))
        if vertical and not grande:
            alto = int(H * 0.27)
        r = alto / recorte.height
        self.img = recorte.resize((max(1, int(recorte.width * r)), alto), Image.LANCZOS)
        self.sombra = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        self.sombra.putalpha(self.img.getchannel("A").point(lambda v: v * 0.35).filter(ImageFilter.GaussianBlur(10)))
        margen = int(W * 0.04)
        if vertical:
            base_y = int(H * (0.755 if grande else 0.74))
        else:
            base_y = H - int(H * 0.04)
        x = (W - margen - self.img.width) if lado == "derecha" else margen
        if grande:
            x = int(W * (0.62 if lado == "derecha" else 0.06)) if not vertical else (W - self.img.width) // 2
        self.x, self.base_y = x, base_y
        self.env, self.fps, self.voz_ini = _envolvente(audio, sr, fps), fps, voz_ini

    def dibujar(self, lienzo, t):
        if t < 0:
            return lienzo
        # Entrada: sube desde abajo con un rebote (0,45 s)
        q = min(1.0, t / 0.45)
        rebote = 1 - (1 - q) ** 3 + (math.sin(q * math.pi) * 0.08 if q < 1 else 0)
        dy = (1 - rebote) * self.img.height * 0.9
        # Al hablar: se «estira» un poco con la voz y se balancea suave
        k = int((t - self.voz_ini) * self.fps)
        habla = float(self.env[k]) if 0 <= k < len(self.env) else 0.0
        estira = 1 + 0.035 * habla
        balanceo = math.sin(t * 2.1) * 1.6 + math.sin(t * 5.3) * habla * 1.2
        img = self.img
        if abs(estira - 1) > 0.002 or abs(balanceo) > 0.05:
            w, h = img.size
            img = img.resize((w, max(1, int(h * estira))), Image.BILINEAR).rotate(
                balanceo, resample=Image.BICUBIC, expand=True, center=(w / 2, h * estira))
        x = int(self.x + (self.img.width - img.width) / 2)
        y = int(self.base_y - img.height + dy)
        _poner(lienzo, self.sombra, self.x + 8, self.base_y - self.sombra.height + dy + 6)
        _poner(lienzo, img, x, y)
        return lienzo
