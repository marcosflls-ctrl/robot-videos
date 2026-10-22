"""Guiones diarios de Al Final de Mes y Dinero en Claro a partir de los datos de cada web.

Cada función devuelve un diccionario:
    frases  -> lo que dice la voz (y los subtítulos), con cifras normales
    tema    -> lo que se ve: titular, cifra grande, gráfico, fuente...
    texto   -> texto sugerido para la publicación (con hashtags)

Los datos salen de src/data de cada web (los bajan sus propios robots), así que no se
inventa ninguna cifra. Cada día de la semana toca un tema distinto (ver PLAN_*).
"""
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from video_datos import COLORES_AFDM, COLORES_DEC, OCRE, ROJO, VERDE

MADRID = ZoneInfo("Europe/Madrid")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
MES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# lunes=0 ... domingo=6
PLAN_AFDM = {0: "luz", 1: "carburantes", 2: "euribor", 3: "luz", 4: "carburantes", 5: "ipc", 6: "luz"}
PLAN_DEC = {0: "mercados", 1: "ahorro", 2: "aportaciones", 3: "mercados", 4: "cripto", 5: "aportaciones", 6: "ahorro"}


# ---------- escenas (para el montaje por escenas) ----------

def C(valor, formato, sub):
    """Escena con una cifra grande que cuenta hasta el valor."""
    return {"tipo": "cifra", "valor": valor, "formato": formato, "texto": formato(valor), "sub": sub}


def T(texto, resaltar=""):
    """Escena con un titular grande; la palabra resaltada va en una caja de color."""
    return {"tipo": "titular", "texto": texto, "resaltar": resaltar}


def G(grafico, titulo=""):
    """Escena con un gráfico que se dibuja poco a poco."""
    return {"tipo": "grafico", "grafico": grafico, "titulo": titulo}


N = {"tipo": "nada"}


# ---------- horas como se dicen («las 2 de la tarde» en vez de «las 14») ----------

def _franja(h):
    h %= 24
    if h == 0:
        return "de la noche"
    if h < 6:
        return "de la madrugada"
    if h < 12:
        return "de la mañana"
    if h == 12:
        return "del mediodía"
    if h < 21:
        return "de la tarde"
    return "de la noche"


def _h12(h):
    h %= 24
    return 12 if h % 12 == 0 else h % 12


def _art(h):
    """Artículo: «la 1», «las 2»..."""
    return "la" if _h12(h) == 1 else "las"


def hora(h):
    """14 -> 'las 2 de la tarde'; 1 -> 'la 1 de la madrugada'"""
    return f"{_art(h)} {_h12(h)} {_franja(h)}"


def tramo(h):
    """Franja de una hora: 14 -> 'de las 2 a las 3 de la tarde'; 11 -> 'de las 11 de la mañana a las 12 del mediodía'"""
    fin = (h + 1) % 24
    de = "de la" if _h12(h) == 1 else "de las"
    if _franja(h) == _franja(fin):
        return f"{de} {_h12(h)} a {_art(fin)} {_h12(fin)} {_franja(h)}"
    return f"{de} {_h12(h)} {_franja(h)} a {_art(fin)} {_h12(fin)} {_franja(fin)}"


def tramo_corto(h):
    """Para rótulos: 14 -> 'de 2 a 3 de la tarde'; 11 -> 'de 11 de la mañana a 12 del mediodía'"""
    fin = (h + 1) % 24
    if _franja(h) == _franja(fin):
        return f"de {_h12(h)} a {_h12(fin)} {_franja(h)}"
    return f"de {_h12(h)} {_franja(h)} a {_h12(fin)} {_franja(fin)}"


# ---------- formato español ----------

def num(x, dec=1):
    """1234.5 -> '1.234,5'"""
    s = f"{abs(x):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if dec and set(s.split(",")[-1]) == {"0"}:
        s = s.split(",")[0]
    return ("-" if x < 0 else "") + s


def fecha_larga(f):
    d = date.fromisoformat(f[:10]) if isinstance(f, str) else f
    return f"{d.day} de {MESES[d.month - 1]}"


def fecha_corta(f):
    d = date.fromisoformat(f[:10]) if isinstance(f, str) else f
    return f"{d.day} {MES_CORTO[d.month - 1]}"


def mes_nombre(ym):
    a, m = ym.split("-")
    return f"{MESES[int(m) - 1]} de {a}"


def sube_baja(v, femenino=False):
    if abs(v) < 0.005:
        return "se mantiene"
    return "sube" if v > 0 else ("baja" if femenino else "cae")


def _leer(carpeta, nombre):
    return json.loads((Path(carpeta) / f"{nombre}.json").read_text(encoding="utf-8"))


def hoy():
    return datetime.now(MADRID).date()


# =====================================================================
#  AL FINAL DE MES
# =====================================================================

def _afdm_tema(**k):
    base = {"marca": "Al Final de Mes", "web": "alfinaldemes.com", "colores": COLORES_AFDM}
    base.update(k)
    return base


def afdm_luz(datos):
    d = _leer(datos, "luz")
    dia = d.get("hoy") or max(d["dias"])
    if dia not in d["dias"]:
        dia = max(d["dias"])
    horas = d["dias"][dia]
    precios = [h["p"] * 100 for h in horas]  # céntimos/kWh
    i_min = min(range(len(precios)), key=precios.__getitem__)
    i_max = max(range(len(precios)), key=precios.__getitem__)
    media = sum(precios) / len(precios)
    h_min, h_max = int(horas[i_min]["h"][:2]), int(horas[i_max]["h"][:2])

    frases = [
        f"Precio de la luz hoy, {fecha_larga(dia)}.",
        f"La hora más barata es {tramo(h_min)}, a {num(precios[i_min])} céntimos el kWh.",
        f"La más cara, {tramo(h_max)}: {num(precios[i_max])} céntimos.",
    ]
    anteriores = sorted(x for x in d["dias"] if x < dia)
    if anteriores:
        ayer = [h["p"] * 100 for h in d["dias"][anteriores[-1]]]
        media_ayer = sum(ayer) / len(ayer)
        dif = media - media_ayer
        if abs(dif) >= 0.1:
            frases.append(f"La media del día es de {num(media)} céntimos, {num(abs(dif))} céntimos {'más' if dif > 0 else 'menos'} que ayer.")
        else:
            frases.append(f"La media del día es de {num(media)} céntimos, casi igual que ayer.")
    else:
        frases.append(f"La media del día es de {num(media)} céntimos.")
    if 9 <= h_min <= 17:
        frases.append("Si puedes, deja la lavadora y el lavavajillas para las horas centrales del día.")
    else:
        frases.append(f"Si puedes, pon la lavadora y el lavavajillas cerca de {hora(h_min)}.")
    frases.append("Todas las horas, en alfinaldemes.com.")

    escenas = []
    for f in frases:
        if f.startswith("Precio de la luz"):
            escenas.append({"visual": T("Precio de la luz hoy", "luz"), "buscar": ["power lines sunset", "electricity tower"]})
        elif f.startswith("La hora más barata"):
            escenas.append({"visual": C(precios[i_min], lambda v: f"{num(v)} cént.", f"la más barata, {tramo_corto(h_min)}"),
                            "buscar": ["light bulb", "light switch"]})
        elif f.startswith("La más cara"):
            escenas.append({"visual": C(precios[i_max], lambda v: f"{num(v)} cént.", f"la más cara, {tramo_corto(h_max)}"),
                            "buscar": "electricity meter"})
        elif f.startswith("La media"):
            escenas.append({"visual": G({"tipo": "barras", "valores": precios, "colores": {i_min: VERDE, i_max: ROJO},
                                          "titulo": "Céntimos por kWh, hora a hora",
                                          "etiquetas": {0: "0 h", 6: "6 h", 12: "12 h", 18: "18 h", 23: "23 h"}}, "Hora a hora"),
                            "buscar": "city lights night"})
        elif "lavadora" in f:
            escenas.append({"visual": T("Pon la lavadora en las horas baratas", "lavadora"), "buscar": ["washing machine", "dishwasher"]})
        else:
            escenas.append({"visual": N, "buscar": "kitchen home"})
    colores = {i_min: VERDE, i_max: ROJO}
    tema = _afdm_tema(
        etiqueta=f"Luz · {fecha_corta(dia)}",
        titular="La hora más barata de hoy",
        cifra=precios[i_min], formato=lambda v: f"{num(v)} cént.",
        unidad=f"por kWh, {tramo_corto(h_min)}",
        grafico={"tipo": "barras", "valores": precios, "colores": colores, "titulo": "Céntimos por kWh, hora a hora",
                 "etiquetas": {0: "0 h", 6: "6 h", 12: "12 h", 18: "18 h", 23: "23 h"}},
        nota="Fuente: Red Eléctrica. Tarifa regulada PVPC 2.0TD, sin impuestos.",
    )
    texto = (f"💡 Precio de la luz hoy, {fecha_larga(dia)}: la hora más barata es {tramo(h_min)} "
             f"({num(precios[i_min])} cént./kWh) y la más cara, {tramo(h_max)}.\n\n"
             "Todas las horas en alfinaldemes.com\n\n#PrecioLuz #Luz #PVPC #Ahorro #EconomíaDoméstica")
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


def afdm_carburantes(datos):
    d = _leer(datos, "carburantes")
    g, ds = d["nacional"]["g95"]["media"], d["nacional"]["diesel"]["media"]
    frases = [
        "Así está hoy el precio de la gasolina en España.",
        f"La sin plomo 95 cuesta de media {num(g, 3)} € el litro, y el diésel, {num(ds, 3)} €.",
    ]
    hist = d.get("historico", {})
    fechas = sorted(hist)
    if len(fechas) >= 3:
        base = fechas[max(0, len(fechas) - 8)]
        dg = (g - hist[base]["g95"]) * 100
        dd = (ds - hist[base]["diesel"]) * 100
        dias = (date.fromisoformat(d["fecha"]) - date.fromisoformat(base)).days
        periodo = "la última semana" if dias >= 6 else f"los últimos {dias} días"

        def cambio(nombre, v):
            if abs(v) < 0.05:
                return f"{nombre} se mantiene"
            return f"{nombre} {'ha subido' if v > 0 else 'ha bajado'} {num(abs(v))} céntimos"
        frases.append(f"En {periodo}, {cambio('la gasolina', dg)} y {cambio('el diésel', dd)}.")
    provs = sorted((p for p in d["provincias"] if p.get("g95")), key=lambda p: p["g95"]["media"])
    barata, cara = provs[0], provs[-1]
    frases.append(f"La provincia más barata es {barata['nombre']}, con {num(barata['g95']['media'], 3)} € de media, "
                  f"y la más cara, {cara['nombre']}, con {num(cara['g95']['media'], 3)} €.")
    frases.append("Las gasolineras más baratas de tu provincia, en alfinaldemes.com.")

    escenas = []
    for f in frases:
        if f.startswith("Así está hoy"):
            escenas.append({"visual": T("Precio de la gasolina hoy", "gasolina"), "buscar": ["gas station", "fuel pump"]})
        elif f.startswith("La sin plomo"):
            escenas.append({"visual": C(g, lambda v: f"{num(v, 3)} €", f"gasolina 95 · diésel {num(ds, 3)} €"), "buscar": "fuel pump nozzle"})
        elif f.startswith("En "):
            escenas.append({"visual": T("Así ha cambiado en la semana", "semana"), "buscar": ["car highway", "traffic road"]})
        elif f.startswith("La provincia"):
            escenas.append({"visual": "RANKING", "buscar": "spain road aerial"})
        else:
            escenas.append({"visual": N, "buscar": "car driving city"})
    filas = [(p["nombre"], p["g95"]["media"] - 1.2, f"{num(p['g95']['media'], 3)} €", VERDE) for p in provs[:5]]
    filas.append(("Media de España", g - 1.2, f"{num(g, 3)} €", OCRE))
    tema = _afdm_tema(
        etiqueta=f"Carburantes · {fecha_corta(d['fecha'])}",
        titular="Gasolina 95: precio medio en España",
        cifra=g, formato=lambda v: f"{num(v, 3)} €",
        unidad=f"el litro · diésel: {num(ds, 3)} €",
        grafico={"tipo": "ranking", "filas": filas, "titulo": "Provincias más baratas (gasolina 95)"},
        nota="Fuente: Ministerio para la Transición Ecológica (Geoportal de Hidrocarburos).",
    )
    texto = (f"⛽ Gasolina 95 a {num(g, 3)} €/l y diésel a {num(ds, 3)} €/l de media en España. "
             f"La provincia más barata: {barata['nombre']}.\n\nGasolineras más baratas en alfinaldemes.com\n\n"
             "#Gasolina #Diésel #PrecioCarburantes #Ahorro #EconomíaDoméstica")
    for e in escenas:
        if e["visual"] == "RANKING":
            e["visual"] = G(tema["grafico"], "Provincias más baratas")
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


def afdm_ipc(datos):
    d = _leer(datos, "ipc")
    mes = d["mes"]
    va = d["general"]["va"]
    meses = sorted(va)
    actual = va[mes]
    anterior = va[meses[meses.index(mes) - 1]]
    if abs(actual - anterior) < 0.05:
        verbo = f"se mantiene en el {num(actual)} %"
    elif actual > anterior:
        verbo = f"sube al {num(actual)} %"
    else:
        verbo = f"baja al {num(actual)} %"
    frases = [f"El IPC {verbo} en {MESES[int(mes[5:]) - 1]}."]

    # ¿Desde cuándo no estaba tan alto (o tan bajo)? Con el histórico del índice
    h = d.get("historico", {})
    serie = sorted(h)
    tasas = {}
    for k in serie:
        a, m = k.split("-")
        previo = f"{int(a) - 1}-{m}"
        if previo in h:
            tasas[k] = (h[k] / h[previo] - 1) * 100
    if tasas:
        antes = [k for k in sorted(tasas) if k < mes]
        if actual > anterior:
            igual = [k for k in antes if round(tasas[k], 1) >= actual]
            if igual and (int(mes[:4]) * 12 + int(mes[5:])) - (int(igual[-1][:4]) * 12 + int(igual[-1][5:])) >= 6:
                frases.append(f"Es la tasa más alta desde {mes_nombre(igual[-1])}.")

    sub = [(v["va"][mes], k) for k, v in d["subclases"].items() if v["va"].get(mes) is not None and k != "Índice general"]
    sub.sort(reverse=True)
    cortos = [(v, k) for v, k in sub if len(k) <= 32]
    top = cortos[:3]
    frases.append("Lo que más se ha encarecido en un año: " + ", ".join(f"{k.lower()}, un {num(v)} %" for v, k in top[:2])
                  + f", y {top[2][1].lower()}, un {num(top[2][0])} %.")
    bajada = cortos[-1]
    if bajada[0] < 0:
        frases.append(f"En cambio, {bajada[1].lower()} ha bajado un {num(abs(bajada[0]))} %.")
    irav = d.get("irav", {})
    if irav:
        ult = max(irav)
        frases.append(f"Y el índice para actualizar el alquiler, el IRAV, está en el {num(irav[ult], 2)} %.")
    frases.append("Todos los datos, en alfinaldemes.com.")

    ultimos_g = meses[-25:]
    escenas = []
    for f in frases:
        if f.startswith("El IPC"):
            escenas.append({"visual": C(actual, lambda v: f"{num(v)} %", f"IPC de {MESES[int(mes[5:]) - 1]}"),
                            "buscar": ["supermarket shopping", "shopping cart"]})
        elif f.startswith("Es la tasa"):
            escenas.append({"visual": G({"tipo": "linea", "series": [[va[m] for m in ultimos_g]], "titulo": "Tasa anual del IPC, en %",
                                          "etiquetas": {0: fecha_mes(ultimos_g[0]), len(ultimos_g) - 1: fecha_mes(ultimos_g[-1])}},
                                         "Inflación, mes a mes"), "buscar": "price tag"})
        elif f.startswith("Lo que más"):
            escenas.append({"visual": G({"tipo": "ranking", "filas": [(k, v, f"+{num(v)} %", ROJO) for v, k in top],
                                          "titulo": "Subida en un año"}, "Lo que más sube"),
                            "buscar": ["fruit market", "grocery store"]})
        elif f.startswith("En cambio"):
            escenas.append({"visual": C(abs(bajada[0]), lambda v: f"-{num(v)} %", bajada[1]), "buscar": "train station"})
        elif "IRAV" in f:
            escenas.append({"visual": C(irav[max(irav)], lambda v: f"{num(v, 2)} %", "IRAV, para actualizar el alquiler"),
                            "buscar": ["apartment building", "house keys"]})
        else:
            escenas.append({"visual": N, "buscar": "shopping street"})
    ultimos = meses[-25:]
    tema = _afdm_tema(
        etiqueta=f"IPC · {mes_nombre(mes)}",
        titular="Inflación: tasa anual del IPC",
        cifra=actual, formato=lambda v: f"{num(v)} %",
        unidad=f"en {MESES[int(mes[5:]) - 1]} · el mes anterior, {num(anterior)} %",
        grafico={"tipo": "linea", "series": [[va[m] for m in ultimos]], "titulo": "Tasa anual del IPC, en %",
                 "etiquetas": {0: fecha_mes(ultimos[0]), len(ultimos) - 1: fecha_mes(ultimos[-1])}},
        nota="Fuente: INE, Índice de Precios de Consumo.",
    )
    texto = (f"📈 El IPC {verbo} en {MESES[int(mes[5:]) - 1]}. Lo que más sube: {top[0][1].lower()} (+{num(top[0][0])} %).\n\n"
             "Todos los datos en alfinaldemes.com\n\n#IPC #Inflación #Precios #EconomíaDoméstica")
    if not any(f.startswith("Es la tasa") for f in frases):  # que el gráfico salga igualmente
        for e in escenas:
            if e["visual"].get("tipo") == "nada":
                e["visual"] = G(tema["grafico"], "Inflación, mes a mes")
                break
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


def fecha_mes(ym):
    a, m = ym.split("-")
    return f"{MES_CORTO[int(m) - 1]} {a[2:]}"


def _cuota(capital, tipo_anual, anios):
    r = tipo_anual / 100 / 12
    n = anios * 12
    return capital * r / (1 - (1 + r) ** -n) if r else capital / n


def afdm_euribor(datos):
    d = _leer(datos, "euribor")
    v, mm = d["valor"], d["media_mes"]
    ya = d["hace_un_anio"]["media"]
    mes = MESES[int(d["mes"][5:]) - 1]
    c_ahora, c_antes = _cuota(150000, mm + 0.75, 25), _cuota(150000, ya + 0.75, 25)
    dif = c_ahora - c_antes
    frases = [
        f"El euríbor cerró el {fecha_larga(d['fecha'])} en el {num(v, 3)} %.",
        f"La media de {mes} va por el {num(mm, 3)} %, frente al {num(ya, 3)} % de hace un año.",
        f"Para una hipoteca de 150.000 € a 25 años con euríbor más 0,75, la cuota pasaría de {num(c_antes, 0)} a {num(c_ahora, 0)} € al mes.",
        f"Son {num(abs(dif), 0)} € {'más' if dif > 0 else 'menos'} cada mes en la revisión.",
        "Toda la evolución del euríbor, en alfinaldemes.com.",
    ]
    escenas = [
        {"visual": C(v, lambda x: f"{num(x, 3)} %", "euríbor a 12 meses"), "buscar": ["house keys", "real estate"]},
        {"visual": "LINEA", "buscar": "apartment building"},
        {"visual": C(c_ahora, lambda x: f"{num(x, 0)} €", "cuota al mes (ejemplo)"), "buscar": ["family home", "calculator money"]},
        {"visual": C(abs(dif), lambda x: f"{'+' if dif > 0 else '-'}{num(x, 0)} €", "al mes en la revisión"), "buscar": "bank"},
        {"visual": N, "buscar": "city apartments"},
    ]
    meses = sorted(d["medias_mensuales"])[-25:]
    tema = _afdm_tema(
        etiqueta=f"Euríbor · {fecha_corta(d['fecha'])}",
        titular="Euríbor a 12 meses",
        cifra=v, formato=lambda x: f"{num(x, 3)} %",
        unidad=f"media de {mes}: {num(mm, 3)} % · hace un año: {num(ya, 3)} %",
        grafico={"tipo": "linea", "series": [[d["medias_mensuales"][m] for m in meses]], "titulo": "Media mensual, en %",
                 "etiquetas": {0: fecha_mes(meses[0]), len(meses) - 1: fecha_mes(meses[-1])}},
        nota="Fuente: Banco de España. Ejemplo de cuota orientativo, con el capital inicial.",
    )
    texto = (f"🏠 Euríbor al {num(v, 3)} %. La media de {mes} va por el {num(mm, 3)} %, frente al {num(ya, 3)} % de hace un año.\n\n"
             "Más en alfinaldemes.com\n\n#Euríbor #Hipoteca #Vivienda #EconomíaDoméstica")
    escenas[1]["visual"] = G(tema["grafico"], "Euríbor, media mensual")
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


# =====================================================================
#  DINERO EN CLARO
# =====================================================================

AVISO_DEC = "Información, no recomendación de inversión. Rentabilidades pasadas no garantizan las futuras."


def _dec_tema(**k):
    base = {"marca": "Dinero en Claro", "web": "dineroenclaro.com", "colores": COLORES_DEC, "aviso": AVISO_DEC}
    base.update(k)
    return base


def dec_mercados(datos):
    a = _leer(datos, "indices")["activos"]
    ibex, sp, nq, oro = a["ibex"], a["sp500"], a["nasdaq100"], a["oro"]
    fecha = ibex["fecha"]

    def mov(x, femenino=False):
        v = x["var_dia"]
        return f"{sube_baja(v, femenino)} un {num(abs(v), 2)} %" if abs(v) >= 0.005 else "se mantiene"

    frases = [
        f"Así cerró la bolsa el {fecha_larga(fecha)}.",
        f"El Ibex 35 {mov(ibex)} y termina en {num(ibex['cierre'], 0)} puntos.",
        f"En Nueva York, el S&P 500 {mov(sp)} y el Nasdaq 100 {mov(nq)}.",
        f"El oro {mov(oro)}.",
    ]
    try:
        btc = next(m for m in _leer(datos, "cripto")["monedas"] if m["id"] == "bitcoin")
        frases.append(f"Y el bitcoin {sube_baja(btc['var_24h'])} un {num(abs(btc['var_24h']), 1)} % en 24 horas.")
    except Exception:
        btc = None
    frases.append(f"En lo que va de año, el Ibex acumula un {num(ibex['var_anio'], 1)} %"
                  f" y el S&P 500, un {num(sp['var_anio'], 1)} % en dólares.")
    frases.append("Toda la información, en dineroenclaro.com.")

    filas = []
    for clave, nombre in [("ibex", "Ibex 35"), ("eurostoxx50", "Euro Stoxx 50"), ("dax", "DAX 40"),
                          ("sp500", "S&P 500"), ("nasdaq100", "Nasdaq 100"), ("oro", "Oro"), ("brent", "Brent")]:
        if clave in a:
            v = a[clave]["var_dia"]
            filas.append((nombre, v, f"{'+' if v >= 0 else ''}{num(v, 2)} %", VERDE if v >= 0 else ROJO))
    if btc:
        v = btc["var_24h"]
        filas.append(("Bitcoin (24 h)", v, f"{'+' if v >= 0 else ''}{num(v, 2)} %", VERDE if v >= 0 else ROJO))
    escenas = []
    for f in frases:
        if f.startswith("Así cerró"):
            escenas.append({"visual": T("Así cerró la bolsa", "bolsa"), "buscar": ["stock market screen", "trading charts"]})
        elif f.startswith("El Ibex"):
            escenas.append({"visual": C(ibex["var_dia"], lambda x: f"{'+' if x >= 0 else ''}{num(x, 2)} %", "Ibex 35"), "buscar": "madrid skyline"})
        elif f.startswith("En Nueva York"):
            escenas.append({"visual": C(sp["var_dia"], lambda x: f"{'+' if x >= 0 else ''}{num(x, 2)} %", "S&P 500"), "buscar": ["wall street new york", "new york skyline"]})
        elif f.startswith("El oro"):
            escenas.append({"visual": C(oro["var_dia"], lambda x: f"{'+' if x >= 0 else ''}{num(x, 2)} %", "oro"), "buscar": "gold bars"})
        elif "bitcoin" in f:
            escenas.append({"visual": "RANKING", "buscar": ["bitcoin", "cryptocurrency"]})
        elif f.startswith("En lo que va"):
            escenas.append({"visual": C(ibex["var_anio"], lambda x: f"{'+' if x >= 0 else ''}{num(x, 1)} %", "Ibex 35 en el año"), "buscar": "financial district"})
        else:
            escenas.append({"visual": N, "buscar": "stock market"})
    tema = _dec_tema(
        etiqueta=f"Mercados · {fecha_corta(fecha)}",
        titular="Así cerró la bolsa",
        cifra=ibex["var_dia"], formato=lambda x: f"{'+' if x >= 0 else ''}{num(x, 2)} %",
        unidad=f"Ibex 35 · {num(ibex['cierre'], 0)} puntos",
        grafico={"tipo": "ranking", "filas": filas, "titulo": "Variación del día"},
        nota="Fuentes: Yahoo Finance y CoinGecko.",
    )
    texto = (f"📊 Cierre del {fecha_larga(fecha)}: Ibex 35 {'+' if ibex['var_dia'] >= 0 else ''}{num(ibex['var_dia'], 2)} %, "
             f"S&P 500 {'+' if sp['var_dia'] >= 0 else ''}{num(sp['var_dia'], 2)} %.\n\nMás en dineroenclaro.com\n\n"
             "#Bolsa #Ibex35 #SP500 #Inversión #Mercados")
    if not any(e["visual"] == "RANKING" for e in escenas):
        escenas[-1]["visual"] = "RANKING"
    for e in escenas:
        if e["visual"] == "RANKING":
            e["visual"] = G(tema["grafico"], "Variación del día")
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


INDICES_APORTACIONES = [
    ("sp500", "el S&P 500", "S&P 500", "en euros, con el precio del índice, sin dividendos ni comisiones del bróker"),
    ("msciworld", "el MSCI World", "MSCI World", "con un fondo cotizado del índice mundial MSCI World, que reinvierte dividendos, sin comisiones del bróker"),
    ("ibex", "el Ibex 35", "Ibex 35", "con el precio del índice, sin dividendos ni comisiones del bróker"),
]


def dec_aportaciones(datos, indice=None):
    a = _leer(datos, "indices")["activos"]
    if indice is None:
        indice = INDICES_APORTACIONES[hoy().isocalendar().week % len(INDICES_APORTACIONES)][0]
    clave, nombre, corto, como = next(x for x in INDICES_APORTACIONES if x[0] == indice)
    act = a[clave]
    serie = (act.get("eur") or {}).get("mensual") or act["mensual"]
    serie = serie[-121:]
    anios = round((len(serie) - 1) / 12)
    participaciones, puesto, valores, aportado = 0.0, 0, [], []
    for _, precio in serie[:-1]:
        participaciones += 100 / precio
        puesto += 100
        valores.append(participaciones * precio)
        aportado.append(puesto)
    final = participaciones * serie[-1][1]
    valores.append(final)
    aportado.append(puesto)
    ganancia = final - puesto
    redondeo = round(final, -2)

    frases = [
        f"Si hubieras invertido 100 € al mes en {nombre} durante los últimos {anios} años…",
        f"habrías puesto {num(puesto, 0)} € de tu bolsillo.",
        f"Hoy tendrías unos {num(redondeo, 0)} €.",
        (f"Es decir, unos {num(round(ganancia, -2), 0)} € más de lo que pusiste." if ganancia > 0
         else f"Es decir, unos {num(round(abs(ganancia), -2), 0)} € menos de lo que pusiste."),
        f"Calculado {como}.",
        "Lo que pasó antes no garantiza lo que pasará. Aprende a empezar en dineroenclaro.com.",
    ]
    escenas = [
        {"visual": T(f"100 € al mes en {corto}", "100 €"), "buscar": ["coins saving", "piggy bank"]},
        {"visual": C(puesto, lambda x: f"{num(round(x, -2), 0)} €", "lo que pusiste"), "buscar": "calendar"},
        {"visual": C(redondeo, lambda x: f"{num(round(x, -2), 0)} €", "lo que tendrías hoy"), "buscar": ["money growth", "plant growing"]},
        {"visual": "LINEA", "buscar": "stock chart"},
        {"visual": T("Sin dividendos ni comisiones" if "sin dividendos" in como else "Con dividendos, sin comisiones", "comisiones"), "buscar": "laptop finance"},
        {"visual": N, "buscar": "notebook planning"},
    ]
    tema = _dec_tema(
        etiqueta=f"Invertir poco a poco · {corto}",
        titular=f"100 € al mes durante {anios} años en {nombre}",
        cifra=redondeo, formato=lambda x: f"{num(round(x, -2), 0)} €",
        unidad=f"tras aportar {num(puesto, 0)} €",
        grafico={"tipo": "linea", "series": [valores, aportado], "nombres": ["Lo que tendrías", "Lo que pusiste"],
                 "etiquetas": {0: serie[0][0][:4], len(serie) - 1: serie[-1][0][:4]}},
        nota=f"Datos mensuales hasta el {fecha_larga(serie[-1][0])}. Cálculo {como}.",
    )
    texto = (f"💶 100 € al mes durante {anios} años en {nombre}: habrías puesto {num(puesto, 0)} € y hoy tendrías unos "
             f"{num(redondeo, 0)} €.\n\nCálculo {como}. No es una recomendación de inversión.\n\n"
             "Aprende a empezar en dineroenclaro.com\n\n#Inversión #FondosIndexados #Ahorro #InteresCompuesto")
    escenas[3]["visual"] = G(tema["grafico"], "Mes a mes")
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


def dec_ahorro(datos, tipo=None):
    d = _leer(datos, "ahorro-bancos")
    if tipo is None:
        tipo = "cuentas" if hoy().isocalendar().week % 2 else "depositos"
    vigentes = [x for x in d[tipo] if x.get("tae") and (not x.get("hasta") or x["hasta"] >= hoy().isoformat())]
    if tipo == "depositos":
        vigentes = [x for x in vigentes if x.get("plazo") == 12] or vigentes
    vigentes.sort(key=lambda x: x["tae"], reverse=True)
    top = vigentes[:5]
    que = "cuentas remuneradas" if tipo == "cuentas" else "depósitos a 12 meses"
    frases = [f"Estas son las {que} que más pagan ahora mismo."]
    for i, x in enumerate(top[:3]):
        pre = ["En primer lugar", "Después", "Y en tercer lugar"][i]
        frases.append(f"{pre}, {x['entidad']}, con un {num(x['tae'], 2)} % TAE.")
    frases.append("Ojo: muchas ofertas son solo para nuevos clientes, tienen un máximo o duran unos meses.")
    frases.append("Todas las condiciones, en dineroenclaro.com.")
    escenas = [{"visual": T(f"Las {que} que más pagan", "más pagan"), "buscar": ["saving money", "coins"]}]
    for i, x in enumerate(top[:3]):
        escenas.append({"visual": C(x["tae"], lambda v: f"{num(v, 2)} %", f"{x['entidad']} · TAE"),
                        "buscar": ["bank", "smartphone banking", "credit card"][i]})
    escenas.append({"visual": "RANKING", "buscar": "reading contract"})
    escenas.append({"visual": N, "buscar": "wallet money"})
    filas = [(x["entidad"], x["tae"], f"{num(x['tae'], 2)} %", VERDE) for x in top]
    tema = _dec_tema(
        etiqueta=f"Ahorro · {fecha_corta(d['actualizado'])}",
        titular=f"Las {que} que más pagan",
        cifra=top[0]["tae"], formato=lambda x: f"{num(x, 2)} %",
        unidad=f"TAE · {top[0]['entidad']}",
        grafico={"tipo": "ranking", "filas": filas, "titulo": "TAE, en %"},
        nota=f"Datos comprobados el {fecha_larga(d['actualizado'])} en las webs de cada banco. Con condiciones.",
        aviso="Información, no recomendación. Revisa las condiciones de cada banco.",
    )
    texto = (f"🏦 Las {que} que más pagan ahora: " + ", ".join(f"{x['entidad']} ({num(x['tae'], 2)} % TAE)" for x in top[:3])
             + ".\n\nCondiciones y letra pequeña en dineroenclaro.com\n\n#Ahorro #Depósitos #CuentaRemunerada #FinanzasPersonales")
    escenas = escenas[:len(frases)]
    for e in escenas:
        if e["visual"] == "RANKING":
            e["visual"] = G(tema["grafico"], "Las que más pagan")
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


def dec_cripto(datos):
    d = _leer(datos, "cripto")
    btc = next(m for m in d["monedas"] if m["id"] == "bitcoin")
    eth = next((m for m in d["monedas"] if m["id"] == "ethereum"), None)
    frases = [
        f"El bitcoin cotiza a {num(btc['precio'], 0)} dólares.",
        f"En las últimas 24 horas {sube_baja(btc['var_24h'])} un {num(abs(btc['var_24h']), 1)} %, "
        f"y en la última semana, {'gana' if btc['var_7d'] >= 0 else 'pierde'} un {num(abs(btc['var_7d']), 1)} %.",
        f"Todavía está un {num(abs(btc['desde_maximo']), 0)} % por debajo de su máximo de {num(btc['maximo'], 0)} dólares, "
        f"del {fecha_larga(btc['fecha_maximo'])} de {btc['fecha_maximo'][:4]}.",
    ]
    if eth:
        frases.append(f"Ethereum está en {num(eth['precio'], 0)} dólares, un {num(abs(eth['var_24h']), 1)} % "
                      f"{'más' if eth['var_24h'] >= 0 else 'menos'} que ayer.")
    frases.append("Recuerda: las criptomonedas son muy volátiles. Más en dineroenclaro.com.")
    escenas = [
        {"visual": C(btc["precio"], lambda x: f"{num(x, 0)} $", "bitcoin"), "buscar": ["bitcoin", "cryptocurrency"]},
        {"visual": C(btc["var_24h"], lambda x: f"{'+' if x >= 0 else ''}{num(x, 1)} %", "en 24 horas"), "buscar": "trading screen"},
        {"visual": "LINEA", "buscar": "blockchain"},
    ]
    if eth:
        escenas.append({"visual": C(eth["precio"], lambda x: f"{num(x, 0)} $", "ethereum"), "buscar": "ethereum"})
    escenas.append({"visual": T("Mucha volatilidad", "volatilidad"), "buscar": "roller coaster"})
    serie = d["series"]["bitcoin"]
    fechas = sorted(serie)[-365:]
    tema = _dec_tema(
        etiqueta=f"Cripto · {fecha_corta(btc['actualizado'][:10])}",
        titular="Bitcoin, precio en dólares",
        cifra=btc["precio"], formato=lambda x: f"{num(x, 0)} $",
        unidad=f"{'+' if btc['var_24h'] >= 0 else ''}{num(btc['var_24h'], 1)} % en 24 h · {num(btc['desde_maximo'], 0)} % desde máximos",
        grafico={"tipo": "linea", "series": [[serie[f] for f in fechas]], "titulo": "Último año, en dólares",
                 "etiquetas": {0: fecha_corta(fechas[0]), len(fechas) - 1: fecha_corta(fechas[-1])}},
        nota="Fuente: CoinGecko.",
    )
    texto = (f"₿ Bitcoin a {num(btc['precio'], 0)} $ ({'+' if btc['var_24h'] >= 0 else ''}{num(btc['var_24h'], 1)} % en 24 h), "
             f"un {num(abs(btc['desde_maximo']), 0)} % por debajo de su máximo.\n\nNo es una recomendación de inversión. "
             "Más en dineroenclaro.com\n\n#Bitcoin #Cripto #Criptomonedas #Inversión")
    escenas[2]["visual"] = G(tema["grafico"], "Bitcoin, último año")
    return {"frases": frases, "tema": tema, "texto": texto, "escenas": escenas}


TEMAS = {
    "afdm": {"luz": afdm_luz, "carburantes": afdm_carburantes, "ipc": afdm_ipc, "euribor": afdm_euribor},
    "dec": {"mercados": dec_mercados, "aportaciones": dec_aportaciones, "ahorro": dec_ahorro, "cripto": dec_cripto},
}
PLANES = {"afdm": PLAN_AFDM, "dec": PLAN_DEC}


def tema_de_hoy(web):
    return PLANES[web][hoy().weekday()]


if __name__ == "__main__":
    import sys

    from numeros import a_voz

    web, carpeta = sys.argv[1], sys.argv[2]
    temas = sys.argv[3:] or list(TEMAS[web])
    for t in temas:
        r = TEMAS[web][t](carpeta)
        print(f"\n===== {web} · {t}")
        for f in r["frases"]:
            print(" ·", f, "\n     →", a_voz(f))
        print("  [texto]", r["texto"].replace("\n", " | "))
