"""Momento exacto de cada palabra de la voz, para clavar los subtítulos.

Se sabe cuánto dura cada frase (Gemini la devuelve aparte). Dentro de cada frase, un
reconocedor de voz local (faster-whisper) escucha el audio y dice cuándo suena cada palabra;
se alinea con el texto. Si el reconocedor falla o no está, se reparte el tiempo según las letras.
"""
import difflib
import os
import re
import unicodedata

import numpy as np

_MODELO = None


def _modelo():
    global _MODELO
    if _MODELO is None:
        from faster_whisper import WhisperModel
        _MODELO = WhisperModel((os.environ.get("WHISPER_MODELO") or "base").strip(), device="cpu", compute_type="int8")
    return _MODELO


def _norm(p):
    p = unicodedata.normalize("NFD", p.lower())
    return re.sub(r"[^a-z0-9ñ]", "", "".join(c for c in p if unicodedata.category(c) != "Mn"))


def _por_letras(palabras, ini, fin):
    letras = [max(1, len(w)) for w in palabras]
    total, t, out = sum(letras), ini, []
    for w, l in zip(palabras, letras):
        d = (fin - ini) * l / total
        out.append((w, t, t + d * 0.92))
        t += d
    return out


def _reconocidas(wav, sr):
    if sr != 16000:
        x = np.linspace(0, 1, len(wav))
        wav = np.interp(np.linspace(0, 1, int(len(wav) * 16000 / sr)), x, wav)
    segs, _ = _modelo().transcribe(wav.astype(np.float32), language="es", word_timestamps=True, beam_size=1,
                                   condition_on_previous_text=False)
    return [(_norm(w.word), float(w.start), float(w.end)) for s in segs for w in (s.words or []) if _norm(w.word)]


def de_frase(wav, sr, frase, desplazamiento=0.0):
    """[(palabra tal cual en el texto, ini, fin)] en segundos (sumando `desplazamiento`)."""
    palabras = frase.split()
    dur = len(wav) / sr
    try:
        oidas = _reconocidas(wav, sr)
    except Exception as e:
        print(f"  (sin reconocedor de voz: reparto por letras · {type(e).__name__})")
        oidas = []
    base = _por_letras(palabras, 0.05, dur - 0.05)
    if oidas:
        esperadas = [_norm(w) for w in palabras]
        m = difflib.SequenceMatcher(None, esperadas, [o[0] for o in oidas], autojunk=False)
        pareja = {}
        for b in m.get_matching_blocks():
            for k in range(b.size):
                pareja[b.a + k] = b.b + k
        if len(pareja) >= 0.5 * len(palabras):
            # palabras reconocidas: su tiempo real; las demás, interpoladas entre vecinas
            tiempos = [None] * len(palabras)
            for i, j in pareja.items():
                tiempos[i] = (oidas[j][1], oidas[j][2])
            for i in range(len(palabras)):
                if tiempos[i] is None:
                    a = next((tiempos[k][1] for k in range(i - 1, -1, -1) if tiempos[k]), 0.0)
                    b = next((tiempos[k][0] for k in range(i + 1, len(palabras)) if tiempos[k]), dur)
                    huecos = [k for k in range(len(palabras)) if tiempos[k] is None]
                    tiempos[i] = (a, max(a + 0.08, min(b, a + 0.4)))
            base = [(w, t0, t1) for w, (t0, t1) in zip(palabras, tiempos)]
    return [(w, round(a + desplazamiento, 3), round(b + desplazamiento, 3)) for w, a, b in base]
