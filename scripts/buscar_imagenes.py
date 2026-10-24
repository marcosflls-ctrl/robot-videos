"""Busca candidatas en Wikimedia Commons y hace una hoja de contactos para elegir la buena.

Uso:  BUSQUEDAS="Bolsa de Madrid;Juan Villalonga" python buscar_imagenes.py
Genera salida/candidatas.png (miniaturas numeradas) y salida/candidatas.txt (nombre exacto, autor y licencia).
Solo muestra imágenes con licencia libre. El nombre exacto se copia al guion como  imagen: "File:..."
"""
import io
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import imagenes

SALIDA = Path("salida")
FUENTE = Path(__file__).resolve().parent.parent / "fuentes" / "SpaceGrotesk-Medium.ttf"


def candidatas(busqueda, n=8):
    datos = imagenes._pedir({"action": "query", "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 330,
                             "generator": "search", "gsrnamespace": 6, "gsrlimit": 30,
                             "gsrsearch": f"{busqueda} filetype:bitmap"})
    paginas = sorted((datos.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
    salida = []
    for p in paginas:
        info = imagenes._info([p])
        if info:
            ii = p["imageinfo"][0]
            salida.append({**info, "mini": ii.get("thumburl") or ii["url"]})
        if len(salida) >= n:
            break
    return salida


def main():
    SALIDA.mkdir(exist_ok=True)
    busquedas = [b.strip() for b in (os.environ.get("BUSQUEDAS") or "").split(";") if b.strip()]
    f = ImageFont.truetype(str(FUENTE), 15)
    fb = ImageFont.truetype(str(FUENTE), 22)
    filas, texto = [], []
    for b in busquedas:
        cs = candidatas(b)
        texto.append(f"\n## {b}")
        fila = Image.new("RGB", (8 * 340 + 10, 300), (30, 30, 30))
        d = ImageDraw.Draw(fila)
        d.text((10, 6), b, font=fb, fill=(255, 210, 120))
        for i, c in enumerate(cs):
            texto.append(f"{i + 1}. {c['titulo']} — {c['autor']} ({c['licencia']})")
            try:
                req = urllib.request.Request(c["mini"], headers={"User-Agent": imagenes.AGENTE})
                with urllib.request.urlopen(req, timeout=30) as r:
                    im = Image.open(io.BytesIO(r.read())).convert("RGB")
                im.thumbnail((330, 220))
                fila.paste(im, (10 + i * 340, 40))
            except Exception as e:
                d.text((10 + i * 340, 100), f"error {type(e).__name__}", font=f, fill=(255, 100, 100))
            d.text((10 + i * 340, 266), f"{i + 1}. {c['titulo'][5:42]}", font=f, fill=(230, 230, 230))
        filas.append(fila)
    hoja = Image.new("RGB", (8 * 340 + 10, 300 * max(1, len(filas))), (0, 0, 0))
    for k, fila in enumerate(filas):
        hoja.paste(fila, (0, 300 * k))
    hoja.save(SALIDA / "candidatas.png")
    (SALIDA / "candidatas.txt").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto))


if __name__ == "__main__":
    main()
