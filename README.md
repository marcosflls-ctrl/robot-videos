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
