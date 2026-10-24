"""Imágenes para el canal de historia: de Wikimedia Commons (licencia libre) o de la carpeta guiones/imagenes/.

En el guion, una escena de tipo foto o boceto puede llevar:
    imagen: "File:Laureano Figuerola.jpg"   archivo exacto de Commons (lo más seguro)
    imagen: "imagenes/mi_foto.jpg"          archivo propio dentro de guiones/
    buscar_imagen: "Laureano Figuerola"     búsqueda en Commons (coge la primera con licencia libre)

Solo se aceptan licencias que permiten uso comercial: dominio público, CC0, CC BY y CC BY-SA.
El autor y la licencia de cada imagen se apuntan para la descripción del vídeo.
Las descargas se guardan en cache_imagenes/ para no repetirlas.
"""
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "cache_imagenes"
API = "https://commons.wikimedia.org/w/api.php"
AGENTE = "robot-videos/1.0 (canal de historia económica; https://github.com/marcosflls-ctrl/robot-videos)"
LIBRES = ("public domain", "pd", "cc0", "cc by", "cc-by", "no restrictions", "attribution")
PROHIBIDAS = ("nc", "nd", "fair use", "non-free")


def _pedir(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    for intento in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as e:
            if intento == 3:
                raise
            time.sleep(3 * (intento + 1))


def _limpiar(txt):
    txt = re.sub(r"<[^>]+>", "", html.unescape(str(txt or "")))
    return " ".join(txt.split())[:120]


def _licencia_ok(meta):
    lic = _limpiar(meta.get("LicenseShortName", {}).get("value", "")).lower()
    uso = _limpiar(meta.get("UsageTerms", {}).get("value", "")).lower()
    texto = f"{lic} {uso}"
    if any(re.search(rf"\b{p}\b", texto) for p in PROHIBIDAS):
        return False
    return any(p in texto for p in LIBRES)


def _info(paginas):
    """Primera página con imagen jpg/png/tif de licencia libre -> dict o None."""
    for p in paginas:
        ii = (p.get("imageinfo") or [None])[0]
        if not ii or ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff", "image/webp"):
            continue
        meta = ii.get("extmetadata") or {}
        if not _licencia_ok(meta):
            print(f"    (descartada por licencia: {p.get('title')})")
            continue
        return {
            "titulo": p["title"],
            "url": ii.get("thumburl") or ii["url"],
            "pagina": ii.get("descriptionurl", ""),
            "autor": _limpiar(meta.get("Artist", {}).get("value", "")) or "Autor desconocido",
            "licencia": _limpiar(meta.get("LicenseShortName", {}).get("value", "")),
        }
    return None


def _commons(archivo=None, busqueda=None):
    comunes = {"action": "query", "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 1920}
    if archivo:
        titulo = archivo if archivo.lower().startswith(("file:", "archivo:")) else f"File:{archivo}"
        datos = _pedir({**comunes, "titles": titulo})
    else:
        datos = _pedir({**comunes, "generator": "search", "gsrnamespace": 6, "gsrlimit": 12,
                        "gsrsearch": f"{busqueda} filetype:bitmap"})
    paginas = (datos.get("query") or {}).get("pages") or []
    paginas.sort(key=lambda p: p.get("index", 0))
    return _info(paginas)


def conseguir(escena, carpeta_guiones):
    """Devuelve (Image, crédito) o (None, "") si no hay imagen o no se encuentra."""
    ref = escena.get("imagen")
    busca = escena.get("buscar_imagen")
    if not ref and not busca:
        return None, ""
    if ref and not str(ref).lower().startswith(("file:", "archivo:")) and (carpeta_guiones / str(ref)).exists():
        ruta = carpeta_guiones / str(ref)
        return Image.open(ruta).convert("RGB"), str(escena.get("credito") or "")
    CACHE.mkdir(exist_ok=True)
    clave = hashlib.sha1(f"{ref}|{busca}".encode("utf-8")).hexdigest()[:16]
    meta_ruta, img_ruta = CACHE / f"{clave}.json", CACHE / f"{clave}.img"
    try:
        if meta_ruta.exists() and img_ruta.exists():
            info = json.loads(meta_ruta.read_text(encoding="utf-8"))
        else:
            info = _commons(archivo=str(ref) if ref else None, busqueda=None if ref else str(busca))
            if not info:
                print(f"::warning::No hay imagen libre en Commons para «{ref or busca}»")
                return None, ""
            req = urllib.request.Request(info["url"], headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=120) as r:
                img_ruta.write_bytes(r.read())
            meta_ruta.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
            print(f"  Commons: «{ref or busca}» -> {info['titulo']} ({info['licencia']}, {info['autor']})")
        img = Image.open(img_ruta)
        img.load()
        escena["_commons"] = info
        credito = escena.get("credito") or f"{info['autor']} · {info['licencia']} · Wikimedia Commons"
        return img.convert("RGB"), credito
    except Exception as e:  # nunca rompemos el vídeo por una imagen
        print(f"::warning::No se pudo traer la imagen «{ref or busca}»: {type(e).__name__}: {str(e)[:200]}")
        return None, ""
