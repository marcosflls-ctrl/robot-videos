import React from "react";
import { Img, random, staticFile } from "remotion";
import { conAlfa, Cristal, F, muelle, Pastilla, prog, salida, usePaleta } from "../comun";
import { PropsEscena } from "./basicas";

/** «objeto:ps5» -> biblioteca de recortes; «http...» tal cual; si no, un archivo de public/ */
export const fuenteImg = (src: string) => {
  if (!src) return "";
  if (src.startsWith("http")) return src;
  if (src.startsWith("objeto:")) return staticFile(`objetos/${src.slice(7)}.png`);
  return staticFile(src);
};

// ---------------------------------------------------------------- OBJETO
// Objeto real recortado, flotando, con aura: escudo (óvalo de energía con rayos y bolas de luz),
// halo (resplandor con rayos que giran) o ninguna. Debajo, una palabra grande espaciada.
export const Objeto: React.FC<PropsEscena> = ({ d, f, fps }) => {
  const p = usePaleta();
  const m = muelle(f, 0, fps, 0.7);
  const flota = Math.sin(f / 22) * 14;
  const aura = d.aura || "halo";
  const alto = d.alto || 820;
  const ta = Math.round(fps * 0.6);
  const pa = prog(f, ta, 12, salida);
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {aura === "halo" && (
        <div style={{
          position: "absolute", left: 540 - 520, top: 640 - 520, width: 1040, height: 1040, borderRadius: "50%", opacity: m,
          background: `conic-gradient(from ${f * 0.8}deg, transparent 0deg, ${conAlfa(p.acento2, 0.25)} 20deg, transparent 40deg, transparent 90deg, ${conAlfa(p.acento3, 0.2)} 110deg, transparent 130deg, transparent 180deg, ${conAlfa(p.acento2, 0.25)} 200deg, transparent 220deg, transparent 270deg, ${conAlfa(p.acento, 0.18)} 290deg, transparent 310deg)`,
          maskImage: "radial-gradient(circle, black 20%, transparent 70%)", WebkitMaskImage: "radial-gradient(circle, black 20%, transparent 70%)",
        }} />
      )}
      <div style={{ position: "absolute", left: 540 - 380, top: 640 - 380, width: 760, height: 760, borderRadius: "50%", background: `radial-gradient(circle, ${conAlfa(p.acento2, 0.35)}, transparent 65%)`, opacity: m }} />
      {/* sombra en el suelo */}
      <div style={{ position: "absolute", left: 540 - 260, top: 640 + alto / 2 - 20, width: 520, height: 60, borderRadius: "50%", background: "rgba(0,0,0,0.55)", filter: "blur(18px)", opacity: m, transform: `scaleX(${1 - flota / 200})` }} />
      <div style={{
        position: "absolute", left: 0, right: 0, top: 640 - alto / 2, height: alto, display: "flex", justifyContent: "center",
        transform: `perspective(1500px) translateY(${flota + (1 - m) * 160}px) rotateY(${(1 - m) * 35 + Math.sin(f / 40) * 6}deg) scale(${0.6 + 0.4 * m})`,
        opacity: Math.min(1, m * 1.5),
      }}>
        <Img src={fuenteImg(d.src)} style={{ height: "100%", objectFit: "contain", filter: `drop-shadow(0 30px 40px rgba(0,0,0,0.6)) drop-shadow(0 0 30px ${conAlfa(p.acento2, 0.35)})` }} />
      </div>
      {aura === "escudo" && pa > 0 && <Escudo f={f - ta} p={pa} cx={540} cy={640} rx={420} ry={alto / 2 + 90} />}
      {d.etiqueta && (
        <div style={{
          position: "absolute", top: 640 + alto / 2 + 70, left: 0, right: 0, textAlign: "center", fontFamily: F.cifra, fontSize: 104,
          color: p.texto, letterSpacing: 16 + 26 * (1 - prog(f, 10, 18, salida)), opacity: prog(f, 10, 10),
          textShadow: `0 0 40px ${conAlfa(p.acento2, 0.6)}`,
        }}>{String(d.etiqueta).toUpperCase()}</div>
      )}
      {d.pastilla && <div style={{ position: "absolute", top: 640 - alto / 2 - 60, right: 120 }}><Pastilla texto={d.pastilla} f={f} ini={16} /></div>}
    </div>
  );
};

/** Óvalo de energía con rayos que chisporrotean y bolas de luz que dan vueltas */
export const Escudo: React.FC<{ f: number; p: number; cx: number; cy: number; rx: number; ry: number }> = ({ f, p, cx, cy, rx, ry }) => {
  const pal = usePaleta();
  const semilla = Math.floor(f / 3);
  const rayos: string[] = [];
  for (let k = 0; k < 9; k++) {
    let ang = random(`e${semilla}-${k}`) * Math.PI * 2;
    let x = cx + Math.cos(ang) * rx, y = cy + Math.sin(ang) * ry;
    let d = `M${x} ${y}`, dir = ang + Math.PI;
    for (let j = 0; j < 6; j++) {
      dir += (random(`e${semilla}-${k}-${j}`) - 0.5) * 1.8;
      const l = 20 + random(`l${semilla}-${k}-${j}`) * 35;
      x += Math.cos(dir) * l; y += Math.sin(dir) * l;
      d += ` L${x} ${y}`;
    }
    rayos.push(d);
  }
  return (
    <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0, opacity: p }}>
      <ellipse cx={cx} cy={cy} rx={rx * (0.9 + 0.1 * p)} ry={ry * (0.9 + 0.1 * p)} fill={conAlfa(pal.acento2, 0.08)} stroke={conAlfa(pal.acento2, 0.7)} strokeWidth={3}
        style={{ filter: `drop-shadow(0 0 18px ${pal.acento2})` }} />
      {rayos.map((d, i) => <path key={i} d={d} stroke={conAlfa("#ffd6f0", 0.9)} strokeWidth={2.5} fill="none" style={{ filter: `drop-shadow(0 0 8px ${pal.acento2})` }} />)}
      {[0, 1, 2].map((k) => {
        const a = f / 18 * (1 + 0.3 * k) + k * 2.1;
        const x = cx + Math.cos(a) * rx, y = cy + Math.sin(a) * ry;
        return <g key={k}>
          <circle cx={x} cy={y} r={34} fill={conAlfa("#fff", 0.12)} />
          <circle cx={x} cy={y} r={14} fill={conAlfa("#fff", 0.6)} style={{ filter: `drop-shadow(0 0 16px ${pal.acento2})` }} />
        </g>;
      })}
    </svg>
  );
};

// ---------------------------------------------------------------- IMAGEN
// Fotograma o foto. Marcos: completa (a sangre, con zoom lento), cristal (tarjeta que entra girando
// en 3D con un reflejo que la cruza) o polaroid (cae inclinada). Efecto opcional: lupa sobre un punto.
export const Imagen: React.FC<PropsEscena> = ({ d, f, dur, fps }) => {
  const p = usePaleta();
  const marco = d.marco || "cristal";
  const src = fuenteImg(d.src);
  const m = muelle(f, 0, fps, 0.7);
  const avance = f / Math.max(1, dur);
  if (marco === "completa") {
    return (
      <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
        <Img src={src} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.08 + 0.12 * avance}) translateX(${(avance - 0.5) * -40}px)` }} />
        <div style={{ position: "absolute", inset: 0, background: `linear-gradient(to bottom, ${conAlfa(p.fondo1, 0.2)}, ${conAlfa(p.fondo1, 0.1)} 40%, ${conAlfa(p.fondo1, 0.85)})` }} />
        {d.lupa && <Lupa src={src} f={f} fps={fps} x={d.lupa.x} y={d.lupa.y} completa />}
        {d.etiqueta && <EtiquetaGrande texto={d.etiqueta} f={f} top={1080} />}
      </div>
    );
  }
  const ancho = d.ancho || (marco === "polaroid" ? 760 : 900);
  const alto = d.alto || (marco === "polaroid" ? 900 : 560);
  const brillo = ((f * 1.0) % 110) / 70;
  const giroIn = marco === "polaroid" ? 0 : (1 - m) * (d.desde === "izq" ? -80 : 80);
  const inclina = marco === "polaroid" ? -6 + (1 - m) * -25 : Math.sin(f / 35) * 4;
  const caida = marco === "polaroid" ? (1 - m) * -700 : 0;
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{
        position: "absolute", left: 540 - ancho / 2, top: 620 - alto / 2, width: ancho, height: alto,
        transform: `perspective(1600px) translateY(${caida}px) rotateY(${giroIn}deg) rotateZ(${inclina}deg) scale(${0.8 + 0.2 * m})`,
      }}>
        {marco === "polaroid" ? (
          <div style={{ width: "100%", height: "100%", background: "#f4efe6", padding: "34px 34px 140px", boxSizing: "border-box", boxShadow: "0 40px 80px rgba(0,0,0,0.6)" }}>
            <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            {d.etiqueta && <div style={{ fontFamily: F.impacto, fontSize: 64, color: "#222", textAlign: "center", marginTop: 26 }}>{d.etiqueta}</div>}
          </div>
        ) : (
          <div style={{ width: "100%", height: "100%", borderRadius: 34, overflow: "hidden", border: `3px solid ${conAlfa("#fff", 0.8)}`, boxShadow: `0 0 60px ${conAlfa(p.acento2, 0.45)}, 0 40px 80px rgba(0,0,0,0.6)`, position: "relative" }}>
            <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.05 + 0.08 * avance})` }} />
            {brillo < 1 && <div style={{ position: "absolute", top: -100, bottom: -100, width: 140, left: `${-30 + brillo * 140}%`, background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.28), transparent)", transform: "rotate(18deg)" }} />}
          </div>
        )}
      </div>
      {d.lupa && <Lupa src={src} f={f} fps={fps} x={d.lupa.x} y={d.lupa.y} caja={{ x: 540 - ancho / 2, y: 620 - alto / 2, w: ancho, h: alto }} />}
      {marco !== "polaroid" && d.etiqueta && <EtiquetaGrande texto={d.etiqueta} f={f} top={620 + alto / 2 + 60} />}
      {d.pastilla && <div style={{ position: "absolute", top: 620 - alto / 2 - 90, left: 0, right: 0, display: "flex", justifyContent: "center" }}><Pastilla texto={d.pastilla} f={f} ini={12} /></div>}
    </div>
  );
};

const EtiquetaGrande: React.FC<{ texto: string; f: number; top: number }> = ({ texto, f, top }) => {
  const p = usePaleta();
  return <div style={{
    position: "absolute", top, left: 0, right: 0, textAlign: "center", fontFamily: F.cifra, fontSize: 96, color: p.texto,
    letterSpacing: 14 + 24 * (1 - prog(f, 8, 16, salida)), opacity: prog(f, 8, 10), textShadow: `0 0 40px ${conAlfa(p.acento2, 0.6)}, 0 4px 0 rgba(0,0,0,0.4)`,
  }}>{texto.toUpperCase()}</div>;
};

/** Lupa circular que se acerca a un punto (x, y en 0..1 de la imagen) y lo amplía */
const Lupa: React.FC<{ src: string; f: number; fps: number; x: number; y: number; completa?: boolean; caja?: { x: number; y: number; w: number; h: number } }> = ({ src, f, fps, x, y, completa, caja }) => {
  const p = usePaleta();
  const c = caja || { x: 0, y: 0, w: 1080, h: 1920 };
  const ini = Math.round(fps * 0.8);
  const pr = prog(f, ini, 16, salida);
  if (pr <= 0) return null;
  const R = 230, Z = 2.4;
  const px = c.x + c.w * x, py = c.y + c.h * y;
  const lx = 540 + (px - 540) * pr * 0.4, ly = (py + 260) * (1 - pr) + (py - 40) * pr;
  return (
    <div style={{ position: "absolute", left: lx - R, top: ly - R, width: R * 2, height: R * 2, borderRadius: "50%", overflow: "hidden", border: `6px solid ${p.texto}`, boxShadow: `0 0 40px ${conAlfa(p.acento2, 0.7)}, 0 20px 50px rgba(0,0,0,0.6)`, transform: `scale(${pr})` }}>
      <Img src={src} style={{ position: "absolute", width: c.w * Z, height: c.h * Z, objectFit: "cover", left: R - c.w * x * Z, top: R - c.h * y * Z }} />
    </div>
  );
};

// ---------------------------------------------------------------- GALERÍA
// Rejilla de fotogramas que aparecen uno a uno; al final la cámara se mete en uno de ellos.
export const Galeria: React.FC<PropsEscena> = ({ d, f, dur, fps }) => {
  const p = usePaleta();
  const imgs: string[] = d.imagenes || [];
  const foco = d.foco ?? 0;
  const cols = 2, w = 460, h = 330, gap = 30;
  const filas = Math.ceil(imgs.length / cols);
  const x0 = 540 - (cols * w + (cols - 1) * gap) / 2, y0 = 640 - (filas * h + (filas - 1) * gap) / 2;
  const entra = prog(f, dur * 0.55, dur * 0.4, salida);
  const fx = x0 + (foco % cols) * (w + gap) + w / 2, fy = y0 + Math.floor(foco / cols) * (h + gap) + h / 2;
  const z = 1 + entra * 1.9;
  return (
    <div style={{ position: "absolute", inset: 0, transform: `translate(${(540 - fx) * entra}px, ${(640 - fy) * entra}px) scale(${z})`, transformOrigin: `${fx}px ${fy}px` }}>
      {imgs.map((s, i) => {
        const a = muelle(f, i * 4, fps, 0.9);
        const x = x0 + (i % cols) * (w + gap), y = y0 + Math.floor(i / cols) * (h + gap);
        return <div key={i} style={{
          position: "absolute", left: x, top: y, width: w, height: h, borderRadius: 24, overflow: "hidden",
          border: `2px solid ${conAlfa("#fff", i === foco ? 0.9 : 0.4)}`, opacity: Math.min(1, a) * (i === foco ? 1 : 1 - entra * 0.7),
          transform: `perspective(1200px) rotateX(${(1 - a) * 50}deg) scale(${0.7 + 0.3 * a})`, boxShadow: `0 20px 40px rgba(0,0,0,0.5)`,
        }}><Img src={fuenteImg(s)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /></div>;
      })}
      {d.etiqueta && <div style={{ position: "absolute", top: y0 - 140, left: 0, right: 0, display: "flex", justifyContent: "center", opacity: 1 - entra }}><Pastilla texto={d.etiqueta} f={f} ini={4} /></div>}
    </div>
  );
};

// ---------------------------------------------------------------- ÓRBITA
// Algo en el centro (objeto o palabra) y satélites que giran a su alrededor en 3D.
export const Orbita: React.FC<PropsEscena> = ({ d, f, fps }) => {
  const p = usePaleta();
  const sats: any[] = d.satelites || [];
  const m = muelle(f, 0, fps, 0.8);
  const rx = 400, ry = 170, cy = 660;
  const items = sats.map((s, i) => {
    const a = f / 45 + (i / sats.length) * Math.PI * 2;
    const prof = Math.sin(a); // -1 detrás, 1 delante
    return { s, i, x: 540 + Math.cos(a) * rx * m, y: cy + prof * ry * m, z: prof, esc: 0.7 + 0.3 * (prof + 1) / 2 };
  });
  const sat = (it: any) => (
    <div key={it.i} style={{ position: "absolute", left: it.x, top: it.y, transform: `translate(-50%,-50%) scale(${it.esc})`, opacity: (0.45 + 0.55 * (it.z + 1) / 2) * Math.min(1, m * 1.4), zIndex: it.z > 0 ? 3 : 1 }}>
      {typeof it.s === "string" && it.s.match(/\.(png|jpe?g|webp)$|^objeto:/) ? (
        <div style={{ width: 260, height: 190, borderRadius: 22, overflow: "hidden", border: `2px solid ${conAlfa("#fff", 0.7)}` }}><Img src={fuenteImg(it.s)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /></div>
      ) : <Pastilla texto={String(it.s)} f={99} tam={34} />}
    </div>
  );
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0, zIndex: 0 }}>
        <ellipse cx={540} cy={cy} rx={rx * m} ry={ry * m} fill="none" stroke={conAlfa(p.acento2, 0.35)} strokeWidth={2} strokeDasharray="8 10" />
      </svg>
      {items.filter((it) => it.z <= 0).map(sat)}
      <div style={{ position: "absolute", left: 0, right: 0, top: cy - 230, height: 460, display: "flex", justifyContent: "center", alignItems: "center", zIndex: 2, transform: `scale(${0.6 + 0.4 * m})` }}>
        {d.centro && String(d.centro).match(/\.(png|jpe?g|webp)$|^objeto:/)
          ? <Img src={fuenteImg(d.centro)} style={{ height: 460, objectFit: "contain", filter: `drop-shadow(0 0 30px ${conAlfa(p.acento2, 0.6)})` }} />
          : <div style={{ fontFamily: F.cifra, fontSize: 120, color: p.texto, textShadow: `0 0 40px ${p.acento2}` }}>{String(d.centro || "").toUpperCase()}</div>}
      </div>
      {items.filter((it) => it.z > 0).map(sat)}
      {d.etiqueta && <EtiquetaGrande texto={d.etiqueta} f={f} top={1000} />}
    </div>
  );
};
