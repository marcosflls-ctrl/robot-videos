"""Lee el texto de prueba con Chatterbox, sin tarjeta gráfica.

Modelo (variable MODELO):
  - "es-es": modelo entrenado en español de España (ResembleAI/Chatterbox-Multilingual-es-es, MIT).
  - "v3":    modelo general de 23 idiomas, versión 3 (ResembleAI/chatterbox, MIT).

Voces que genera:
  - la voz que trae el modelo;
  - una voz española de muestra de Resemble (solo para comparar; antes de usarla en
    vídeos habría que confirmar que se puede usar comercialmente);
  - tu voz, si en el repositorio hay un archivo voz_referencia.wav (10-20 s).
"""
import os
import shutil
import time
import urllib.request
from pathlib import Path

import soundfile as sf
import torch
from huggingface_hub import hf_hub_download

from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from comun import RAIZ, SALIDA, guardar_tiempo, leer_texto

MODELO = os.environ.get("MODELO", "es-es")
MUESTRA_ES = "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/es_f1.flac"

SALIDA.mkdir(exist_ok=True)
texto = leer_texto()


def aviso(mensaje: str) -> None:
    """Deja el mensaje visible en el resumen de la ejecución de GitHub."""
    print("::error::" + mensaje.replace("\n", " | ")[:900])


def cargar_es_es() -> ChatterboxMultilingualTTS:
    """Junta en una carpeta las piezas del modelo de España y las comunes del modelo base.

    El paquete de España trae su propio decodificador de voz (s3gen_v3.pt), al que le faltan
    dos tablas fijas que el programa calcula solo; por eso se carga encima del decodificador
    base sin exigir esas dos tablas. Si algo falla, el motivo queda en el resumen de la ejecución.
    """
    carpeta = Path("modelo_es_es")
    carpeta.mkdir(exist_ok=True)
    piezas = [
        ("ResembleAI/chatterbox", "ve.pt"),
        ("ResembleAI/chatterbox", "conds.pt"),
        ("ResembleAI/chatterbox", "s3gen.pt"),
        ("ResembleAI/Chatterbox-Multilingual-es-es", "t3_es_es.safetensors"),
        ("ResembleAI/Chatterbox-Multilingual-es-es", "grapheme_mtl_merged_expanded_v1.json"),
    ]
    try:
        for repo, archivo in piezas:
            shutil.copyfile(hf_hub_download(repo, archivo), carpeta / archivo)
        modelo = ChatterboxMultilingualTTS.from_local(carpeta, "cpu", t3_model="t3_es_es.safetensors")
    except Exception as error:
        aviso(f"No se pudo cargar el modelo de España: {type(error).__name__}: {str(error)[:600]}")
        raise

    try:
        estado = torch.load(
            hf_hub_download("ResembleAI/Chatterbox-Multilingual-es-es", "s3gen_v3.pt"),
            map_location="cpu", weights_only=True,
        )
        faltan, sobran = modelo.s3gen.load_state_dict(estado, strict=False)
        faltan = [k for k in faltan if not k.startswith("tokenizer.")]
        if faltan or sobran:
            raise RuntimeError(f"no encaja: faltan {faltan[:5]}, sobran {sobran[:5]}")
        print("Modelo de España cargado con su propio decodificador de voz (s3gen_v3)")
    except Exception as error:
        aviso(f"Decodificador de España no usado, sigo con el base: {type(error).__name__}: {str(error)[:600]}")
        modelo.s3gen.load_state_dict(
            torch.load(carpeta / "s3gen.pt", map_location="cpu", weights_only=True)
        )
    return modelo


inicio = time.time()
modelo = cargar_es_es() if MODELO == "es-es" else ChatterboxMultilingualTTS.from_pretrained("cpu", t3_model="v3")
print(f"Modelo {MODELO} cargado en {round(time.time() - inicio)} s")

voces = {"defecto": None}
try:
    urllib.request.urlretrieve(MUESTRA_ES, "muestra_es.flac")
    voces["muestra-es"] = "muestra_es.flac"
except Exception as error:  # si no se puede bajar la muestra, seguimos con el resto
    print("No se pudo bajar la voz de muestra:", error)
if (RAIZ / "voz_referencia.wav").exists():
    voces["tu-voz"] = str(RAIZ / "voz_referencia.wav")

for voz, referencia in voces.items():
    nombre = f"chatterbox_{MODELO}_{voz}"
    inicio = time.time()
    extra = {"audio_prompt_path": referencia} if referencia else {}
    wav = modelo.generate(texto, language_id="es", **extra)
    sf.write(SALIDA / f"{nombre}.wav", wav.squeeze(0).cpu().numpy(), modelo.sr)
    guardar_tiempo(nombre, inicio)
