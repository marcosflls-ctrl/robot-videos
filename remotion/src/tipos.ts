// Guion visual: lo que escribe el director (la IA) para cada vídeo.
// Cada vídeo elige sus escenas, cámaras, transiciones, fondo y estilo de subtítulos,
// así que dos vídeos no tienen por qué parecerse.

export type Paleta = {
  fondo1: string; // color oscuro de fondo
  fondo2: string; // segundo color del degradado
  texto: string;
  suave: string; // texto secundario
  acento: string; // palabras clave, cifras
  acento2: string; // brillos, auras
  acento3: string; // tercer color (etiquetas)
  peligro: string; // rojo de alertas
};

export type Camara =
  | "acercar" | "alejar" | "paneo_izq" | "paneo_der" | "subir" | "bajar"
  | "orbita" | "inclinar" | "quieta";

export type Transicion = "corte" | "flash" | "barrido" | "zoom" | "giro" | "glitch" | "empuje";

export type Escena = {
  ini: number; // segundos
  fin: number;
  tipo: string; // cifra, titular, objeto, imagen, comparar, cronologia, pila, alerta, prensa, galeria, orbita, pregunta
  datos: any;
  camara?: Camara;
  transicion?: Transicion;
  fondo?: string; // imagen de fondo de esta escena (desenfocada y oscurecida)
};

export type Palabra = { t: string; ini: number; fin: number };

export type Guion = {
  duracion: number; // segundos
  audio?: string; // archivo en public/
  palabras: Palabra[];
  claves: string[]; // palabras que van en color
  paleta: Paleta;
  fondo: "particulas" | "rejilla" | "humo";
  subtitulos: "volteo" | "pop" | "caja" | "deslizar";
  marca?: string;
  fondos?: string[]; // imágenes que se turnan de fondo en las escenas que no traen el suyo
  escenas: Escena[];
};
