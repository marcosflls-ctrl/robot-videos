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


def _silencios(wav, sr, t0, t1, minimo=0.06):
    """Silencios [(inicio, fin) en muestras] entre t0 y t1 segundos."""
    a, b = max(0, int(t0 * sr)), min(len(wav), int(t1 * sr))
    if b - a < int(0.04 * sr):
        return []
    ventana = max(1, int(0.02 * sr))
    env = np.convolve(np.abs(wav[a:b]), np.ones(ventana) / ventana, mode="same")
    silencio = env < 0.04 * (np.abs(wav).max() or 1)
    salida, i = [], 0
    while i < len(silencio):
        if silencio[i]:
            j = i
            while j < len(silencio) and silencio[j]:
                j += 1
            if (j - i) / sr >= minimo:
                salida.append((a + i, a + j))
            i = j
        else:
            i += 1
    return salida


def _elegir_corte(huecos, sr, t0, t1, estimado):
    """Entre los silencios que tocan [t0, t1] (segundos), el más largo y más cerca de lo estimado.

    Se mira cada silencio entero, aunque se salga de la ventana: el reconocedor suele dar los
    tiempos de las palabras un poco adelantados."""
    a, b = t0 * sr, t1 * sr
    tocan = [h for h in huecos if h[1] >= a and h[0] <= b]
    if not tocan:
        return int(((t0 + t1) / 2) * sr)
    def nota(h):
        largo = (h[1] - h[0]) / sr
        centro = (h[0] + h[1]) / 2 / sr
        return largo - 0.5 * abs(centro - estimado)
    h = max(tocan, key=nota)
    return (h[0] + h[1]) // 2


def cortar_tanda(wav, sr, dichos, holgura=6):
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
    huecos = _silencios(wav, sr, 0, len(wav) / sr)
    cortes = []
    for k in range(n - 1):
        ultima = max(i for i, f in enumerate(frase_de) if f == k)
        primera = ultima + 1
        antes = [i for i in range(ultima, max(-1, ultima - holgura - 1), -1) if i in pareja]
        despues = [i for i in range(primera, min(len(esperadas), primera + holgura + 1)) if i in pareja]
        if not antes or not despues:
            print(f"  (no se reconocen las palabras alrededor del final de la frase {k + 1})")
            return None
        t0 = oidas[pareja[antes[0]]][2]
        t1 = oidas[pareja[despues[0]]][1]
        if t1 < t0 - 0.15:
            print(f"  (tiempos cruzados al final de la frase {k + 1})")
            return None
        # Palabras sin reconocer entre las dos anclas: el corte cae en proporción a sus letras
        letras_antes = sum(len(esperadas[i]) for i in range(antes[0] + 1, primera))
        letras_despues = sum(len(esperadas[i]) for i in range(primera, despues[0]))
        reparto = letras_antes / (letras_antes + letras_despues) if letras_antes + letras_despues else 0.5
        estimado = t0 + (t1 - t0) * reparto
        cortes.append(_elegir_corte(huecos, sr, min(t0, t1) - 0.1, max(t0, t1) + 0.1, estimado))
    # Comprobación final: ningún corte puede caer en mitad de una palabra oída
    for c in cortes:
        t = c / sr
        for _, ini, fin in oidas:
            if ini + 0.1 < t < fin - 0.1:
                print(f"  (un corte cae en mitad de una palabra, en el segundo {t:.1f})")
                return None
    if any(b <= a for a, b in zip([0] + cortes, cortes + [len(wav)])):
        return None
    limites = [0] + cortes + [len(wav)]
    return [(limites[i], limites[i + 1]) for i in range(n)]
