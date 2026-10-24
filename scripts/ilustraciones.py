"""Ilustraciones generadas con el modelo de imágenes de Gemini («Nano Banana»).

En el guion, una escena «ilustracion» lleva «escena»: qué se ve (lugar, época, situación).
El robot le añade siempre el mismo estilo del canal (canal_historia.yaml → ilustraciones.estilo),
para que todas parezcan de la misma mano.

Usa la clave GEMINI_API_KEY (la misma de la voz). Las imágenes se guardan en cache_imagenes/:
si la descripción no cambia, no se vuelve a pagar.

Para ambientar, no para retratar personas reales ni para «documentar» hechos concretos:
eso va con fotos de archivo o bocetos.
"""
import base64
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "cache_imagenes"
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def _pedir(clave, cuerpo):
    datos = json.dumps(cuerpo).encode("utf-8")
    for intento in range(5):
        req = urllib.request.Request(URL, data=datos, method="POST",
                                     headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:400]
            if e.code in (429, 500, 503) and intento < 4:
                time.sleep(15 * (intento + 1))
                continue
            raise RuntimeError(f"Gemini respondió {e.code}: {detalle}")
        except urllib.error.URLError:
            if intento < 4:
                time.sleep(5)
                continue
            raise


def _imagen(respuesta):
    trozos = []
    for paso in respuesta.get("steps", []):
        if paso.get("type") not in (None, "model_output"):
            continue
        for c in paso.get("content", []):
            if c.get("type") == "image" and c.get("data"):
                trozos.append(c["data"])
    if not trozos and isinstance(respuesta.get("output_image"), dict):
        trozos.append(respuesta["output_image"].get("data"))
    if not trozos or not trozos[-1]:
        raise RuntimeError("Gemini no devolvió imagen: " + json.dumps(respuesta)[:300])
    return Image.open(io.BytesIO(base64.b64decode(trozos[-1]))).convert("RGB")


def generar(escena, canal):
    """Devuelve (Image, crédito) o (None, "") si no se puede (sin clave, error...)."""
    cfg = canal.get("ilustraciones") or {}
    descripcion = str(escena.get("escena") or "").strip()
    if not descripcion:
        return None, ""
    estilo = " ".join(str(cfg.get("estilo", "")).split())
    modelo = str(cfg.get("modelo") or "gemini-nano-banana-2.1")
    tam = str(cfg.get("tamano") or "2K")
    prompt = f"{descripcion}\n\nEstilo: {estilo}"
    CACHE.mkdir(exist_ok=True)
    clave_cache = hashlib.sha1(f"{modelo}|{tam}|{prompt}".encode("utf-8")).hexdigest()[:16]
    ruta = CACHE / f"ia_{clave_cache}.jpg"
    credito = str(cfg.get("credito") or "Ilustración")
    if ruta.exists():
        return Image.open(ruta).convert("RGB"), credito
    clave = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not clave:
        print(f"::warning::Sin GEMINI_API_KEY no se puede generar la ilustración «{descripcion[:60]}»")
        return None, ""
    cuerpo = {"model": modelo, "input": prompt,
              "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "16:9", "image_size": tam}}
    try:
        inicio = time.time()
        img = _imagen(_pedir(clave, cuerpo))
        img.save(ruta, quality=93)
        print(f"  Ilustración ({modelo}, {time.time() - inicio:.0f} s): «{descripcion[:70]}»")
        return img, credito
    except Exception as e:  # nunca rompemos el vídeo por una ilustración
        print(f"::warning::No se pudo generar la ilustración «{descripcion[:60]}»: {str(e)[:300]}")
        return None, ""
