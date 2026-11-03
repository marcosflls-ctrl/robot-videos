# Quizzes del canal Dale al Coco (antes TrivialXpress)

Cada archivo `.yaml` de esta carpeta es un Short. El robot **Vídeo de quiz** lo convierte en un vídeo
vertical de unos 50 segundos: gancho, 3 preguntas con cuenta atrás, respuesta y dato curioso, y un final
con una pregunta extra sin respuesta para que la gente comente. NO publica nada: el vídeo te llega por
Telegram (y a Drive) con el título, la descripción y las respuestas, y lo subes tú.

La identidad del canal (nombre, voz, colores, categorías, plan de la semana) está en `canal_quiz.yaml`.

## Plan de la semana y calendario

El robot se lanza **solo cada día a las 17:37** (hora de Madrid en invierno; 18:37 en verano) y monta el quiz
que tenga la **fecha** de ese día. Te llega por Telegram (y a Drive) para que lo subas tú.

| Lunes | Martes | Miércoles | Jueves | Viernes | Sábado | Domingo |
|---|---|---|---|---|---|---|
| Mitología | Historia | Geografía | Ciencia | Arte y letras | Deporte | **Vídeo largo** |

- Los quizzes **no se repiten**: cuando se acaban las fechas, hay que escribir más (el robot avisa).
- Los que no tienen `fecha` son **de reserva**: se usan si un día no tiene ninguno.
- Hay quizzes escritos hasta el **sábado 5 de diciembre de 2026**.

## Vídeo largo (domingos)

Horizontal, de unos 7–8 minutos: 24 preguntas en tres niveles (8 fáciles, 8 medias y 8 difíciles), con la
categoría de cada una, una pantalla de resultado («0–8: calentando motores… 23–24: ¡genio total!») y 14 s de
pantalla final para poner otros vídeos encima. Llegan también la **miniatura** y la **descripción con capítulos**.
Si pesa más de 45 MB, a Telegram llega una copia ligera; el de calidad completa está en Drive y en Artifacts.

```yaml
fecha: "2026-11-08"
formato: largo
categoria: variado
titulo: "24 preguntas de cultura general 🧠 ¿Cuántas aciertas?"
gancho: "Veinticuatro preguntas de cultura general..."   # se lee
gancho_pantalla: "24 preguntas de cultura general..."  # se ve
miniatura_de: 16        # (opcional) número de la pregunta (desde 0) cuya ilustración va en la miniatura
preguntas:
  - categoria: geografia
    dificultad: facil     # facil, media o dificil: decide el nivel
    pregunta: "..."
    ...                   # igual que en los Shorts
```

## Cómo se escribe un quiz

```yaml
fecha: "2026-11-09"             # el día en que el robot lo monta (sin fecha = de reserva)
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

- Short: 3 ilustraciones (unos céntimos cada una, en 1K) y 11 frases de voz (unas 3 peticiones a Gemini).
- Largo: 24 ilustraciones (alrededor de 1 €) y unas 77 frases de voz (unas 16 peticiones).
Lo ya generado se guarda: volver a montarlo sin cambios no gasta nada.
Con **Prueba rápida sin voz** se ve el montaje gratis (sin voz ni imágenes).
