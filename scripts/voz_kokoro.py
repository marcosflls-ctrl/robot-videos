"""Lee el texto de prueba con Kokoro (voces españolas Dora y Alex)."""
import time

import numpy as np
import soundfile as sf
from kokoro import KPipeline

from comun import SALIDA, guardar_tiempo, leer_texto

SALIDA.mkdir(exist_ok=True)
texto = leer_texto()
print("Texto:", texto)

pipeline = KPipeline(lang_code="e", repo_id="hexgrad/Kokoro-82M")  # "e" = español

for voz, nombre in [("ef_dora", "kokoro_dora"), ("em_alex", "kokoro_alex")]:
    inicio = time.time()
    trozos = [r.audio for r in pipeline(texto, voice=voz, speed=1.0) if r.audio is not None]
    audio = np.concatenate([np.asarray(t) for t in trozos])
    sf.write(SALIDA / f"{nombre}.wav", audio, 24000)
    guardar_tiempo(nombre, inicio)
