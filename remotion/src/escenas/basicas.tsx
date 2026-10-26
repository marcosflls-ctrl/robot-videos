import React from "react";
import { random } from "remotion";
import { conAlfa, Cristal, F, muelle, Pastilla, prog, salida, usePaleta } from "../comun";

export type PropsEscena = { d: any; f: number; dur: number; fps: number };

// ---------------------------------------------------------------- CIFRA
// Número grande que cuenta hasta su valor, con un anillo de luz que se dibuja detrás.
export const Cifra: React.FC<PropsEscena> = ({ d, f, dur, fps }) => {
  const p = usePaleta();
  const valor = Number(d.valor ?? 0);
  const dec = Number(d.decimales ?? 0);
  const cuenta = d.contar === false ? 1 : prog(f, 0, fps * 0.9, salida);
  const n = valor * cuenta;
  const texto = d.texto ?? n.toLocaleString("es-ES", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const m = muelle(f, 0, fps, 0.8);
  const anillo = prog(f, 2, fps * 1.1, salida);
  const color = d.color === "peligro" ? p.peligro : d.color === "acento2" ? p.acento2 : p.texto;
  const variante = d.variante || "anillo";
  const tam = Math.min(330, 1500 / Math.max(2.4, String(texto).length + (d.sufijo || "").length * 0.5));
  const nucleo = (
    <div style={{ textAlign: "center" }}>
      {d.arriba && <div style={{ fontFamily: F.etiqueta, fontSize: 34, letterSpacing: 8, color: p.suave, textTransform: "uppercase", marginBottom: 10 }}>{d.arriba}</div>}
      <div style={{ fontFamily: F.cifra, fontSize: tam, lineHeight: 1, color, textShadow: `0 0 40px ${conAlfa(p.acento2, 0.55)}`, whiteSpace: "nowrap" }}>
        <span style={{ fontSize: tam * 0.55 }}>{d.prefijo || ""}</span>{texto}<span style={{ fontSize: tam * 0.45 }}>{d.sufijo || ""}</span>
      </div>
      {d.etiqueta && <div style={{
        fontFamily: F.etiqueta, fontSize: 40, letterSpacing: 6 + 10 * (1 - prog(f, 6, 18, salida)), color: p.texto,
        textTransform: "uppercase", marginTop: 26, opacity: prog(f, 6, 12),
      }}>{d.etiqueta}</div>}
    </div>
  );
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", top: -220 }}>
      {variante === "anillo" && (
        <svg width={860} height={860} style={{ position: "absolute", transform: `rotate(${-90 + f * 0.4}deg)` }}>
          <circle cx={430} cy={430} r={400} fill="none" stroke={conAlfa(p.texto, 0.12)} strokeWidth={3} />
          <circle cx={430} cy={430} r={400} fill="none" stroke={p.acento2} strokeWidth={6} strokeLinecap="round"
            strokeDasharray={`${2513 * anillo * 0.82} 2513`} style={{ filter: `drop-shadow(0 0 14px ${p.acento2})` }} />
        </svg>
      )}
      <div style={{ transform: `perspective(1400px) rotateX(${(1 - m) * 25}deg) rotateY(${(1 - m) * -18}deg) scale(${0.7 + 0.3 * m})` }}>
        {variante === "tarjeta" ? (
          <Cristal ancho={760} alto={720}>
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>{nucleo}</div>
          </Cristal>
        ) : nucleo}
      </div>
      {d.pastilla && <div style={{ position: "absolute", top: 1240 }}><Pastilla texto={d.pastilla} f={f} ini={14} /></div>}
    </div>
  );
};

// ---------------------------------------------------------------- TITULAR
// Frase corta enorme. Variantes: letras3d (cada letra gira al entrar), bloques (palabras que suben
// de una máscara con la clave subrayada en color) y gigante (entra enorme y se posa).
export const Titular: React.FC<PropsEscena> = ({ d, f, fps }) => {
  const p = usePaleta();
  const texto = String(d.texto || "").toUpperCase();
  const clave = new Set(String(d.resaltar || "").toUpperCase().split(/\s+/).filter(Boolean));
  const variante = d.variante || "letras3d";
  const palabras = texto.split(/\s+/);
  const tam = d.tam || Math.min(190, 2100 / Math.max(6, Math.max(...palabras.map((w) => w.length)) * 1.9));
  if (variante === "letras3d") {
    let k = 0;
    return (
      <div style={{ position: "absolute", inset: 0, display: "flex", flexWrap: "wrap", alignContent: "center", justifyContent: "center", gap: "0 40px", padding: "0 60px", top: -200, perspective: 1200 }}>
        {palabras.map((w, i) => (
          <div key={i} style={{ display: "flex" }}>
            {w.split("").map((c) => {
              const pr = prog(f, (k++) * 1.6, 12, salida);
              return <span key={k} style={{
                fontFamily: F.cifra, fontSize: tam, letterSpacing: tam * 0.06, display: "inline-block",
                color: clave.has(w) ? p.acento : p.texto, opacity: pr,
                transform: `rotateY(${(1 - pr) * 100}deg) translateY(${(1 - pr) * 30}px)`,
                textShadow: `0 0 30px ${conAlfa(clave.has(w) ? p.acento : p.acento2, 0.5)}`,
              }}>{c}</span>;
            })}
          </div>
        ))}
        {d.sub && <div style={{ width: "100%", textAlign: "center", fontFamily: F.etiqueta, fontSize: 40, letterSpacing: 6, color: p.suave, marginTop: 30, opacity: prog(f, 18, 12) }}>{d.sub.toUpperCase()}</div>}
      </div>
    );
  }
  if (variante === "bloques") {
    return (
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", top: -200 }}>
        {palabras.map((w, i) => {
          const pr = prog(f, i * 4, 14, salida);
          const subraya = prog(f, i * 4 + 10, 12, salida);
          return (
            <div key={i} style={{ overflow: "hidden", padding: "0 20px", position: "relative" }}>
              {clave.has(w) && <div style={{ position: "absolute", left: 10, bottom: tam * 0.14, height: tam * 0.32, width: `calc(${subraya * 100}% - 20px)`, background: p.acento, opacity: 0.9 }} />}
              <div style={{ fontFamily: F.impacto, fontSize: tam * 1.15, lineHeight: 1.02, color: clave.has(w) ? "#fff" : p.texto, transform: `translateY(${(1 - pr) * 110}%)`, position: "relative" }}>{w}</div>
            </div>
          );
        })}
      </div>
    );
  }
  // gigante
  const pr = prog(f, 0, fps * 0.5, salida);
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", top: -200 }}>
      <div style={{
        fontFamily: F.impacto, fontSize: tam * 1.3, color: p.texto, textAlign: "center", lineHeight: 1, padding: "0 40px",
        transform: `scale(${3 - 2 * pr + f * 0.0015})`, opacity: Math.min(1, pr * 2), filter: `blur(${(1 - pr) * 12}px)`,
        textShadow: `0 0 50px ${conAlfa(p.acento2, 0.6)}`,
      }}>
        {palabras.map((w, i) => <span key={i} style={{ color: clave.has(w) ? p.acento : undefined }}>{w} </span>)}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- ALERTA
// Icono grande (candado que se cierra, aviso, cruz, grieta) con ondas de choque y tinte rojo.
export const Alerta: React.FC<PropsEscena> = ({ d, f, fps }) => {
  const p = usePaleta();
  const c = d.color === "acento" ? p.acento : p.peligro;
  const icono = d.icono || "candado";
  const m = muelle(f, 0, fps, 1.1);
  const golpe = Math.round(fps * 0.35);
  const sacude = f > golpe && f < golpe + 10 ? Math.sin(f * 3) * (10 - (f - golpe)) * 2 : 0;
  const cierre = prog(f, golpe - 5, 6);
  return (
    <div style={{ position: "absolute", inset: 0, transform: `translateX(${sacude}px)` }}>
      <div style={{ position: "absolute", inset: 0, background: `radial-gradient(circle at 50% 40%, transparent 30%, ${conAlfa(c, 0.35 * prog(f, golpe, 6) * (1 - prog(f, golpe + 8, 25)))})` }} />
      {[0, 1, 2].map((i) => {
        const o = prog(f, golpe + i * 4, 22, salida);
        return o > 0 && o < 1 ? <div key={i} style={{
          position: "absolute", left: 540 - 150 - o * 350, top: 650 - 150 - o * 350, width: 300 + o * 700, height: 300 + o * 700,
          borderRadius: "50%", border: `${6 * (1 - o)}px solid ${c}`, opacity: 1 - o,
        }} /> : null;
      })}
      <div style={{ position: "absolute", left: 0, right: 0, top: 650 - 170, display: "flex", justifyContent: "center", transform: `scale(${0.4 + 0.6 * m})` }}>
        <svg width={340} height={340} viewBox="0 0 120 120" style={{ filter: `drop-shadow(0 0 30px ${c})` }}>
          {icono === "candado" && (<>
            <path d={`M34 ${56 - (1 - cierre) * 18} V40 a26 26 0 0 1 52 0 V${56 - (1 - cierre) * 6}`} fill="none" stroke={c} strokeWidth={11} strokeLinecap="round" />
            <rect x={22} y={54} width={76} height={58} rx={12} fill={c} />
            <circle cx={60} cy={78} r={7} fill={p.fondo1} /><rect x={57} y={80} width={6} height={16} fill={p.fondo1} />
          </>)}
          {icono === "aviso" && (<>
            <path d="M60 10 L112 104 H8 Z" fill="none" stroke={c} strokeWidth={9} strokeLinejoin="round" />
            <rect x={55} y={42} width={10} height={36} rx={4} fill={c} /><circle cx={60} cy={90} r={6} fill={c} />
          </>)}
          {icono === "cruz" && (<>
            <circle cx={60} cy={60} r={52} fill="none" stroke={c} strokeWidth={8} />
            <path d={`M38 38 L${38 + 44 * cierre} ${38 + 44 * cierre} M82 38 L${82 - 44 * cierre} ${38 + 44 * cierre}`} stroke={c} strokeWidth={10} strokeLinecap="round" />
          </>)}
          {icono === "check" && (<>
            <circle cx={60} cy={60} r={52} fill="none" stroke={c} strokeWidth={8} />
            <path d="M34 62 L52 80 L88 42" fill="none" stroke={c} strokeWidth={10} strokeLinecap="round" strokeDasharray={90} strokeDashoffset={90 * (1 - cierre)} />
          </>)}
        </svg>
      </div>
      {d.texto && <div style={{
        position: "absolute", top: 930, left: 0, right: 0, textAlign: "center", fontFamily: F.cifra, fontSize: 110, color: c,
        letterSpacing: 12 + 20 * (1 - prog(f, golpe, 14, salida)), opacity: prog(f, golpe, 8), textShadow: `0 0 40px ${conAlfa(c, 0.6)}`,
      }}>{String(d.texto).toUpperCase()}</div>}
      {d.pastilla && <div style={{ position: "absolute", top: 1100, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
        <Pastilla texto={d.pastilla} color={c} f={f} ini={golpe + 6} /></div>}
    </div>
  );
};

// ---------------------------------------------------------------- PREGUNTA (cierre)
// Pregunta grande palabra a palabra y un comentario del canal que invita a responder.
export const Pregunta: React.FC<PropsEscena> = ({ d, f, fps }) => {
  const p = usePaleta();
  const palabras = String(d.pregunta || "").split(/\s+/);
  const c = prog(f, fps * 0.7, 14, salida);
  const comentario = String(d.comentario || "");
  const escrito = comentario.slice(0, Math.floor(comentario.length * prog(f, fps * 1.0, fps * 0.9, (x) => x)));
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", top: 520, left: 60, right: 60, display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 26px" }}>
        {palabras.map((w, i) => {
          const m = muelle(f, i * 3, fps, 1.2);
          return <span key={i} style={{ fontFamily: F.impacto, fontSize: 130, lineHeight: 1.05, color: i === palabras.length - 1 ? p.acento : p.texto, display: "inline-block", transform: `scale(${Math.max(0, m)})`, textShadow: `0 6px 0 ${conAlfa("#000", 0.35)}` }}>{w}</span>;
        })}
      </div>
      <div style={{ position: "absolute", top: 1020, left: 90, right: 90, transform: `translateY(${(1 - c) * 120}px)`, opacity: c }}>
        <Cristal ancho={900} alto={250} color={p.acento2}>
          <div style={{ position: "absolute", left: 36, top: 36, width: 76, height: 76, borderRadius: 99, background: `linear-gradient(135deg, ${p.acento2}, ${p.acento3})`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: F.impacto, fontSize: 34, color: "#fff" }}>{d.iniciales || "ZL"}</div>
          <div style={{ position: "absolute", left: 136, top: 38, fontFamily: F.etiqueta, fontSize: 30, color: p.acento }}>{d.marca || "Zona Leonida"} · fijado</div>
          <div style={{ position: "absolute", left: 136, top: 84, right: 30, fontFamily: F.negrita, fontSize: 40, color: p.texto }}>{escrito}<span style={{ opacity: Math.floor(f / 8) % 2 }}>|</span></div>
          <div style={{ position: "absolute", right: 36, bottom: 30, padding: "12px 34px", borderRadius: 99, background: p.peligro, fontFamily: F.etiqueta, fontSize: 30, color: "#fff", transform: `scale(${1 + 0.05 * Math.sin(f / 5)})` }}>COMENTAR</div>
        </Cristal>
      </div>
      <div style={{ position: "absolute", top: 1330, left: 0, right: 0, textAlign: "center", fontSize: 90, color: p.acento, transform: `translateY(${Math.sin(f / 6) * 14}px)`, opacity: c }}>↓</div>
    </div>
  );
};

/** Grieta: ramas que salen de un punto (para «se rompe», «hackeada»...) */
export const Grieta: React.FC<{ f: number; ini: number; ancho: number; alto: number; semilla?: string; color?: string }> = ({ f, ini, ancho, alto, semilla = "g", color = "#fff" }) => {
  const p = prog(f, ini, 10);
  if (p <= 0) return null;
  const cx = ancho * (0.35 + 0.3 * random(semilla + "x")), cy = alto * (0.3 + 0.3 * random(semilla + "y"));
  const ramas: string[] = [];
  for (let k = 0; k < 10; k++) {
    let ang = random(`${semilla}a${k}`) * Math.PI * 2, x = cx, y = cy;
    let d = `M${x} ${y}`;
    const pasos = 4 + Math.floor(random(`${semilla}n${k}`) * 5);
    for (let j = 0; j < Math.ceil(pasos * p); j++) {
      ang += (random(`${semilla}${k}-${j}`) - 0.5) * 1.2;
      const l = 18 + random(`${semilla}l${k}-${j}`) * 30;
      x += Math.cos(ang) * l; y += Math.sin(ang) * l;
      d += ` L${x} ${y}`;
    }
    ramas.push(d);
  }
  return (
    <svg width={ancho} height={alto} style={{ position: "absolute", left: 0, top: 0, pointerEvents: "none" }}>
      {ramas.map((d, i) => <path key={i} d={d} stroke={color} strokeWidth={2.5} fill="none" style={{ filter: `drop-shadow(0 0 6px ${color})` }} />)}
      {f - ini < 8 && <circle cx={cx} cy={cy} r={20 + (f - ini) * 8} fill={conAlfa("#ff6680", 0.7 * (1 - (f - ini) / 8))} />}
    </svg>
  );
};
