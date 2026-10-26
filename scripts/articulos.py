"""Segunda tanda: guion de 30–40 s a partir del último artículo publicado en cada web.

Lee el RSS público de la web (solo artículos ya publicados, nunca borradores), abre el
artículo, y Gemini (texto) lo resume en 5–6 frases con su escena. Sin datos inventados:
solo lo que dice el artículo.
"""
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

WEBS = {
    "gta": {"dominio": "zonaleonida.com", "nombre": "Zona Leonida",
            "tono": "español neutro (que se entienda en España y Latinoamérica), cercano y con gancho, para fans de GTA 6",
            "reglas": "Si algo es un rumor o filtración, dilo claramente como rumor y de quién viene. Nada de spoilers.",
            "etiquetas": "#GTA6 #GTAVI #GrandTheftAuto #ViceCity #ZonaLeonida #Gaming #Shorts"},
    "afdm": {"dominio": "alfinaldemes.com", "nombre": "Al Final de Mes",
             "tono": "español de España, cercano y claro, para cualquier familia que quiere entender cómo le afecta en su bolsillo",
             "reglas": "Si algo no está aprobado todavía, dilo. Las cifras, exactamente como en el artículo.",
             "etiquetas": "#AlFinalDeMes #Economía #Ahorro #España #Shorts"},
    "dec": {"dominio": "dineroenclaro.com", "nombre": "Dinero en Claro",
            "tono": "español de España, cercano y claro, para ahorradores que no son expertos",
            "reglas": "Nunca recomiendes comprar ni vender nada: es información, no consejo. Las cifras, exactamente como en el artículo.",
            "etiquetas": "#DineroEnClaro #Ahorro #Inversión #FinanzasPersonales #Shorts"},
}

VENTANA_HORAS = float(os.environ.get("VENTANA_HORAS") or 26)  # artículos de las últimas X horas


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (robot-videos; +https://github.com/marcosflls-ctrl/robot-videos)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def ultimo_articulo(web):
    """Devuelve {titulo, descripcion, enlace, fecha} del artículo más reciente, o None si no hay nada nuevo."""
    dominio = WEBS[web]["dominio"]
    try:
        raiz = ET.fromstring(_get(f"https://{dominio}/rss.xml"))
    except Exception as error:
        print(f"::warning::{dominio}: no pude leer el RSS ({type(error).__name__}: {error})")
        return None
    items = []
    for it in raiz.iter("item"):
        try:
            fecha = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            continue
        items.append({"titulo": (it.findtext("title") or "").strip(), "descripcion": (it.findtext("description") or "").strip(),
                      "enlace": (it.findtext("link") or "").strip(), "fecha": fecha})
    ahora = datetime.now(timezone.utc)
    items = [i for i in items if i["fecha"] <= ahora and i["titulo"] and i["enlace"]]
    if not items:
        return None
    nuevo = max(items, key=lambda i: i["fecha"])
    if ahora - nuevo["fecha"] > timedelta(hours=VENTANA_HORAS):
        print(f"{dominio}: el último artículo es del {nuevo['fecha']:%d/%m %H:%M} UTC; no hay nada nuevo.")
        return None
    return nuevo


def texto_del_articulo(enlace):
    try:
        pagina = _get(enlace)
    except Exception as error:
        print(f"::warning::No pude abrir {enlace}: {error}")
        return ""
    m = re.search(r'<article[^>]*>(.*?)</article>', pagina, re.S) or re.search(r'class="[^"]*prose[^"]*"[^>]*>(.*?)</(?:div|section)>\s*</', pagina, re.S) \
        or re.search(r'<main[^>]*>(.*?)</main>', pagina, re.S)
    bloque = m.group(1) if m else pagina
    bloque = re.sub(r"<(script|style|nav|aside|footer|figure)[^>]*>.*?</\1>", " ", bloque, flags=re.S)
    bloque = re.sub(r"</(p|h\d|li|tr)>", "\n", bloque)
    texto = html.unescape(re.sub(r"<[^>]+>", " ", bloque))
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto).strip()
    return texto[:7000]


INSTRUCCIONES = """Eres guionista de vídeos cortos verticales (YouTube Shorts, TikTok) de la web «{nombre}» ({dominio}).
Escribe el guion de un vídeo de 30 a 40 segundos que resuma este artículo.

Tono: {tono}.
Reglas:
- Solo hechos que estén en el artículo. No inventes cifras, fechas ni nombres. {reglas}
- 5 o 6 frases, entre 75 y 100 palabras en total. Frases cortas, fáciles de decir en voz alta.
- La primera frase es un gancho que cuenta lo más llamativo de la noticia.
- La última frase invita a leer el artículo completo en {dominio}.
- Escribe los números con cifras (1.300 euros, 5%), como en el artículo.

Para cada frase, da también lo que se ve en pantalla:
- "visual": o bien {{"tipo": "cifra", "texto": "<cifra corta, máx. 7 caracteres, p. ej. 5% o 1.300 €>", "sub": "<qué es, máx. 4 palabras>"}}
  o bien {{"tipo": "titular", "texto": "<máx. 4 palabras>", "resaltar": "<1 o 2 palabras de ese texto>"}}.
  Usa "cifra" solo si la frase dice esa cifra. Al menos una escena con cifra si el artículo tiene una cifra clave.
- "buscar": 2 o 3 palabras en INGLÉS para buscar un clip de vídeo de archivo que acompañe (p. ej. "euro coins", "city traffic night").

Devuelve SOLO un JSON así:
{{"titulo": "<título del vídeo, máx. 70 caracteres, con gancho>",
  "escenas": [{{"frase": "...", "visual": {{...}}, "buscar": "..."}}, ...]}}

ARTÍCULO
Título: {titulo}
Resumen: {descripcion}
Texto:
{texto}
"""


def _gemini_texto(prompt):
    clave = os.environ["GEMINI_API_KEY"].strip()
    modelos = [m for m in [(os.environ.get("GEMINI_MODELO_TEXTO") or "").strip(), "gemini-flash-latest", "gemini-2.5-flash"] if m]
    cuerpo = json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                         "generationConfig": {"responseMimeType": "application/json", "temperature": 0.6}}).encode()
    ultimo = None
    for modelo in modelos:
        for intento in range(4):
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent", data=cuerpo,
                method="POST", headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    datos = json.loads(r.read())
                partes = datos["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in partes if not p.get("thought"))
            except urllib.error.HTTPError as e:
                ultimo = f"{modelo}: {e.code} {e.read().decode('utf-8', 'replace')[:200]}"
                if e.code in (429, 500, 503) and intento < 3:
                    time.sleep(15 * (intento + 1))
                    continue
                break  # 404 u otro: prueba el siguiente modelo
            except Exception as e:
                ultimo = f"{modelo}: {e}"
                break
    raise RuntimeError(f"Gemini (texto) no respondió: {ultimo}")


def _limpiar_visual(v, frase):
    if not isinstance(v, dict):
        return {"tipo": "nada"}
    if v.get("tipo") == "cifra" and str(v.get("texto", "")).strip():
        texto = str(v["texto"]).strip()[:8]
        return {"tipo": "cifra", "texto": texto, "sub": str(v.get("sub", "")).strip()[:30]}
    if v.get("tipo") == "titular" and str(v.get("texto", "")).strip():
        texto = " ".join(str(v["texto"]).split()[:5])[:32]
        return {"tipo": "titular", "texto": texto, "resaltar": str(v.get("resaltar", "")).strip()}
    return {"tipo": "nada"}


def guion_de_articulo(web, art):
    w = WEBS[web]
    prompt = INSTRUCCIONES.format(nombre=w["nombre"], dominio=w["dominio"], tono=w["tono"], reglas=w["reglas"],
                                  titulo=art["titulo"], descripcion=art["descripcion"],
                                  texto=texto_del_articulo(art["enlace"]) or art["descripcion"])
    bruto = _gemini_texto(prompt)
    bruto = re.sub(r"^```(?:json)?|```$", "", bruto.strip()).strip()
    datos = json.loads(bruto)
    escenas = [e for e in datos.get("escenas", []) if isinstance(e, dict) and str(e.get("frase", "")).strip()]
    if not 3 <= len(escenas) <= 8:
        raise ValueError(f"guion con {len(escenas)} frases")
    frases = [" ".join(str(e["frase"]).split()) for e in escenas]
    if sum(len(f.split()) for f in frases) > 140:
        raise ValueError("guion demasiado largo")
    titulo = " ".join(str(datos.get("titulo") or art["titulo"]).split())[:90]
    texto = f"{titulo}\n\n{art['descripcion']}\n\nLéelo completo: {art['enlace']}\n\n{w['etiquetas']}"
    return {"frases": frases, "texto": texto,
            "escenas": [{"visual": _limpiar_visual(e.get("visual"), f), "buscar": str(e.get("buscar") or "city timelapse")[:40]}
                        for e, f in zip(escenas, frases)]}


if __name__ == "__main__":  # prueba: python articulos.py afdm
    import sys
    web = sys.argv[1] if len(sys.argv) > 1 else "afdm"
    a = ultimo_articulo(web)
    print(a)
    if a:
        print(json.dumps(guion_de_articulo(web, a), ensure_ascii=False, indent=1))
