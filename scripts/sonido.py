"""Efectos y música de fondo generados por código (sin sonidos de terceros, sin derechos).

- whoosh(): golpe de aire para las transiciones.
- pop(): «toc» corto cuando aparece una cifra.
- musica(): base suave de acordes, con un pulso ligero; baja sola cuando habla la voz.
"""
import numpy as np

SR = 48000


def _env(n, ataque, caida):
    a = int(ataque * SR)
    e = np.ones(n, dtype=np.float32)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[a:] = np.exp(-np.linspace(0, caida, n - a))
    return e


def _paso_bajo(x, alfas):
    """Filtro paso bajo de un polo con corte variable (alfas: 0..1 por muestra)."""
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alfas[i] * (x[i] - acc)
        y[i] = acc
    return y


def whoosh(dur=0.45, semilla=0):
    rnd = np.random.default_rng(semilla)
    n = int(dur * SR)
    ruido = rnd.standard_normal(n).astype(np.float32)
    barrido = np.concatenate([np.linspace(0.02, 0.35, n // 2), np.linspace(0.35, 0.03, n - n // 2)]).astype(np.float32)
    s = _paso_bajo(ruido, barrido) - _paso_bajo(ruido, barrido * 0.15)
    s *= _env(n, dur * 0.55, 5)
    return (s / (np.abs(s).max() + 1e-9) * 0.5).astype(np.float32)


def pop(frec=880, dur=0.12):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = frec * (1 + 0.6 * np.exp(-t * 40))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 32)
    return (s * 0.35).astype(np.float32)


def golpe(dur=0.35):
    """Bombo grave para el gancho inicial."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 28)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    return (s * 0.8).astype(np.float32)


ACORDES = {
    # Notas MIDI. Progresión i–VI–III–VII (suena a «noticia», sin ser triste)
    "gta": [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],
    "datos": [[50, 57, 62, 65], [46, 53, 58, 62], [48, 55, 60, 64], [45, 52, 57, 60]],
}


def musica(dur, estilo="datos", bpm=100):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    compas = 4 * 60 / bpm
    acordes = ACORDES.get(estilo, ACORDES["datos"])
    for i in range(int(dur / compas) + 1):
        ini = int(i * compas * SR)
        fin = min(n, int((i + 1) * compas * SR) + int(0.3 * SR))
        if ini >= n:
            break
        tt = t[ini:fin] - t[ini]
        env = np.minimum(1, tt / 0.6) * np.exp(-np.maximum(0, tt - compas) * 6)
        for nota in acordes[i % len(acordes)]:
            f = 440 * 2 ** ((nota - 69) / 12)
            for det in (-0.12, 0.12):
                s[ini:fin] += (np.sin(2 * np.pi * f * (1 + det / 100) * tt) * 0.5
                               + 0.15 * np.sin(2 * np.pi * 2 * f * tt)) * env * 0.05
    # Pulso suave en cada tiempo (bombo muy bajo) para dar ritmo
    tiempo = 60 / bpm
    k = golpe(0.25) * 0.35
    for i in range(int(dur / tiempo)):
        a = int(i * tiempo * SR)
        b = min(n, a + len(k))
        s[a:b] += k[: b - a]
    if estilo == "gta":  # arpegio brillante tipo synthwave
        paso = tiempo / 2
        for i in range(int(dur / paso)):
            acorde = acordes[int(i * paso / compas) % len(acordes)]
            nota = acorde[i % len(acorde)] + 12
            f = 440 * 2 ** ((nota - 69) / 12)
            a = int(i * paso * SR)
            m = min(n - a, int(paso * SR))
            if m <= 0:
                break
            tt = np.arange(m) / SR
            s[a:a + m] += np.sign(np.sin(2 * np.pi * f * tt)) * np.exp(-tt * 9) * 0.025
    fade = int(1.0 * SR)
    s[:fade] *= np.linspace(0, 1, fade)
    s[-fade:] *= np.linspace(1, 0, fade)
    return s


def mezclar(voz, sr_voz, efectos, dur, estilo, volumen_musica=0.55):
    """Junta voz, efectos [(segundo, señal)] y música. La música baja cuando habla la voz."""
    n = int(dur * SR)
    if sr_voz != SR:
        x_old = np.linspace(0, 1, len(voz))
        x_new = np.linspace(0, 1, int(len(voz) * SR / sr_voz))
        voz = np.interp(x_new, x_old, voz).astype(np.float32)
    v = np.zeros(n, dtype=np.float32)
    v[: min(n, len(voz))] = voz[:n]
    fx = np.zeros(n, dtype=np.float32)
    for seg, señal in efectos:
        a = int(seg * SR)
        if 0 <= a < n:
            b = min(n, a + len(señal))
            fx[a:b] += señal[: b - a]
    m = musica(dur, estilo)
    # Ducking: envolvente de la voz suavizada
    ventana = int(0.25 * SR)
    env = np.convolve(np.abs(v), np.ones(ventana) / ventana, mode="same")
    env = env / (env.max() + 1e-9)
    m *= volumen_musica * (1 - 0.65 * np.clip(env * 4, 0, 1))
    mezcla = v + fx * 0.6 + m
    return (mezcla / max(1.0, np.abs(mezcla).max() / 0.95)).astype(np.float32)
