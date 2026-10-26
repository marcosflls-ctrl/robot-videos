"""Short de Zona Leonida con el motor nuevo (Remotion): el director inventa el montaje de cada vídeo.

Pasos: tema del día (cuenta atrás o último artículo) -> fotogramas del tráiler descritos por la IA
-> el director escribe el guion visual (y la voz, si es una noticia) -> voz de Gemini -> momento de
cada palabra -> Remotion monta el vídeo. No publica nada: deja el vídeo y su texto en salida/.

Variables: MODO (cuenta | articulo | auto; auto = artículo si hay uno nuevo, si no cuenta atrás),
GEMINI_API_KEY, GEMINI_VOZ, FOTOGRAMAS (carpeta de imágenes), VENTANA_HORAS, SIN_VOZ=1 (prueba).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

import director as D
from fotogramas import describir
from guion_gta import dias_que_faltan, guion_completo

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
MOTOR = RAIZ / "remotion"
PUBLICO = MOTOR / "public"
SALIDA = AQUI / "salida"
CACHE = RAIZ / "cache_director"
SALIDA.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)


def tema_del_dia(modo):
    if modo in ("articulo", "auto"):
        from articulos import texto_del_articulo, ultimo_articulo
        art = ultimo_articulo("gta")
        if art:
            texto = texto_del_articulo(art["enlace"]) or art["descripcion"]
            return "articulo", f"Artículo: {art['titulo']}\n\n{texto[:6000]}", None, art
        if modo == "articulo":
            raise SystemExit("No hay artículo nuevo en Zona Leonida.")
    dias = dias_que_faltan()
    frases = [f for f, _, _ in guion_completo(dias)]
    if not frases:
        raise SystemExit("GTA 6 ya ha salido: no hay cuenta atrás.")
    tema = (f"Cuenta atrás diaria: faltan {dias} días para GTA 6. Sale el 19 de noviembre de 2026 en PlayStation 5 y "
            f"Xbox Series. Vuelve Vice City, en el estado de Leonida; protagonistas Lucía y Jason.")
    return "cuenta", tema, frases, None


def main():
    modo = (os.environ.get("MODO") or "auto").strip()
    tipo, tema, frases, art = tema_del_dia(modo)
    print(f"Vídeo: {tipo}")

    # Fotogramas del tráiler (descritos una vez) y objetos recortados
    fotos = describir(os.environ.get("FOTOGRAMAS") or (RAIZ / "privado" / "imagenes_gta"), CACHE / "fotogramas.json")
    destino = PUBLICO / "fotogramas"
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    rutas = {}
    for k, v in fotos.items():
        nombre = f"{k}{Path(v['archivo']).suffix.lower()}"
        shutil.copy(v["archivo"], destino / nombre)
        rutas[k] = f"fotogramas/{nombre}"
    imagenes = {k: v["describe"] for k, v in fotos.items()}
    objetos_info = json.loads((PUBLICO / "objetos" / "objetos.json").read_text(encoding="utf-8"))
    objetos = {k: v["describe"] for k, v in objetos_info.items()}

    # El director
    ruta_hist = CACHE / "historial.json"
    historial = D.cargar_historial(ruta_hist)
    plan = D.pedir_plan(tema, imagenes, objetos, historial, frases=frases)
    for e in plan["escenas"]:
        print(f"  [{e['frase']}] {e['tipo']:10s} {e['camara']:9s} {e['transicion']:8s} {json.dumps(e['datos'], ensure_ascii=False)[:100]}")
    print("  fondo:", plan["fondo"], "· subtítulos:", plan["subtitulos"])

    # Voz y momento de cada palabra
    if (os.environ.get("SIN_VOZ") or "").strip() == "1":
        palabras, duracion = D.tiempos_a_ojo(plan["frases"])
        audio_rel = None
    else:
        from motor_voz import crear_motor, decir_guion
        from tiempos_palabras import de_frase
        voz = crear_motor()
        audios, _ = decir_guion(voz, plan["frases"])
        sr = voz.sr
        pausa = np.zeros(int(sr * 0.28), dtype=np.float32)
        trozos = [np.zeros(int(sr * 0.3), dtype=np.float32)]
        for a in audios:
            trozos += [a, pausa]
        cola = np.zeros(int(sr * 1.6), dtype=np.float32)  # el cierre respira un poco
        total = np.concatenate(trozos + [cola])
        # se escucha el audio entero y se alinea con todo el texto (no depende de dónde se cortó cada frase)
        palabras = de_frase(total, sr, " ".join(plan["frases"]))
        sf.write(PUBLICO / "voz.wav", total, sr)
        duracion = len(total) / sr
        audio_rel = "voz.wav"

    guion = D.a_guion(plan, palabras, duracion, rutas, audio=audio_rel, fondos_extra=list(rutas.values())[:6])
    hoy = D.date.today().isoformat()
    base = SALIDA / f"zonaleonida_{hoy}_{tipo}"
    (base.with_suffix(".json")).write_text(json.dumps(guion, ensure_ascii=False, indent=1), encoding="utf-8")

    # Montaje con Remotion
    env = dict(os.environ)
    r = subprocess.run(["node", "render.mjs", str(base.with_suffix(".json")), str(base.with_suffix(".mp4"))], cwd=MOTOR, env=env)
    if r.returncode != 0:
        raise SystemExit("Remotion no pudo montar el vídeo")
    D.guardar_historial(ruta_hist, historial, plan)

    # Texto para subirlo: título, descripción, créditos
    usados = {v[7:] for e in plan["escenas"] for v in _cadenas(e["datos"]) if v.startswith("objeto:")}
    creditos = [objetos_info[o]["credito"] for o in sorted(usados) if o in objetos_info]
    lineas = [plan["titulo"], ""]
    if art:
        lineas += [art["descripcion"], "", f"Léelo completo: {art['enlace']}", ""]
    else:
        lineas += ["Cada día, cuánto falta para GTA 6. Todas las novedades en zonaleonida.com", ""]
    if fotos:
        lineas.append("Imágenes: Rockstar Games.")
    lineas += creditos
    lineas += ["", "#GTA6 #GTAVI #GrandTheftAuto #ViceCity #ZonaLeonida #Gaming #Shorts"]
    base.with_suffix(".txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("Listo:", base.with_suffix(".mp4"))


def _cadenas(d):
    if isinstance(d, str):
        yield d
    elif isinstance(d, dict):
        for v in d.values():
            yield from _cadenas(v)
    elif isinstance(d, list):
        for v in d:
            yield from _cadenas(v)


if __name__ == "__main__":
    sys.exit(main())
