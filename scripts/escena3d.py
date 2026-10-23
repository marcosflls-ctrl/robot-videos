"""Mini motor 3D para los vídeos de física: dibuja esquemas que se mueven y una cámara que hace zoom.

Todo es código (polígonos, líneas y puntos proyectados en perspectiva). No usa imágenes de terceros.

Coordenadas del mundo: x a la derecha, y hacia arriba, z hacia el espectador.

    cam = Camara(objetivo=(0, 0, 0), distancia=12, giro=0.5, inclinacion=0.3)
    esc = Escena()
    esc.caja((-1, -1, -1), (1, 1, 1), (200, 40, 40))
    esc.linea([(0, 0, 0), (0, 2, 0)], (255, 200, 0), grosor=0.1)
    capa_nitida, capa_brillo = esc.dibujar(cam, 1080, 1920, centro=(540, 820))
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 2  # supermuestreo: se dibuja al doble y se reduce (bordes suaves)
LUZ = np.array([-0.4, 0.8, 0.6])
LUZ = LUZ / np.linalg.norm(LUZ)


def _mezcla(a, b, q):
    return tuple(x + (y - x) * q for x, y in zip(a, b))


class Camara:
    def __init__(self, objetivo=(0, 0, 0), distancia=12.0, giro=0.5, inclinacion=0.3, focal=1500.0):
        self.objetivo = tuple(objetivo)
        self.distancia = distancia
        self.giro = giro
        self.inclinacion = inclinacion
        self.focal = focal

    def mezclar(self, otra, q):
        return Camara(_mezcla(self.objetivo, otra.objetivo, q),
                      self.distancia + (otra.distancia - self.distancia) * q,
                      self.giro + (otra.giro - self.giro) * q,
                      self.inclinacion + (otra.inclinacion - self.inclinacion) * q,
                      self.focal + (otra.focal - self.focal) * q)

    def base(self):
        o = np.array(self.objetivo, dtype=float)
        ci, si = math.cos(self.inclinacion), math.sin(self.inclinacion)
        pos = o + self.distancia * np.array([math.sin(self.giro) * ci, si, math.cos(self.giro) * ci])
        f = o - pos
        f /= np.linalg.norm(f)
        r = np.cross(f, [0, 1, 0])
        r /= np.linalg.norm(r)
        u = np.cross(r, f)
        return pos, f, r, u


class Escena:
    """Lista de cosas que dibujar en un cuadro. Se vacía en cada cuadro."""

    def __init__(self):
        self.prims = []  # (tipo, datos)

    # ---------- primitivas ----------
    def poligono(self, puntos, color, alfa=1.0, sombrear=True, borde=None):
        self.prims.append(("poli", (np.array(puntos, dtype=float), color, alfa, sombrear, borde)))

    def caja(self, a, b, color, alfa=1.0, borde=(0, 0, 0)):
        (x0, y0, z0), (x1, y1, z1) = a, b
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        caras = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (3, 7, 6, 2), (0, 4, 7, 3), (1, 2, 6, 5)]
        for c in caras:
            self.poligono([v[i] for i in c], color, alfa, True, borde)

    def cilindro(self, centro, radio, z0, z1, color, ang0=0.0, ang1=2 * math.pi, lados=20, alfa=1.0, tapa=True):
        """Cilindro (o trozo de cilindro) con eje paralelo a z."""
        cx, cy = centro
        angs = np.linspace(ang0, ang1, lados + 1)
        for a, b in zip(angs[:-1], angs[1:]):
            p = [(cx + radio * math.cos(a), cy + radio * math.sin(a), z0),
                 (cx + radio * math.cos(b), cy + radio * math.sin(b), z0),
                 (cx + radio * math.cos(b), cy + radio * math.sin(b), z1),
                 (cx + radio * math.cos(a), cy + radio * math.sin(a), z1)]
            self.poligono(p, color, alfa, True, None)
        if tapa:
            pts = [(cx, cy, z1)] if ang1 - ang0 < 2 * math.pi - 1e-6 else []
            pts += [(cx + radio * math.cos(a), cy + radio * math.sin(a), z1) for a in angs]
            self.poligono(pts, color, alfa, True, (0, 0, 0))

    def linea(self, puntos, color, grosor=0.08, alfa=1.0, brillo=False):
        """Polilínea gruesa. grosor en unidades del mundo (se ve más gruesa cuanto más cerca)."""
        for a, b in zip(puntos[:-1], puntos[1:]):
            self.prims.append(("seg", (np.array(a, float), np.array(b, float), color, grosor, alfa, brillo)))

    def punto(self, p, color, radio=0.08, alfa=1.0, brillo=True):
        self.prims.append(("pto", (np.array(p, float), color, radio, alfa, brillo)))

    def flecha(self, a, b, color, grosor=0.12, alfa=1.0, brillo=True):
        """Flecha 3D de a a b, con punta dibujada en pantalla."""
        self.prims.append(("flecha", (np.array(a, float), np.array(b, float), color, grosor, alfa, brillo)))

    # ---------- proyección ----------
    def _proy(self, p, cam_base, focal, centro):
        pos, f, r, u = cam_base
        d = p - pos
        prof = float(np.dot(d, f))
        prof = max(prof, 0.3)
        x = centro[0] + focal * float(np.dot(d, r)) / prof
        y = centro[1] - focal * float(np.dot(d, u)) / prof
        return (x, y), prof

    def proyectar(self, cam, p, centro):
        (x, y), prof = self._proy(np.array(p, float), cam.base(), cam.focal, centro)
        return x, y, prof

    # ---------- dibujo ----------
    def dibujar(self, cam, ancho, alto, centro):
        """Devuelve (capa nítida RGBA ancho x alto, capa de brillo RGBA ancho x alto)."""
        base = cam.base()
        pos, f = base[0], base[1]
        foc = cam.focal * SS
        cen = (centro[0] * SS, centro[1] * SS)
        orden = []
        for tipo, d in self.prims:
            if tipo == "poli":
                pts, color, alfa, sombrear, borde = d
                c = pts.mean(axis=0)
                n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
                nn = np.linalg.norm(n)
                if nn < 1e-9:
                    continue
                n /= nn
                if np.dot(n, pos - c) <= 0 and alfa >= 0.99:
                    continue  # cara de espaldas
                prof = float(np.dot(c - pos, f))
                orden.append((prof, tipo, d, n))
            elif tipo in ("seg", "flecha"):
                prof = float(np.dot((d[0] + d[1]) / 2 - pos, f))
                orden.append((prof - 0.05, tipo, d, None))
            else:
                prof = float(np.dot(d[0] - pos, f))
                orden.append((prof - 0.1, tipo, d, None))
        orden.sort(key=lambda x: -x[0])

        img = Image.new("RGBA", (ancho * SS, alto * SS), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img, "RGBA")
        gw, gh = ancho // 4, alto // 4
        glow = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow, "RGBA")
        k = 1 / (4 * SS)

        for prof, tipo, d, n in orden:
            if tipo == "poli":
                pts, color, alfa, sombrear, borde = d
                pp = [self._proy(p, base, foc, cen)[0] for p in pts]
                if sombrear:
                    luz = 0.5 + 0.5 * max(0.0, float(np.dot(n, LUZ)))
                    col = tuple(int(min(255, c * luz)) for c in color)
                else:
                    col = tuple(int(c) for c in color)
                a = int(255 * alfa)
                dr.polygon(pp, fill=col + (a,))
                if borde is not None:
                    dr.line(pp + [pp[0]], fill=tuple(borde) + (int(110 * alfa),), width=max(1, SS))
            elif tipo == "seg":
                a3, b3, color, grosor, alfa, brillo = d
                (pa, za), (pb, zb) = self._proy(a3, base, foc, cen), self._proy(b3, base, foc, cen)
                w = min(28.0 * SS, max(1.0, grosor * foc / ((za + zb) / 2)))
                col = tuple(int(c) for c in color) + (int(255 * alfa),)
                dr.line([pa, pb], fill=col, width=int(w))
                rr = w / 2
                for p in (pa, pb):
                    dr.ellipse((p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr), fill=col)
                if brillo:
                    dg.line([(pa[0] * k, pa[1] * k), (pb[0] * k, pb[1] * k)], fill=col, width=max(2, int(w * k * 2.5)))
            elif tipo == "flecha":
                a3, b3, color, grosor, alfa, brillo = d
                (pa, za), (pb, zb) = self._proy(a3, base, foc, cen), self._proy(b3, base, foc, cen)
                w = max(2.0, grosor * foc / ((za + zb) / 2))
                col = tuple(int(c) for c in color) + (int(255 * alfa),)
                dx, dy = pb[0] - pa[0], pb[1] - pa[1]
                L = math.hypot(dx, dy) or 1
                ux, uy = dx / L, dy / L
                punta = min(L * 0.45, w * 3.2)
                base_p = (pb[0] - ux * punta, pb[1] - uy * punta)
                dr.line([pa, base_p], fill=col, width=int(w))
                dr.ellipse((pa[0] - w / 2, pa[1] - w / 2, pa[0] + w / 2, pa[1] + w / 2), fill=col)
                tri = [pb, (base_p[0] - uy * w * 1.6, base_p[1] + ux * w * 1.6),
                       (base_p[0] + uy * w * 1.6, base_p[1] - ux * w * 1.6)]
                dr.polygon(tri, fill=col)
                if brillo:
                    dg.line([(pa[0] * k, pa[1] * k), (pb[0] * k, pb[1] * k)], fill=col, width=max(2, int(w * k * 3)))
            else:  # punto
                p3, color, radio, alfa, brillo = d
                p, z = self._proy(p3, base, foc, cen)
                rr = min(9.0 * SS, max(1.5, radio * foc / z))
                col = tuple(int(c) for c in color) + (int(255 * alfa),)
                dr.ellipse((p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr), fill=col)
                if brillo:
                    g = rr * k * 2.6
                    dg.ellipse((p[0] * k - g, p[1] * k - g, p[0] * k + g, p[1] * k + g), fill=col)

        nitida = img.reduce(SS)
        glow = glow.filter(ImageFilter.GaussianBlur(3)).resize((ancho, alto), Image.BILINEAR)
        return nitida, glow
