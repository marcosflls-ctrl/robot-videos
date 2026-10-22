"""Guion diario de la cuenta atrás de GTA 6 para Zona Leonida.

Devuelve una lista de frases tal y como se ven en pantalla (con cifras); la voz las
pasa a palabras sola. Hay varias plantillas que se van turnando para que no sea
siempre el mismo vídeo. Solo datos confirmados: fecha, Vice City, Leonida, Lucía y
Jason, consolas.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

ESTRENO = date(2026, 11, 19)
MADRID = ZoneInfo("Europe/Madrid")


def dias_que_faltan(hoy: date | None = None) -> int:
    hoy = hoy or datetime.now(MADRID).date()
    return (ESTRENO - hoy).days


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def guion_completo(dias: int) -> list:
    if dias < 0:
        return []
    if dias == 0:
        return [
            ("Hoy sale GTA 6.", {"tipo": "cifra", "texto": "HOY", "sub": "sale GTA 6"}, "fireworks night city"),
            ("Después de años de espera, Vice City y todo el estado de Leonida ya están aquí.",
             {"tipo": "titular", "texto": "Ya está aquí", "resaltar": "aquí"}, ["miami aerial", "miami night neon"]),
            ("Lucía y Jason por fin dejan de ser un tráiler.", {"tipo": "titular", "texto": "Lucía y Jason", "resaltar": "Lucía Jason"}, "sports car night"),
            ("Cuéntanos en los comentarios qué es lo primero que vas a hacer.",
             {"tipo": "titular", "texto": "¿Qué harás primero?", "resaltar": "primero"}, "gaming controller neon"),
            ("Y todas las novedades, en zonaleonida.com.", {"tipo": "titular", "texto": "zonaleonida.com", "resaltar": "zonaleonida.com"}, "palm trees neon"),
        ]
    if dias == 1:
        return [
            ("Mañana sale GTA 6.", {"tipo": "cifra", "texto": "1", "sub": "día para GTA 6"}, "miami night neon"),
            ("Esta es la última noche de espera antes de volver a Vice City.",
             {"tipo": "titular", "texto": "Última noche", "resaltar": "noche"}, ["city night timelapse", "ocean drive night"]),
            ("Lucía y Jason llegan mañana a PlayStation 5 y Xbox Series.",
             {"tipo": "titular", "texto": "Lucía y Jason", "resaltar": "Lucía Jason"}, "sports car sunset"),
            ("¿Lo vas a jugar el primer día o vas a esperar?",
             {"tipo": "titular", "texto": "¿El primer día?", "resaltar": "primer"}, "gaming controller neon"),
            ("Te lo contamos todo en zonaleonida.com.", {"tipo": "titular", "texto": "zonaleonida.com", "resaltar": "zonaleonida.com"}, "palm trees neon"),
        ]

    C = lambda texto, sub: {"tipo": "cifra", "texto": texto, "sub": sub}
    T = lambda texto, resaltar="": {"tipo": "titular", "texto": texto, "resaltar": resaltar}
    N = {"tipo": "nada"}
    semanas, resto = divmod(dias, 7)
    horas = dias * 24
    plural_sem = "semana" if semanas == 1 else "semanas"
    plural_dia = "día" if resto == 1 else "días"
    if semanas and resto:
        en_semanas = f"{semanas} {plural_sem} y {resto} {plural_dia}"
    elif semanas:
        en_semanas = f"{semanas} {plural_sem} " + ("justa" if semanas == 1 else "justas")
    else:
        en_semanas = "menos de una semana"

    # Cada frase con su escena: (frase, visual, búsqueda de clips de Pexels)
    plantillas = [
        [
            (f"Faltan {dias} días para GTA 6.", C(str(dias), "días para GTA 6"), "miami night neon"),
            ("El 19 de noviembre volvemos a Vice City, esta vez con todo el estado de Leonida para recorrer.",
             T("Vuelve Vice City", "Vice City"), ["miami beach aerial", "florida highway sunset"]),
            ("Lucía y Jason serán los protagonistas de la historia.", T("Lucía y Jason", "Lucía Jason"), "sports car night city"),
            (f"{'Eso son' if semanas else 'Eso es'} {en_semanas}, o lo que es lo mismo, {_miles(horas)} horas.",
             C(_miles(horas), "horas"), ["city timelapse night", "highway night timelapse"]),
            ("Cada día te contamos cuánto falta en zonaleonida.com.", T("zonaleonida.com", "zonaleonida.com"), "neon lights"),
            ("Síguenos para no perderte la cuenta atrás.", N, "palm trees sunset"),
        ],
        [
            (f"Quedan solo {dias} días para GTA 6.", C(str(dias), "días para GTA 6"), "neon city night"),
            ("Llega el 19 de noviembre a PlayStation 5 y Xbox Series.", T("19 de noviembre", "noviembre"), "gaming controller neon"),
            (f"Si lo cuentas en minutos, son {_miles(horas * 60)} minutos de espera.", C(_miles(horas * 60), "minutos"),
             ["clock", "city timelapse"]),
            ("¿Qué es lo primero que vas a hacer en Vice City? Te leemos en los comentarios.",
             T("¿Qué harás primero?", "primero"), ["miami beach", "ocean drive night"]),
            ("Las novedades, todos los días en zonaleonida.com.", T("zonaleonida.com", "zonaleonida.com"), "neon sign"),
        ],
        [
            (f"Cuenta atrás: {dias} días para GTA 6.", C(str(dias), "días para GTA 6"), "miami skyline night"),
            ("Esta vez la historia transcurre en Leonida, un estado nuevo con Vice City como gran ciudad.",
             T("Bienvenido a Leonida", "Leonida"), ["florida everglades aerial", "miami aerial"]),
            (f"Quedan {en_semanas} para el 19 de noviembre.", T(en_semanas, en_semanas), "calendar"),
            ("Lucía y Jason, PlayStation 5 y Xbox Series. Ya queda menos.", T("Ya queda menos", "menos"), "sports car sunset"),
            ("Síguenos y entra en zonaleonida.com para no perderte nada.", T("zonaleonida.com", "zonaleonida.com"), "palm trees neon"),
        ],
    ]
    return plantillas[dias % len(plantillas)]


def guion(dias: int) -> list[str]:
    return [f for f, _, _ in guion_completo(dias)]


def escenas(dias: int) -> list[dict]:
    return [{"visual": v, "buscar": b} for _, v, b in guion_completo(dias)]


if __name__ == "__main__":
    import sys

    from numeros import a_voz

    d = int(sys.argv[1]) if len(sys.argv) > 1 else dias_que_faltan()
    for frase in guion(d):
        print(frase, "\n   →", a_voz(frase))
