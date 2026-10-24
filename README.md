# Robot de vídeos

Robots que hacen cada día un vídeo vertical para zonaleonida.com, alfinaldemes.com y dineroenclaro.com.

Este repositorio es **público** (no gasta minutos de GitHub Actions). Lo privado —la grabación de la voz
(`voz_referencia.wav`) y las imágenes de GTA (`imagenes_gta/`)— está en el repositorio privado
`videos-cortos`, y el robot lo trae en cada ejecución con la clave de solo lectura `DATOS_TOKEN`.

Claves necesarias (Settings → Secrets → Actions): `DATOS_TOKEN` (lectura de `al-final-de-mes`,
`dinero-en-claro` y `videos-cortos`), `PIXABAY_API_KEY` (o `PEXELS_API_KEY`), `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`.


Robots que harán cada día un vídeo vertical de 30–40 s para zonaleonida.com, alfinaldemes.com y dineroenclaro.com.
Este repositorio está separado de las webs: nada de aquí las modifica.

## Paso 1 (ahora): prueba de voces

El robot **Prueba de voces** lee el mismo texto con:

- **Kokoro** (Apache 2.0): voces Dora (mujer) y Alex (hombre).
- **Chatterbox español de España** (`Chatterbox-Multilingual-es-es`, MIT) y **Chatterbox V3** (modelo general, MIT), cada uno con su voz por defecto, una voz española de muestra y, si subes `voz_referencia.wav`, la tuya.

Antes de leer, el robot pasa números, porcentajes, euros y siglas a palabras («4,9 %» → «cuatro coma nueve por ciento»). Cómo se dice cada sigla se cambia en `glosario.txt`. El resultado se guarda en `texto_leido.txt`.

Cómo lanzarlo: pestaña **Actions** → **Prueba de voces** → **Run workflow**. Puedes escribir otro texto o dejarlo vacío para usar `texto_prueba.txt`.

Los audios llegan por Telegram si están las claves `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`. Si no, se descargan en el apartado **Artifacts** de la ejecución. Cada audio indica cuánto tardó en generarse.

## Paso 2: vídeo de Zona Leonida («Faltan X días para GTA 6»)

El robot **Vídeo GTA (prueba)** monta un vídeo vertical de 30–40 s con:

- **Voz:** la de Marcos, clonada con Chatterbox español de España.
- **Gráficos:** propios, hechos con código (atardecer, rejilla, cifra grande y subtítulos). Nada de Rockstar.

Lo manda por Telegram con el texto para la publicación. **No publica nada.** Se lanza a mano en **Actions** → **Vídeo GTA (prueba)** → **Run workflow**. Puedes poner otro número de días para ver cómo quedaría.

- El guion está en `scripts/guion_gta.py`: tres plantillas que se turnan cada día.
- El diseño está en `scripts/video.py`.
- Las fuentes (Anton e Inter) tienen licencia libre SIL OFL; la licencia está en `fuentes/OFL.txt`.

## Paso 3: vídeos de Al Final de Mes y Dinero en Claro

El robot **Vídeos webs (prueba)** lee los datos que ya bajan los robots de cada web (`src/data`, solo lectura) y monta un vídeo por web. Usa el estilo sobrio de cada web (sus colores y la letra IBM Plex) y un gráfico que se dibuja poco a poco. Cada día toca un tema:

| Día | Al Final de Mes | Dinero en Claro |
|---|---|---|
| Lunes | Luz hoy | Cierre de la bolsa |
| Martes | Gasolina y diésel | Cuentas / depósitos que más pagan |
| Miércoles | Euríbor | 100 € al mes en un índice |
| Jueves | Luz hoy | Cierre de la bolsa |
| Viernes | Gasolina y diésel | Bitcoin |
| Sábado | IPC | 100 € al mes en un índice |
| Domingo | Luz hoy | Cuentas / depósitos que más pagan |

Al lanzarlo a mano se puede elegir la web y el tema. El plan se cambia en `scripts/guiones_webs.py` (`PLAN_AFDM` y `PLAN_DEC`).

Necesita la clave `DATOS_TOKEN`: un token de GitHub de **solo lectura** para los repositorios de las dos webs.

## Montaje por escenas

Por defecto, los vídeos se montan **por escenas** (`scripts/montaje.py`):

- **Gancho:** la primera cifra o titular entra a pantalla completa con un golpe de sonido.
- **Una escena por frase** (cifra grande, titular, gráfico…) y un corte de fondo en cada coma, así que algo cambia cada 2–3 s.
- **Transiciones** rápidas (barrido, zoom, destello) con un «whoosh», más un zoom en cada corte.
- **Subtítulos palabra a palabra**, con la palabra que suena resaltada.
- **Música de fondo suave** y efectos, generados por código (`scripts/sonido.py`), sin derechos de terceros. La música baja sola cuando habla la voz.
- **Fondos:** clips de vídeo de **Pexels** (`PEXELS_API_KEY`) o **Pixabay** (`PIXABAY_API_KEY`), según la clave que haya. Licencia de Pixabay: uso comercial gratis sin atribución (https://pixabay.com/service/license-summary/). Su licencia permite uso comercial gratis sin citar al autor (https://www.pexels.com/license/). Sin clave, o si Pexels falla, se usan fondos animados propios. Las búsquedas de cada escena están en `guion_gta.py` y `guiones_webs.py`.
- **GTA:** nada de material de Rockstar. Solo gráficos propios y clips de ambiente (Miami, neones, palmeras…).

Al lanzar un robot puedes elegir **Montaje → clasico** para volver a la versión de una sola pantalla.

## Imágenes de GTA en tarjeta

Si existe la carpeta `imagenes_gta/`, cada escena del vídeo de GTA muestra una de esas imágenes enmarcada en la parte de arriba. Es una tarjeta, no un fondo a pantalla completa, con zoom lento por dentro y el crédito «Imagen: Rockstar Games». Cada día cambian el orden y la imagen de cada escena.

Las imágenes son de Rockstar Games. Su uso en vídeos monetizados no está cubierto por la política de Rockstar (solo permite usos no comerciales), así que puede haber reclamaciones. Es una decisión asumida por Marcos. Por eso esta carpeta solo debe estar en el repositorio **privado**.

## Voz con Gemini

Por defecto, la voz la hace **Gemini TTS** (API de Google): suena más natural y tarda segundos.

- `GEMINI_API_KEY`: clave de https://aistudio.google.com/apikey
- `GEMINI_VOICE_ID` (opcional): la voz clonada de Marcos, creada en https://aistudio.google.com/generate-speech (Voice Replication). Empieza por `voice_`.
- Al lanzar un robot: **Motor de voz** (`gemini` o `chatterbox`) y **Voz de Gemini** (`clonada` o una voz de Gemini, como Orus o Charon).
- Pronunciación para Gemini: `glosario_gemini.txt` (corto; Gemini ya sabe decir nombres en inglés). El de Chatterbox sigue en `glosario.txt`.

## Vídeos de física (esquema 3D animado)

El robot **Vídeo de física (prueba)** explica un fenómeno con un esquema 3D hecho con código: piezas que se mueven,
puntos que muestran la corriente y el campo, flechas de fuerza, etiquetas y una cámara que hace zoom a cada parte.
La voz es la de Gemini. Lo manda por Telegram; **no publica nada**.

- Primer tema: **cómo funciona un motor eléctrico** (`scripts/fisica_motor.py`): imanes, espira, fuerzas, par y conmutador.
- El motor 3D está en `scripts/escena3d.py` y el montaje en `scripts/video_fisica.py`.
- Para un tema nuevo: copiar `fisica_motor.py`, cambiar el guion (`FRASES`), las cámaras (`ESCENAS`) y el dibujo, y añadirlo a `TEMAS` en `video_fisica.py` y a las opciones del robot.
- Opción **Prueba rápida sin voz**: monta solo la animación, para ver cómo queda sin gastar la API.

## Canal de historia económica (vídeo largo + Shorts)

El robot **Vídeo de historia** monta un vídeo largo horizontal (1920x1080) a partir de un guion de la carpeta
`guiones/`, y un Short vertical por cada capítulo marcado. Estilo «Editorial»: fondo negro cálido, crema,
rojo anaranjado y dorado, titulares con serifa y grano de película.

- **Identidad del canal** (nombre, colores, fuentes, voz del narrador, subtítulos): `canal_historia.yaml`. El nombre es provisional.
- **Guiones:** cómo se escriben, en `guiones/LEEME.md`. `guiones/ejemplo.yaml` es una prueba con todos los tipos de escena.
- **Escenas:** titulares, cifras, gráficos, fechas, citas, listas, fotos de época, bocetos que se dibujan a trazos,
  mapas animados, esquemas de cajas y flechas y clips de archivo.
- **Fotos e imágenes:** de Wikimedia Commons, solo con licencia libre; el crédito sale en pantalla y en la descripción.
- **Ilustraciones con IA** (escenas `ilustracion`): modelo de imágenes de Gemini con la misma clave `GEMINI_API_KEY`.
  Necesita la facturación activada en Google AI Studio (el plan gratuito no incluye imágenes). Unos céntimos por imagen.
- **Mapas:** datos de Natural Earth (dominio público), en `mapas/paises.geojson`.
- **Voz:** Gemini (clave `GEMINI_API_KEY`), con una voz de narrador distinta de la de los Shorts de las webs.
  Las frases ya leídas y las imágenes se guardan entre ejecuciones.
- **Clips de archivo:** Pixabay o Pexels, si están sus claves.
- **Qué te llega por Telegram:** miniatura, copia ligera del vídeo largo, descripción con capítulos, fuentes y créditos,
  subtítulos `.srt` y los Shorts con su texto. El largo en calidad completa está en **Artifacts** (7 días).
- Cómo lanzarlo: **Actions** → **Vídeo de historia** → **Run workflow**, escribe el nombre del guion.
  Con **Prueba rápida sin voz** se ve el montaje sin gastar la API.

**No publica nada.**
