"""TEMPORAL: demo del estilo lienzo v2 con elementos reales (fotos libres de Wikimedia Commons).

En el robot de verdad, los fondos y portadas serán los fotogramas del tráiler que ya usa Zona Leonida.
"""
from pathlib import Path

import numpy as np
from rembg import new_session, remove

import imagenes
import lienzo as L

SAL = Path("salida"); SAL.mkdir(exist_ok=True)
sr = 24000
frases = [
    "Faltan 24 días para GTA 6.",
    "El 19 de noviembre llega a PlayStation 5 y Xbox Series.",
    "¿Y en PC? Rockstar todavía no ha dado fecha.",
    "Volvemos a Vice City, en el estado de Leonida.",
    "Con dos protagonistas: Lucía y Jason.",
    "Si lo cuentas en horas, son 576 horas de espera.",
    "¿Lo jugarás el primer día? Te leo abajo.",
]
claves = ["24", "días", "19", "noviembre", "PC", "fecha", "Vice", "City", "Lucía", "Jason", "576", "horas", "primer"]
palabras, ini, t = [], [], 0.4
for f in frases:
    ini.append(t)
    for w in f.split():
        d = 0.16 + 0.055 * len(w)
        palabras.append((w, t, t + d))
        t += d + 0.05
    t += 0.35
dur = t + 1.2
audio = np.zeros(int(sr * dur), dtype=np.float32)


def foto(busqueda):
    im, cred = imagenes.conseguir({"buscar_imagen": busqueda}, Path("."))
    print("foto:", busqueda, "->", cred)
    return im if im is not None else L._postal_vice_city(1600, 900)


ses = new_session("isnet-general-use")


def recorte(archivo):
    busqueda = archivo
    im, cred = imagenes.conseguir({"imagen": archivo}, Path("."))
    print("recorte:", busqueda, "->", cred)
    if im is None:
        return None
    im.thumbnail((1400, 1400))
    sin_fondo = remove(im, session=ses)
    sin_fondo.save(SAL / f"recorte_{abs(hash(archivo)) % 1000}.png")
    return sin_fondo


miami_noche = foto("Miami skyline night")
miami_aire = foto("Miami Beach aerial view")
palmeras = foto("Miami palm trees sunset")
coche = foto("Miami Beach classic car Ocean Drive")
ps5 = recorte("File:PlayStation 5 and DualSense with transparent background.png")
xbox = recorte("File:Xbox series X (50648118708).jpg")
pc_foto = recorte("File:Gaming-PC 20240426 HOF2520-HDR RAW-Export.png")

T = L.Tarjeta
b = []
# 1. Cuenta atrás
y = 0
c1 = T(540, y, ini[0] + 0.15, "24", etiqueta="Cuenta atrás", sub="días para GTA 6")
c1.giro_entrada, c1.balanceo = 70, 4
tit = L.Titular3D(540, y - 330, ini[0] + 0.5, "Días", tam=96)
b.append({"ini": ini[0], "piezas": [c1, tit], "foco": (540, y - 60, 1.2), "fondo": L.preparar_fondo(palmeras),
          "efectos": [L.flash(0.0)]})
# 2. Consolas reales recortadas
y2 = 800
piezas2 = [L.Pastilla(540, y2 - 330, ini[1] + 0.2, "19 nov 2026"),
           L.Conector(540, y2 - 170, ini[1] + 0.6, separacion=500, alto=150)]
piezas2.append(L.Recorte(290, y2 + 160, ini[1] + 1.4, ps5, alto=520, max_ancho=360, escudo=True) if ps5 is not None
               else T(290, y2 + 160, ini[1] + 1.4, "PS5", ancho=320, alto=260, barra=False))
piezas2.append(L.Recorte(790, y2 + 160, ini[1] + 2.0, xbox, alto=460, max_ancho=360) if xbox is not None
               else T(790, y2 + 160, ini[1] + 2.0, "XBOX", ancho=320, alto=260, barra=False))
b.append({"ini": ini[1], "piezas": piezas2, "foco": (540, y2 + 40, 0.92)})
# 3. PC bloqueado
y3 = y2 + 900
pc = (L.Recorte(540, y3 + 20, ini[2], pc_foto, alto=440, max_ancho=420) if pc_foto is not None
      else T(540, y3, ini[2], "PC", etiqueta="Ordenador", sub="sin fecha", ancho=360, alto=300, barra=False))
pc.giro_entrada = -60
cand = L.Candado(540, y3 - 300, ini[2] + 1.1, color=L.ROJO)
tn = L.Pastilla(540, y3 + 300, ini[2] + 1.3, "Todavía no", color=L.ROJO)
g = lambda te: pc.iluminar(te) if hasattr(pc, "iluminar") else None
g.golpe = True
b.append({"ini": ini[2], "piezas": [pc, cand, tn], "foco": (540, y3, 1.1), "efectos": [(ini[2] + 1.1, g)],
          "fondo": L.preparar_fondo(miami_noche)})
# 4. Vice City: portada girando, titular 3D, lluvia de tarjetas
y4 = y3 + 900
lluvia = L.Lluvia(540, y4, ini[3] + 0.9, palmeras, n=8, radio=560)
port = L.Portada(540, y4, ini[3] + 0.1, imagen=miami_aire, ancho=760, alto=430)
t4 = L.Titular3D(540, y4 - 360, ini[3] + 0.5, "Vice City", tam=104)
lp = L.Pastilla(540, y4 + 300, ini[3] + 1.6, "Estado de Leonida", color=L.CIAN)
b.append({"ini": ini[3], "piezas": [lluvia, port, t4, lp], "foco": (540, y4 - 40, 1.0),
          "fondo": L.preparar_fondo(miami_aire), "efectos": [L.flash(ini[3] - 0.05)]})
# 5. Protagonistas
y5 = y4 + 900
con2 = L.Conector(540, y5 - 200, ini[4] + 0.2, separacion=470, alto=140)
lu = L.Portada(305, y5 + 60, ini[4] + 0.8, imagen=coche, ancho=400, alto=500, etiqueta="Lucía")
ja = L.Portada(775, y5 + 60, ini[4] + 1.4, imagen=miami_noche, ancho=400, alto=500, etiqueta="Jason")
lu.giro_entrada, ja.giro_entrada = -75, 75
b.append({"ini": ini[4], "piezas": [con2, lu, ja], "foco": (540, y5, 0.95), "fondo": L.preparar_fondo(coche)})
# 6. Horas
y6 = y5 + 760
hr = T(540, y6, ini[5], "576", etiqueta="Espera", sub="horas")
hr.giro_entrada = 70
x24 = L.Multiplicador(870, y6 - 40, ini[5] + 1.6, "×24")
r = lambda te: hr.romper(te)
r.golpe = True
b.append({"ini": ini[5], "piezas": [hr, x24], "foco": (540, y6, 1.2), "efectos": [(ini[5] + 2.4, r)]})
b.append({"ini": ini[5] + 2.9, "piezas": [], "foco": (540, y6 / 2 + 300, 0.4)})

cierre = {"ini": ini[6] - 0.1,
          "dibujar": L.cierre_comentarios("¿Lo jugarás el primer día?", "Te leemos en los comentarios")}
L.montar(b, audio, sr, palabras, str(SAL / "demo_lienzo2.mp4"), claves=claves, cierre=cierre)
print("ok", round(dur, 1))
