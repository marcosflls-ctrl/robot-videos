import React from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ajustar, conAlfa, F, FN, Humo, PaletaCtx, Particulas, prog, Rejilla, salida, suave, useFuentes, usePaleta } from "./comun";
import { Alerta, Cifra, Pregunta, PropsEscena, Titular } from "./escenas/basicas";
import { Comparar, Cronologia, Pila, Prensa } from "./escenas/estructura";
import { fuenteImg, Galeria, Imagen, Objeto, Orbita } from "./escenas/visuales";
import { Camara, Escena, Guion, Palabra, Transicion } from "./tipos";

const ESCENAS: Record<string, React.FC<PropsEscena>> = {
  cifra: Cifra, titular: Titular, alerta: Alerta, pregunta: Pregunta,
  objeto: Objeto, imagen: Imagen, galeria: Galeria, orbita: Orbita,
  comparar: Comparar, cronologia: Cronologia, pila: Pila, prensa: Prensa,
};

const T = 9; // fotogramas de transición (solapan la escena que sale con la que entra)
const ADELANTO = 6; // el contenido empieza a animarse durante la transición, no después (si no, queda un hueco vacío)

/** Movimiento de cámara a lo largo de la escena (p: 0 -> 1) */
const camara = (tipo: Camara | undefined, p: number, f: number): string => {
  const pulso = `translate(${Math.sin(f / 37) * 4}px, ${Math.cos(f / 43) * 4}px)`; // cámara en mano, muy leve
  switch (tipo) {
    case "acercar": return `${pulso} scale(${1 + 0.12 * p})`;
    case "alejar": return `${pulso} scale(${1.16 - 0.14 * p})`;
    case "paneo_izq": return `${pulso} scale(1.1) translateX(${60 - 120 * p}px)`;
    case "paneo_der": return `${pulso} scale(1.1) translateX(${-60 + 120 * p}px)`;
    case "subir": return `${pulso} scale(1.08) translateY(${80 - 160 * p}px)`;
    case "bajar": return `${pulso} scale(1.08) translateY(${-80 + 160 * p}px)`;
    case "orbita": return `${pulso} perspective(1800px) rotateY(${-10 + 20 * p}deg) scale(1.06)`;
    case "inclinar": return `${pulso} perspective(1800px) rotateX(${12 - 12 * p}deg) rotateZ(${-3 + 3 * p}deg) scale(${1.04 + 0.04 * p})`;
    default: return `${pulso} scale(${1 + 0.03 * p})`;
  }
};

/** Cómo entra la escena (e: 0 -> 1). La transición es la de ESTA escena. */
const entradaEstilo = (tipo: Transicion | undefined, e: number): { transform?: string; filter?: string; opacity: number } => {
  const ee = salida(e);
  const tarde = Math.max(0, (e - 0.3) / 0.7); // aparece cuando la anterior ya se ha ido
  switch (tipo) {
    case "barrido": return { transform: `translateX(${(1 - ee) * 110}%)`, filter: `blur(${(1 - ee) * 18}px)`, opacity: 1 };
    case "zoom": return { transform: `scale(${1 + (1 - ee) * 1.4})`, filter: `blur(${(1 - ee) * 14}px)`, opacity: tarde };
    case "giro": return { transform: `perspective(1600px) rotateY(${(1 - ee) * 90}deg)`, opacity: Math.min(tarde * 2, 1) };
    case "empuje": return { transform: `translateY(${(1 - ee) * 100}%)`, opacity: 1 };
    case "glitch": {
      const j = e < 1 ? Math.sin(e * 40) * 30 * (1 - e) : 0;
      return { transform: `translateX(${j}px)`, opacity: Math.min(1, tarde * 3), filter: e < 1 ? `drop-shadow(${12 * (1 - e)}px 0 0 rgba(255,0,80,0.8)) drop-shadow(${-12 * (1 - e)}px 0 0 rgba(0,220,255,0.8))` : undefined };
    }
    case "corte": return { opacity: e > 0.5 ? 1 : 0 };
    default: return { opacity: salida(tarde) }; // flash y fundido: el fogonazo lo pone la capa de arriba
  }
};

/** Cómo sale la escena (s: 0 -> 1). Va con la transición de la escena SIGUIENTE y siempre se apaga
 *  deprisa (a mitad de la transición ya no se ve), para que nada suyo quede encima del texto nuevo. */
const salidaEstilo = (tipo: Transicion | undefined, s: number): { transform?: string; filter?: string; opacity: number } => {
  const ss = suave(s);
  const apaga = 1 - Math.min(1, s * 3); // a un tercio de la transición ya no se ve
  switch (tipo) {
    case "barrido": return { transform: `translateX(${-ss * 110}%)`, filter: `blur(${ss * 18}px)`, opacity: apaga };
    case "zoom": return { transform: `scale(${1 - ss * 0.4})`, filter: `blur(${ss * 10}px)`, opacity: apaga };
    case "giro": return { transform: `perspective(1600px) rotateY(${-ss * 90}deg)`, opacity: apaga };
    case "empuje": return { transform: `translateY(${-ss * 100}%)`, opacity: apaga };
    case "corte": return { opacity: s > 0.5 ? 0 : 1 };
    default: return { opacity: apaga };
  }
};

const unir = (a: any, b: any): React.CSSProperties => ({
  transform: [a.transform, b.transform].filter(Boolean).join(" ") || undefined,
  filter: [a.filter, b.filter].filter(Boolean).join(" ") || undefined,
  opacity: a.opacity * b.opacity,
});

const BloqueEscena: React.FC<{ esc: Escena; durCore: number; siguiente?: Transicion }> = ({ esc, durCore, siguiente }) => {
  const f = useCurrentFrame() - T; // 0 = empieza la escena de verdad
  const { fps } = useVideoConfig();
  const pal = usePaleta();
  const Comp = ESCENAS[esc.tipo] || Titular;
  // sale en los mismos fotogramas en que entra la siguiente (los T últimos de esta escena)
  const e = prog(f, -T, T, (x) => x), s = siguiente ? prog(f, durCore - T, T, (x) => x) : 0;
  return (
    <AbsoluteFill style={unir(entradaEstilo(esc.transicion, e), salidaEstilo(siguiente, s))}>
      {esc.fondo && (
        <AbsoluteFill>
          <Img src={fuenteImg(esc.fondo)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.15 + 0.08 * (f / durCore)})`, filter: "blur(5px) brightness(0.5) saturate(1.25)" }} />
          <AbsoluteFill style={{ background: `linear-gradient(${conAlfa(pal.fondo1, 0.25)}, ${conAlfa(pal.fondo1, 0.35)} 45%, ${conAlfa(pal.fondo1, 0.75)})` }} />
        </AbsoluteFill>
      )}
      <AbsoluteFill style={{ transform: camara(esc.camara, Math.max(0, f) / durCore, f) }}>
        <Comp d={esc.datos || {}} f={f + ADELANTO} dur={durCore} fps={fps} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- SUBTÍTULOS
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9ñ]/g, "");

const trozos = (pal: Palabra[], claves: Set<string>) => {
  const out: Palabra[][] = [];
  let act: Palabra[] = [];
  pal.forEach((w, i) => {
    act.push(w);
    const fin = /[.,:;?!]$/.test(w.t);
    const sigueClave = i + 1 < pal.length && claves.has(norm(w.t)) && claves.has(norm(pal[i + 1].t)) && !fin;
    if (sigueClave && act.length < 4) return;
    if (act.length >= 3 || (act.length >= 2 && fin) || (fin && w.t.length > 6)) { out.push(act); act = []; }
  });
  if (act.length) out.push(act);
  return out;
};

const Subtitulos: React.FC<{ g: Guion }> = ({ g }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = usePaleta();
  const t = f / fps;
  const claves = React.useMemo(() => new Set(g.claves.map(norm)), [g.claves]);
  const lista = React.useMemo(() => trozos(g.palabras, claves), [g.palabras, claves]);
  const tr = lista.find((x) => x[0].ini - 0.05 <= t && t <= x[x.length - 1].fin + 0.15);
  if (!tr) return null;
  const ent = prog(t - tr[0].ini + 0.05, 0, 0.18, salida);
  const tamSub = ajustar(tr.map((w) => w.t).join(" "), FN.impacto, 960, 82, 1, 0, true);
  const estilo = g.subtitulos;
  const base: React.CSSProperties =
    estilo === "volteo" ? { transform: `perspective(800px) rotateX(${(1 - ent) * -85}deg)`, opacity: ent }
      : estilo === "pop" ? { transform: `scale(${0.6 + 0.4 * ent + Math.sin(ent * Math.PI) * 0.12})`, opacity: ent }
        : estilo === "deslizar" ? { transform: `translateY(${(1 - ent) * 40}px)`, opacity: ent, clipPath: `inset(0 0 ${(1 - ent) * 100}% 0)` }
          : { opacity: ent };
  return (
    <div style={{ position: "absolute", left: 40, right: 40, top: 1370, display: "flex", justifyContent: "center", gap: "0 32px", flexWrap: "wrap", ...base }}>
      {tr.map((w, i) => {
        const clave = claves.has(norm(w.t));
        const sonando = w.ini - 0.04 <= t && t <= w.fin + 0.04;
        const caja = estilo === "caja" && sonando;
        return (
          <span key={i} style={{
            fontFamily: F.impacto, fontSize: tamSub, lineHeight: 1.1, textTransform: "uppercase", display: "inline-block",
            color: caja ? p.fondo1 : clave ? p.acento : p.texto, padding: caja ? "0 14px" : 0,
            background: caja ? p.acento : "transparent", borderRadius: 10,
            transform: `scale(${sonando && !caja ? 1.08 : 1})`,
            WebkitTextStroke: caja ? undefined : `10px ${conAlfa("#0a0410", 0.9)}`, paintOrder: "stroke fill",
            textShadow: "0 6px 14px rgba(0,0,0,0.5)",
          }}>{w.t.replace(/[.,:;]$/, "")}</span>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- VÍDEO
export const Short: React.FC<Guion> = (g) => {
  const listas = useFuentes();
  const { fps } = useVideoConfig();
  const f = useCurrentFrame();
  const p = g.paleta;
  const escenas = g.escenas || [];
  // fogonazos blancos al empezar las escenas con transición «flash»
  const flash = escenas.map((e) => f - Math.round(e.ini * fps)).filter((d, i) => escenas[i].transicion === "flash" && d >= -2 && d < 10);
  const fogonazo = flash.length ? 1 - (flash[0] + 2) / 12 : 0;
  if (!listas) return null;
  return (
    <PaletaCtx.Provider value={p}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 38%, ${p.fondo2}, ${p.fondo1} 70%)`, overflow: "hidden" }}>
        {g.fondo === "rejilla" && <Rejilla />}
        {g.fondo === "humo" && <Humo />}
        <Particulas n={g.fondo === "particulas" ? 80 : 40} />
        {escenas.map((esc, i) => {
          const desde = Math.round(esc.ini * fps), hasta = Math.round(esc.fin * fps);
          const durCore = Math.max(1, hasta - desde);
          return (
            <Sequence key={i} from={desde - T} durationInFrames={durCore + T} layout="none">
              <BloqueEscena esc={esc.fondo || !g.fondos?.length ? esc : { ...esc, fondo: g.fondos[i % g.fondos.length] }} durCore={durCore} siguiente={escenas[i + 1]?.transicion} />
            </Sequence>
          );
        })}
        <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.65))", pointerEvents: "none" }} />
        <Subtitulos g={g} />
        {fogonazo > 0 && <AbsoluteFill style={{ background: "#fffaf2", opacity: Math.pow(fogonazo, 1.5) }} />}
        {g.marca && <div style={{ position: "absolute", top: 70, left: 0, right: 0, textAlign: "center", fontFamily: F.etiqueta, fontSize: 28, letterSpacing: 8, color: conAlfa(p.texto, 0.55) }}>{g.marca}</div>}
        {g.audio && <Audio src={staticFile(g.audio)} />}
      </AbsoluteFill>
    </PaletaCtx.Provider>
  );
};
