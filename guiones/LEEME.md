# Guiones del canal de historia económica

Cada vídeo es un archivo `.yaml` de esta carpeta. El robot **Vídeo de historia** lo convierte en:

- un vídeo largo horizontal (1920x1080) con cabecera del canal, capítulos y pantalla final;
- un Short vertical por cada capítulo marcado con `short: true`;
- la descripción para YouTube con los capítulos (minutos) y las fuentes, los subtítulos (`.srt`) y la miniatura.

`ejemplo.yaml` enseña todos los tipos de escena. Es solo una prueba: no es para publicar.

## Estructura

```yaml
titulo: "Título del vídeo"
descripcion: "Texto para la descripción de YouTube"
hashtags: "#historia #economía"
miniatura: {texto: "Adiós a la peseta", resaltar: "peseta", cifra: "166,386"}

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

| tipo | qué se ve | datos |
|---|---|---|
| `titulo` | titular grande | `texto`, `resaltar`, `kicker` (etiqueta pequeña) |
| `cifra` | número que cuenta | `valor`, `decimales`, `prefijo`, `sufijo`, `etiqueta`, `color` (`acento`, `acento2`, `sube`, `baja`) |
| `comparar` | dos barras | `titulo`, `izquierda: {etiqueta, valor, texto}`, `derecha: {...}` |
| `linea` | gráfico de línea | `titulo`, `valores`, `etiquetas`, `decimales`, `sufijo`, `marcas: [{indice, texto}]` |
| `barras` | gráfico de barras | `titulo`, `valores`, `etiquetas`, `destacar: [índices]` |
| `fecha` | fecha sobre línea de tiempo | `fecha`, `lugar` |
| `cita` | cita textual | `texto`, `autor`, `fecha` |
| `lista` | puntos uno a uno | `titulo`, `puntos` |
| `archivo` | clip de vídeo de archivo | `buscar` (en inglés funciona mejor), `texto`, `sub` |

## Reglas del canal

- Cada dato con su fuente; si un dato no tiene fuente, no entra.
- Las citas, cortas y siempre con autor y fecha.
- Variar los tipos de escena: nada de cinco titulares seguidos.
- Para que un Short cobre en TikTok tiene que pasar de 1 minuto; el robot lo avisa en el texto de cada Short.
