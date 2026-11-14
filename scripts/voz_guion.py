"""Lee un guion entero con la voz de Gemini y lo guarda listo para la skill «Vídeos animados 2D».

Pensado para el canal de historia alternativa: pegas el título y el guion que da el prompt,
y el robot devuelve:
    salida/<nombre_del_archivo>.wav   (el workflow lo pasa a .mp3)
    salida/<nombre_del_archivo>.txt   (el guion tal cual, para que la skill lo alinee con el audio)

<nombre_del_archivo> sigue las mismas reglas que el prompt: minúsculas, sin tildes ni ñ,
sin signos y con guiones bajos («que_habria_pasado_si_espana_no_hubiera_perdido_cuba»).

Variables:
    TITULO          título del vídeo
    GUION           texto del guion (un párrafo; también vale con saltos de línea)
    GEMINI_API_KEY  clave de la API de Gemini
    GEMINI_VOZ      voz de Gemini (por defecto Orus)
    GEMINI_ESTILO   cómo debe sonar (por defecto, narrador de historia con suspense)

El guion se lee en tandas de unas cien palabras, cortando siempre al final de una frase,
y luego se unen con una pausa corta. Así no se pasa del límite de cada petición.
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))

ESTILO = ("Narrador de vídeos animados de historia en español de España: cálido, cinematográfico y con suspense, "
          "ritmo ágil y con energía, pausas dramáticas breves en los puntos suspensivos, frases cortas con energía, sin titubeos")
TANDA = 650     # letras por petición (≈ 100 palabras)
PAUSA = 0.25    # segundos de silencio entre tandas


def nombre_archivo(titulo: str) -> str:
    t = titulo.lower().replace("ñ", "n")
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[¿?¡!,.:;()\"'«»“”‘’…]", "", t)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t[:80].rstrip("_") or "voz"


def tandas(texto: str, largo: int = TANDA) -> list[str]:
    frases = re.findall(r"[^.!?…]+(?:\.\.\.|[.!?…]+)?[\"'»”]?\s*", texto)
    salida, actual = [], ""
    for f in frases:
        if actual and len(actual) + len(f) > largo:
            salida.append(actual.strip())
            actual = ""
        actual += f
    if actual.strip():
        salida.append(actual.strip())
    return salida


def main():
    titulo = (os.environ.get("TITULO") or "").strip()
    guion = re.sub(r"\s+", " ", os.environ.get("GUION") or "").strip()
    if not titulo or not guion:
        raise SystemExit("::error::Falta el título o el guion.")
    os.environ.setdefault("GEMINI_ESTILO", ESTILO)
    if not (os.environ.get("GEMINI_ESTILO") or "").strip():
        os.environ["GEMINI_ESTILO"] = ESTILO

    from motor_gemini import MotorVozGemini
    voz = MotorVozGemini()

    partes = tandas(guion)
    palabras = len(guion.split())
    print(f"Guion: {palabras} palabras (≈ {palabras / 150:.1f} min) en {len(partes)} tandas")
    silencio = np.zeros(int(PAUSA * voz.sr), dtype=np.float32)
    trozos = []
    for i, p in enumerate(partes, 1):
        print(f"Tanda {i}/{len(partes)}")
        trozos += [voz.decir(p), silencio]
    audio = np.concatenate(trozos[:-1])

    nombre = nombre_archivo(titulo)
    salida = Path("salida")
    salida.mkdir(exist_ok=True)
    sf.write(salida / f"{nombre}.wav", audio, voz.sr)
    (salida / f"{nombre}.txt").write_text(guion + "\n", encoding="utf-8")
    Path("nombre.txt").write_text(nombre, encoding="utf-8")
    print(f"Listo: {nombre}.mp3 ({len(audio) / voz.sr / 60:.1f} min)")


if __name__ == "__main__":
    main()
