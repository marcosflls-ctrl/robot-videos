"""Genera dos guiones visuales de prueba con el MISMO texto y flujos distintos (tiempos de voz a ojo)."""
import json
from pathlib import Path

PALETA = {"fondo1": "#0e0816", "fondo2": "#2a1636", "texto": "#faf4fa", "suave": "#bcaec4",
          "acento": "#ffc446", "acento2": "#ff5caa", "acento3": "#5adcff", "peligro": "#ff4658"}


def tiempos(frases):
    palabras, tramos, t = [], [], 0.35
    for f in frases:
        ini = t
        for w in f.split():
            d = 0.16 + 0.055 * len(w)
            palabras.append({"t": w, "ini": round(t, 2), "fin": round(t + d, 2)})
            t += d + 0.05
        tramos.append((ini, t))
        t += 0.35
    return palabras, tramos, t + 1.0


def guion(frases, escenas, fondo, subtitulos, claves):
    palabras, tramos, dur = tiempos(frases)
    lista = []
    for i, e in enumerate(escenas):
        ini = 0 if i == 0 else tramos[e["frase"]][0] - 0.1
        fin = tramos[escenas[i + 1]["frase"]][0] - 0.1 if i + 1 < len(escenas) else dur
        e = dict(e); e.pop("frase")
        lista.append({"ini": round(ini, 2), "fin": round(fin, 2), **e})
    return {"duracion": round(dur, 2), "palabras": palabras, "claves": claves, "paleta": PALETA,
            "fondo": fondo, "subtitulos": subtitulos, "marca": "ZONA LEONIDA", "escenas": lista}


A = [
    "Faltan 24 días para GTA 6.",
    "El 19 de noviembre llega a PlayStation 5 y Xbox Series.",
    "¿Y en PC? Rockstar todavía no ha dado fecha.",
    "Volvemos a Vice City, en el estado de Leonida.",
    "Con dos protagonistas: Lucía y Jason.",
    "Si lo cuentas en horas, son 576 horas de espera.",
    "¿Lo jugarás el primer día? Te leo abajo.",
]
claves = ["24", "días", "19", "noviembre", "PC", "fecha", "Vice", "City", "Lucía", "Jason", "576", "horas", "primer"]
demo_a = guion(A, [
    {"frase": 0, "tipo": "cifra", "datos": {"valor": 24, "etiqueta": "días para GTA 6", "pastilla": "Hoy · 26 oct"}, "camara": "acercar", "transicion": "flash"},
    {"frase": 1, "tipo": "comparar", "datos": {"modo": "bifurcacion", "arriba": "19 nov 2026",
                                               "a": {"src": "objeto:ps5", "etiqueta": "PlayStation 5"}, "b": {"src": "objeto:xbox", "etiqueta": "Xbox Series"}},
     "camara": "subir", "transicion": "barrido"},
    {"frase": 2, "tipo": "alerta", "datos": {"icono": "candado", "texto": "PC", "pastilla": "Todavía no"}, "camara": "quieta", "transicion": "glitch"},
    {"frase": 3, "tipo": "titular", "datos": {"texto": "Vice City", "resaltar": "City", "variante": "letras3d", "sub": "Estado de Leonida"},
     "camara": "orbita", "transicion": "flash", "fondo": "demo/atardecer.jpg"},
    {"frase": 4, "tipo": "orbita", "datos": {"centro": "Leonida", "satelites": ["Lucía", "Jason", "Vice City", "Cayos"]}, "camara": "inclinar", "transicion": "zoom"},
    {"frase": 5, "tipo": "cifra", "datos": {"valor": 576, "etiqueta": "horas de espera", "variante": "tarjeta"}, "camara": "alejar", "transicion": "giro"},
    {"frase": 6, "tipo": "pregunta", "datos": {"pregunta": "¿Lo jugarás el primer día?", "comentario": "Te leemos en los comentarios"}, "transicion": "empuje"},
], "rejilla", "volteo", claves)

B = [
    "24 días. Es lo que queda para GTA 6.",
    "Todo empezó en diciembre de 2023 con el primer tráiler. El segundo llegó en mayo de 2025.",
    "Y la fecha final: 19 de noviembre de 2026.",
    "Saldrá en PlayStation 5 y Xbox Series, y de momento no en PC.",
    "Lo que sabemos: Vice City, el estado de Leonida y dos protagonistas, Lucía y Jason.",
    "¿Lo jugarás el primer día? Te leo abajo.",
]
claves_b = ["24", "días", "2023", "2025", "19", "noviembre", "PC", "Vice", "City", "Lucía", "Jason", "primer"]
demo_b = guion(B, [
    {"frase": 0, "tipo": "titular", "datos": {"texto": "24 días", "resaltar": "24", "variante": "gigante"}, "camara": "acercar", "transicion": "zoom"},
    {"frase": 1, "tipo": "cronologia", "datos": {"orientacion": "horizontal", "hitos": [
        {"arriba": "Tráiler 1", "fecha": "DIC 2023", "texto": "Primer tráiler"},
        {"arriba": "Tráiler 2", "fecha": "MAY 2025", "texto": "Segundo tráiler"},
        {"arriba": "Lanzamiento", "fecha": "19 NOV", "texto": "Llega GTA 6", "estado": "futuro", "pastilla": "2026"}]},
     "camara": "quieta", "transicion": "barrido"},
    {"frase": 2, "tipo": "prensa", "datos": {"medio": "Zona Leonida", "fecha": "26 oct 2026", "titular": "GTA 6 llega el 19 de noviembre de 2026",
                                             "resaltar": "19 de noviembre", "pastilla": "Confirmado"}, "camara": "inclinar", "transicion": "giro"},
    {"frase": 3, "tipo": "comparar", "datos": {"modo": "vs", "a": {"src": "objeto:ps5", "etiqueta": "Sí"}, "b": {"src": "objeto:pc", "etiqueta": "De momento no", "estado": "mal"}},
     "camara": "paneo_der", "transicion": "glitch"},
    {"frase": 4, "tipo": "pila", "datos": {"titulo": "Lo que sabemos", "tarjetas": [
        {"arriba": "Ciudad", "titulo": "Vice City", "src": "demo/atardecer.jpg"},
        {"arriba": "Mapa", "titulo": "Estado de Leonida"},
        {"arriba": "Protagonistas", "titulo": "Lucía y Jason"}]}, "camara": "subir", "transicion": "empuje", "fondo": "demo/atardecer.jpg"},
    {"frase": 5, "tipo": "pregunta", "datos": {"pregunta": "¿Lo jugarás el primer día?", "comentario": "Te leemos en los comentarios"}, "transicion": "flash"},
], "humo", "caja", claves_b)

aqui = Path(__file__).parent
(aqui / "demo_a.json").write_text(json.dumps(demo_a, ensure_ascii=False, indent=1), encoding="utf-8")
(aqui / "demo_b.json").write_text(json.dumps(demo_b, ensure_ascii=False, indent=1), encoding="utf-8")
print("demo_a", demo_a["duracion"], "s · demo_b", demo_b["duracion"], "s")
