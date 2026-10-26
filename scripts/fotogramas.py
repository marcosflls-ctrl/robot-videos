"""Describe con IA (Gemini, visión) los fotogramas de una carpeta, una sola vez por imagen.

Así el director sabe qué muestra cada imagen («Lucía al volante de noche», «playa de Vice City
al atardecer»...) y la usa solo donde encaja. Las descripciones se guardan en un JSON (caché):
si la imagen no cambia, no se vuelve a pedir.
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

EXT = (".jpg", ".jpeg", ".png", ".webp")
PROMPT = ("Describe esta imagen en español en una sola frase de máximo 14 palabras: qué se ve (personas, "
          "vehículos, lugar, hora del día). Si es claramente un fotograma de GTA 6 y reconoces a Lucía o a Jason, "
          "dilo; si no estás seguro de quién es, no pongas nombres. Solo la frase, sin comillas.")


def _pedir(img_bytes):
    clave = os.environ["GEMINI_API_KEY"].strip()
    modelos = [m for m in [(os.environ.get("GEMINI_MODELO_TEXTO") or "").strip(), "gemini-flash-latest", "gemini-2.5-flash"] if m]
    cuerpo = json.dumps({"contents": [{"role": "user", "parts": [
        {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode()}},
        {"text": PROMPT}]}], "generationConfig": {"temperature": 0.2}}).encode()
    ultimo = None
    for modelo in modelos:
        for intento in range(3):
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                                         data=cuerpo, method="POST", headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    datos = json.loads(r.read())
                partes = datos["candidates"][0]["content"]["parts"]
                return " ".join("".join(p.get("text", "") for p in partes if not p.get("thought")).split())[:140]
            except urllib.error.HTTPError as e:
                ultimo = f"{modelo}: {e.code}"
                if e.code in (429, 500, 503) and intento < 2:
                    time.sleep(10 * (intento + 1))
                    continue
                break
            except Exception as e:
                ultimo = f"{modelo}: {e}"
                break
    raise RuntimeError(f"no pude describir la imagen ({ultimo})")


def describir(carpeta, cache_json, maximo=60):
    """Devuelve {id: {"archivo": ruta, "describe": texto}} de hasta `maximo` imágenes de la carpeta."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return {}
    try:
        cache = json.loads(Path(cache_json).read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    salida, nuevas = {}, 0
    archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXT)[:maximo]
    for i, p in enumerate(archivos, 1):
        datos = p.read_bytes()
        huella = hashlib.sha1(datos).hexdigest()[:16]
        if huella not in cache:
            try:
                im = Image.open(io.BytesIO(datos)).convert("RGB")
                im.thumbnail((768, 768))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=85)
                cache[huella] = _pedir(buf.getvalue())
                nuevas += 1
                print(f"  fotograma {p.name}: {cache[huella]}")
            except Exception as e:
                print(f"::warning::{p.name}: {e}")
                continue
        salida[f"t{i}"] = {"archivo": str(p), "describe": cache[huella]}
    Path(cache_json).write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Fotogramas: {len(salida)} ({nuevas} descritos ahora, el resto de la caché)")
    return salida
