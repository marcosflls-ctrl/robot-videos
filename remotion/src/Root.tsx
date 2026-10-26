import React from "react";
import { Composition } from "remotion";
import { Short } from "./Short";
import { Guion } from "./tipos";

const ejemplo: Guion = {
  duracion: 6,
  palabras: [{ t: "Prueba", ini: 0.3, fin: 0.8 }, { t: "del", ini: 0.85, fin: 1.0 }, { t: "motor.", ini: 1.05, fin: 1.6 }],
  claves: ["motor"],
  paleta: { fondo1: "#0e0816", fondo2: "#2a1636", texto: "#faf4fa", suave: "#bcaec4", acento: "#ffc446", acento2: "#ff5caa", acento3: "#5adcff", peligro: "#ff4658" },
  fondo: "particulas",
  subtitulos: "volteo",
  escenas: [{ ini: 0, fin: 6, tipo: "cifra", datos: { valor: 24, etiqueta: "días" }, camara: "acercar", transicion: "flash" }],
};

export const Root: React.FC = () => (
  <Composition
    id="Short"
    component={Short as any}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={180}
    defaultProps={ejemplo as any}
    calculateMetadata={({ props }) => ({ durationInFrames: Math.ceil((props as any).duracion * 30) })}
  />
);
