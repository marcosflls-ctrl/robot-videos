// Monta un vídeo a partir de un guion visual en JSON.
// Uso: node render.mjs guion.json salida.mp4
// Variable opcional NAVEGADOR: ruta a un Chrome/Chromium ya instalado.
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const [, , archivoGuion, salida = "out/video.mp4"] = process.argv;
if (!archivoGuion) {
  console.error("Uso: node render.mjs guion.json salida.mp4");
  process.exit(1);
}
const guion = JSON.parse(fs.readFileSync(archivoGuion, "utf8"));
const browserExecutable = process.env.NAVEGADOR || null;

console.log("Preparando el proyecto...");
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), publicDir: path.resolve("public") });
const composition = await selectComposition({ serveUrl, id: "Short", inputProps: guion, browserExecutable });
console.log(`Montando ${composition.durationInFrames} fotogramas...`);
let ultimo = -1;
await renderMedia({
  composition, serveUrl, codec: "h264", outputLocation: salida, inputProps: guion, browserExecutable,
  concurrency: Math.max(1, Math.min(8, os.cpus().length)), crf: 20, x264Preset: "veryfast",
  chromiumOptions: { gl: "swangle" },
  onProgress: ({ progress }) => {
    const p = Math.floor(progress * 10);
    if (p !== ultimo) { ultimo = p; console.log(`  ${p * 10} %`); }
  },
});
console.log("Listo:", salida);
