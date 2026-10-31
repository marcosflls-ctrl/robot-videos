# Guiones de los vídeos largos (historia económica y misterios)

Esta carpeta sirve para los tres canales. Lo que cambia de uno a otro (nombre, voz, velocidad de la voz,
colores, fuentes y estilo de las ilustraciones) está en su archivo `canal_<nombre>.yaml`:

| Canal | Archivo | Línea en el guion | Aspecto |
|---|---|---|---|
| Historia económica | `canal_historia.yaml` | (ninguna) | fondo oscuro, Fraunces y Space Grotesk, voz Charon |
| Misterios (Casos a trazos) | `canal_misterios.yaml` | `canal: misterios` | papel sepia, letra rotulada a mano, muñecos de palo, voz Orus |
| Ciencias medioambientales (Bitácora de la Tierra) | `canal_medioambiente.yaml` | `canal: medioambiente` | papel frío de cuaderno, Bricolage Grotesque, láminas de naturalista, voz Sulafat |

Sin la línea `canal:`, el robot usa el de historia. `prueba_medioambiente.yaml` es una prueba del aspecto
del canal de medio ambiente: no es para publicar.

### Canal de ciencias medioambientales

- Cada vídeo explica un **fenómeno** a fondo usando un **caso real** como hilo (temario: Geología, Riesgos
  naturales, Residuos sólidos y Economía del medio ambiente). Secciones que se turnan: *El suceso*,
  *Cómo funciona* y *El debate, con datos*.
- Fuentes de primera mano (IGN, AEMET, Copernicus, IPCC, NASA, NOAA, artículos revisados). La prensa solo
  para hechos que no publica ningún organismo, y siempre citada.
- Los debates se cuentan con sus dos posturas, sin alarmismo y sin consignas.
- Las fuentes del canal no tienen subíndices: escribe `CO2`, no `CO₂` (saldría un cuadrado).
- Las ilustraciones son láminas de naturalista: cortes del terreno, paisajes y figuras humanas diminutas
  sin rasgos, solo para dar la escala.

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

## Tres títulos y tres miniaturas (prueba A/B)

YouTube deja probar hasta **3 títulos y 3 miniaturas** en cada vídeo largo («Prueba A/B», en YouTube Studio)
y se queda con el que más tiempo de visualización consigue. Por eso cada guion lleva `titulos` y `miniaturas`:

- **Que sean de verdad distintos**, no la misma frase cambiando una palabra: si se parecen mucho, la prueba
  tarda más y no aclara nada. Un enfoque por título: la cifra, el misterio, la pregunta.
- **Una idea por miniatura**, 3–5 palabras, con su propia imagen (`escena`, `imagen` o `buscar_imagen`).
  Si no trae imagen, usa la primera del vídeo. Con `lado: izquierda`, la imagen va a la izquierda y el texto
  a la derecha, para que se distinga más.
- Los títulos, como mucho 100 letras (el robot avisa si alguno pasa).
- **Solo miniaturas y títulos:** al lanzar el robot, en «Qué montar» elige `miniaturas`. No gasta voz ni
  monta vídeo: solo las ilustraciones nuevas de las miniaturas (unos céntimos). Sirve para vídeos ya subidos.

Siguen valiendo `titulo` y `miniatura` (una sola) en los guiones antiguos.

## Estructura

```yaml
titulos:                      # hasta 3, para la prueba A/B de YouTube (el 1.º es el que se sube)
  - "Título principal"
  - "Otro enfoque"
  - "Otro más"
descripcion: "Texto para la descripción de YouTube"
hashtags: "#historia #economía"
miniaturas:                   # hasta 3; cada una con su texto, cifra e imagen
  - {texto: "Adiós a la peseta", resaltar: "peseta", cifra: "166,386", buscar_imagen: "peseta 1869"}
  - {texto: "Otra idea", resaltar: "idea", cifra: "2002", lado: izquierda}

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

### Montar solo algunos Shorts

Al lanzar el robot, en «Solo estos Shorts» escribe los números de capítulo separados por comas (por
ejemplo `1,4,6`) para montar solo esos. Vacío = todos los capítulos marcados con `short: true`.

### Velocidad de la voz

En el archivo del canal, `velocidad_voz: 1.1` hace la voz un 10 % más rápida (de 0.8 a 1.3). Se aplica al
montar, sobre las voces ya guardadas: cambiarla no gasta cupo de Gemini ni cambia el tono. Para probar otra
velocidad sin tocar el archivo, elige «Velocidad de la voz» al lanzar el robot.

## Reglas del canal

- Cada dato con su fuente; si un dato no tiene fuente, no entra.
- Las citas, cortas y siempre con autor y fecha.
- Variar los tipos de escena: nada de cinco titulares seguidos; meter fotos, mapas y esquemas.
- Para que un Short cobre en TikTok tiene que pasar de 1 minuto; el robot lo avisa en el texto de cada Short.
