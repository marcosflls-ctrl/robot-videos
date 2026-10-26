import React from "react";
import { continueRender, delayRender, Easing, interpolate, random, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Paleta } from "./tipos";

export const W = 1080;
export const H = 1920;

export const PaletaCtx = React.createContext<Paleta>(null as any);
export const usePaleta = () => React.useContext(PaletaCtx);

export const F = {
  impacto: "Anton, sans-serif",
  cifra: "InterXB, sans-serif",
  negrita: "InterB, sans-serif",
  etiqueta: "GroteskB, sans-serif",
  texto: "GroteskM, sans-serif",
  prensa: "Fraunces, serif",
};

const FUENTES: [string, string][] = [
  ["Anton", "fuentes/Anton.ttf"],
  ["InterXB", "fuentes/Inter-ExtraBold.ttf"],
  ["InterB", "fuentes/Inter-Bold.ttf"],
  ["GroteskB", "fuentes/SpaceGrotesk-Bold.ttf"],
  ["GroteskM", "fuentes/SpaceGrotesk-Medium.ttf"],
  ["Fraunces", "fuentes/Fraunces-Black.ttf"],
];

let cargadas = false;
export const useFuentes = () => {
  const [handle] = React.useState(() => (cargadas ? null : delayRender("fuentes")));
  React.useEffect(() => {
    if (cargadas || handle === null) return;
    Promise.all(
      FUENTES.map(([n, f]) => {
        const ff = new FontFace(n, `url(${staticFile(f)})`);
        return ff.load().then((x) => (document as any).fonts.add(x));
      })
    ).then(() => {
      cargadas = true;
      continueRender(handle);
    });
  }, [handle]);
};

export const clamp = (x: number) => Math.max(0, Math.min(1, x));
export const suave = Easing.bezier(0.45, 0, 0.2, 1);
export const salida = Easing.bezier(0.16, 1, 0.3, 1); // rápido al principio, se posa despacio
export const prog = (f: number, ini: number, dur: number, easing = suave) =>
  easing(clamp((f - ini) / Math.max(1, dur)));

/** Rebote tipo muelle sin depender del fps */
export const muelle = (f: number, ini: number, fps: number, rigidez = 1) => {
  const t = Math.max(0, (f - ini) / fps) * 7 * rigidez;
  return 1 - Math.exp(-t) * Math.cos(t * 1.6);
};

export const conAlfa = (hex: string, a: number) => {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

/** Pastilla: «• 19 NOV», «RUMOR», «TODAVÍA NO»... */
export const Pastilla: React.FC<{ texto: string; color?: string; f: number; ini?: number; tam?: number }> = ({
  texto, color, f, ini = 0, tam = 30,
}) => {
  const p = usePaleta();
  const c = color || p.acento2;
  const a = prog(f, ini, 9, salida);
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: tam * 0.45, padding: `${tam * 0.35}px ${tam * 0.8}px`,
      borderRadius: 999, border: `2px solid ${c}`, background: conAlfa(p.fondo1, 0.85),
      color: p.texto, fontFamily: F.etiqueta, fontSize: tam, letterSpacing: 2, textTransform: "uppercase",
      opacity: a, transform: `translateY(${(1 - a) * 18}px) scale(${0.9 + 0.1 * a})`,
      boxShadow: `0 0 24px ${conAlfa(c, 0.45)}`,
    }}>
      <span style={{ width: tam * 0.38, height: tam * 0.38, borderRadius: 99, background: c, boxShadow: `0 0 12px ${c}` }} />
      {texto}
    </div>
  );
};

/** Tarjeta de cristal OPACA por dentro (así ninguna línea la atraviesa) */
export const Cristal: React.FC<{ children: React.ReactNode; ancho: number; alto?: number; color?: string; style?: React.CSSProperties }> = ({
  children, ancho, alto, color, style,
}) => {
  const p = usePaleta();
  const c = color || p.texto;
  return (
    <div style={{
      width: ancho, height: alto, borderRadius: 40, position: "relative", overflow: "hidden",
      background: `linear-gradient(160deg, ${conAlfa(p.fondo2, 0.97)}, ${conAlfa(p.fondo1, 0.97)})`,
      border: `2.5px solid ${conAlfa(c, 0.75)}`,
      boxShadow: `0 0 50px ${conAlfa(c === p.texto ? p.acento2 : c, 0.35)}, inset 0 1px 0 ${conAlfa("#ffffff", 0.25)}`,
      ...style,
    }}>
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(170deg, rgba(255,255,255,0.10), rgba(255,255,255,0) 45%)" }} />
      <div style={{ position: "relative", width: "100%", height: "100%" }}>{children}</div>
    </div>
  );
};

/** Partículas de polvo de luz que flotan */
export const Particulas: React.FC<{ n?: number; semilla?: string }> = ({ n = 60, semilla = "p" }) => {
  const f = useCurrentFrame();
  const p = usePaleta();
  return (
    <>
      {new Array(n).fill(0).map((_, i) => {
        const x = random(`${semilla}x${i}`) * W;
        const y0 = random(`${semilla}y${i}`) * H;
        const r = 1 + random(`${semilla}r${i}`) * 3;
        const v = 8 + random(`${semilla}v${i}`) * 25;
        const y = ((y0 - f * v / 30) % H + H) % H;
        const a = 0.25 + 0.45 * (0.5 + 0.5 * Math.sin(f / 20 + i));
        return <div key={i} style={{
          position: "absolute", left: x + Math.sin(f / 40 + i) * 12, top: y, width: r * 2, height: r * 2, borderRadius: 99,
          background: p.texto, opacity: a * (r / 4), boxShadow: `0 0 ${r * 4}px ${p.acento2}`,
        }} />;
      })}
    </>
  );
};

/** Suelo de rejilla en perspectiva (estilo synthwave / Vice City) */
export const Rejilla: React.FC = () => {
  const f = useCurrentFrame();
  const p = usePaleta();
  const desplaza = (f * 2.2) % 80;
  return (
    <div style={{ position: "absolute", left: -600, right: -600, bottom: -200, height: 1100, perspective: 600, overflow: "hidden" }}>
      <div style={{
        position: "absolute", inset: 0, transform: "rotateX(72deg)", transformOrigin: "50% 100%",
        backgroundImage: `linear-gradient(${conAlfa(p.acento2, 0.5)} 2px, transparent 2px), linear-gradient(90deg, ${conAlfa(p.acento2, 0.5)} 2px, transparent 2px)`,
        backgroundSize: "80px 80px", backgroundPosition: `0 ${desplaza}px`,
        maskImage: "linear-gradient(to top, black 30%, transparent 95%)", WebkitMaskImage: "linear-gradient(to top, black 30%, transparent 95%)",
      }} />
    </div>
  );
};

/** Manchas de color difusas que se mueven despacio */
export const Humo: React.FC = () => {
  const f = useCurrentFrame();
  const p = usePaleta();
  const manchas = [p.acento2, p.acento3, p.acento];
  return (
    <>
      {manchas.map((c, i) => (
        <div key={i} style={{
          position: "absolute", width: 900, height: 900, borderRadius: "50%",
          left: 540 - 450 + Math.sin(f / (90 + i * 30) + i * 2) * 380, top: 400 + i * 450 + Math.cos(f / (110 + i * 20) + i) * 260,
          background: `radial-gradient(circle, ${conAlfa(c, 0.22)}, transparent 65%)`, filter: "blur(30px)",
        }} />
      ))}
    </>
  );
};

/** Escala de tiempo: segundos -> fotogramas */
export const useS = () => {
  const { fps } = useVideoConfig();
  return (s: number) => Math.round(s * fps);
};

export const mezclar = interpolate;
