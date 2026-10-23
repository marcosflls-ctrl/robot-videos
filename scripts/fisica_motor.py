"""Tema de física: cómo funciona un motor eléctrico de corriente continua.

Escena 3D (escena3d.py): dos imanes (N y S), una espira de cobre que gira sobre un eje,
el conmutador con sus escobillas y una pila. La corriente, el campo y las fuerzas se ven
como puntos y flechas que se mueven. La física es la de verdad:
    - El campo B va del polo N (izquierda) al S (derecha): eje x.
    - La espira gira alrededor del eje z. Sus lados largos van paralelos a z.
    - Fuerza sobre cada lado: F = I·L × B -> un lado hacia arriba y el otro hacia abajo.
    - El conmutador invierte la corriente cada media vuelta, así el giro sigue en el mismo sentido.

Para hacer otro tema, copia este archivo y cambia FRASES, ESCENAS y dibujar().
"""
import math

from escena3d import Camara

NOMBRE = "motor"
TITULO = "¿Cómo gira un motor eléctrico?"
HASHTAGS = "#fisica #ciencia #motorelectrico #electromagnetismo #aprendeentiktok #shorts"

# Lo que dice la voz (una escena por frase). Se lee tal cual; los números irían en cifras.
FRASES = [
    "¿Cómo consigue un motor convertir la electricidad en movimiento?",
    "Si lo abrimos, dentro hay dos imanes enfrentados: un polo norte y un polo sur, con un campo magnético entre ellos.",
    "En medio hay una espira de cobre, y cuando le llega la corriente de la pila...",
    "...el campo empuja un lado hacia arriba y el otro hacia abajo.",
    "Esas dos fuerzas forman un par, y la espira empieza a girar.",
    "Pero al dar media vuelta, el conmutador invierte la corriente, así que el empuje sigue siempre en el mismo sentido.",
    "Por eso no se para: así funcionan desde un ventilador hasta un coche eléctrico.",
]

# Cámara al principio (a) y al final (b) de cada escena. Entre escenas, la cámara viaja sola.
C = Camara
ESCENAS = [
    {"kicker": "¿CÓMO GIRA UN MOTOR?", "a": C((0, 0, 1.2), 7.5, 0.9, 0.25), "b": C((0, -0.2, 0.6), 15.5, 0.55, 0.32)},
    {"kicker": "1 · LOS IMANES", "a": C((0, 0, 0), 14.0, 0.55, 0.30), "b": C((0, 0, 0), 13.0, 0.18, 0.22)},
    {"kicker": "2 · LA CORRIENTE", "a": C((0.3, 0, 1.0), 12.0, 0.35, 0.35), "b": C((0.4, 0, 1.2), 10.5, 0.55, 0.40)},
    {"kicker": "3 · LA FUERZA", "a": C((0, 0.2, 0), 10.0, 0.35, 0.22), "b": C((0, 0.2, 0), 9.0, 0.25, 0.18)},
    {"kicker": "4 · EL GIRO", "a": C((0, 0, 0.8), 11.5, 0.15, 0.22), "b": C((0, 0, 0.8), 12.5, 0.32, 0.28)},
    {"kicker": "5 · EL TRUCO: EL CONMUTADOR", "a": C((0, 0, 2.1), 5.2, 0.75, 0.22), "b": C((0, 0, 2.1), 4.4, 0.95, 0.18)},
    {"kicker": "MOTOR ELÉCTRICO", "a": C((0, -0.2, 0.6), 13.0, 0.50, 0.30), "b": C((0, -0.2, 0.6), 15.0, 1.10, 0.36)},
]
CAMARA_CIERRE = C((0, -0.2, 0.6), 16.0, 1.4, 0.38)

# ---------- colores ----------
ROJO = (226, 64, 64)
AZUL = (52, 110, 226)
COBRE = (232, 140, 64)
GRIS = (150, 162, 178)
ORO = (226, 186, 90)
CIAN = (90, 220, 255)
AMARILLO = (255, 214, 60)
NARANJA = (255, 150, 40)
BLANCO = (240, 244, 255)

R_ESPIRA = 1.35       # radio de giro de la espira
Z_ESP0, Z_ESP1 = -1.3, 1.35
Z_CON0, Z_CON1 = 1.75, 2.45
R_CON = 0.42
Z_ESCOBILLA = 2.1
THETA_REPOSO = 0.28   # posición de la espira en las escenas en las que está quieta


def velocidades():
    """Velocidad de giro (rad/s, negativo = sentido de las agujas visto de frente) por escena.
    None = quieta en THETA_REPOSO."""
    return [-9.0, None, None, None, "arranque", -1.7, -11.0]


def preparar(tiempos_escena, n_frames, fps):
    """Calcula el ángulo de la espira en cada cuadro."""
    v = velocidades()
    theta = [THETA_REPOSO] * n_frames
    t1 = tiempos_escena[1][0]
    w = 0.0
    th = THETA_REPOSO
    for n in range(n_frames):
        t = n / fps
        i = _escena_de(tiempos_escena, t)
        vi = v[i] if i < len(v) else -11.0
        if i == 0:
            th = THETA_REPOSO + vi * (t - t1)  # gira rápido y llega justo a la posición de reposo
            w = 0.0
        elif vi is None:
            th, w = THETA_REPOSO, 0.0
        else:
            objetivo = -6.5 if vi == "arranque" else vi
            acel = 2.2 if vi == "arranque" else 4.0
            w += (objetivo - w) * min(1.0, acel / fps)
            th += w / fps
        theta[n] = th
    return {"theta": theta}


def _escena_de(tiempos, t):
    for i, (a, b) in enumerate(tiempos):
        if t < b:
            return i
    return len(tiempos)


def _aparece(t, ini=0.0, dur=0.4):
    return max(0.0, min(1.0, (t - ini) / dur))


def _circuito(theta):
    """Camino de la corriente (de + a -) y si pasa corriente ahora (no pasa en el hueco del conmutador)."""
    c, s = math.cos(theta), math.sin(theta)
    A = lambda z: (R_ESPIRA * c, R_ESPIRA * s, z)    # lado A de la espira
    B = lambda z: (-R_ESPIRA * c, -R_ESPIRA * s, z)  # lado B (opuesto)
    # Mitad «a» del conmutador centrada en theta+90º (unida al lado A); mitad «b» en theta-90º
    ma = (R_CON * math.cos(theta + math.pi / 2), R_CON * math.sin(theta + math.pi / 2), Z_CON0)
    mb = (R_CON * math.cos(theta - math.pi / 2), R_CON * math.sin(theta - math.pi / 2), Z_CON0)
    arriba = [(-1.9, -0.75, 3.1), (-1.9, 1.6, 3.1), (0, 1.6, Z_ESCOBILLA), (0, R_CON + 0.55, Z_ESCOBILLA),
              (0, R_CON, Z_ESCOBILLA)]
    abajo = [(0, -R_CON, Z_ESCOBILLA), (0, -R_CON - 0.55, Z_ESCOBILLA), (0, -1.7, Z_ESCOBILLA), (-1.45, -1.7, 3.1)]
    if c >= 0:  # la escobilla de arriba (+) toca la mitad a -> entra por el lado A (a la derecha)
        espira = [ma, A(Z_ESP1), A(Z_ESP0), B(Z_ESP0), B(Z_ESP1), mb]
    else:
        espira = [mb, B(Z_ESP1), B(Z_ESP0), A(Z_ESP0), A(Z_ESP1), ma]
    pasa = abs(c) > 0.12
    return arriba + espira + abajo, pasa


def _puntos_en(camino, separacion, desfase):
    """Puntos repartidos a lo largo de una polilínea, desplazados según el tiempo."""
    largos = [math.dist(a, b) for a, b in zip(camino[:-1], camino[1:])]
    total = sum(largos)
    s = desfase % separacion
    out = []
    while s < total:
        acc = 0.0
        for (a, b), L in zip(zip(camino[:-1], camino[1:]), largos):
            if acc + L >= s:
                q = (s - acc) / (L or 1)
                out.append(tuple(x + (y - x) * q for x, y in zip(a, b)))
                break
            acc += L
        s += separacion
    return out


def dibujar(esc, estado, n, t, i, tl, dur):
    """Rellena la escena 3D del cuadro n. Devuelve las etiquetas [(punto3d, texto, (dx, dy), alfa, color)]."""
    theta = estado["theta"][n]
    etiquetas = []
    cierre = i >= len(FRASES)

    # Visibilidad de cada parte según la escena
    alfa_espira = 1.0
    if i == 1:
        alfa_espira = max(0.12, 1 - _aparece(tl, 0, 0.35))
    elif i == 2:
        alfa_espira = max(0.12, _aparece(tl, 0, 0.5))
    corriente = i in (0, 2, 3, 4, 5, 6) or cierre
    if i == 2:
        corriente = tl > 0.9
    campo = True

    # --- Base
    esc.caja((-3.7, -2.25, -2.2), (3.7, -1.95, 3.8), (38, 52, 78), borde=(120, 160, 220))

    # --- Imanes
    esc.caja((-3.35, -1.95, -1.7), (-2.05, 1.6, 1.7), ROJO)
    esc.caja((2.05, -1.95, -1.7), (3.35, 1.6, 1.7), AZUL)
    for x, letra in ((-2.7, "N"), (2.7, "S")):
        etiquetas.append(((x, 0.1, 1.72), letra, (0, 0), 1.0, "letra"))

    # --- Campo magnético: puntos que viajan de N a S
    if campo:
        a_campo = 0.55 if i == 0 else (_aparece(tl, 0.3, 0.6) if i == 1 else 0.85)
        for y in (-0.9, 0.0, 0.9):
            for z in (-1.0, 0.0, 1.0):
                esc.linea([(-2.0, y, z), (2.0, y, z)], CIAN, grosor=0.018, alfa=0.35 * a_campo, brillo=False)
                for p in _puntos_en([(-2.0, y, z), (2.0, y, z)], 0.8, t * 1.6 + 0.37 * (y + 2 * z)):
                    esc.punto(p, CIAN, radio=0.04, alfa=a_campo)
        if i == 1:
            esc.flecha((-1.0, 1.35, 0), (1.0, 1.35, 0), CIAN, grosor=0.09, alfa=_aparece(tl, 0.8))

    # --- Eje
    esc.linea([(0, 0, -2.0), (0, 0, Z_CON1 + 0.5)], GRIS, grosor=0.12, alfa=max(alfa_espira, 0.4), brillo=False)
    esc.caja((-0.35, -1.95, -2.15), (0.35, -0.0, -1.85), (90, 100, 120), alfa=1.0)  # soporte trasero

    # --- Espira
    c, s = math.cos(theta), math.sin(theta)
    A0, A1 = (R_ESPIRA * c, R_ESPIRA * s, Z_ESP0), (R_ESPIRA * c, R_ESPIRA * s, Z_ESP1)
    B0, B1 = (-R_ESPIRA * c, -R_ESPIRA * s, Z_ESP0), (-R_ESPIRA * c, -R_ESPIRA * s, Z_ESP1)
    ma = (R_CON * math.cos(theta + math.pi / 2), R_CON * math.sin(theta + math.pi / 2), Z_CON0)
    mb = (R_CON * math.cos(theta - math.pi / 2), R_CON * math.sin(theta - math.pi / 2), Z_CON0)
    esc.linea([ma, A1, A0, B0, B1, mb], COBRE, grosor=0.19, alfa=alfa_espira, brillo=False)

    # --- Conmutador (dos medias cañas) y escobillas
    gap = 0.18
    esc.cilindro((0, 0), R_CON, Z_CON0, Z_CON1, ORO, theta + gap, theta + math.pi - gap, lados=8, alfa=alfa_espira)
    esc.cilindro((0, 0), R_CON, Z_CON0, Z_CON1, (205, 160, 70), theta + math.pi + gap, theta + 2 * math.pi - gap,
                 lados=8, alfa=alfa_espira)
    for sgn in (1, -1):
        y0 = sgn * R_CON
        y1 = sgn * (R_CON + 0.5)
        esc.caja((-0.13, min(y0, y1), Z_ESCOBILLA - 0.16), (0.13, max(y0, y1), Z_ESCOBILLA + 0.16), (70, 70, 80),
                 alfa=alfa_espira)

    # --- Pila
    esc.caja((-2.35, -1.95, 2.75), (-1.45, -0.85, 3.45), (40, 40, 46))
    esc.caja((-2.35, -0.85, 2.75), (-1.45, -0.75, 3.45), ORO)
    etiquetas.append(((-1.9, -1.35, 3.47), "+  −", (0, 0), alfa_espira, "pila"))

    # --- Cables (fijos)
    camino, pasa = _circuito(theta)
    esc.linea(camino[:5], (200, 60, 60), grosor=0.06, alfa=max(alfa_espira, 0.3), brillo=False)
    esc.linea(camino[-4:], (60, 60, 70), grosor=0.06, alfa=max(alfa_espira, 0.3), brillo=False)

    # --- Corriente: puntos naranjas que recorren el circuito
    if corriente and pasa:
        vel = 3.2 if i != 5 else 2.0
        for p in _puntos_en(camino, 0.42, t * vel):
            esc.punto(p, NARANJA, radio=0.05, alfa=alfa_espira)
    elif corriente and not pasa and (i == 5 or i == 4):
        # Chispa en el hueco del conmutador
        for k in range(6):
            a = t * 37 + k
            esc.punto((0.12 * math.cos(a * 3.1), R_CON + 0.05 * math.sin(a * 2.3), Z_ESCOBILLA + 0.1 * math.cos(a)),
                      (255, 255, 200), radio=0.04, brillo=True)

    # --- Fuerzas: en el lado que está junto al polo N empuja hacia arriba; el otro, hacia abajo
    if (i == 3 or i == 4) and pasa:
        a_f = _aparece(tl, 0.15, 0.35) if i == 3 else max(0.0, 1 - _aparece(tl, 1.6, 0.5))
        lado_a, lado_b = (A0, A1), (B0, B1)
        izq, der = (lado_a, lado_b) if c < 0 else (lado_b, lado_a)
        izq_m = tuple((x + y) / 2 for x, y in zip(izq[0], izq[1]))
        der_m = tuple((x + y) / 2 for x, y in zip(der[0], der[1]))
        largo = 1.2 * (0.6 + 0.4 * _aparece(tl, 0.15, 0.6))
        esc.flecha(izq_m, (izq_m[0], izq_m[1] + largo, izq_m[2]), AMARILLO, grosor=0.13, alfa=a_f)
        esc.flecha(der_m, (der_m[0], der_m[1] - largo, der_m[2]), AMARILLO, grosor=0.13, alfa=a_f)
        if a_f > 0.05:
            etiquetas.append(((izq_m[0], izq_m[1] + largo + 0.25, izq_m[2]), "F", (0, -10), a_f, "fuerza"))
            etiquetas.append(((der_m[0], der_m[1] - largo - 0.3, der_m[2]), "F", (0, 10), a_f, "fuerza"))

    # --- Flecha de giro (par de fuerzas)
    if i == 4:
        a_g = _aparece(tl, 1.0, 0.4)
        arco = [(2.0 * math.cos(a), 2.0 * math.sin(a), Z_CON1 + 0.25) for a in
                [math.radians(125 - 12 * k) for k in range(8)]]
        esc.linea(arco[:-1], BLANCO, grosor=0.07, alfa=a_g)
        esc.flecha(arco[-2], arco[-1], BLANCO, grosor=0.07, alfa=a_g)
        etiquetas.append((arco[3], "PAR DE FUERZAS", (40, -70), a_g, "normal"))

    # --- Etiquetas de cada escena
    if i == 1:
        etiquetas.append(((-2.7, 1.6, 0), "IMÁN", (-50, -110), _aparece(tl, 0.2), "normal"))
        etiquetas.append(((2.7, 1.6, 0), "IMÁN", (50, -110), _aparece(tl, 0.35), "normal"))
        etiquetas.append(((0, 1.35, 0), "CAMPO MAGNÉTICO", (0, -270), _aparece(tl, 1.0), "campo"))
    elif i == 2:
        etiquetas.append(((-R_ESPIRA * c, -R_ESPIRA * s, -0.6), "ESPIRA DE COBRE", (-60, -150), _aparece(tl, 0.3),
                          "normal"))
        etiquetas.append(((-1.9, -0.75, 3.1), "PILA", (-110, 60), _aparece(tl, 0.7), "normal"))
        etiquetas.append(((-0.95, 1.6, 2.6), "CORRIENTE", (-40, -130), _aparece(tl, 1.1), "corriente"))
    elif i == 5:
        etiquetas.append(((0, -R_CON - 0.5, Z_ESCOBILLA), "ESCOBILLA", (190, 140), _aparece(tl, 0.3), "normal"))
        etiquetas.append(((R_CON * 0.7, R_CON * 0.7, Z_CON1), "CONMUTADOR", (190, -170), _aparece(tl, 0.1), "normal"))
        if not pasa:
            etiquetas.append(((0, 0, Z_CON1), "¡SE INVIERTE LA CORRIENTE!", (0, 330), 1.0, "aviso"))
    return etiquetas


def camara_en(tiempos, i, tl, dur):
    """Cámara de la escena i en el instante tl (con suavizado)."""
    if i >= len(ESCENAS):
        return ESCENAS[-1]["b"].mezclar(CAMARA_CIERRE, min(1.0, tl / 2.0))
    e = ESCENAS[i]
    q = tl / max(dur, 0.1)
    q = q * q * (3 - 2 * q)
    return e["a"].mezclar(e["b"], q)
