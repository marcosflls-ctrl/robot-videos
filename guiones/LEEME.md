# Guiones de los vídeos largos (historia económica y misterios)

Esta carpeta sirve para los dos canales. Lo que cambia de uno a otro (nombre, voz, colores y estilo
de las ilustraciones) está en `canal_historia.yaml` y `canal_misterios.yaml`. Un guion del canal de
misterios lleva al principio la línea `canal: misterios`; sin esa línea, el robot usa el de historia.

En el canal de misterios casi todas las imágenes son `ilustracion` (muñecos de palo con fondos de
acuarela). Para gastar menos, repite fondos: si dos escenas tienen exactamente la misma `escena`,
la imagen se genera una vez y se reutiliza gratis (en el YAML se marca con `&nombre` la primera vez
y con `*nombre` las siguientes; mira `los_rodeos.yaml`). La miniatura también puede ser una
ilustración: `miniatura: {texto: ..., escena: "qué se ve"}`.

Cada vídeo es un archivo `.yaml` de esta carpeta. El robot **Vídeo de historia** lo convierte en:

- un vídeo largo horizontal (1920x1080) con cabecera del canal, capítulos y pantalla final;
- un Short vertical por cada capítulo marcado con `short: true`;
- la descripción para YouTube con los capítulos (minutos), las fuentes y los créditos de las imágenes;
- los subtítulos (`.srt`) y la miniatura.

`ejemplo.yaml` enseña todos los tipos de escena. Es solo una prueba: no es para publicar.

## Estructura

```yaml
titulo: "Título del vídeo"
descripcion: "Texto para la descripción de YouTube"
hashtags: "#historia #economía"
miniatura: {texto: "Adiós a la peseta", resaltar: "peseta", cifra: "166,386", buscar_imagen: "peseta 1869"}

fuentes:                      # cada dato del guion apunta a una de estas
  - id: 1
    corta: "Banco de España (2002)"          # lo que se ve abajo en pantalla
    cita: "Autor (año). Título. Publicación." # lo que va en la descripción
    url: "https://..."

gancho: [escenas]             # opcional: lo primero que se oye, antes de la cabecera
capitulos:
  - titulo: "Nombre del capítulo"
    short: true               # true = sacar un Short de este capítulo
    gancho_short: [escenas]   # opcional: frase-gancho que solo sale en el Short
    escenas: [escenas]
cierre: [escenas]             # opcional: despedida
```

## Escenas

Todas llevan `voz` (lo que dice el narrador) y pueden llevar `fuente: 1` (o `[1, 2]`).
Si una palabra se pronuncia mal, se añade `pronunciar: "texto tal y como debe sonar"`.
Con `pausa: 2` la imagen se queda 2 segundos más en pantalla.

| tipo | qué se ve | datos |
|---|---|---|
| `titulo` | titular grande | `texto`, `resaltar` (palabras en color y subrayadas), `kicker` |
| `cifra` | número que cuenta | `valor`, `decimales`, `prefijo`, `sufijo`, `etiqueta`, `color` |
| `comparar` | dos barras | `titulo`, `izquierda: {etiqueta, valor, texto}`, `derecha: {...}` |
| `linea` | gráfico de línea | `titulo`, `subtitulo`, `valores`, `etiquetas`, `decimales`, `sufijo`, `marcas: [{indice, texto}]` |
| `barras` | gráfico de barras | `titulo`, `valores`, `etiquetas`, `destacar: [índices]` |
| `fecha` | fecha sobre línea de tiempo | `fecha`, `lugar` |
| `cita` | cita textual | `texto`, `autor`, `fecha` |
| `lista` | puntos uno a uno | `titulo`, `puntos` |
| `foto` | foto de época en sepia con zoom lento | imagen (ver abajo), `diseno` (`sangre`, `completa`, `marco`), `kicker`, `texto`, `sub`, `foco: [x, y]` |
| `boceto` | la figura se dibuja a trazos | imagen (ver abajo), `nombre`, `kicker`, `sub`, `detalle` (`bajo`, `medio`, `alto`), `revelar: true` (al final aparece la foto) |
| `mapa` | mapa con zoom y países que se colorean | `region` (`europa`, `espana`, `latinoamerica`, `america_sur`, `centroamerica`, `mundo`…) o `caja: [lon_min, lon_max, lat_min, lat_max]`, `titulo`, `grupos: [{paises, color, leyenda}]`, `etiquetas: [{pais, texto}]` |
| `esquema` | cajas y flechas | `modo` (`cadena` o `causas`), `titulo`, `nodos: [{etiqueta, texto, destacar}]`, `flechas` (textos), `resultado` (en `causas`), `nota` |
| `ilustracion` | ilustración generada con IA, con el estilo del canal y zoom lento | `escena` (qué se ve: lugar, época, gente, luz), `diseno` (`completa`, `sangre`, `marco`), `kicker`, `texto`, `sub` |
| `archivo` | clip de vídeo de archivo | `buscar` (en inglés funciona mejor), `texto`, `sub` |

### Imágenes (para `foto`, `boceto` y la miniatura)

- `imagen: "File:Nombre exacto.jpg"` → archivo concreto de Wikimedia Commons (lo más seguro).
- `buscar_imagen: "Laureano Figuerola"` → busca en Commons y coge la primera con licencia libre.
- `imagen: "imagenes/mi_foto.jpg"` → archivo propio dentro de `guiones/` (añade `credito: "..."`).

Solo se usan imágenes de dominio público, CC0, CC BY o CC BY-SA. El autor y la licencia
salen en pequeño en pantalla y en la descripción del vídeo.

Para los bocetos funcionan mejor los retratos y edificios con buen contraste y fondo sencillo.

### Ilustraciones con IA

Sirven para **ambientar** (una calle de 1868, una cola ante un banco en 1929) cuando no hay fotos.
No se usan para retratar a personas reales ni para «demostrar» un hecho: para eso, fotos de archivo o bocetos.
En pantalla llevan la marca «Ilustración» y la descripción del vídeo avisa de que están hechas con IA.
Cuanto más concreta sea la `escena` (época, ropa, edificios, luz), mejor sale. Cuestan unos céntimos cada una
y se guardan: si no cambias la descripción, no se vuelven a pagar. El estilo común está en `canal_historia.yaml`.

Colores que se pueden usar: `acento` (rojo anaranjado), `acento2` (dorado), `texto`, `suave`, `sube`, `baja`.

## Reglas del canal

- Cada dato con su fuente; si un dato no tiene fuente, no entra.
- Las citas, cortas y siempre con autor y fecha.
- Variar los tipos de escena: nada de cinco titulares seguidos; meter fotos, mapas y esquemas.
- Para que un Short cobre en TikTok tiene que pasar de 1 minuto; el robot lo avisa en el texto de cada Short.
