"""Sube a YouTube los vídeos de salida/, cada uno a su canal, SIEMPRE EN PRIVADO.

Hacerlos públicos lo decide Marcos (a mano en YouTube Studio, o más adelante con su permiso).

Variables (secretos de GitHub):
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET   la «llave» de la app de Google
    YOUTUBE_REFRESH_GTA / _AFDM / _DEC         permiso de cada canal (Zona Leonida, Al Final de Mes, Dinero en Claro)
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID           (opcional) para avisar con el enlace

Si falta la llave o el permiso de un canal, ese vídeo se salta con un aviso: nunca rompe el robot.
"""
import glob
import json
import os
import urllib.error
import urllib.parse
import urllib.request

CANALES = {  # prefijo del archivo -> (secreto del canal, nombre, categoría de YouTube)
    "zonaleonida": ("YOUTUBE_REFRESH_GTA", "Zona Leonida", "20"),     # 20 = Videojuegos
    "alfinaldemes": ("YOUTUBE_REFRESH_AFDM", "Al Final de Mes", "25"),  # 25 = Noticias y política
    "dineroenclaro": ("YOUTUBE_REFRESH_DEC", "Dinero en Claro", "27"),  # 27 = Educación
    "gta": ("YOUTUBE_REFRESH_GTA", "Zona Leonida", "20"),
}


def _env(nombre):
    return (os.environ.get(nombre) or "").strip()


def token_de_acceso(refresh):
    datos = urllib.parse.urlencode({
        "client_id": _env("YOUTUBE_CLIENT_ID"), "client_secret": _env("YOUTUBE_CLIENT_SECRET"),
        "refresh_token": refresh, "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=datos), timeout=30) as r:
        return json.loads(r.read())["access_token"]


def titulo_y_descripcion(ruta_txt):
    try:
        texto = open(ruta_txt, encoding="utf-8").read().strip()
    except FileNotFoundError:
        texto = ""
    primera = texto.splitlines()[0].strip() if texto else "Vídeo del día"
    titulo = primera.replace("<", "").replace(">", "")
    if "#shorts" not in titulo.lower() and len(titulo) <= 90:
        titulo += " #Shorts"
    return titulo[:100], texto.replace("<", "").replace(">", "")[:4900]


def subir(ruta_mp4, token, titulo, descripcion, categoria):
    metadatos = {
        "snippet": {"title": titulo, "description": descripcion, "categoryId": categoria,
                    "defaultLanguage": "es", "defaultAudioLanguage": "es-ES"},
        # Privado siempre. Voz hecha con IA: se declara como contenido sintético, como pide YouTube.
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    tam = os.path.getsize(ruta_mp4)
    inicio = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(metadatos).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(tam)})
    with urllib.request.urlopen(inicio, timeout=60) as r:
        destino = r.headers["Location"]
    with open(ruta_mp4, "rb") as fh:
        envio = urllib.request.Request(destino, data=fh.read(), method="PUT",
                                       headers={"Content-Type": "video/mp4", "Content-Length": str(tam)})
    with urllib.request.urlopen(envio, timeout=600) as r:
        return json.loads(r.read())["id"]


def avisar_telegram(texto):
    tok, chat = _env("TELEGRAM_TOKEN"), _env("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    datos = urllib.parse.urlencode({"chat_id": chat, "text": texto, "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=datos, timeout=30).read()
    except Exception as error:
        print(f"::warning::No pude avisar por Telegram: {error}")


def main(carpeta="salida"):
    if not (_env("YOUTUBE_CLIENT_ID") and _env("YOUTUBE_CLIENT_SECRET")):
        print("::warning::YouTube no está configurado (faltan YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET): no subo nada.")
        return
    avisos = []
    for ruta in sorted(glob.glob(f"{carpeta}/*.mp4")):
        prefijo = os.path.basename(ruta).split("_")[0]
        if prefijo not in CANALES:
            continue
        secreto, nombre, categoria = CANALES[prefijo]
        refresh = _env(secreto)
        if not refresh:
            print(f"::warning::{nombre}: falta el secreto {secreto}, no lo subo.")
            continue
        titulo, descripcion = titulo_y_descripcion(ruta[:-4] + ".txt")
        try:
            vid = subir(ruta, token_de_acceso(refresh), titulo, descripcion, categoria)
        except urllib.error.HTTPError as e:
            print(f"::error::{nombre}: YouTube respondió {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
            continue
        except Exception as e:
            print(f"::error::{nombre}: no se pudo subir: {type(e).__name__}: {e}")
            continue
        enlace = f"https://studio.youtube.com/video/{vid}/edit"
        print(f"Subido EN PRIVADO a {nombre}: https://youtu.be/{vid}")
        avisos.append(f"• {nombre}: {titulo}\n  {enlace}")
    if avisos:
        avisar_telegram("📺 Subidos a YouTube EN PRIVADO (revísalos y hazlos públicos si te gustan):\n\n" + "\n\n".join(avisos))


if __name__ == "__main__":
    main()
