"""Clips de vídeo de archivo gratuitos: Pexels o Pixabay (uso comercial gratis, sin atribución obligatoria).

Usa la clave que haya: PEXELS_API_KEY y/o PIXABAY_API_KEY (si están las dos, prueba primero Pexels).
Sin clave, o si algo falla, devuelve None y el vídeo se monta con fondos propios:
nunca se queda sin vídeo por culpa de un banco de clips.

Licencias: https://www.pexels.com/license/ · https://pixabay.com/service/license-summary/
"""
import hashlib
import json
import os
import random
import urllib.parse
import urllib.request
from pathlib import Path

CARPETA = Path("clips")
API = "https://api.pexels.com/videos/search"
_usados = set()


def _pedir(url, clave):
    req = urllib.request.Request(url, headers={"Authorization": clave, "User-Agent": "videos-cortos/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _mejor_archivo(video, orientacion="portrait"):
    """Elige el archivo más cercano a 1080x1920 (vertical) o a 1920x1080 (horizontal)."""
    archivos = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")]
    if not archivos:
        return None
    if orientacion == "landscape":
        horizontales = [f for f in archivos if f["width"] > f["height"]]
        candidatos = horizontales or archivos
        return min(candidatos, key=lambda f: abs(f["width"] - 1920) + (0 if f["width"] >= 1280 else 5000))
    verticales = [f for f in archivos if f["height"] > f["width"]]
    candidatos = verticales or archivos
    return min(candidatos, key=lambda f: abs(f["height"] - 1920) + (0 if f["height"] >= 1280 else 5000))


def buscar_clip(consulta, semilla="", minimo_seg=4, orientacion="portrait"):
    """Busca un clip en Pexels y, si no hay clave o no encuentra nada, en Pixabay.

    orientacion: «portrait» (Shorts, por defecto) o «landscape» (vídeos largos horizontales).
    """
    clip = _buscar_pexels(consulta, semilla, minimo_seg, orientacion)
    if clip is None:
        clip = _buscar_pixabay(consulta, semilla, minimo_seg)
    return clip


_cache_pixabay = {}


def _buscar_pixabay(consulta, semilla="", minimo_seg=4):
    clave = (os.environ.get("PIXABAY_API_KEY") or "").strip()
    if not clave:
        return None
    try:
        CARPETA.mkdir(exist_ok=True)
        if consulta not in _cache_pixabay:  # una sola petición por búsqueda y ejecución
            url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
                {"key": clave, "q": consulta[:100], "video_type": "film", "per_page": 50, "safesearch": "true"})
            _cache_pixabay[consulta] = _pedir_sin_cabecera(url).get("hits", [])
        videos = [v for v in _cache_pixabay[consulta] if v.get("duration", 0) >= minimo_seg and ("px", v["id"]) not in _usados]
        if not videos:
            print(f"  Pixabay: nada para «{consulta}»")
            return None
        rnd = random.Random(int(hashlib.md5((consulta + semilla).encode()).hexdigest(), 16))
        video = rnd.choice(videos[:25])
        # Calidad: 1080p (medium). El 4K se ve casi igual en el móvil y hace el montaje mucho más lento.
        vs = video["videos"]
        opciones = [vs.get("medium", {}), vs.get("large", {}), vs.get("small", {})]
        tam = next((o for o in opciones if o.get("url")), None)
        if not tam:
            return None
        _usados.add(("px", video["id"]))
        destino = CARPETA / f"pixabay_{video['id']}.mp4"
        if not destino.exists():
            req = urllib.request.Request(tam["url"], headers={"User-Agent": "videos-cortos/1.0"})
            with urllib.request.urlopen(req, timeout=180) as r, open(destino, "wb") as fh:
                fh.write(r.read())
        print(f"  Pixabay: «{consulta}» -> {video['id']} ({tam['width']}x{tam['height']}, {video['duration']} s) de {video.get('user', '?')}")
        return {"ruta": str(destino), "duracion": float(video["duration"]), "autor": video.get("user", ""),
                "url": video.get("pageURL", "")}
    except Exception as error:
        print(f"::warning::Pixabay falló con «{consulta}»: {type(error).__name__}: {str(error)[:200]}")
        return None


def _pedir_sin_cabecera(url):
    req = urllib.request.Request(url, headers={"User-Agent": "videos-cortos/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _buscar_pexels(consulta, semilla="", minimo_seg=4, orientacion="portrait"):
    clave = (os.environ.get("PEXELS_API_KEY") or "").strip()
    if not clave:
        return None
    try:
        CARPETA.mkdir(exist_ok=True)
        url = API + "?" + urllib.parse.urlencode({"query": consulta, "orientation": orientacion, "size": "medium", "per_page": 30})
        datos = _pedir(url, clave)
        videos = [v for v in datos.get("videos", []) if v.get("duration", 0) >= minimo_seg and v["id"] not in _usados]
        if not videos:
            url = API + "?" + urllib.parse.urlencode({"query": consulta, "per_page": 30})
            datos = _pedir(url, clave)
            videos = [v for v in datos.get("videos", []) if v.get("duration", 0) >= minimo_seg and v["id"] not in _usados]
        if not videos:
            print(f"  Pexels: nada para «{consulta}»")
            return None
        # Mismo día y misma consulta -> mismo clip; otro día -> otro clip
        rnd = random.Random(int(hashlib.md5((consulta + semilla).encode()).hexdigest(), 16))
        video = rnd.choice(videos[:20])
        archivo = _mejor_archivo(video, orientacion)
        if not archivo:
            return None
        _usados.add(video["id"])
        destino = CARPETA / f"{video['id']}.mp4"
        if not destino.exists():
            req = urllib.request.Request(archivo["link"], headers={"User-Agent": "videos-cortos/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as fh:
                fh.write(r.read())
        print(f"  Pexels: «{consulta}» -> {video['id']} ({archivo['width']}x{archivo['height']}, {video['duration']} s) de {video.get('user', {}).get('name', '?')}")
        return {"ruta": str(destino), "duracion": float(video["duration"]), "autor": video.get("user", {}).get("name", ""),
                "url": video.get("url", "")}
    except Exception as error:  # nunca rompemos el vídeo por Pexels
        print(f"::warning::Pexels falló con «{consulta}»: {type(error).__name__}: {str(error)[:200]}")
        return None
