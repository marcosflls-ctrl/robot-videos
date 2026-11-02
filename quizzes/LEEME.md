# Quizzes del canal Dale al Coco (antes TrivialXpress)

Cada archivo `.yaml` de esta carpeta es un Short. El robot **Vídeo de quiz** lo convierte en un vídeo
vertical de unos 50 segundos: gancho, 3 preguntas con cuenta atrás, respuesta y dato curioso, y un final
con una pregunta extra sin respuesta para que la gente comente. NO publica nada: el vídeo te llega por
Telegram (y a Drive) con el título, la descripción y las respuestas, y lo subes tú.

La identidad del canal (nombre, voz, colores, categorías, plan de la semana) está en `canal_quiz.yaml`.

## Plan de la semana

Si lanzas el robot sin escribir el nombre de un quiz, coge el primero sin publicar de la categoría del día:

| Lunes | Martes | Miércoles | Jueves | Viernes | Sábado | Domingo |
|---|---|---|---|---|---|---|
| Mitología | Historia | Geografía | Ciencia | Arte y letras | Deporte | Nivel Primaria |

## Cómo se escribe un quiz

```yaml
categoria: mitologia            # mitologia, historia, geografia, ciencia, arte, deporte o primaria
titulo: "Título para YouTube #quiz"
gancho: "Tres preguntas de mitología nórdica. La última casi nadie la acierta."
decir_gancho: "..."             # (opcional) cómo se lee, si es distinto de lo que se ve (p. ej. «6º» -> «sexto»)
preguntas:
  - pregunta: "¿Cómo se llama el martillo de Thor?"
    opciones: ["Gungnir", "Mjölnir", "Draupnir", "Gram"]   # de 2 a 4
    correcta: B
    decir: "..."                 # (opcional) cómo se lee la pregunta
    decir_respuesta: "¡La B: Mjölnir!"   # (opcional) si no, dice «¡La B: Mjölnir!» él solo
    dato: "Gungnir, en cambio, era la lanza de Odín."   # se lee y se ve al revelar
    dato_pantalla: "..."         # (opcional) el dato tal como se ve, si es distinto de como se lee
    dificultad: facil            # (opcional) facil, media o dificil; si no, va subiendo sola
    escena: "Qué se ve en la ilustración"
  - tipo: vf                     # verdadero o falso
    pregunta: "Odín dio uno de sus ojos a cambio de beber del pozo de la sabiduría."
    correcta: verdadero
    dato: "..."
    escena: "..."
extra: "Pregunta sin respuesta para los comentarios"
fuentes: ["enlaces para comprobar las respuestas"]
publicado: false                 # ponlo a true cuando lo subas: así el robot no lo vuelve a montar
```

## Normas

- **Cada respuesta, comprobada** en una fuente fiable (enciclopedia, organismo oficial, museo) y apuntada en
  `fuentes`. En un quiz, un error se nota enseguida en los comentarios.
- **3 preguntas de dificultad creciente** y la última, con trampa (algo que casi todo el mundo cree mal).
- El **dato** corto: una frase, dos como mucho. Si el vídeo pasa de 60 s, el robot avisa.
- Las **ilustraciones** ambientan, no retratan: nada de personas reales, ni personajes de películas,
  series o videojuegos, ni copias de cuadros u obras concretas (se ve el taller, el museo, el lugar).
- Para que no parezcan todos iguales: mezcla preguntas de 4 opciones con `vf` y cambia los ganchos.

## Gasto por vídeo

3 ilustraciones (unos céntimos cada una, en 1K) y 8 frases de voz (2 o 3 peticiones a Gemini).
Lo ya generado se guarda: volver a montarlo sin cambios no gasta nada.
Con **Prueba rápida sin voz** se ve el montaje gratis (sin voz ni imágenes).
