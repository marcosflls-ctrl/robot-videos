"""Imagen del canal de quiz: la mascota (un cerebro con cara), el logo y el banner de YouTube.

Todo se dibuja con código (sin imágenes de terceros ni IA), así que es gratis y se puede repetir igual.
Los colores y el nombre salen de canal_quiz.yaml.

    python marca_quiz.py            -> salida/marca/logo.png (800x800) y banner.png (2560x1440)

La mascota también la usa quiz.py en el gancho y en la pantalla final de cada Short.
"""
import math
import random
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "fuentes"


def cargar_canal():
    return yaml.safe_load((RAIZ / "canal_quiz.yaml").read_text(encoding="utf-8"))


def c(v, a=255):
    return tuple(v) + (a,)


def fuente(nombre, tam):
    return ImageFont.truetype(str(FUENTES / nombre), max(8, int(tam)))


# ---------------------------------------------------------------------
#  Mascota: cerebro con cara
# ---------------------------------------------------------------------

def _bultos(cx, cy, rx, ry, n, r, semilla):
    """Círculos repartidos por el borde de una elipse: dan la silueta «abollada» del cerebro."""
    rnd = random.Random(semilla)
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * rnd.uniform(0.85, 1.12)
        out.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry, rr))
    return out


def mascota(lado=600, colores=None, gesto="feliz", mirada=(0.0, 0.0)):
    """Devuelve una imagen RGBA cuadrada con la mascota. gesto: feliz, sorpresa, guino, pensando."""
    col = colores or {}
    rosa = tuple(col.get("cerebro", (255, 138, 170)))
    rosa2 = tuple(col.get("cerebro_sombra", (232, 96, 136)))
    tinta = tuple(col.get("tinta", (38, 24, 52)))
    S = 4  # se dibuja a 4x y se reduce: bordes suaves
    L = lado * S
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = L * 0.5, L * 0.47
    rx, ry = L * 0.31, L * 0.25
    bultos = _bultos(cx, cy, rx, ry, 14, L * 0.12, 7)
    borde = int(L * 0.022)
    # Contorno: lo mismo un poco más grande, en tinta
    for x, y, r in bultos:
        d.ellipse((x - r - borde, y - r - borde, x + r + borde, y + r + borde), fill=c(tinta))
    d.ellipse((cx - rx - borde, cy - ry - borde, cx + rx + borde, cy + ry + borde), fill=c(tinta))
    for x, y, r in bultos:
        d.ellipse((x - r, y - r, x + r, y + r), fill=c(rosa))
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=c(rosa))
    # Sombra en la parte de abajo (volumen)
    sombra = Image.new("L", (L, L), 0)
    ds = ImageDraw.Draw(sombra)
    for x, y, r in bultos:
        if y > cy:
            ds.ellipse((x - r * 0.9, y - r * 0.5, x + r * 0.9, y + r * 0.95), fill=150)
    mascara = img.getchannel("A").point(lambda v: 255 if v > 0 else 0)
    interior = Image.new("L", (L, L), 0)
    for x, y, r in bultos:
        ImageDraw.Draw(interior).ellipse((x - r, y - r, x + r, y + r), fill=255)
    ImageDraw.Draw(interior).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    sombra = Image.composite(sombra, Image.new("L", (L, L), 0), interior).filter(ImageFilter.GaussianBlur(L * 0.02))
    capa = Image.new("RGBA", (L, L), c(rosa2))
    capa.putalpha(sombra)
    img.alpha_composite(capa)
    d = ImageDraw.Draw(img)
    # Pliegues (circunvoluciones) y la raya del medio
    g = int(L * 0.011)
    d.line([(cx, cy - ry - L * 0.08), (cx - L * 0.01, cy - ry * 0.4)], fill=c(tinta), width=g)
    for (ax, ay, a0, a1, rr) in [(-0.17, -0.13, 200, 320, 0.07), (0.17, -0.13, 220, 340, 0.07),
                                  (-0.27, 0.02, 120, 230, 0.06), (0.27, 0.02, 310, 60, 0.06),
                                  (-0.08, -0.25, 190, 330, 0.05), (0.09, -0.25, 210, 350, 0.05)]:
        r = L * rr
        x, y = cx + L * ax, cy + L * ay
        d.arc((x - r, y - r, x + r, y + r), a0, a1, fill=c(tinta), width=g)
    # Brillo
    brillo = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((cx - L * 0.2, cy - L * 0.24, cx - L * 0.12, cy - L * 0.19), fill=(255, 255, 255, 150))
    img.alpha_composite(brillo)
    d = ImageDraw.Draw(img)
    # Cara
    ojo_r = L * 0.062
    mx, my = mirada
    for lado_ojo in (-1, 1):
        ex, ey = cx + lado_ojo * L * 0.1, cy + L * 0.03
        if gesto == "guino" and lado_ojo == 1:
            d.arc((ex - ojo_r, ey - ojo_r * 0.6, ex + ojo_r, ey + ojo_r * 0.6), 200, 340, fill=c(tinta), width=int(g * 1.3))
            continue
        esc = 1.18 if gesto == "sorpresa" else 1.0
        d.ellipse((ex - ojo_r * esc - g, ey - ojo_r * esc * 1.1 - g, ex + ojo_r * esc + g, ey + ojo_r * esc * 1.1 + g),
                  fill=c(tinta))
        d.ellipse((ex - ojo_r * esc, ey - ojo_r * esc * 1.1, ex + ojo_r * esc, ey + ojo_r * esc * 1.1), fill=(255, 255, 255, 255))
        pr = ojo_r * 0.55
        px, py = ex + mx * ojo_r * 0.35, ey + my * ojo_r * 0.35 + (-ojo_r * 0.25 if gesto == "pensando" else 0)
        d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=c(tinta))
        d.ellipse((px - pr * 0.2 - pr * 0.35, py - pr * 0.55, px + pr * 0.2 - pr * 0.35, py - pr * 0.15), fill=(255, 255, 255, 255))
    # Mejillas
    for lado_ojo in (-1, 1):
        x, y = cx + lado_ojo * L * 0.19, cy + L * 0.1
        d.ellipse((x - L * 0.035, y - L * 0.018, x + L * 0.035, y + L * 0.018), fill=(250, 110, 140, 255))
    # Boca
    bx, by = cx, cy + L * 0.13
    if gesto == "sorpresa":
        d.ellipse((bx - L * 0.03, by - L * 0.035, bx + L * 0.03, by + L * 0.035), fill=c(tinta))
    elif gesto == "pensando":
        d.line([(bx - L * 0.04, by + L * 0.005), (bx + L * 0.04, by - L * 0.01)], fill=c(tinta), width=int(g * 1.2))
    else:
        d.chord((bx - L * 0.07, by - L * 0.05, bx + L * 0.07, by + L * 0.05), 0, 180, fill=c(tinta))
        d.chord((bx - L * 0.04, by + L * 0.005, bx + L * 0.04, by + L * 0.048), 0, 180, fill=(255, 110, 130, 255))
    # Patitas
    for lado_p in (-1, 1):
        x = cx + lado_p * L * 0.1
        d.line([(x, cy + ry + L * 0.04), (x, cy + ry + L * 0.13)], fill=c(tinta), width=int(g * 1.4))
        d.ellipse((x - L * 0.04 + lado_p * L * 0.015, cy + ry + L * 0.115, x + L * 0.04 + lado_p * L * 0.015,
                   cy + ry + L * 0.155), fill=c(tinta))
    return img.resize((lado, lado), Image.LANCZOS)


# ---------------------------------------------------------------------
#  Logo y banner
# ---------------------------------------------------------------------

def _fondo_puntos(w, h, base, punto, paso=46, r=4):
    img = Image.new("RGBA", (w, h), c(base))
    d = ImageDraw.Draw(img)
    for y in range(0, h + paso, paso):
        for x in range(0, w + paso, paso):
            xx = x + (paso // 2 if (y // paso) % 2 else 0)
            d.ellipse((xx - r, y - r, xx + r, y + r), fill=c(punto, 70))
    return img


def _interrogantes(img, caja, colores, n, tam, semilla, fuente_n):
    rnd = random.Random(semilla)
    x0, y0, x1, y1 = caja
    for _ in range(n):
        s = rnd.randint(int(tam * 0.6), tam)
        f = fuente(fuente_n, s)
        capa = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
        ImageDraw.Draw(capa).text((s, s), "?", font=f, fill=c(rnd.choice(colores), 200), anchor="mm")
        capa = capa.rotate(rnd.uniform(-25, 25), resample=Image.BICUBIC)
        img.alpha_composite(capa, (rnd.randint(x0, x1) - s, rnd.randint(y0, y1) - s))


def logo(canal, lado=800):
    col = canal["colores"]
    img = Image.new("RGBA", (lado, lado), c(col["fondo"]))
    d = ImageDraw.Draw(img)
    # Círculo de color detrás (YouTube recorta el logo en círculo)
    m = int(lado * 0.06)
    d.ellipse((m, m, lado - m, lado - m), fill=c(col["acento"]))
    m2 = int(lado * 0.1)
    d.ellipse((m2, m2, lado - m2, lado - m2), fill=c(col["fondo2"]))
    _interrogantes(img, (int(lado * .15), int(lado * .15), int(lado * .85), int(lado * .5)),
                   [col["acento"], col["acento2"]], 5, int(lado * 0.12), 3, canal["fuentes"]["tit"])
    masc = mascota(int(lado * 0.78), col)
    img.alpha_composite(masc, ((lado - masc.width) // 2, int(lado * 0.06)))
    # Nombre corto abajo, en una cinta
    f = fuente(canal["fuentes"]["tit"], lado * 0.085)
    texto = canal["marca_corta"]
    tw = f.getlength(texto)
    y = int(lado * 0.72)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((lado / 2 - tw / 2 - 30, y - 4, lado / 2 + tw / 2 + 30, y + lado * 0.11), radius=26,
                        fill=c(col["tinta"]))
    d.text((lado / 2, y + lado * 0.052), texto, font=f, fill=c(col["acento"]), anchor="mm")
    return img.convert("RGB")


def banner(canal, w=2560, h=1440):
    """Banner de YouTube (2560x1440). Todo lo importante va DENTRO de la zona segura central
    (1546x423), que es lo único que se ve en el móvil; fuera solo hay fondo decorativo."""
    col = canal["colores"]
    img = _fondo_puntos(w, h, col["fondo"], col["fondo2"])
    SW, SH = 1546, 423
    sx0, sy0 = (w - SW) // 2, (h - SH) // 2
    _interrogantes(img, (0, 0, w, h), [col["acento"], col["acento2"], col["cerebro"]], 26, 150, 11, canal["fuentes"]["tit"])
    franja = Image.new("RGBA", (w, SH + 60), c(col["fondo"], 235))
    img.alpha_composite(franja, (0, sy0 - 30))
    margen = 24
    # Mascota a la izquierda, entera dentro de la zona segura
    lado_m = SH - 2 * margen
    masc = mascota(lado_m, col, gesto="guino")
    img.alpha_composite(masc, (sx0 + margen, sy0 + margen))
    # Bloque de texto: desde la mascota hasta el borde derecho de la zona segura
    x = sx0 + margen + lado_m + 30
    ancho = sx0 + SW - margen - x
    d = ImageDraw.Draw(img)

    def ajustar(texto, nombre, tam):
        f = fuente(nombre, tam)
        while f.getlength(texto) > ancho and tam > 20:
            tam -= 2
            f = fuente(nombre, tam)
        return f

    f = ajustar(canal["marca"], canal["fuentes"]["tit"], 130)
    f2 = ajustar(canal["lema"], canal["fuentes"]["txt_b"], 44)
    d.text((x, sy0 + 105), canal["marca"], font=f, fill=c(col["texto"]), anchor="lm")
    d.text((x + 4, sy0 + 200), canal["lema"], font=f2, fill=c(col["acento"]), anchor="lm")
    # Categorías en chips, en las filas que hagan falta sin salirse
    fx = fuente(canal["fuentes"]["txt_b"], 30)
    xx, yy, alto, hueco = x, sy0 + 250, 54, 14
    for cat in canal["categorias"].values():
        t = cat["nombre"]
        cw = fx.getlength(t) + 40
        if xx + cw > x + ancho:
            xx, yy = x, yy + alto + hueco
        if yy + alto > sy0 + SH - margen:
            break
        d.rounded_rectangle((xx, yy, xx + cw, yy + alto), radius=alto // 2, fill=c(cat["color"]))
        d.text((xx + cw / 2, yy + alto / 2), t, font=fx, fill=c(col["tinta"]), anchor="mm")
        xx += cw + hueco
    return img.convert("RGB")


def comprobar_banner(img):
    """Copia del banner con las zonas que usa YouTube marcadas, para revisarlo."""
    w, h = img.size
    out = img.convert("RGBA")
    d = ImageDraw.Draw(out)
    for (zw, zh, color) in [(1546, 423, (0, 255, 0)), (2560, 423, (255, 200, 0)), (1855, 423, (0, 180, 255))]:
        x0, y0 = (w - zw) // 2, (h - zh) // 2
        d.rectangle((x0, y0, x0 + zw, y0 + zh), outline=color + (255,), width=4)
    return out.convert("RGB")


def main():
    canal = cargar_canal()
    out = RAIZ / "scripts" / "salida" / "marca"
    out.mkdir(parents=True, exist_ok=True)
    logo(canal).save(out / "logo.png")
    b = banner(canal)
    b.save(out / "banner.png")
    comprobar_banner(b).save(out / "banner_zonas.png")
    for g in ("feliz", "sorpresa", "guino", "pensando"):
        mascota(500, canal["colores"], gesto=g).save(out / f"mascota_{g}.png")
    print(f"Listo: {out}")


if __name__ == "__main__":
    sys.exit(main())
