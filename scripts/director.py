"""Director: inventa el guion visual de cada Short (y su texto, si no se lo dan).

Recibe el tema (texto del artículo o datos del día), la lista de imágenes y objetos que puede
usar, y el historial de los últimos vídeos. Pide a Gemini un guion visual en JSON eligiendo
escenas, cámaras, transiciones, fondo y estilo de subtítulos, con la orden de NO repetir lo
que se hizo en los últimos vídeos. Después lo revisa (tipos válidos, textos que quepan,
imágenes que existan) y lo convierte en el JSON que monta el motor de Remotion.
"""
import json
import random
import re
from datetime import date
from pathlib import Path

from articulos import _gemini_texto

TIPOS = ["cifra", "titular", "objeto", "imagen", "comparar", "cronologia", "pila", "alerta", "prensa", "galeria", "orbita", "pregunta"]
CAMARAS = ["acercar", "alejar", "paneo_izq", "paneo_der", "subir", "bajar", "orbita", "inclinar", "quieta"]
TRANSICIONES = ["corte", "flash", "barrido", "zoom", "giro", "glitch", "empuje"]
FONDOS = ["particulas", "rejilla", "humo"]
SUBTITULOS = ["volteo", "pop", "caja", "deslizar"]

PALETAS = {
    "gta": {"fondo1": "#0e0816", "fondo2": "#2a1636", "texto": "#faf4fa", "suave": "#bcaec4",
            "acento": "#ffc446", "acento2": "#ff5caa", "acento3": "#5adcff", "peligro": "#ff4658"},
}

CATALOGO = """
TIPOS DE ESCENA (campo "tipo") y lo que lleva cada uno en "datos":
- cifra: un número grande que cuenta. datos: valor (número), decimales, prefijo, sufijo (p. ej. " %", " €"), etiqueta (≤ 24 letras), arriba (≤ 20), pastilla (≤ 18), variante: "anillo" | "tarjeta".
- titular: 1–3 palabras enormes. datos: texto (≤ 3 palabras, ≤ 18 letras), resaltar (palabra del texto que va en color), sub (≤ 26 letras), variante: "letras3d" | "bloques" | "gigante".
- objeto: un objeto real recortado flotando. datos: src ("objeto:NOMBRE" de la biblioteca), aura: "halo" | "escudo" | "ninguna", etiqueta (≤ 14 letras, palabra grande debajo), pastilla (≤ 18).
- imagen: una foto/fotograma. datos: src ("img:ID"), marco: "completa" | "cristal" | "polaroid", etiqueta (≤ 16), pastilla (≤ 18), desde: "izq" | "der", lupa: {x, y} opcional (punto 0–1 de la imagen a ampliar).
- comparar: dos cosas enfrentadas. datos: modo: "vs" | "bifurcacion" | "antes_despues", arriba (≤ 18), a y b: cada uno {src ("objeto:NOMBRE" o "img:ID") o texto (≤ 12 letras), sub (≤ 18), etiqueta (≤ 16), estado: "ok" | "mal"}.
- cronologia: 2–4 hitos que la cámara recorre. datos: orientacion: "vertical" | "horizontal", hitos: [{arriba (≤ 14), fecha (≤ 9 letras, p. ej. "DIC 2023"), texto (≤ 30), estado: "ok" | "mal" | "futuro", pastilla (≤ 12)}].
- pila: 2–4 tarjetas que caen una sobre otra. datos: titulo (≤ 22), tarjetas: [{arriba (≤ 14), titulo (≤ 28), sub (≤ 40), src ("img:ID", opcional), color: "peligro" opcional}].
- alerta: icono grande con impacto. datos: icono: "candado" | "aviso" | "cruz" | "check", texto (≤ 12 letras), pastilla (≤ 18), color: "peligro" | "acento".
- prensa: titular de periódico con rotulador. datos: medio (SIEMPRE "Zona Leonida"), fecha (≤ 14), titular (≤ 70 letras), resaltar (trozo exacto del titular), entradilla (≤ 90), pastilla (≤ 14).
- galeria: 4 o 6 imágenes en rejilla y la cámara se mete en una. datos: imagenes: ["img:ID", ...], foco (índice), etiqueta (≤ 18).
- orbita: algo en el centro y satélites girando. datos: centro (palabra ≤ 10 letras u "objeto:NOMBRE"), satelites: 3–5 palabras cortas (≤ 12) o "img:ID", etiqueta (≤ 16).
- pregunta: cierre con pregunta y comentario fijado. datos: pregunta (≤ 40 letras), comentario (≤ 34 letras).

CÁMARAS ("camara"): acercar, alejar, paneo_izq, paneo_der, subir, bajar, orbita, inclinar, quieta.
TRANSICIONES de entrada ("transicion"): corte, flash, barrido, zoom, giro, glitch, empuje.
FONDO del vídeo ("fondo"): particulas, rejilla, humo.   SUBTÍTULOS ("subtitulos"): volteo, pop, caja, deslizar.
"""

INSTRUCCIONES = """Eres el director de montaje de un canal de Shorts verticales ({canal}). Tu trabajo es inventar
un montaje visual DISTINTO para cada vídeo, con ritmo: algo nuevo cada 2–4 segundos.

TEMA DEL VÍDEO:
{tema}

{bloque_frases}

MATERIAL DISPONIBLE (usa solo esto; nunca inventes otras imágenes u objetos):
Imágenes (para fondos y escenas): {imagenes}
Objetos recortados (biblioteca): {objetos}

{catalogo}

LO QUE YA SE HIZO EN LOS ÚLTIMOS VÍDEOS (NO lo repitas):
{historial}

REGLAS:
1. Una o dos escenas por frase (dos solo si la frase es larga), en el mismo orden que las frases. Campo "frase": índice de la frase (0, 1, 2...).
2. Escoge para cada frase la escena que MEJOR cuente lo que dice: cifras -> cifra o cronologia; dos opciones -> comparar; algo bloqueado o negado -> alerta; un dato confirmado -> prensa; lista de cosas -> pila u orbita; consolas o aparatos -> objeto; lugares o personajes -> imagen o galeria.
3. Variedad: nunca el mismo tipo dos veces seguidas; al menos 5 tipos distintos; al menos 3 transiciones distintas; cámaras variadas.
4. No repitas lo de los últimos vídeos: empieza con un tipo de escena distinto de los últimos 3 vídeos y usa un "fondo" y unos "subtitulos" distintos de los del vídeo anterior.
5. Pon imagen de fondo ("fondo": "img:ID") en al menos 6 de cada 10 escenas, eligiendo la más relacionada.
6. Respeta los límites de letras de cada campo (si no cabe, acórtalo). Los textos en pantalla, en español y sin inventar datos: solo lo que dice el tema.
7. Si la última frase es una pregunta o invita a comentar, la última escena es "pregunta".
8. "claves": 6–12 palabras de las frases que deben ir en color en los subtítulos (cifras, nombres, palabras fuertes).

Responde SOLO con JSON:
{{"titulo": "título para YouTube (≤ 90 letras)", {campo_frases}"claves": [...], "fondo": "...", "subtitulos": "...",
  "escenas": [{{"frase": 0, "tipo": "...", "datos": {{...}}, "camara": "...", "transicion": "...", "fondo": "img:ID o null"}}]}}
"""


def _resumen_historial(historial):
    if not historial:
        return "(ninguno todavía)"
    lineas = []
    for h in historial[-6:]:
        lineas.append(f"- {h.get('fecha', '')}: escenas {' > '.join(h.get('tipos', []))}; fondo {h.get('fondo')}; "
                      f"subtítulos {h.get('subtitulos')}; transiciones {', '.join(h.get('transiciones', []))}")
    return "\n".join(lineas)


def pedir_plan(tema, imagenes, objetos, historial, frases=None, canal="Zona Leonida, noticias de GTA 6"):
    """imagenes: {id: descripción}; objetos: {nombre: descripción}. Devuelve el plan ya revisado."""
    if frases:
        bloque = "FRASES DE LA VOZ (ya escritas, no las cambies):\n" + "\n".join(f"{i}. {f}" for i, f in enumerate(frases))
        campo = ""
    else:
        bloque = ("ESCRIBE TAMBIÉN LA VOZ: 5–7 frases, 90–120 palabras en total, español neutro, cercano y con gancho; "
                  "la primera engancha en 2 segundos; la última pregunta algo al espectador. Rumores, siempre como rumor.")
        campo = '"frases": ["..."], '
    prompt = INSTRUCCIONES.format(
        canal=canal, tema=tema, bloque_frases=bloque, catalogo=CATALOGO, campo_frases=campo,
        imagenes=json.dumps(imagenes, ensure_ascii=False), objetos=json.dumps(objetos, ensure_ascii=False),
        historial=_resumen_historial(historial))
    bruto = _gemini_texto(prompt)
    bruto = re.sub(r"^```(?:json)?|```$", "", bruto.strip()).strip()
    plan = json.loads(bruto)
    if frases:
        plan["frases"] = frases
    return revisar(plan, imagenes, objetos, historial)


# ---------------------------------------------------------------- revisión
LIMITES = {"etiqueta": 24, "arriba": 20, "pastilla": 18, "sub": 40, "texto": 30, "titulo": 28, "fecha": 10,
           "titular": 70, "entradilla": 90, "pregunta": 40, "comentario": 34, "centro": 12}


def _corta(v, n):
    v = " ".join(str(v).split())
    if len(v) <= n:
        return v
    corte = v[:n].rsplit(" ", 1)[0]
    corte = corte if len(corte) > n * 0.5 else v[:n]
    if v.endswith("?") and not corte.endswith("?"):
        corte = corte.rstrip(" ,.;:") + "?"
    return corte


def _limpia(d, imagenes, objetos):
    """Recorta textos y quita referencias a imágenes u objetos que no existen."""
    if isinstance(d, list):
        return [x for x in (_limpia(v, imagenes, objetos) for v in d) if x not in (None, "")]
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                out[k] = _limpia(v, imagenes, objetos)
            elif isinstance(v, str):
                if v.startswith("img:") and v[4:] not in imagenes:
                    continue
                if v.startswith("objeto:") and v[7:] not in objetos:
                    continue
                out[k] = _corta(v, LIMITES[k]) if k in LIMITES and not v.startswith(("img:", "objeto:")) else v
            else:
                out[k] = v
        return out
    if isinstance(d, str) and ((d.startswith("img:") and d[4:] not in imagenes) or (d.startswith("objeto:") and d[7:] not in objetos)):
        return None
    return d


def revisar(plan, imagenes, objetos, historial):
    rnd = random.Random(json.dumps(plan.get("frases", []), ensure_ascii=False))
    frases = [" ".join(str(f).split()) for f in plan.get("frases", []) if str(f).strip()]
    if not 3 <= len(frases) <= 9:
        raise ValueError(f"el director devolvió {len(frases)} frases")
    escenas, prev = [], None
    for e in plan.get("escenas", []):
        if not isinstance(e, dict):
            continue
        tipo = e.get("tipo") if e.get("tipo") in TIPOS else "titular"
        try:
            fr = max(0, min(len(frases) - 1, int(e.get("frase", 0))))
        except (TypeError, ValueError):
            continue
        if escenas and fr < escenas[-1]["frase"]:
            continue
        datos = _limpia(e.get("datos") or {}, imagenes, objetos)
        if tipo == "titular" and not datos.get("texto"):
            datos["texto"] = " ".join(frases[fr].split()[:3])
        if tipo in ("objeto",) and not datos.get("src"):
            tipo, datos = "titular", {"texto": " ".join(frases[fr].split()[:3]), "variante": "gigante"}
        if tipo == "imagen" and not datos.get("src"):
            tipo, datos = "titular", {"texto": " ".join(frases[fr].split()[:3]), "variante": "bloques"}
        if tipo == "prensa":
            datos["medio"] = "Zona Leonida"
        cam = e.get("camara") if e.get("camara") in CAMARAS else rnd.choice(CAMARAS)
        tra = e.get("transicion") if e.get("transicion") in TRANSICIONES else rnd.choice(TRANSICIONES)
        fondo = e.get("fondo") if isinstance(e.get("fondo"), str) and str(e.get("fondo")).startswith("img:") and e["fondo"][4:] in imagenes else None
        if prev and prev["tipo"] == tipo and prev["frase"] != fr:
            print(f"  (aviso: dos escenas «{tipo}» seguidas)")
        nueva = {"frase": fr, "tipo": tipo, "datos": datos, "camara": cam, "transicion": tra, "fondo": fondo}
        escenas.append(nueva)
        prev = nueva
    # que todas las frases tengan al menos una escena
    cubiertas = {e["frase"] for e in escenas}
    for i in range(len(frases)):
        if i not in cubiertas:
            pos = next((k for k, e in enumerate(escenas) if e["frase"] > i), len(escenas))
            escenas.insert(pos, {"frase": i, "tipo": "titular", "camara": rnd.choice(CAMARAS), "transicion": rnd.choice(TRANSICIONES),
                                 "datos": {"texto": " ".join(frases[i].split()[:3]), "variante": rnd.choice(["letras3d", "bloques", "gigante"])}, "fondo": None})
    anterior = historial[-1] if historial else {}
    fondo = plan.get("fondo") if plan.get("fondo") in FONDOS else rnd.choice(FONDOS)
    subt = plan.get("subtitulos") if plan.get("subtitulos") in SUBTITULOS else rnd.choice(SUBTITULOS)
    if fondo == anterior.get("fondo"):
        fondo = rnd.choice([f for f in FONDOS if f != fondo])
    if subt == anterior.get("subtitulos"):
        subt = rnd.choice([s for s in SUBTITULOS if s != subt])
    claves = [str(c) for c in plan.get("claves", []) if str(c).strip()][:14]
    return {"titulo": _corta(plan.get("titulo") or frases[0], 90), "frases": frases, "claves": claves,
            "fondo": fondo, "subtitulos": subt, "escenas": escenas}


def para_historial(plan):
    return {"fecha": date.today().isoformat(), "tipos": [e["tipo"] for e in plan["escenas"]], "fondo": plan["fondo"],
            "subtitulos": plan["subtitulos"], "transiciones": sorted({e["transicion"] for e in plan["escenas"]})}


def cargar_historial(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return []


def guardar_historial(ruta, historial, plan):
    historial = (historial + [para_historial(plan)])[-12:]
    Path(ruta).write_text(json.dumps(historial, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- al motor
def a_guion(plan, palabras, duracion, rutas_img, paleta="gta", audio=None, marca="ZONA LEONIDA", fondos_extra=None):
    """palabras: [(texto, ini, fin)] de la voz real (o calculada). rutas_img: {id: ruta en public/}."""
    frases = plan["frases"]
    # a qué frase pertenece cada palabra: contando palabras
    limites, k = [], 0
    for f in frases:
        n = len(f.split())
        tramo = palabras[k:k + n] or palabras[-1:]
        limites.append((tramo[0][1], tramo[-1][2]))
        k += n
    escenas = plan["escenas"]
    # escenas de la misma frase: se reparten su tiempo
    inicios = []
    for i, e in enumerate(escenas):
        mismas = [x for x in escenas if x["frase"] == e["frase"]]
        idx = mismas.index(e)
        a, b = limites[e["frase"]]
        inicios.append(a + (b - a) * idx / len(mismas))

    def ruta(v):
        if isinstance(v, str) and v.startswith("img:"):
            return rutas_img.get(v[4:])
        if isinstance(v, dict):
            return {k: ruta(x) for k, x in v.items()}
        if isinstance(v, list):
            return [ruta(x) for x in v]
        return v

    lista = []
    for i, e in enumerate(escenas):
        ini = 0.0 if i == 0 else max(0.0, inicios[i] - 0.12)
        fin = (inicios[i + 1] - 0.12) if i + 1 < len(escenas) else duracion
        lista.append({"ini": round(ini, 3), "fin": round(max(fin, ini + 0.5), 3), "tipo": e["tipo"], "datos": ruta(e["datos"]),
                      "camara": e["camara"], "transicion": e["transicion"], "fondo": ruta(e["fondo"])})
    return {"duracion": round(duracion, 3), "audio": audio,
            "palabras": [{"t": t, "ini": round(a, 3), "fin": round(b, 3)} for t, a, b in palabras],
            "claves": plan["claves"], "paleta": PALETAS[paleta], "fondo": plan["fondo"], "subtitulos": plan["subtitulos"],
            "marca": marca, "fondos": fondos_extra or [], "escenas": lista}


def tiempos_a_ojo(frases):
    """Tiempos de cada palabra calculados a ojo (para pruebas sin voz)."""
    palabras, t = [], 0.35
    for f in frases:
        for w in f.split():
            d = 0.16 + 0.055 * len(w)
            palabras.append((w, t, t + d))
            t += d + 0.05
        t += 0.35
    return palabras, t + 1.0
