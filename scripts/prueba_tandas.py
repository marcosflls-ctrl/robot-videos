"""TEMPORAL: comprueba el corte por frases con voz sintética (espeak-ng) y verdad conocida."""
import io, subprocess, time, random
import numpy as np, soundfile as sf, yaml
from numeros import a_voz
import voz_tandas

sr = 24000
g = yaml.safe_load(open("../guiones/sellos.yaml"))
textos = [e["voz"] for e in g["gancho"] + sum([c["escenas"] for c in g["capitulos"]], [])]
import os; random.seed(int(os.environ.get('SEMILLA') or 1))

def decir(t, velocidad):
    out = subprocess.run(["espeak-ng", "-v", "es", "-s", str(velocidad), "--stdout", t], capture_output=True, check=True).stdout
    w, r = sf.read(io.BytesIO(out), dtype="float32")
    w = np.interp(np.linspace(0, 1, int(len(w) * sr / r)), np.linspace(0, 1, len(w)), w).astype(np.float32)
    env = np.abs(w); act = np.where(env > 0.02 * env.max())[0]
    return w[act[0]:act[-1]]

bien = mal = fallos = 0; t0 = time.time()
for i in range(0, len(textos), 6):
    grupo = [a_voz(t) for t in textos[i:i + 6]]
    segs = [decir(t, random.choice([150, 170, 190])) for t in grupo]
    piezas, huecos, pos = [], [], 0
    for k, s in enumerate(segs):
        piezas.append(s); pos += len(s)
        if k < len(segs) - 1:
            gap = int(sr * random.uniform(0.2, 0.5)); piezas.append(np.zeros(gap, np.float32))
            huecos.append((pos, pos + gap)); pos += gap
    wav = np.concatenate(piezas)
    cortes = voz_tandas.cortar_tanda(wav, sr, grupo)
    if cortes is None:
        fallos += 1; print(i, "NONE"); continue
    for (a, b), (h0, h1) in zip(cortes[:-1], huecos):
        ok = h0 - int(0.05 * sr) <= b <= h1 + int(0.05 * sr)
        bien += ok; mal += not ok
        if not ok:
            print(i, "corte fuera", round(b / sr, 2), "hueco", round(h0 / sr, 2), round(h1 / sr, 2))
            print("   frases:", grupo)
            print("   oídas:", [(p, round(x, 2), round(y, 2)) for p, x, y in voz_tandas._reconocer(wav, sr) if h0 / sr - 3 < x < h1 / sr + 2])
            print("   silencios:", [(round(x / sr, 2), round(y / sr, 2)) for x, y in voz_tandas._silencios(wav, sr, h0 / sr - 3, h1 / sr + 2)])
print(f"cortes bien {bien} · mal {mal} · tandas sin cortar {fallos} · {time.time() - t0:.0f} s")
