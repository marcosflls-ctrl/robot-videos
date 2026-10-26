"""Segunda tanda diaria: un vídeo por web con su último artículo publicado.

Variables: WEBS ("gta,afdm,dec" por defecto), GEMINI_API_KEY, VENTANA_HORAS (26 por defecto).
Si una web no ha publicado nada en esas horas, ese día no hay segundo vídeo de esa web.
Genera en salida/ un .mp4 y un .txt por web. No publica nada.
"""
import os
import time

from articulos import guion_de_articulo, ultimo_articulo
from guiones_webs import AVISO_DEC, hoy
from montaje import ESTILO_AFDM, ESTILO_DEC, ESTILO_GTA, montar_escenas

ESTILOS = {"gta": ESTILO_GTA, "afdm": ESTILO_AFDM, "dec": dict(ESTILO_DEC, aviso=AVISO_DEC)}
NOMBRES = {"gta": "zonaleonida", "afdm": "alfinaldemes", "dec": "dineroenclaro"}
SALIDA = "salida"

webs = [w.strip() for w in (os.environ.get("WEBS") or "gta,afdm,dec").split(",") if w.strip()]
trabajos = []
for web in webs:
    art = ultimo_articulo(web)
    if not art:
        continue
    print(f"\n{web} · {art['titulo']} ({art['enlace']})")
    try:
        guion = guion_de_articulo(web, art)
    except Exception as error:
        print(f"::warning::{web}: no pude hacer el guion ({type(error).__name__}: {error}); hoy no hay segundo vídeo")
        continue
    for f, e in zip(guion["frases"], guion["escenas"]):
        print("  -", f, "   ", e["visual"])
    trabajos.append((web, guion))

if not trabajos:
    print("Hoy no hay artículos nuevos: no hay segunda tanda.")
    raise SystemExit(0)

from motor_voz import crear_motor, decir_guion

inicio = time.time()
voz = crear_motor()
os.makedirs(SALIDA, exist_ok=True)
for web, guion in trabajos:
    audios, trozos = decir_guion(voz, guion["frases"])
    base = f"{SALIDA}/{NOMBRES[web]}_{hoy().isoformat()}_articulo"
    montar_escenas(guion["frases"], audios, voz.sr, guion["escenas"], ESTILOS[web], base + ".mp4", trozos,
                   semilla=f"{web}-art-{hoy().isoformat()}")
    with open(base + ".txt", "w", encoding="utf-8") as fh:
        fh.write(guion["texto"] + "\n")
print(f"Listo en {round(time.time() - inicio)} s")
