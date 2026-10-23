"""Vídeos diarios de las tres webs: Zona Leonida (GTA), Al Final de Mes y Dinero en Claro.

Variables:
    WEBS        webs a hacer, separadas por comas: "gta,afdm,dec" (por defecto, las tres)
    TEMA_AFDM   forzar un tema (luz, carburantes, ipc, euribor). Vacío = el que toca hoy.
    TEMA_DEC    forzar un tema (mercados, aportaciones, ahorro, cripto). Vacío = el que toca hoy.
    DATOS_AFDM  carpeta con los datos de Al Final de Mes (src/data)
    DATOS_DEC   carpeta con los datos de Dinero en Claro (src/data)

Genera en salida/ un .mp4 y un .txt (texto para la publicación) por web. No publica nada.
"""
import os
import time

import guion_gta
import video as video_gta
from guiones_webs import AVISO_DEC, TEMAS, hoy, tema_de_hoy
from montaje import ESTILO_AFDM, ESTILO_DEC, ESTILO_GTA, montar_escenas
from video_datos import montar

# MONTAJE=escenas (por defecto: cortes rápidos, Pexels si hay clave) o clasico (una sola pantalla)
MONTAJE = (os.environ.get("MONTAJE") or "escenas").strip()
ESTILOS = {"gta": ESTILO_GTA, "afdm": ESTILO_AFDM, "dec": dict(ESTILO_DEC, aviso=AVISO_DEC)}

SALIDA = "salida"
NOMBRES = {"gta": "zonaleonida", "afdm": "alfinaldemes", "dec": "dineroenclaro"}
CARPETAS = {"afdm": os.environ.get("DATOS_AFDM", "../datos/afdm/src/data"),
            "dec": os.environ.get("DATOS_DEC", "../datos/dec/src/data")}

webs = [w.strip() for w in os.environ.get("WEBS", "gta,afdm,dec").split(",") if w.strip()]
trabajos = []
for web in webs:
    if web == "gta":
        dias = guion_gta.dias_que_faltan()
        frases = guion_gta.guion(dias)
        if not frases:
            print("GTA 6 ya ha salido: no hay vídeo de cuenta atrás.")
            continue
        cifra, bajo = ("HOY", "SALE GTA 6") if dias == 0 else (str(dias), "DÍA PARA GTA 6" if dias == 1 else "DÍAS PARA GTA 6")
        tema_gta = dict(video_gta.TEMA_GTA, cifra=cifra, bajo_cifra=bajo)
        texto = (f"{frases[0].rstrip('.')} ⏳\n\nEl 19 de noviembre de 2026 llega GTA 6. Cada día, la cuenta atrás en "
                 "zonaleonida.com\n\n#GTA6 #GTAVI #GrandTheftAuto #ViceCity #Leonida #ZonaLeonida #Gaming #Shorts")
        print(f"\ngta · faltan {dias} días:")
        for f in frases:
            print("  -", f)
        trabajos.append(("gta", "cuenta-atras", {"frases": frases, "tema": tema_gta, "texto": texto,
                                                 "escenas": guion_gta.escenas(dias)}))
        continue
    tema = (os.environ.get(f"TEMA_{web.upper()}") or "").strip() or tema_de_hoy(web)
    guion = TEMAS[web][tema](CARPETAS[web])
    print(f"\n{web} · {tema}:")
    for f in guion["frases"]:
        print("  -", f)
    trabajos.append((web, tema, guion))

from motor_voz import crear_motor  # tarda en cargar: solo después de comprobar los datos

inicio = time.time()
voz = crear_motor()
print(f"Voz cargada en {round(time.time() - inicio)} s")
os.makedirs(SALIDA, exist_ok=True)
for web, tema, guion in trabajos:
    audios, trozos = [], []
    for f in guion["frases"]:
        t = time.time()
        audios.append(voz.decir(f))
        trozos.append(voz.ultimas_piezas)
        print(f"    ({round(time.time() - t)} s)")
    base = f"{SALIDA}/{NOMBRES[web]}_{hoy().isoformat()}_{tema}"
    if MONTAJE == "clasico":
        montador = video_gta.montar if web == "gta" else montar
        montador(guion["frases"], audios, voz.sr, guion["tema"], base + ".mp4", trozos)
    else:
        r = montar_escenas(guion["frases"], audios, voz.sr, guion["escenas"], ESTILOS[web], base + ".mp4", trozos,
                           semilla=f"{web}-{hoy().isoformat()}")
        if r["creditos"]:
            with open(base + "_creditos_pexels.txt", "w", encoding="utf-8") as fh:
                fh.write("Clips de Pexels (no hace falta citarlos, pero queda constancia):\n" + "\n".join(r["creditos"]) + "\n")
    with open(base + ".txt", "w", encoding="utf-8") as fh:
        fh.write(guion["texto"] + "\n")
print(f"Listo en {round(time.time() - inicio)} s")
