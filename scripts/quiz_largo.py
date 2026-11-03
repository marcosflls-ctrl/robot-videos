"""Vídeo largo de quiz (horizontal, 1920x1080) para el domingo: unas 24 preguntas en tres niveles.

    intro  ->  NIVEL FÁCIL (preguntas)  ->  NIVEL MEDIO  ->  NIVEL DIFÍCIL  ->  resultado + pantalla final

Mismo formato de quiz que los Shorts (quizzes/*.yaml) con «formato: largo»; cada pregunta lleva su
«categoria» (color e ilustración) y su «dificultad» (facil, media, dificil), que decide el nivel.
Lo llama quiz.py; también deja la miniatura y la descripción con capítulos.
"""
import hashlib
import math
import random
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import marca_quiz
import quiz as Q
from quiz import F, chip, encajar_texto, mezcla_color, palomita, pegar, rebote, redondear, rgba, sombra, suave

W, H, FPS = 1920, 1080, 30
NIVELES = [("facil", "NIVEL FÁCIL", "Para calentar"), ("media", "NIVEL MEDIO", "Aquí empieza lo bueno"),
           ("dificil", "NIVEL DIFÍCIL", "Solo para cerebritos")]
# Columnas: ilustración a la izquierda, pregunta y respuestas a la derecha
IX0, IX1, IY0 = 80, 980, 170
IH = int((IX1 - IX0) * 9 / 16)
RX0, RX1 = 1040, 1840
RCX = (RX0 + RX1) // 2


def ordenar(q):
    """Preguntas en orden de nivel (fácil, media, difícil), respetando el orden dentro de cada uno."""
    orden = {"facil": 0, "media": 1, "dificil": 2}
    for p in q["preguntas"]:
        p["dificultad"] = str(p.get("dificultad") or "media").lower()
        if p["dificultad"] not in orden:
            raise SystemExit(f"::error::{q['_nombre']}: dificultad «{p['dificultad']}» no válida (facil, media o dificil)")
    q["preguntas"].sort(key=lambda p: orden[p["dificultad"]])


class MontadorLargo:
    def __init__(self, q, canal, imgs):
        self.q, self.canal = q, canal
        self.col = {k: tuple(v) for k, v in canal["colores"].items()}
        self.ft = canal["fuentes"]
        self.cats = [canal["categorias"][p.get("categoria") or q["categoria"]] for p in q["preguntas"]]
        self.cat = canal["categorias"][q["categoria"]]
        semilla = int(hashlib.sha1(q["_nombre"].encode()).hexdigest()[:8], 16)
        self.rnd = random.Random(semilla)
        self.base, self.patron = Q.fondo(canal, self.cat, semilla, W, H)
        self.n = len(q["preguntas"])
        self.tarjetas = [(img if img is not None else Q.imagen_provisional(self.cats[i], self.col, i)).convert("RGB")
                         for i, img in enumerate(imgs)]
        self.mascotas = {g: marca_quiz.mascota(440, canal["colores"], gesto=g) for g in ("feliz", "sorpresa", "guino", "pensando")}
        self.mini = {g: m.resize((190, 190), Image.LANCZOS) for g, m in self.mascotas.items()}
        self.chip_marca = chip(canal["marca"], F(self.ft["tit"], 34), rgba(self.col["tinta"], 220), rgba(self.col["acento"]), pad=26)
        self._cache = {}

    def _guardado(self, clave, hacer):
        if clave not in self._cache:
            self._cache[clave] = hacer()
        return self._cache[clave]

    # ----- fondo con cabecera -----

    def lienzo(self, t, total, i=None):
        lz = self.base.copy()
        off = int((t * 14) % 400)
        lz.alpha_composite(self.patron.crop((0, off, W, off + H)))
        d = ImageDraw.Draw(lz)
        color = self.cats[i]["color"] if i is not None else self.col["acento"]
        d.rectangle((0, H - 10, W, H), fill=rgba(self.col["fondo2"]))
        d.rectangle((0, H - 10, int(W * min(1, t / total)), H), fill=rgba(color))
        pegar(lz, self.chip_marca, 80 + self.chip_marca.width / 2, 80)
        if i is not None:
            p = self.q["preguntas"][i]
            txt = f"PREGUNTA {i + 1} DE {self.n}"
            f = F(self.ft["txt_b"], 34)
            d.text((W - 80, 80), txt, font=f, fill=rgba(self.col["texto"]), anchor="rm")
            nivel = {"facil": ("FÁCIL", self.col["correcto"]), "media": ("MEDIO", self.col["acento"]),
                     "dificil": ("DIFÍCIL", self.col["incorrecto"])}[p["dificultad"]]
            ch = chip(nivel[0], F(self.ft["txt_b"], 28), rgba(nivel[1]), (255, 255, 255, 255), pad=18)
            pegar(lz, ch, W - 80 - f.getlength(txt) - 24 - ch.width / 2, 80)
        return lz

    # ----- piezas -----

    def capa_pregunta(self, i):
        def hacer():
            texto = self.q["preguntas"][i]["pregunta"]
            ancho = RX1 - RX0
            f, lineas = encajar_texto(texto, self.ft["tit"], ancho - 10, 4, 60, 34)
            lh = f.size * 1.16
            img = Image.new("RGBA", (ancho, int(len(lineas) * lh + 14)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            for k, l in enumerate(lineas):
                y = k * lh + f.size * 0.6
                d.text((3, y + 4), l, font=f, fill=(0, 0, 0, 120), anchor="lm")
                d.text((0, y), l, font=f, fill=rgba(self.col["texto"]), anchor="lm")
            return img
        return self._guardado(("preg", i), hacer)

    def cajas(self, i):
        p = self.q["preguntas"][i]
        y0 = 470
        if p["tipo"] == "vf":
            m = RCX
            return [(RX0, y0, m - 12, y0 + 200), (m + 12, y0, RX1, y0 + 200)]
        n = len(p["opciones"])
        alto, hueco = (96, 18) if n > 2 else (130, 26)
        return [(RX0, y0 + k * (alto + hueco), RX1, y0 + k * (alto + hueco) + alto) for k in range(n)]

    def capa_opcion(self, i, k, estado):
        def hacer():
            p = self.q["preguntas"][i]
            cc = tuple(self.cats[i]["color"])
            x0, y0, x1, y1 = self.cajas(i)[k]
            w, h = int(x1 - x0), int(y1 - y0)
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            if estado == "bien":
                relleno, txt = self.col["correcto"], (255, 255, 255)
            elif estado == "mal":
                relleno, txt = mezcla_color(self.col["fondo2"], self.col["fondo"], 0.4), self.col["suave"]
            else:
                relleno, txt = self.col["panel"], self.col["tinta"]
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=26, fill=rgba(relleno))
            texto = p["opciones"][k]
            if p["tipo"] == "vf":
                f, lineas = encajar_texto(texto.upper(), self.ft["tit"], w - 40, 1, 60, 32)
                d.text((w / 2, h / 2 - (16 if estado == "bien" else 0)), lineas[0], font=f, fill=rgba(txt), anchor="mm")
                if estado == "bien":
                    palomita(d, w / 2, h - 42, 34, (255, 255, 255), 9)
                return img
            r = h * 0.34
            cx, cy = 20 + r, h / 2
            circulo = cc if estado == "normal" else ((255, 255, 255) if estado == "bien" else self.col["fondo2"])
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba(circulo))
            if estado == "bien":
                palomita(d, cx, cy, r * 0.9, rgba(self.col["correcto"]), 7)
            else:
                d.text((cx, cy), Q.LETRAS[k], font=F(self.ft["tit"], r * 1.25), fill=rgba(self.col["tinta"]), anchor="mm")
            f, lineas = encajar_texto(texto, self.ft["txt_b"], w - (cx + r + 24) - 24, 2, 42, 26)
            lh = f.size * 1.1
            y = h / 2 - (len(lineas) - 1) * lh / 2
            for l in lineas:
                d.text((cx + r + 22, y), l, font=f, fill=rgba(txt), anchor="lm")
                y += lh
            return img
        return self._guardado(("op", i, k, estado), hacer)

    def capa_dato(self, i):
        def hacer():
            p = self.q["preguntas"][i]
            dato = str(p.get("dato_pantalla") or p.get("dato") or "").strip()
            if not dato:
                return None
            w = IX1 - IX0
            f, lineas = encajar_texto(dato, self.ft["txt_b"], w - 60, 4, 36, 24)
            lh = int(f.size * 1.22)
            h = 80 + len(lineas) * lh + 18
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            cc = tuple(self.cats[i]["color"])
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=26, fill=rgba(self.col["tinta"], 238), outline=rgba(cc), width=4)
            img.alpha_composite(chip("¿SABÍAS QUE…?", F(self.ft["txt_b"], 26), rgba(cc), rgba(self.col["tinta"]), pad=16), (28, 22))
            y = 80
            for l in lineas:
                d.text((30, y), l, font=f, fill=rgba(self.col["texto"]))
                y += lh
            return img
        return self._guardado(("dato", i), hacer)

    def tarjeta(self, i, t):
        img = self.tarjetas[i]
        w, h = IX1 - IX0, IH
        z = 1.04 + 0.08 * min(1.0, t / 16)
        iw, ih = img.size
        prop = w / h
        cw, ch = (ih * prop, ih) if iw / ih > prop else (iw, iw / prop)
        cw, ch = cw / z, ch / z
        x0 = (iw - cw) * (0.5 + 0.35 * math.sin(t * 0.15 + i))
        y0 = (ih - ch) * 0.5
        return redondear(img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR), 30)

    def _texto(self, texto, f, color, ancla="mm"):
        tw = int(f.getlength(texto)) + 20
        img = Image.new("RGBA", (tw, int(f.size * 1.4)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((tw / 2 + 3, img.height / 2 + 4), texto, font=f, fill=(0, 0, 0, 120), anchor="mm")
        d.text((tw / 2, img.height / 2), texto, font=f, fill=rgba(color), anchor="mm")
        return img

    # ----- pantallas -----

    def intro(self, t, tl, total, b):
        lz = self.lienzo(t, total)
        d = ImageDraw.Draw(lz)
        pegar(lz, self.mascotas["pensando" if tl < 1.5 else "sorpresa"], 520, 560 + 12 * math.sin(tl * 3), 1, 1.25)
        txt = f"{self.n} PREGUNTAS"
        tam = 150
        while F(self.ft["tit"], tam).getlength(txt) > W - 80 - 1000 and tam > 60:
            tam -= 4
        f = F(self.ft["tit"], tam)
        d.text((1004, 386), txt, font=f, fill=(0, 0, 0, 120), anchor="lm")
        d.text((1000, 380), txt, font=f, fill=rgba(self.col["acento"]), anchor="lm")
        gancho = str(self.q.get("gancho_pantalla") or self.q.get("gancho") or "")
        fg, lineas = encajar_texto(gancho, self.ft["tit"], 820, 3, 60, 36)
        y = 520
        for l in lineas:
            d.text((1000, y), l, font=fg, fill=rgba(self.col["texto"]), anchor="lm")
            y += fg.size * 1.2
        x = 1000
        for k, (_, nombre, _) in enumerate(NIVELES):
            c = [self.col["correcto"], self.col["acento"], self.col["incorrecto"]][k]
            ch = chip(nombre.replace("NIVEL ", ""), F(self.ft["txt_b"], 34), rgba(c), (255, 255, 255, 255), pad=24)
            pegar(lz, ch, x + ch.width / 2, y + 60, 1, 1 + 0.08 * max(0.0, 1 - abs(tl - 0.8 - 0.3 * k) / 0.15))
            x += ch.width + 22
        nota = self._texto("Apunta tus aciertos y compáralos al final", F(self.ft["txt_b"], 34), self.col["suave"])
        pegar(lz, nota, 1000 + nota.width / 2, y + 150, suave((tl - 1.0) / 0.4))
        return lz

    def nivel(self, t, tl, total, b):
        lz = self.lienzo(t, total)
        k = b["nivel"]
        _, nombre, lema = NIVELES[k]
        c = [self.col["correcto"], self.col["acento"], self.col["incorrecto"]][k]
        ch = chip(nombre, F(self.ft["tit"], 130), rgba(c), (255, 255, 255, 255), pad=70)
        pegar(lz, ch, W / 2, H * 0.44, 1, rebote(tl / 0.35))
        pegar(lz, self._texto(lema, F(self.ft["tit2"], 56), self.col["texto"]), W / 2, H * 0.44 + 150, suave((tl - 0.3) / 0.3))
        rango = f"Preguntas {b['desde'] + 1} a {b['hasta']}"
        pegar(lz, self._texto(rango, F(self.ft["txt_b"], 36), self.col["suave"]), W / 2, H * 0.44 + 225, suave((tl - 0.5) / 0.3))
        pegar(lz, self.mini["guino" if k == 2 else "feliz"], W / 2 + ch.width / 2 + 40, H * 0.44 - 110, suave(tl / 0.3))
        return lz

    def pregunta(self, t, tl, total, b):
        i, ts = b["i"], b["tiempos"]
        p = self.q["preguntas"][i]
        lz = self.lienzo(t, total, i)
        cat = self.cats[i]
        # Ilustración y categoría
        tar = self.tarjeta(i, tl)
        sb, pos = sombra((IX0, IY0, IX1, IY0 + IH), 30)
        lz.alpha_composite(sb, pos)
        a = suave(tl / 0.3)
        pegar(lz, tar, (IX0 + IX1) / 2 - (1 - a) * 120, IY0 + IH / 2, a)
        cch = chip(cat["nombre"].upper(), F(self.ft["txt_b"], 28), rgba(cat["color"]), rgba(self.col["tinta"]), pad=18)
        pegar(lz, cch, IX0 + 22 + cch.width / 2, IY0 + 36, suave((tl - 0.2) / 0.2))
        # Pregunta
        cp = self.capa_pregunta(i)
        ap = suave((tl - 0.1) / 0.3)
        pegar(lz, cp, RX0 + cp.width / 2 + (1 - ap) * 120, IY0 + 140, ap)
        # Respuestas
        revela = tl >= ts["revela"]
        for k, caja in enumerate(self.cajas(i)):
            x0, y0, x1, y1 = caja
            apar = ts["opciones"][k]
            if tl < apar:
                continue
            if revela:
                estado = "bien" if k == p["_ok"] else "mal"
                tr = tl - ts["revela"]
                esc = 1 + 0.06 * math.sin(min(1, tr / 0.35) * math.pi) if estado == "bien" else 1
                alfa = 1 if estado == "bien" else 0.55 + 0.45 * (1 - suave(tr / 0.3))
                pegar(lz, self.capa_opcion(i, k, estado), (x0 + x1) / 2, (y0 + y1) / 2, alfa, esc)
            else:
                aa = (tl - apar) / 0.22
                sb, pos = sombra(caja, 26, 90, 12)
                lz.alpha_composite(sb, pos)
                pegar(lz, self.capa_opcion(i, k, "normal"), (x0 + x1) / 2, (y0 + y1) / 2, suave(aa), 0.9 + 0.1 * rebote(aa))
        # Cuenta atrás en la esquina de la ilustración
        cx, cy = IX1 - 90, IY0 + 90
        if ts["cuenta"] <= tl < ts["revela"]:
            dur = ts["revela"] - ts["cuenta"]
            tc = tl - ts["cuenta"]
            falta = max(0.0, dur - tc)
            frac = falta / dur
            d = ImageDraw.Draw(lz)
            r = 70
            color = mezcla_color(self.col["correcto"], self.col["incorrecto"], 1 - frac)
            d.ellipse((cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10), fill=rgba(self.col["tinta"], 235))
            d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * frac, fill=rgba(color), width=13)
            lat = 1 + 0.18 * max(0.0, 1 - ((tc % 1.0) / 0.25))
            d.text((cx, cy + 2), str(max(1, int(math.ceil(falta)))), font=F(self.ft["tit"], 78 * lat),
                   fill=rgba(self.col["texto"]), anchor="mm")
        if revela:
            tr = tl - ts["revela"]
            pegar(lz, self.mini["feliz" if tr < 1.2 else "guino"], cx, cy + (1 - rebote(tr / 0.4)) * 50, suave(tr / 0.2))
            cd = self.capa_dato(i)
            td = tl - ts["dato"]
            if cd is not None and td > 0:
                pegar(lz, cd, (IX0 + IX1) / 2, IY0 + IH + 30 + cd.height / 2 + (1 - suave(td / 0.3)) * 40, suave(td / 0.3))
        return lz

    def final(self, t, tl, total, b):
        lz = self.lienzo(t, total)
        d = ImageDraw.Draw(lz)
        pegar(lz, self.mascotas["feliz" if tl < 2 else "guino"], 330, 520 + 10 * math.sin(tl * 3), 1, rebote(tl / 0.4))
        f = F(self.ft["tit"], 76)
        pegar(lz, self._texto("¿Cuántas has acertado?", f, self.col["acento"]), 660 + f.getlength("¿Cuántas has acertado?") / 2,
              250, suave(tl / 0.3))
        n = self.n
        tramos = [(0, n // 3, "Calentando motores"), (n // 3 + 1, 2 * n // 3, "Buen coco"),
                  (2 * n // 3 + 1, n - 2, "Cerebrito"), (n - 1, n, "¡Genio total!")]
        y = 370
        for k, (a, bb, txt) in enumerate(tramos):
            al = suave((tl - 0.4 - 0.2 * k) / 0.3)
            c = mezcla_color(self.col["incorrecto"], self.col["correcto"], k / 3)
            ch = chip(f"{a}–{bb}", F(self.ft["tit"], 44), rgba(c), (255, 255, 255, 255), pad=26, alto=76)
            pegar(lz, ch, 680 + 110, y, al)
            pegar(lz, self._texto(txt, F(self.ft["txt_b"], 44), self.col["texto"]), 680 + 260 + F(self.ft["txt_b"], 44).getlength(txt) / 2,
                  y, al)
            y += 100
        sus = self._texto("Cada domingo, un quiz largo nuevo. ¡Suscríbete!", F(self.ft["txt_b"], 38), self.col["suave"])
        pegar(lz, sus, 660 + sus.width / 2, y + 40, suave((tl - 1.4) / 0.3))
        return lz


# =====================================================================
#  Línea de tiempo
# =====================================================================

def textos_largo(q, canal):
    textos = [str(q.get("decir_gancho") or q.get("gancho") or "")]
    plan = []  # (tipo, índice en textos)
    plan.append(("intro", 0))
    nivel_actual = None
    for i, p in enumerate(q["preguntas"]):
        if p["dificultad"] != nivel_actual:
            nivel_actual = p["dificultad"]
            k = [n[0] for n in NIVELES].index(nivel_actual)
            textos.append(["Nivel fácil. ¡Empezamos!", "Nivel medio. Aquí empieza lo bueno.",
                           "Nivel difícil. Solo para cerebritos."][k])
            plan.append(("nivel", len(textos) - 1, k))
        textos += [f"Pregunta {i + 1}. " + (f"¿Verdadero o falso? {p['pregunta']}" if p["tipo"] == "vf"
                                            else str(p.get("decir") or p["pregunta"])),
                   Q.frase_respuesta(p), Q.frase_dato(p)]
        plan.append(("pregunta", len(textos) - 3))
    textos.append(str(q.get("cierre") or "Y hasta aquí el quiz de hoy. ¿Cuántas has acertado? Dímelo en los comentarios, "
                                          "y si te ha gustado, suscríbete: cada domingo hay uno nuevo."))
    plan.append(("final", len(textos) - 1))
    return textos, plan


def linea_de_tiempo(q, canal, sr, audios, plan):
    cuenta = float((canal.get("largo") or {}).get("cuenta_atras") or 5)
    final_seg = float((canal.get("largo") or {}).get("pantalla_final") or 14)
    bloques, voz, t, i_preg = [], [], 0.0, 0
    niveles_vistos = 0
    for paso_plan in plan:
        tipo, k = paso_plan[0], paso_plan[1]
        if tipo == "intro":
            dur = max(4.0, len(audios[k]) / sr + 1.2)
            bloques.append({"tipo": "intro", "ini": t, "fin": t + dur})
            voz.append((t + 0.2, audios[k]))
        elif tipo == "nivel":
            niveles_vistos = paso_plan[2]
            dif = NIVELES[niveles_vistos][0]
            desde = next(j for j, p in enumerate(q["preguntas"]) if p["dificultad"] == dif)
            hasta = max(j for j, p in enumerate(q["preguntas"]) if p["dificultad"] == dif) + 1
            dur = max(2.6, len(audios[k]) / sr + 1.0)
            bloques.append({"tipo": "nivel", "ini": t, "fin": t + dur, "nivel": niveles_vistos, "desde": desde, "hasta": hasta})
            voz.append((t + 0.35, audios[k]))
        elif tipo == "pregunta":
            a_preg, a_resp, a_dato = audios[k], audios[k + 1], audios[k + 2]
            p = q["preguntas"][i_preg]
            voz_ini = 0.35
            voz_fin = voz_ini + len(a_preg) / sr
            n_op = len(p["opciones"])
            primera = voz_ini + max(0.4, (voz_fin - voz_ini) * 0.45)
            paso = min(0.35, max(0.18, (voz_fin - primera) / max(1, n_op)))
            opciones = [primera + j * paso for j in range(n_op)]
            c_ini = max(voz_fin + 0.2, opciones[-1] + 0.3)
            revela = c_ini + cuenta
            resp_ini = revela + 0.25
            dato_ini = resp_ini + len(a_resp) / sr + 0.7
            fin = (dato_ini + len(a_dato) / sr + 1.1) if len(a_dato) else (resp_ini + len(a_resp) / sr + 1.2)
            bloques.append({"tipo": "pregunta", "i": i_preg, "ini": t, "fin": t + fin,
                            "tiempos": {"voz_fin": voz_fin, "cuenta": c_ini, "revela": revela, "opciones": opciones,
                                        "dato": dato_ini - 0.25}})
            voz.append((t + voz_ini, a_preg))
            voz.append((t + resp_ini, a_resp))
            if len(a_dato):
                voz.append((t + dato_ini, a_dato))
            i_preg += 1
            t += fin
            continue
        else:
            dur = max(final_seg, len(audios[k]) / sr + 2)
            bloques.append({"tipo": "final", "ini": t, "fin": t + dur})
            voz.append((t + 0.4, audios[k]))
        t = bloques[-1]["fin"]
    return bloques, voz


# =====================================================================
#  Montaje, miniatura y textos
# =====================================================================

def montar(m, bloques, ruta_audio, salida, solo=None):
    total = bloques[-1]["fin"]
    n_frames = int(math.ceil(total * FPS))
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(ruta_audio), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{n_frames / FPS:.3f}",
           "-movflags", "+faststart", str(salida)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    inicio, bi_ant, corte_t, anterior, ultimo = time.time(), -1, 0.0, None, None
    for nf in range(n_frames):
        t = nf / FPS
        bi = next((k for k, b in enumerate(bloques) if b["ini"] <= t < b["fin"]), len(bloques) - 1)
        b = bloques[bi]
        lz = getattr(m, b["tipo"])(t, t - b["ini"], total, b)
        if bi != bi_ant:
            corte_t, ultimo = t, anterior
        if bi > 0 and t - corte_t < 0.15 and ultimo is not None:
            lz = Image.blend(ultimo, lz, (t - corte_t) / 0.15)
        bi_ant, anterior = bi, lz
        ff.stdin.write(lz.convert("RGB").tobytes())
        if solo is not None and nf in solo:
            lz.convert("RGB").save(Q.SALIDA / f"{m.q['_nombre']}_fotograma_{nf:05d}.png")
        if nf % (FPS * 30) == 0:
            print(f"  {t:.0f}/{total:.0f} s ({time.time() - inicio:.0f} s montando)")
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("::error::ffmpeg no pudo montar el vídeo")
    print(f"Vídeo largo listo: {salida} ({total / 60:.1f} min, {Path(salida).stat().st_size / 1e6:.0f} MB)")
    return total


def miniatura(m, ruta):
    """Miniatura 1280x720: una ilustración de fondo, la mascota y «24 PREGUNTAS»."""
    q = m.q
    i = int(q.get("miniatura_de") or (m.n - 1))
    w, h = 1280, 720
    fondo = m.tarjetas[min(i, m.n - 1)].copy()
    iw, ih = fondo.size
    prop = w / h
    cw, ch = (ih * prop, ih) if iw / ih > prop else (iw, iw / prop)
    img = fondo.crop((int((iw - cw) / 2), int((ih - ch) / 2), int((iw + cw) / 2), int((ih + ch) / 2))).resize((w, h)).convert("RGBA")
    velo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dv = ImageDraw.Draw(velo)
    for x in range(w):
        a = int(235 * max(0.0, min(1.0, (x - 380) / 420)))
        dv.line([(x, 0), (x, h)], fill=rgba(m.col["fondo"], a))
    img.alpha_composite(velo)
    masc = marca_quiz.mascota(420, m.canal["colores"], gesto="sorpresa")
    img.alpha_composite(masc, (30, h - 420))
    d = ImageDraw.Draw(img)
    txt1 = str(q.get("miniatura_texto") or f"{m.n} PREGUNTAS")
    f1 = F(m.ft["tit"], 120)
    while f1.getlength(txt1) > 640 and f1.size > 60:
        f1 = F(m.ft["tit"], f1.size - 6)
    d.text((1236, 236), txt1, font=f1, fill=(0, 0, 0, 160), anchor="rm")
    d.text((1230, 230), txt1, font=f1, fill=rgba(m.col["acento"]), anchor="rm")
    f2 = F(m.ft["tit"], 70)
    for k, l in enumerate(["¿CUÁNTAS", "ACIERTAS?"]):
        d.text((1234, 364 + k * 84), l, font=f2, fill=(0, 0, 0, 160), anchor="rm")
        d.text((1230, 360 + k * 84), l, font=f2, fill=rgba(m.col["texto"]), anchor="rm")
    x = 1230
    for k, nombre in enumerate(["DIFÍCIL", "MEDIO", "FÁCIL"]):
        c = [m.col["incorrecto"], m.col["acento"], m.col["correcto"]][k]
        ch_ = chip(nombre, F(m.ft["txt_b"], 34), rgba(c), (255, 255, 255, 255), pad=22)
        img.alpha_composite(ch_, (int(x - ch_.width), 560))
        x -= ch_.width + 16
    img.convert("RGB").save(ruta, quality=92)


def minuto(s):
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def texto_publicacion(q, canal, bloques):
    lineas = [f"TÍTULO: {q.get('titulo')}", "", "DESCRIPCIÓN:",
              f"{q.get('gancho', '')} Apunta tus aciertos y dime en los comentarios cuántas has sacado.", "",
              "Capítulos:"]
    for b in bloques:
        if b["tipo"] == "intro":
            lineas.append(f"{minuto(b['ini'])} Empezamos")
        elif b["tipo"] == "nivel":
            lineas.append(f"{minuto(b['ini'])} {NIVELES[b['nivel']][1].capitalize()}")
        elif b["tipo"] == "final":
            lineas.append(f"{minuto(b['ini'])} ¿Cuántas has acertado?")
    lineas += ["", f"Cada domingo, un quiz largo nuevo en {Q.nombre_canal(canal)}; y de lunes a sábado, un Short.",
               "Ilustraciones generadas con IA.", "", "#quiz #trivia #culturageneral #preguntas"]
    lineas += ["", "RESPUESTAS (para fijar un comentario, si quieres):"]
    for i, p in enumerate(q["preguntas"], 1):
        lineas.append(f"{i}. {p['opciones'][p['_ok']]}")
    if q.get("fuentes"):
        lineas += ["", "FUENTES (para comprobar las respuestas):"] + [f"- {f}" for f in q["fuentes"]]
    return "\n".join(lineas) + "\n"


def copia_ligera(entrada, salida, duracion, max_mb=45):
    """Copia que cabe en Telegram (50 MB) para verla en el móvil."""
    kbps = int(max_mb * 8 * 1024 / duracion) - 96
    if kbps < 250:
        return False
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(entrada), "-vf", "scale=1280:720",
                    "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.4)}k",
                    "-bufsize", f"{kbps * 2}k", "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", str(salida)],
                   check=True)
    return Path(salida).stat().st_size / 1024 / 1024 < 49


def montar_largo(q, canal):
    nombre = q["_nombre"]
    ordenar(q)
    print(f"Quiz largo: {nombre} · {len(q['preguntas'])} preguntas")
    Q.SALIDA.mkdir(parents=True, exist_ok=True)
    textos, plan = textos_largo(q, canal)
    sr, auds = Q.voces(textos, canal)
    imgs = Q.imagenes(q, canal)
    bloques, voz = linea_de_tiempo(q, canal, sr, auds, plan)
    m = MontadorLargo(q, canal, imgs)
    with tempfile.TemporaryDirectory() as tmp:
        ruta_audio = Q.audio(bloques, voz, sr, canal, canal["categorias"][q["categoria"]], Path(tmp))
        solo = {int(float(x) * FPS) for x in Q._env("FOTOGRAMAS").split(",")} if Q._env("FOTOGRAMAS") else None
        video = Q.SALIDA / f"{nombre}.mp4"
        dur = montar(m, bloques, ruta_audio, video, solo)
    miniatura(m, Q.SALIDA / f"{nombre}_miniatura.png")
    (Q.SALIDA / f"{nombre}.txt").write_text(texto_publicacion(q, canal, bloques), encoding="utf-8")
    if video.stat().st_size > 45 * 1024 * 1024:
        copia_ligera(video, Q.SALIDA / f"{nombre}_movil.mp4", dur)
    if Q._env("GITHUB_OUTPUT"):
        with open(Q._env("GITHUB_OUTPUT"), "a") as f:
            f.write(f"quiz={nombre}\nformato=largo\n")
