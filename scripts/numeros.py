"""Reescribe el texto tal y como se dice en voz alta, antes de pasarlo a la voz.

Ejemplos:
    "El IPC sube al 4,9 %"      -> "El i pe ce sube al cuatro coma nueve por ciento"
    "100 € al mes"              -> "cien euros al mes"
    "21.450,50 €"               -> "veintiún mil cuatrocientos cincuenta euros con cincuenta céntimos"
    "GTA 6" / "S&P 500"         -> se leen como indica glosario.txt

Las siglas y nombres raros se corrigen en glosario.txt (una línea por palabra: escrito = dicho).
"""
import re
from pathlib import Path

from num2words import num2words

GLOSARIO = Path(__file__).resolve().parent.parent / "glosario.txt"

# Un número español: 21.450 / 4,9 / 1.250,50 / 2026 / -0,3
NUM = r"[-−+]?\d{1,3}(?:\.\d{3})+(?:,\d+)?|[-−+]?\d+(?:,\d+)?"


def _cargar_glosario() -> list[tuple[str, str]]:
    pares = []
    if GLOSARIO.exists():
        for linea in GLOSARIO.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            escrito, dicho = linea.split("=", 1)
            pares.append((escrito.strip(), dicho.strip()))
    # Primero las expresiones más largas ("S&P 500" antes que "S&P")
    return sorted(pares, key=lambda p: -len(p[0]))


def _entero(n: int) -> str:
    return num2words(n, lang="es")


def _numero(txt: str) -> str:
    """'4,9' -> 'cuatro coma nueve'; '21.450' -> 'veintiuno mil cuatrocientos cincuenta'."""
    signo = ""
    if txt[0] in "-−":
        signo, txt = "menos ", txt[1:]
    elif txt[0] == "+":
        signo, txt = "más ", txt[1:]
    entero, _, decimales = txt.replace(".", "").partition(",")
    dicho = _entero(int(entero))
    if decimales and int(decimales) == 0:
        decimales = ""
    if decimales:
        ceros = len(decimales) - len(decimales.lstrip("0"))
        resto = decimales.lstrip("0")
        dicho += " coma " + " ".join(["cero"] * ceros + ([_entero(int(resto))] if resto else []))
    return signo + dicho


def _euros(m: re.Match) -> str:
    txt = m.group("n")
    signo = ""
    if txt[0] in "-−+":
        signo, txt = ("menos " if txt[0] != "+" else "más "), txt[1:]
    entero, _, cent = txt.replace(".", "").partition(",")
    euros = int(entero)
    centimos = round(int(cent) / 10 ** len(cent) * 100) if cent else 0
    if centimos == 100:
        euros, centimos = euros + 1, 0
    if euros == 0 and centimos:
        return signo + _entero(centimos) + (" céntimo" if centimos == 1 else " céntimos")
    dicho = signo + _entero(euros) + (" euro" if euros == 1 else " euros")
    if centimos:
        dicho += " con " + _entero(centimos) + (" céntimo" if centimos == 1 else " céntimos")
    return dicho


def _apocope(texto: str) -> str:
    """'veintiuno mil' -> 'veintiún mil', 'uno euros' -> 'un euros' (delante de otra palabra)."""
    texto = re.sub(r"\bveintiuno(?=\s+(?!por\b)[a-záéíóúñ])", "veintiún", texto)
    # Horas en femenino: "las veintiuno" -> "las veintiuna", "la uno" -> "la una"
    texto = re.sub(r"\b(las?|y las?|a las?)\s+(veinti)?uno\b", lambda m: f"{m.group(1)} {m.group(2) or ''}una", texto)
    texto = re.sub(r"\buno(?=\s+(?:mil|millón|millones|euros?|céntimos?|años?|días?|meses|mes|dólares|puntos)\b)", "un", texto)
    return texto


def a_voz(texto: str) -> str:
    for escrito, dicho in _cargar_glosario():
        texto = re.sub(r"(?<!\w)" + re.escape(escrito) + r"(?!\w)", dicho, texto)

    texto = re.sub(rf"(?P<n>{NUM})\s?(?:€|euros?\b|EUR\b)", _euros, texto)
    texto = re.sub(rf"(?P<n>{NUM})\s?%", lambda m: _numero(m.group("n")) + " por ciento", texto)
    texto = re.sub(rf"(?P<n>{NUM})\s?pp\b", lambda m: _numero(m.group("n")) + " puntos porcentuales", texto)
    texto = re.sub(rf"(?<![\w,.])(?P<n>{NUM})(?![\w])", lambda m: _numero(m.group("n")), texto)

    texto = _apocope(texto)
    texto = texto.replace("−", "-")
    return re.sub(r"\s{2,}", " ", texto).strip()


if __name__ == "__main__":
    import sys

    print(a_voz(" ".join(sys.argv[1:]) or "El IPC sube al 4,9 % y la luz un -0,3 %; 100 € al mes en el S&P 500 son 21.450,50 €."))
