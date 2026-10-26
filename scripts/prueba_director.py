"""TEMPORAL: el director inventa 3 vídeos (cuenta atrás + 2 noticias reales de Zona Leonida).

Se ejecuta con el código de la rama motor-remotion (carpeta ../motor). Fotos de prueba: libres de
Wikimedia Commons (en el robot real serán los fotogramas del tráiler).
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MOTOR = Path(__file__).resolve().parent.parent / "motor"
sys.path.insert(0, str(MOTOR / "scripts"))
import articulos  # noqa: E402
import director as D  # noqa: E402
import imagenes  # noqa: E402
from guion_gta import dias_que_faltan, guion_completo  # noqa: E402

PUBLICO = MOTOR / "remotion" / "public"
(PUBLICO / "demo").mkdir(parents=True, exist_ok=True)
SALIDA = MOTOR / "remotion" / "demos"

FOTOS = {
    "f1": ("Miami skyline night", "skyline de una ciudad costera de noche con luces de neón"),
    "f2": ("Miami Beach aerial view", "vista aérea de una playa con hoteles"),
    "f3": ("Miami palm trees sunset", "palmeras y ciudad al atardecer"),
    "f4": ("Ocean Drive Miami Beach art deco", "calle con edificios art déco y neones"),
    "f5": ("Florida Everglades airboat", "pantano de Florida con lancha"),
    "f6": ("Florida Keys Seven Mile Bridge", "puente largo sobre el mar en los cayos"),
    "f7": ("sports car night city lights", "coche deportivo de noche en la ciudad"),
    "f8": ("video game controller", "mando de videoconsola"),
}
rutas, descripciones = {}, {}
for k, (busca, desc) in FOTOS.items():
    im, cred = imagenes.conseguir({"buscar_imagen": busca}, Path("."))
    if im is None:
        continue
    im.thumbnail((1600, 1600))
    im.save(PUBLICO / "demo" / f"{k}.jpg", quality=88)
    rutas[k] = f"demo/{k}.jpg"
    descripciones[k] = desc
    print("foto", k, "->", cred)
objetos = {"ps5": "consola PlayStation 5 blanca con mando", "xbox": "consola Xbox Series X negra con mando",
           "pc": "torre de PC gaming con ventiladores"}

# Temas: cuenta atrás + 2 últimos artículos de Zona Leonida
temas = []
dias = dias_que_faltan()
frases_cuenta = [f for f, _, _ in guion_completo(dias)]
temas.append(("cuenta_atras", f"Cuenta atrás diaria: faltan {dias} días para GTA 6 (sale el 19 de noviembre de 2026 en PS5 y Xbox Series).", frases_cuenta))
raiz = ET.fromstring(articulos._get("https://zonaleonida.com/rss.xml"))
for it in list(raiz.iter("item"))[:2]:
    titulo, enlace = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
    texto = articulos.texto_del_articulo(enlace) or (it.findtext("description") or "")
    temas.append((f"noticia_{len(temas)}", f"Artículo: {titulo}\n\n{texto[:5000]}", None))

historial = []
for nombre, tema, frases in temas:
    print(f"\n== {nombre}")
    plan = D.pedir_plan(tema, descripciones, objetos, historial, frases=frases)
    historial.append(D.para_historial(plan))
    for e in plan["escenas"]:
        print(f"  [{e['frase']}] {e['tipo']:10s} {e['camara']:9s} {e['transicion']:8s} fondo={e['fondo']}  {json.dumps(e['datos'], ensure_ascii=False)[:110]}")
    print("  fondo:", plan["fondo"], "· subtítulos:", plan["subtitulos"])
    palabras, dur = D.tiempos_a_ojo(plan["frases"])
    g = D.a_guion(plan, palabras, dur, rutas, fondos_extra=list(rutas.values())[:4])
    (SALIDA / f"{nombre}.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    (SALIDA / f"{nombre}_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nlisto")
