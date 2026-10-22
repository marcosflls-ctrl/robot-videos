"""Cosas compartidas por los scripts de voz."""
import os
import time
from pathlib import Path

from numeros import a_voz

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "salida"


def leer_texto() -> str:
    """Usa el texto escrito al lanzar el robot o, si está vacío, texto_prueba.txt.

    Antes de devolverlo, pasa números, porcentajes, euros y siglas a palabras.
    """
    texto = (os.environ.get("TEXTO") or "").strip()
    if not texto:
        texto = (RAIZ / "texto_prueba.txt").read_text(encoding="utf-8").strip()
    dicho = a_voz(texto)
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / "texto_leido.txt").write_text(f"ESCRITO:\n{texto}\n\nLEÍDO:\n{dicho}\n", encoding="utf-8")
    print("Escrito:", texto)
    print("Leído:  ", dicho)
    return dicho


def guardar_tiempo(nombre: str, inicio: float) -> None:
    """Apunta cuánto tardó cada voz, para saber si es viable a diario."""
    segundos = round(time.time() - inicio)
    (SALIDA / f"{nombre}.tiempo.txt").write_text(f"{segundos} s", encoding="utf-8")
    print(f"{nombre}: {segundos} s")
