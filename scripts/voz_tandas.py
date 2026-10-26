"""Corta en frases un audio que Gemini ha leído de una vez (varias frases por petición).

Gemini no dice dónde acaba cada frase, así que un reconocedor de voz local (faster-whisper)
escucha el audio, saca el momento de cada palabra y se alinea con el texto. El corte se pone
en el silencio entre la última palabra de una frase y la primera de la siguiente.

Si algo no cuadra devuelve None, y quien llama pide esas frases una a una (más seguro).
"""
import difflib
import os
import re
import unicodedata

import numpy as np

from numeros import a_voz

_MODELO = None


def _modelo():
    global _MODELO
    if _MODELO is None:
        from faster_whisper import WhisperModel
        nombre = (os.environ.get("WHISPER_MODELO") or "base").strip()
        _MODELO = WhisperModel(nombre, device="cpu", compute_type="int8")
    return _MODELO


def _norm(palabra):
    p = unicodedata.normalize("NFD", palabra.lower())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", p)


def _palabras(texto):
    return [w for w in (_norm(x) for x in texto.split()) if w]


def _reconocer(wav, sr):
    """Palabras reconocidas: [(palabra normalizada, inicio s, fin s)]."""
    if sr != 16000:
        x = np.linspace(0, 1, len(wav))
        wav = np.interp(np.linspace(0, 1, int(len(wav) * 16000 / sr)), x, wav)
    segmentos, _ = _modelo().transcribe(wav.astype(np.float32), language="es", word_timestamps=True,
                                        beam_size=1, vad_filter=False, condition_on_previous_text=False)
    salida = []
    for s in segmentos:
        for w in s.words or []:
            texto = w.word.strip()
            if any(ch.isdigit() for ch in texto):  # «1979» -> «mil novecientos setenta y nueve»
                texto = a_voz(texto)
            for p in _palabras(texto):
                salida.append((p, float(w.start), float(w.end)))
    return salida


def _silencio_mas_largo(wav, sr, t0, t1):
    """Centro (en muestras) del silencio más largo entre t0 y t1 segundos."""
    a, b = max(0, int(t0 * sr)), min(len(wav), int(t1 * sr))
    if b - a < int(0.04 * sr):
        return (a + b) // 2
    ventana = max(1, int(0.02 * sr))
    env = np.convolve(np.abs(wav[a:b]), np.ones(ventana) / ventana, mode="same")
    silencio = env < 0.04 * (np.abs(wav).max() or 1)
    mejor, i = None, 0
    while i < len(silencio):
        if silencio[i]:
            j = i
            while j < len(silencio) and silencio[j]:
                j += 1
            if mejor is None or j - i > mejor[1] - mejor[0]:
                mejor = (i, j)
            i = j
        else:
            i += 1
    if mejor is None:
        return (a + b) // 2
    return a + (mejor[0] + mejor[1]) // 2


def cortar_tanda(wav, sr, dichos, holgura=4):
    """Devuelve [(inicio, fin)] en muestras, uno por frase de `dichos`, o None si no es fiable."""
    n = len(dichos)
    if n <= 1:
        return [(0, len(wav))]
    esperadas, frase_de = [], []
    for k, d in enumerate(dichos):
        ps = _palabras(d)
        if not ps:
            return None
        esperadas += ps
        frase_de += [k] * len(ps)
    try:
        oidas = _reconocer(wav, sr)
    except Exception as e:  # sin reconocedor: mejor pedir una a una
        print(f"  (no se pudo escuchar el audio para cortarlo: {e})")
        return None
    if not oidas:
        return None
    emparejar = difflib.SequenceMatcher(None, esperadas, [p for p, _, _ in oidas], autojunk=False)
    pareja = {}  # índice de palabra esperada -> índice de palabra oída
    for bloque in emparejar.get_matching_blocks():
        for d in range(bloque.size):
            pareja[bloque.a + d] = bloque.b + d
    if len(pareja) < 0.6 * len(esperadas):
        print(f"  (solo se reconoció el {100 * len(pareja) // len(esperadas)} % de las palabras)")
        return None
    cortes = []
    for k in range(n - 1):
        ultima = max(i for i, f in enumerate(frase_de) if f == k)
        primera = ultima + 1
        antes = [i for i in range(ultima, max(-1, ultima - holgura - 1), -1) if i in pareja]
        despues = [i for i in range(primera, min(len(esperadas), primera + holgura + 1)) if i in pareja]
        if not antes or not despues:
            return None
        t0 = oidas[pareja[antes[0]]][2]
        t1 = oidas[pareja[despues[0]]][1]
        if t1 < t0 - 0.05:
            return None
        cortes.append(_silencio_mas_largo(wav, sr, t0 - 0.05, t1 + 0.05))
    if any(b <= a for a, b in zip([0] + cortes, cortes + [len(wav)])):
        return None
    limites = [0] + cortes + [len(wav)]
    return [(limites[i], limites[i + 1]) for i in range(n)]
