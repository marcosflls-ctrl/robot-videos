"""Voz con Gemini TTS (API de Google), mismo uso que MotorVoz.

Variables:
    GEMINI_API_KEY   clave de la API de Gemini (Google AI Studio)
    GEMINI_VOICE_ID  voz clonada de Marcos creada en AI Studio («voice_...»).
    GEMINI_VOZ       «clonada» (por defecto: la de GEMINI_VOICE_ID) o el nombre de una voz de
                     Gemini (Orus, Charon, Puck...). Sin voz clonada, se usa Orus.
    GEMINI_MODELO    modelo (por defecto gemini-3.8-flash-tts)
    GEMINI_ESTILO    cómo debe sonar (por defecto, presentador de vídeos cortos)

Cada frase se pide por separado (una petición por frase) para saber cuánto dura y
sincronizar los subtítulos. No necesita tarjeta gráfica: va en segundos.
"""
import base64
import io
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np
import soundfile as sf

from numeros import a_voz
from pathlib import Path

# Gemini sabe pronunciar nombres en inglés: usa un glosario corto propio (no el de Chatterbox)
GLOSARIO_GEMINI = Path(__file__).resolve().parent.parent / "glosario_gemini.txt"

URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
ESTILO = ("Presentador de vídeos cortos en español de España: cercano, con energía y ritmo ágil, "
          "pausas naturales en las comas, sin titubeos")


class MotorVozGemini:
    sr = 24000

    def __init__(self):
        self.clave = os.environ["GEMINI_API_KEY"].strip()
        self.modelo = (os.environ.get("GEMINI_MODELO") or "gemini-3.8-flash-tts").strip()
        elegida = (os.environ.get("GEMINI_VOZ") or "clonada").strip()
        clonada = (os.environ.get("GEMINI_VOICE_ID") or "").strip()
        if elegida == "clonada":
            if not clonada:
                print("::warning::No hay GEMINI_VOICE_ID (tu voz clonada): uso la voz Orus de Gemini")
            self.voz = clonada or "Orus"
        else:
            self.voz = elegida
        self.estilo = (os.environ.get("GEMINI_ESTILO") or ESTILO).strip()
        self.ultimas_piezas = []
        print(f"Voz: Gemini ({self.modelo}) · {'voz clonada' if self.voz.startswith(('voice_', 'voicekey_')) else 'voz ' + self.voz}")

    def _pedir(self, texto):
        cuerpo = {
            "model": self.modelo,
            "input": [{
                "type": "user_input",
                "content": [{
                    "type": "text",
                    "text": texto,
                    "annotations": [{"type": "speech_metadata", "style": self.estilo}],
                }],
            }],
            "response_format": {"type": "audio", "mime_type": "audio/l16", "sample_rate": self.sr},
            "generation_config": {"speech_config": [{"voice": self.voz}]},
        }
        datos = json.dumps(cuerpo).encode("utf-8")
        for intento in range(6):
            req = urllib.request.Request(URL, data=datos, method="POST", headers={
                "x-goog-api-key": self.clave, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detalle = e.read().decode("utf-8", "replace")[:500]
                if e.code in (429, 500, 503) and intento < 5:
                    espera = 10 * (intento + 1)
                    print(f"    (Gemini ocupado o límite gratuito: espero {espera} s)")
                    time.sleep(espera)
                    continue
                raise SystemExit(f"::error::Gemini TTS respondió {e.code}: {detalle}")
            except urllib.error.URLError as e:
                if intento < 5:
                    time.sleep(5)
                    continue
                raise SystemExit(f"::error::No se pudo conectar con Gemini: {e}")

    def _audio(self, respuesta):
        trozos = []
        for paso in respuesta.get("steps", []):
            if paso.get("type") not in (None, "model_output"):
                continue
            for c in paso.get("content", []):
                if c.get("type") == "audio" and c.get("data"):
                    trozos.append(base64.b64decode(c["data"]))
        if not trozos and isinstance(respuesta.get("output_audio"), dict):
            trozos.append(base64.b64decode(respuesta["output_audio"]["data"]))
        if not trozos:
            raise SystemExit("::error::Gemini no devolvió audio: " + json.dumps(respuesta)[:400])
        bruto = trozos[-1]
        if bruto[:4] == b"RIFF":  # vino como WAV
            wav, sr = sf.read(io.BytesIO(bruto), dtype="float32")
            if wav.ndim > 1:
                wav = wav.mean(axis=1)
            if sr != self.sr:
                x = np.linspace(0, 1, len(wav))
                wav = np.interp(np.linspace(0, 1, int(len(wav) * self.sr / sr)), x, wav).astype(np.float32)
            return wav
        return (np.frombuffer(bruto, dtype="<i2").astype(np.float32) / 32768.0)

    def decir(self, texto_pantalla: str) -> np.ndarray:
        dicho = a_voz(texto_pantalla, GLOSARIO_GEMINI)
        print("  ·", dicho)
        wav = self._audio(self._pedir(dicho))
        # Quita silencio al principio y al final
        env = np.abs(wav)
        activo = np.where(env > 0.02 * (env.max() or 1))[0]
        if len(activo):
            wav = wav[max(0, activo[0] - int(0.03 * self.sr)): activo[-1] + int(0.08 * self.sr)]
        self.ultimas_piezas = [(texto_pantalla, 0.0, len(wav) / self.sr)]
        return wav.astype(np.float32)
