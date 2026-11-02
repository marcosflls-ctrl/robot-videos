"""Copia a Google Drive los vídeos de salida/, con nombres claros y una carpeta por canal y por vídeo.

    Vídeos/
      Bitácora de la Tierra/
        La Palma (2021)/
          Largo - Cómo funciona un volcán….mp4
          Short 1 - Cómo nacieron las islas Canarias.mp4
          Miniatura 1.png · Títulos.txt · Descripción.txt · Subtítulos.srt

No borra nada: si un archivo con el mismo nombre ya está en la carpeta, lo sustituye por la versión nueva.
Las copias ligeras para Telegram (_movil) no se suben.

Variables (secretos de GitHub):
    GDRIVE_REFRESH                          permiso de Google Drive (ver guiones/LEEME.md)
    GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET  (opcional) la «llave» de la app; si faltan, usa las de YouTube
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET
    GUION                                   nombre del guion (sin .yaml)

Si falta algo o Drive falla, avisa y sigue: nunca rompe el robot.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = Path("salida")
CARPETA_RAIZ = "Vídeos"
CARPETA = "application/vnd.google-apps.folder"
API = "https://www.googleapis.com/drive/v3/files"
SUBIDA = "https://www.googleapis.com/upload/drive/v3/files"
MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "e", "o", "a", "al", "en", "con", "sin", "por", "para"}
TIPOS = {".mp4": "video/mp4", ".png": "image/png", ".txt": "text/plain", ".srt": "application/x-subrip"}


def _env(nombre):
    return (os.environ.get(nombre) or "").strip()


def nombre_propio(marca):
    palabras = str(marca).lower().split()
    return " ".join(p if (i and p in MINUSCULAS) else p[:1].upper() + p[1:] for i, p in enumerate(palabras))


def limpio(texto, largo=110):
    """Nombre de archivo seguro: sin barras ni caracteres raros, y no demasiado largo."""
    t = re.sub(r'[\\/:*?"<>|#\n\r\t]+', " ", str(texto))
    t = re.sub(r"\s+", " ", t).strip(" .")
    return (t[:largo].rsplit(" ", 1)[0] if len(t) > largo else t) or "Sin título"


def nombres(g, nombre):
    """De los archivos del robot (la_palma_short_02.mp4) a los de Drive (Short 2 - Título.mp4)."""
    caps = g.get("capitulos") or []
    t = g.get("titulos") or [g.get("titulo")]
    titulo = limpio((t[0] if isinstance(t, list) else t) or nombre)
    fijos = {
        f"{nombre}_largo.mp4": f"Largo - {titulo}.mp4",
        f"{nombre}_largo.srt": "Subtítulos.srt",
        f"{nombre}_descripcion.txt": "Descripción.txt",
        f"{nombre}_titulos.txt": "Títulos.txt",
        f"{nombre}_miniatura.png": "Miniatura.png",
    }
    lista = []
    for ruta in sorted(SALIDA.glob(f"{nombre}_*")):
        if ruta.name.endswith("_movil.mp4"):
            continue
        destino = fijos.get(ruta.name)
        m = re.fullmatch(rf"{re.escape(nombre)}_short_(\d+)\.(mp4|txt)", ruta.name)
        if m:
            n = int(m.group(1))
            cap = caps[n - 1] if 0 < n <= len(caps) else {}
            t = limpio(cap.get("titulo_short") or cap.get("titulo") or f"Capítulo {n}")
            destino = f"Short {n} - {t}.{m.group(2)}"  # el .txt, con el título y el texto para YouTube
        m = re.fullmatch(rf"{re.escape(nombre)}_miniatura_(\d+)\.png", ruta.name)
        if m:
            destino = f"Miniatura {int(m.group(1))}.png"
        if destino:
            lista.append((ruta, destino))
    return lista


class Drive:
    def __init__(self):
        cid = _env("GDRIVE_CLIENT_ID") or _env("YOUTUBE_CLIENT_ID")
        secreto = _env("GDRIVE_CLIENT_SECRET") or _env("YOUTUBE_CLIENT_SECRET")
        datos = urllib.parse.urlencode({"client_id": cid, "client_secret": secreto,
                                        "refresh_token": _env("GDRIVE_REFRESH"),
                                        "grant_type": "refresh_token"}).encode()
        with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=datos),
                                    timeout=30) as r:
            self.token = json.loads(r.read())["access_token"]

    def _pedir(self, url, datos=None, metodo=None, cabeceras=None):
        c = {"Authorization": f"Bearer {self.token}"}
        c.update(cabeceras or {})
        req = urllib.request.Request(url, data=datos, method=metodo, headers=c)
        with urllib.request.urlopen(req, timeout=600) as r:
            cuerpo = r.read()
            return (json.loads(cuerpo) if cuerpo else {}), r.headers

    def buscar(self, nombre, padre, carpeta=False):
        q = [f"name = '{nombre.replace(chr(39), chr(92) + chr(39))}'", "trashed = false", f"'{padre}' in parents"]
        if carpeta:
            q.append(f"mimeType = '{CARPETA}'")
        url = API + "?" + urllib.parse.urlencode({"q": " and ".join(q), "fields": "files(id)", "pageSize": 1})
        r, _ = self._pedir(url)
        return (r.get("files") or [{}])[0].get("id")

    def carpeta(self, nombre, padre):
        existe = self.buscar(nombre, padre, carpeta=True)
        if existe:
            return existe
        meta = json.dumps({"name": nombre, "mimeType": CARPETA, "parents": [padre]}).encode()
        r, _ = self._pedir(API + "?fields=id", meta, "POST", {"Content-Type": "application/json"})
        return r["id"]

    def subir(self, ruta, nombre, padre):
        tipo = TIPOS.get(ruta.suffix, "application/octet-stream")
        existe = self.buscar(nombre, padre)
        if existe:  # misma carpeta y mismo nombre: se sustituye el contenido
            url, metodo, meta = f"{SUBIDA}/{existe}?uploadType=resumable", "PATCH", {}
        else:
            url, metodo, meta = f"{SUBIDA}?uploadType=resumable", "POST", {"name": nombre, "parents": [padre]}
        _, cab = self._pedir(url, json.dumps(meta).encode(), metodo,
                             {"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": tipo})
        destino = cab["Location"]
        tam = ruta.stat().st_size
        with open(ruta, "rb") as f:
            req = urllib.request.Request(destino, data=f, method="PUT",
                                         headers={"Content-Type": tipo, "Content-Length": str(tam)})
            with urllib.request.urlopen(req, timeout=1800) as r:
                r.read()
        return "actualizado" if existe else "subido"


def main():
    nombre = _env("GUION")
    if not _env("GDRIVE_REFRESH"):
        print("Google Drive no está configurado (falta el secreto GDRIVE_REFRESH): no copio nada.")
        return
    if not nombre:
        print("::warning::Drive: no sé qué guion es (falta GUION).")
        return
    g = yaml.safe_load((RAIZ / "guiones" / f"{nombre}.yaml").read_text(encoding="utf-8"))
    canal = yaml.safe_load((RAIZ / f"canal_{str(g.get('canal') or 'historia').strip()}.yaml").read_text(encoding="utf-8"))
    carpeta_canal = limpio(nombre_propio(canal.get("marca", "Canal")))
    carpeta_video = limpio(g.get("carpeta") or nombre.replace("_", " ").capitalize(), 80)
    archivos = nombres(g, nombre)
    if not archivos:
        print("Drive: no hay archivos que copiar.")
        return
    try:
        d = Drive()
        raiz = d.carpeta(CARPETA_RAIZ, "root")
        destino = d.carpeta(carpeta_video, d.carpeta(carpeta_canal, raiz))
        print(f"Drive: {CARPETA_RAIZ}/{carpeta_canal}/{carpeta_video}/")
        for ruta, nuevo in archivos:
            print(f"  {d.subir(ruta, nuevo, destino)}: {nuevo}")
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        print(f"::warning::Google Drive respondió con el error {e.code}: {detalle}")
    except Exception as e:  # nunca rompemos el robot por Drive
        print(f"::warning::No se pudo copiar a Google Drive: {str(e)[:300]}")


if __name__ == "__main__":
    sys.exit(main())
