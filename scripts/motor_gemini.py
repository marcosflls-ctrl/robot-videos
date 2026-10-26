"""Voz con Gemini TTS (API de Google), mismo uso que MotorVoz.

Variables:
    GEMINI_API_KEY   clave de la API de Gemini (Google AI Studio)
    GEMINI_VOZ       nombre de una voz de Gemini (por defecto Orus; también Charon, Puck...).
                     «clonada» usa GEMINI_VOICE_ID si algún día se crea una voz propia.
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
        elegida = (os.environ.get("GEMINI_VOZ") or "Orus").strip()
        clonada = (os.environ.get("GEMINI_VOICE_ID") or "").strip()
        if elegida == "clonada":
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
                if e.code == 429 and "per day" in detalle:
                    # Cupo del día gastado: reintentar no sirve. Lo ya hecho queda en la caché.
                    raise SystemExit("::error::Se ha gastado el cupo diario de voz de Gemini. Las frases ya leídas "
                                     "quedan guardadas: vuelve a lanzarlo mañana y seguirá donde lo dejó. "
                                     f"Detalle: {detalle}")
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


    # ---------- varias frases en UNA sola petición (ahorra cupo: 1 petición por vídeo) ----------

    def decir_seguido(self, frases, separador="\n\n"):
        """Lee varias frases en UNA petición y devuelve (audio entero, textos tal como se dijeron).

        El corte por frases lo hace voz_tandas.py escuchando el audio."""
        dichos = [a_voz(f, GLOSARIO_GEMINI) for f in frases]
        for d in dichos:
            print("  ·", d)
        return self._audio(self._pedir(separador.join(dichos))), dichos

    def decir_varias(self, frases, separador=" "):
        """Devuelve [(audio, piezas)] por frase, pidiendo todo el guion de una vez.

        Gemini lee el texto seguido; luego se corta el audio en los silencios que caen más
        cerca de donde debería acabar cada frase (según su número de letras).
        """
        dichos = [a_voz(f, GLOSARIO_GEMINI) for f in frases]
        print("  · (una sola petición) " + " | ".join(dichos))
        wav = self._audio(self._pedir(separador.join(dichos)))
        cortes = _cortar_en_silencios(wav, self.sr, [len(d) for d in dichos])
        salida = []
        for (a, b), frase in zip(cortes, frases):
            trozo = _recortar(wav[a:b], self.sr)
            salida.append((trozo, [(frase, 0.0, len(trozo) / self.sr)]))
        return salida


def _recortar(wav, sr):
    env = np.abs(wav)
    activo = np.where(env > 0.02 * (env.max() or 1))[0]
    if len(activo):
        wav = wav[max(0, activo[0] - int(0.03 * sr)): activo[-1] + int(0.08 * sr)]
    return wav.astype(np.float32)


def _cortar_en_silencios(wav, sr, letras):
    """Divide el audio en len(letras) tramos, cortando en silencios cercanos al punto esperado."""
    n = len(letras)
    if n <= 1:
        return [(0, len(wav))]
    ventana = max(1, int(0.02 * sr))
    env = np.convolve(np.abs(wav), np.ones(ventana) / ventana, mode="same")
    umbral = 0.04 * (env.max() or 1)
    silencio = env < umbral
    # Huecos de silencio de al menos 0,12 s: (inicio, fin, centro)
    huecos, i = [], 0
    while i < len(silencio):
        if silencio[i]:
            j = i
            while j < len(silencio) and silencio[j]:
                j += 1
            if (j - i) / sr >= 0.12 and i > 0 and j < len(silencio):
                huecos.append((i, j, (i + j) // 2))
            i = j
        else:
            i += 1
    total = sum(letras)
    acumulado, esperados = 0, []
    for l in letras[:-1]:
        acumulado += l
        esperados.append(int(len(wav) * acumulado / total))
    cortes, ultimo = [], 0
    for e in esperados:
        candidatos = [h for h in huecos if h[2] > ultimo + int(0.3 * sr)]
        if candidatos:
            # El hueco más cercano al punto esperado; a igualdad, el más largo
            h = min(candidatos, key=lambda h: abs(h[2] - e) - 0.3 * (h[1] - h[0]))
            corte = h[2]
        else:
            corte = max(e, ultimo + 1)
        cortes.append(corte)
        ultimo = corte
    limites = [0] + cortes + [len(wav)]
    return [(limites[k], limites[k + 1]) for k in range(n)]
