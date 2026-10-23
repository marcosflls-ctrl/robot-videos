"""Vídeo diario de Zona Leonida: «Faltan X días para GTA 6».

Genera salida/gta_AAAA-MM-DD.mp4 y salida/gta_AAAA-MM-DD.txt (texto para la publicación).
No publica nada: el robot solo te lo manda para revisarlo.

Para probar otro día: variable DIAS (por ejemplo DIAS=10).
"""
import os
import time
from datetime import datetime

from guion_gta import ESTRENO, MADRID, dias_que_faltan, escenas, guion
from montaje import ESTILO_GTA, montar_escenas
from video import TEMA_GTA, montar

SALIDA = "salida"
MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

dias = int(os.environ["DIAS"]) if os.environ.get("DIAS", "").strip() else dias_que_faltan()
frases = guion(dias)
if not frases:
    print("GTA 6 ya ha salido: no hay vídeo de cuenta atrás.")
    raise SystemExit(0)

hoy = datetime.now(MADRID).strftime("%Y-%m-%d")
print(f"Faltan {dias} días. Guion:")
for f in frases:
    print("  -", f)

if dias == 0:
    cifra, bajo = "HOY", "SALE GTA 6"
elif dias == 1:
    cifra, bajo = "1", "DÍA PARA GTA 6"
else:
    cifra, bajo = str(dias), "DÍAS PARA GTA 6"
tema = dict(TEMA_GTA, cifra=cifra, bajo_cifra=bajo,
            dato=f"{ESTRENO.day} · {MESES[ESTRENO.month - 1]} · {ESTRENO.year}")

from motor_voz import crear_motor  # se importa aquí porque tarda en cargar

inicio = time.time()
voz = crear_motor()
print(f"Voz cargada en {round(time.time() - inicio)} s")
audios, trozos = [], []
for f in frases:
    t = time.time()
    audios.append(voz.decir(f))
    trozos.append(voz.ultimas_piezas)
    print(f"    ({round(time.time() - t)} s)")

os.makedirs(SALIDA, exist_ok=True)
if (os.environ.get("MONTAJE") or "escenas").strip() == "clasico":
    duracion = montar(frases, audios, voz.sr, tema, f"{SALIDA}/gta_{hoy}.mp4", trozos)
else:
    duracion = montar_escenas(frases, audios, voz.sr, escenas(dias), ESTILO_GTA, f"{SALIDA}/gta_{hoy}.mp4", trozos,
                              semilla=f"gta-{hoy}")["duracion"]

titulo = frases[0].rstrip(".")
texto = (
    f"{titulo} ⏳\n\n"
    f"El {ESTRENO.day} de noviembre de {ESTRENO.year} llega GTA 6. Cada día, la cuenta atrás en zonaleonida.com\n\n"
    "#GTA6 #GTAVI #GrandTheftAuto #ViceCity #Leonida #ZonaLeonida #Gaming #Shorts"
)
with open(f"{SALIDA}/gta_{hoy}.txt", "w", encoding="utf-8") as fh:
    fh.write(texto + "\n")
print(f"Listo en {round(time.time() - inicio)} s · vídeo de {duracion:.1f} s")
