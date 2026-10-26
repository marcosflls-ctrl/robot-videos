import React from "react";
import { Img } from "remotion";
import { ajustar, conAlfa, Cristal, F, FN, muelle, Pastilla, prog, salida, usePaleta } from "../comun";
import { Grieta, PropsEscena } from "./basicas";
import { fuenteImg } from "./visuales";

const esImagen = (s: any) => typeof s === "string" && /\.(png|jpe?g|webp)$|^objeto:/.test(s);

/** Un lado de una comparación: objeto recortado, foto o tarjeta con texto */
const Lado: React.FC<{ it: any; f: number; ini: number; fps: number; ancho: number }> = ({ it, f, ini, fps, ancho }) => {
  const p = usePaleta();
  const m = muelle(f, ini, fps, 0.8);
  const mal = it.estado === "mal", bien = it.estado === "ok";
  const color = mal ? p.peligro : bien ? p.acento3 : p.texto;
  let cuerpo: React.ReactNode;
  if (esImagen(it.src) && String(it.src).startsWith("objeto:")) {
    cuerpo = <Img src={fuenteImg(it.src)} style={{ height: it.alto || 600, maxWidth: ancho, objectFit: "contain", filter: `drop-shadow(0 20px 30px rgba(0,0,0,0.6)) ${mal ? "grayscale(0.6)" : ""}` }} />;
  } else if (esImagen(it.src)) {
    cuerpo = <div style={{ width: ancho, height: 420, borderRadius: 28, overflow: "hidden", border: `3px solid ${conAlfa(color, 0.8)}` }}><Img src={fuenteImg(it.src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} /></div>;
  } else {
    cuerpo = (
      <Cristal ancho={ancho} alto={360} color={mal ? p.peligro : undefined}>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ fontFamily: F.cifra, fontSize: ajustar(String(it.texto || ""), FN.cifra, ancho - 60, 120, 2), color, textAlign: "center", lineHeight: 1.05 }}>{it.texto}</div>
          {it.sub && <div style={{ fontFamily: F.etiqueta, fontSize: ajustar(it.sub, FN.etiqueta, ancho - 60, 30, 1, 3, true), color: p.suave, letterSpacing: 3, marginTop: 10, textTransform: "uppercase" }}>{it.sub}</div>}
        </div>
        {mal && <Grieta f={f} ini={ini + 14} ancho={ancho} alto={360} semilla={String(it.texto)} />}
      </Cristal>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 26, opacity: Math.min(1, m * 1.4), transform: `perspective(1400px) translateY(${(1 - m) * 120}px) rotateX(${(1 - m) * 40}deg)` }}>
      {cuerpo}
      {it.etiqueta && <Pastilla texto={it.etiqueta} color={mal ? p.peligro : undefined} f={f} ini={ini + 8} />}
    </div>
  );
};

// ---------------------------------------------------------------- COMPARAR
// Dos cosas enfrentadas. Modos: vs (paneles con insignia VS en medio), bifurcacion (un tronco
// que se abre en dos ramas) y antes_despues (cortinilla que pasa de una a otra).
export const Comparar: React.FC<PropsEscena> = ({ d, f, dur, fps }) => {
  const p = usePaleta();
  const modo = d.modo || "vs";
  const a = d.a || {}, b = d.b || {};
  if (modo === "bifurcacion") {
    const tr = prog(f, 0, 14, salida);
    return (
      <div style={{ position: "absolute", inset: 0 }}>
        {d.arriba && <div style={{ position: "absolute", top: 150, left: 0, right: 0, display: "flex", justifyContent: "center" }}><Pastilla texto={d.arriba} f={f} /></div>}
        <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0 }}>
          {[-1, 1].map((s) => (
            <path key={s} d={`M540 250 L540 330 C540 420 ${540 + s * 250} 400 ${540 + s * 250} 500`} fill="none" stroke={conAlfa("#fff", 0.75)} strokeWidth={4}
              strokeDasharray={600} strokeDashoffset={600 * (1 - tr)} style={{ filter: `drop-shadow(0 0 10px ${p.acento2})` }} />
          ))}
        </svg>
        <div style={{ position: "absolute", top: 500, left: 0, right: 0, display: "flex", justifyContent: "space-around", alignItems: "flex-end", padding: "0 30px" }}>
          <Lado it={a} f={f} ini={8} fps={fps} ancho={440} />
          <Lado it={b} f={f} ini={18} fps={fps} ancho={440} />
        </div>
      </div>
    );
  }
  if (modo === "antes_despues") {
    const corte = prog(f, dur * 0.45, 18);
    return (
      <div style={{ position: "absolute", inset: 0 }}>
        <div style={{ position: "absolute", top: 260, left: 0, right: 0, display: "flex", justifyContent: "center" }}><Lado it={a} f={f} ini={0} fps={fps} ancho={820} /></div>
        <div style={{ position: "absolute", top: 260, left: 0, right: 0, display: "flex", justifyContent: "center", clipPath: `inset(0 ${100 - corte * 100}% 0 0)` }}><Lado it={b} f={f} ini={0} fps={fps} ancho={820} /></div>
        {corte > 0 && corte < 1 && <div style={{ position: "absolute", top: 200, height: 640, left: 130 + 820 * corte, width: 6, background: p.acento, boxShadow: `0 0 20px ${p.acento}` }} />}
      </div>
    );
  }
  // vs
  const vs = muelle(f, 14, fps, 1.3);
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {d.arriba && <div style={{ position: "absolute", top: 170, left: 0, right: 0, display: "flex", justifyContent: "center" }}><Pastilla texto={d.arriba} f={f} /></div>}
      <div style={{ position: "absolute", top: 380, left: 0, right: 0, display: "flex", justifyContent: "space-between", padding: "0 40px" }}>
        <div style={{ transform: `translateX(${(1 - prog(f, 0, 12, salida)) * -500}px)` }}><Lado it={a} f={f} ini={0} fps={fps} ancho={430} /></div>
        <div style={{ transform: `translateX(${(1 - prog(f, 4, 12, salida)) * 500}px)` }}><Lado it={b} f={f} ini={4} fps={fps} ancho={430} /></div>
      </div>
      <div style={{
        position: "absolute", left: 540 - 85, top: 520, width: 170, height: 170, borderRadius: "50%", background: p.acento,
        display: "flex", alignItems: "center", justifyContent: "center", fontFamily: F.impacto, fontSize: 84, color: p.fondo1,
        transform: `scale(${Math.max(0, vs)}) rotate(${(1 - vs) * 180}deg)`, boxShadow: `0 0 60px ${p.acento}`,
      }}>VS</div>
    </div>
  );
};

// ---------------------------------------------------------------- CRONOLOGÍA
// Hitos con fecha sobre un eje; la cámara viaja de uno a otro. El eje va POR DETRÁS de las tarjetas
// (que son opacas), así que nunca las cruza.
export const Cronologia: React.FC<PropsEscena> = ({ d, f, dur, fps }) => {
  const p = usePaleta();
  const hitos: any[] = d.hitos || [];
  const n = Math.max(1, hitos.length);
  const vertical = (d.orientacion || "vertical") === "vertical";
  const paso = vertical ? 470 : 640;
  const tramo = dur / n;
  // posición de cámara: se mueve suave al hito actual
  let pos = 0;
  for (let k = 1; k < n; k++) pos += prog(f, k * tramo - 8, 16);
  const despl = pos * paso;
  const eje = vertical
    ? <div style={{ position: "absolute", left: 540 - 2, top: -2000, height: 6000, width: 4, background: `linear-gradient(${conAlfa("#fff", 0.1)}, ${conAlfa("#fff", 0.7)}, ${conAlfa("#fff", 0.1)})`, zIndex: 0 }} />
    : <div style={{ position: "absolute", top: 640 - 2, left: -2000, width: 8000, height: 4, background: conAlfa("#fff", 0.6), zIndex: 0 }} />;
  return (
    <div style={{ position: "absolute", inset: 0, transform: vertical ? `translateY(${-despl}px)` : `translateX(${-despl}px)` }}>
      {eje}
      {hitos.map((h, i) => {
        const ini = i * tramo;
        const m = muelle(f, ini, fps, 0.9);
        const activo = Math.round(pos) === i;
        const mal = h.estado === "mal", futuro = h.estado === "futuro";
        const color = mal ? p.peligro : futuro ? p.acento3 : p.texto;
        const x = vertical ? 540 : 540 + i * paso, y = vertical ? 640 + i * paso : 640;
        if (f < ini - 2) return null;
        return (
          <div key={i} style={{ position: "absolute", left: x - 230, top: y - 190, width: 460, height: 380, zIndex: 2, opacity: Math.min(1, m * 1.4) * (activo ? 1 : 0.55), transform: `perspective(1400px) rotateY(${(1 - m) * 70}deg) scale(${(activo ? 1 : 0.82) * (0.8 + 0.2 * m)})` }}>
            <Cristal ancho={460} alto={380} color={mal ? p.peligro : futuro ? p.acento3 : undefined} style={futuro ? { borderStyle: "dashed" } : {}}>
              <div style={{ position: "absolute", top: 34, left: 36, fontFamily: F.etiqueta, fontSize: 24, letterSpacing: 4, color: p.suave }}>{(h.arriba || "").toUpperCase()}</div>
              <div style={{ position: "absolute", top: 70, left: 0, right: 0, textAlign: "center", fontFamily: F.cifra, fontSize: ajustar(String(h.fecha), FN.cifra, 400, 110), color }}>{h.fecha}</div>
              <div style={{ position: "absolute", top: 230, left: 30, right: 30, textAlign: "center", fontFamily: F.etiqueta, fontSize: ajustar(String(h.texto || ""), FN.etiqueta, 400, 34, 2), color: p.texto, lineHeight: 1.2 }}>{h.texto}</div>
              <div style={{ position: "absolute", bottom: 34, left: 50, right: 50, height: 6, borderRadius: 3, background: conAlfa("#fff", 0.15) }}>
                <div style={{ width: `${prog(f, ini + 6, 20) * 100}%`, height: "100%", borderRadius: 3, background: color }} />
              </div>
              {mal && <Grieta f={f} ini={ini + 18} ancho={460} alto={380} semilla={h.fecha} />}
            </Cristal>
            {h.pastilla && <div style={{ position: "absolute", left: 470, top: 150 }}><Pastilla texto={h.pastilla} f={f} ini={ini + 10} color={mal ? p.peligro : undefined} /></div>}
          </div>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- PILA
// Tarjetas que van cayendo una encima de otra (las anteriores se apilan detrás, más pequeñas).
export const Pila: React.FC<PropsEscena> = ({ d, f, dur, fps }) => {
  const p = usePaleta();
  const tarjetas: any[] = d.tarjetas || [];
  const tramo = dur / Math.max(1, tarjetas.length);
  const actual = Math.min(tarjetas.length - 1, Math.floor(f / tramo));
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {d.titulo && <div style={{ position: "absolute", top: 200, left: 0, right: 0, textAlign: "center", fontFamily: F.cifra, fontSize: ajustar(String(d.titulo), FN.cifra, 960, 70, 1, 8, true), color: p.texto, letterSpacing: 8 }}>{String(d.titulo).toUpperCase()}</div>}
      {tarjetas.map((t, i) => {
        if (i > actual) return null;
        const m = muelle(f, i * tramo, fps, 0.9);
        const detras = actual - i;
        const y = 640 - detras * 70 + (1 - m) * 700;
        const esc = 1 - detras * 0.07;
        const rot = (i % 2 ? 1 : -1) * (2 + detras * 1.5) + (1 - m) * 25;
        return (
          <div key={i} style={{ position: "absolute", left: 540 - 400, top: y - 200, width: 800, height: 400, zIndex: 10 + i, transform: `scale(${esc}) rotate(${rot}deg)`, opacity: detras > 3 ? 0 : 1 - detras * 0.2 }}>
            <Cristal ancho={800} alto={400} color={t.color === "peligro" ? p.peligro : undefined}>
              {t.src && <Img src={fuenteImg(t.src)} style={{ position: "absolute", left: 0, top: 0, width: 300, height: "100%", objectFit: "cover" }} />}
              <div style={{ position: "absolute", left: t.src ? 330 : 50, right: 40, top: 0, bottom: 0, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                {t.arriba && <div style={{ fontFamily: F.etiqueta, fontSize: 26, letterSpacing: 4, color: p.suave }}>{t.arriba.toUpperCase()}</div>}
                <div style={{ fontFamily: F.cifra, fontSize: ajustar(String(t.titulo || ""), FN.cifra, t.src ? 420 : 700, 64, 2), color: t.color === "peligro" ? p.peligro : p.texto, lineHeight: 1.05 }}>{t.titulo}</div>
                {t.sub && <div style={{ fontFamily: F.texto, fontSize: ajustar(String(t.sub), FN.texto, t.src ? 420 : 700, 32, 2), color: p.suave, marginTop: 10 }}>{t.sub}</div>}
              </div>
            </Cristal>
          </div>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- PRENSA
// Titular «de periódico» (sin logotipos de medios reales: solo el nombre en texto) que entra
// girando y un rotulador que subraya la parte clave.
export const Prensa: React.FC<PropsEscena> = ({ d, f, fps }) => {
  const p = usePaleta();
  const m = muelle(f, 0, fps, 0.8);
  const marca = prog(f, fps * 0.7, 14, salida);
  const titular = String(d.titular || "");
  const clave = String(d.resaltar || "");
  const i = clave ? titular.indexOf(clave) : -1;
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{
        position: "absolute", left: 90, right: 90, top: 330, padding: "50px 56px", background: "#f5f0e6", borderRadius: 10,
        boxShadow: "0 40px 90px rgba(0,0,0,0.6)", transform: `perspective(1600px) rotateX(${(1 - m) * 60}deg) rotateZ(${-2 + (1 - m) * 6}deg) scale(${0.85 + 0.15 * m})`,
        opacity: Math.min(1, m * 1.5),
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "3px solid #222", paddingBottom: 16, marginBottom: 26 }}>
          <span style={{ fontFamily: F.prensa, fontSize: 40, color: "#111" }}>{d.medio || "Noticias"}</span>
          <span style={{ fontFamily: F.etiqueta, fontSize: 26, color: "#555", alignSelf: "flex-end" }}>{d.fecha || ""}</span>
        </div>
        <div style={{ fontFamily: F.prensa, fontSize: ajustar(titular, FN.prensa, 780, 74, 4), lineHeight: 1.08, color: "#111" }}>
          {i >= 0 ? (<>
            {titular.slice(0, i)}
            <span style={{ position: "relative", whiteSpace: "pre-wrap" }}>
              <span style={{ position: "absolute", left: -6, right: `${100 - marca * 100}%`, top: "18%", bottom: "8%", background: conAlfa(p.acento, 0.75), zIndex: 0 }} />
              <span style={{ position: "relative" }}>{clave}</span>
            </span>
            {titular.slice(i + clave.length)}
          </>) : titular}
        </div>
        {d.entradilla && <div style={{ fontFamily: F.texto, fontSize: ajustar(d.entradilla, FN.texto, 780, 34, 3), color: "#444", marginTop: 24, lineHeight: 1.3 }}>{d.entradilla}</div>}
      </div>
      {d.pastilla && <div style={{ position: "absolute", top: 220, left: 90 }}><Pastilla texto={d.pastilla} f={f} ini={8} /></div>}
    </div>
  );
};
