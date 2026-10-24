"""Voces para los vídeos.

- crear_motor(): elige el motor con la variable VOZ_MOTOR:
    gemini     -> Gemini TTS (voz clonada de Marcos si hay GEMINI_VOICE_ID; si no, una voz de Gemini)
    chatterbox -> Chatterbox español de España con la voz de Marcos (en el ordenador de GitHub)
  Si se pide Gemini pero no hay GEMINI_API_KEY, se usa Chatterbox.

Motor Chatterbox:

Uso:
    voz = MotorVoz()
    audio = voz.decir("Faltan 28 días para GTA 6.")   # numpy, a voz.sr muestras por segundo

Cada frase se genera por separado: así suena más estable y sabemos cuánto dura cada una
(para sincronizar los subtítulos).
"""
import os
import re
import shutil
from pathlib import Path

import numpy as np

from numeros import a_voz

RAIZ = Path(__file__).resolve().parent.parent
# La grabación de la voz vive en el repositorio privado (carpeta privado/); si no, en la raíz
REFERENCIA = next((p for p in [RAIZ / "privado" / "voz_referencia.wav", RAIZ / "voz_referencia.wav"] if p.exists()),
                  RAIZ / "privado" / "voz_referencia.wav")


def _cargar_es_es():
    # Se importan aquí para no necesitarlos cuando la voz la hace Gemini
    import torch
    from huggingface_hub import hf_hub_download

    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    carpeta = Path("modelo_es_es")
    carpeta.mkdir(exist_ok=True)
    for repo, archivo in [
        ("ResembleAI/chatterbox", "ve.pt"),
        ("ResembleAI/chatterbox", "conds.pt"),
        ("ResembleAI/chatterbox", "s3gen.pt"),
        ("ResembleAI/Chatterbox-Multilingual-es-es", "t3_es_es.safetensors"),
        ("ResembleAI/Chatterbox-Multilingual-es-es", "grapheme_mtl_merged_expanded_v1.json"),
    ]:
        shutil.copyfile(hf_hub_download(repo, archivo), carpeta / archivo)
    modelo = ChatterboxMultilingualTTS.from_local(carpeta, "cpu", t3_model="t3_es_es.safetensors")

    # Decodificador de voz propio del paquete de España (le faltan dos tablas fijas que
    # el programa calcula solo, por eso no se exigen).
    estado = torch.load(
        hf_hub_download("ResembleAI/Chatterbox-Multilingual-es-es", "s3gen_v3.pt"),
        map_location="cpu", weights_only=True,
    )
    faltan, sobran = modelo.s3gen.load_state_dict(estado, strict=False)
    faltan = [k for k in faltan if not k.startswith("tokenizer.")]
    if faltan or sobran:
        print("::warning::Decodificador de España no encaja, uso el base")
        modelo.s3gen.load_state_dict(torch.load(carpeta / "s3gen.pt", map_location="cpu", weights_only=True))
    return modelo


# Estilos de voz (se elige con la variable VOZ):
#   natural   -> pausas en las comas y ritmo más pausado (recomendado)
#   expresivo -> como natural, pero con más entonación
#   antes     -> como en la primera prueba: cada frase de un tirón
ESTILOS = {
    "natural": {"exaggeration": 0.5, "cfg_weight": 0.3, "temperature": 0.65, "trocear": True},
    "expresivo": {"exaggeration": 0.7, "cfg_weight": 0.3, "temperature": 0.7, "trocear": True},
    "antes": {"exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.8, "trocear": False},
}
PAUSA_COMA = 0.18  # segundos de silencio en cada coma, dos puntos o punto y coma


def _trozos_de_frase(texto):
    """'Faltan 28 días, o sea, mucho.' -> ['Faltan 28 días,', 'o sea,', 'mucho.']
    No corta dentro de números con coma decimal (4,9)."""
    partes = re.split(r"(?<=[,;:])\s+", texto)
    unidas = []
    for p in partes:
        # Trozos muy cortos («o sea,») se juntan con el siguiente para que no suene entrecortado
        if unidas and len(unidas[-1].split()) < 4:
            unidas[-1] = unidas[-1] + " " + p
        else:
            unidas.append(p)
    return [u for u in unidas if u.strip()]


def _recortar_silencio(wav, sr, umbral=0.02, margen=0.04):
    """Quita el silencio y los ruidos sueltos del principio y del final."""
    if len(wav) == 0:
        return wav
    nivel = np.abs(wav)
    ventana = max(1, int(sr * 0.01))
    env = np.convolve(nivel, np.ones(ventana) / ventana, mode="same")
    activo = np.where(env > umbral * env.max())[0]
    if len(activo) == 0:
        return wav
    ini = max(0, activo[0] - int(margen * sr))
    fin = min(len(wav), activo[-1] + int(margen * sr * 2))
    return wav[ini:fin]


def _quitar_muletilla(wav, sr, texto):
    """Quita un «eee» o respiración al principio: un sonido corto seguido de un silencio,
    antes de que empiece la frase de verdad. Devuelve (audio, se_quitó)."""
    if len(wav) < sr:
        return wav, False
    ventana = max(1, int(sr * 0.02))
    env = np.convolve(np.abs(wav), np.ones(ventana) / ventana, mode="same")
    umbral = 0.06 * env.max()
    activo = env > umbral
    # Busca, en el primer segundo, un hueco de silencio de al menos 0,15 s tras un sonido corto
    limite = min(len(wav), int(1.0 * sr))
    i = 0
    while i < limite and not activo[i]:
        i += 1
    inicio_sonido = i
    while i < limite and activo[i]:
        i += 1
    fin_sonido = i
    while i < len(wav) and not activo[i]:
        i += 1
    hueco = (i - fin_sonido) / sr
    corto = (fin_sonido - inicio_sonido) / sr
    # Un «eee» dura poco y va seguido de pausa; una primera palabra real casi nunca (salvo con coma)
    primera = texto.split()[0] if texto.split() else ""
    if 0.05 < corto < 0.6 and hueco >= 0.15 and i < len(wav) and not primera.endswith((",", ":", ";", ".")):
        return wav[max(0, i - int(0.03 * sr)):], True
    return wav, False


class MotorVoz:
    def __init__(self, estilo=None):
        if not REFERENCIA.exists():
            raise SystemExit("::error::Falta voz_referencia.wav en el repositorio")
        self.estilo_nombre = (estilo or os.environ.get("VOZ") or "natural").strip() or "natural"
        self.estilo = ESTILOS.get(self.estilo_nombre, ESTILOS["natural"])
        print(f"Estilo de voz: {self.estilo_nombre} {self.estilo}")
        import torch
        torch.manual_seed(1234)  # misma entonación para el mismo texto
        self.modelo = _cargar_es_es()
        self.modelo.prepare_conditionals(str(REFERENCIA), exaggeration=self.estilo["exaggeration"])
        self.sr = self.modelo.sr
        self.ultimas_piezas = []  # [(texto en pantalla, inicio, fin)] de la última frase, en segundos
        self.intentos = max(1, int(os.environ.get("VOZ_TOMAS") or 2))  # tomas por trozo para elegir la mejor
        self.ritmos = []

    def _una_toma(self, dicho):
        wav = self.modelo.generate(dicho, language_id="es", exaggeration=self.estilo["exaggeration"],
                                   cfg_weight=self.estilo["cfg_weight"], temperature=self.estilo["temperature"])
        wav = _recortar_silencio(wav.squeeze(0).cpu().numpy().astype(np.float32), self.sr)
        return _quitar_muletilla(wav, self.sr, dicho)

    def _generar(self, texto_pantalla):
        """Graba varias tomas del mismo trozo y se queda con la más limpia.

        Un «eee», una respiración o una sílaba repetida alargan la toma, así que se elige
        la que más se acerca a la duración esperada para ese texto (según el ritmo
        real de la voz en las tomas anteriores) y se penalizan las que traían «eee».
        """
        dicho = a_voz(texto_pantalla)
        print("  ·", dicho)
        letras = max(1, len(dicho.replace(" ", "")))
        ritmo = float(np.median(self.ritmos)) if self.ritmos else 13.0  # letras por segundo
        esperado = letras / ritmo
        tomas = []
        for _ in range(self.intentos):
            wav, tenia_eee = self._una_toma(dicho)
            dur = len(wav) / self.sr
            nota = abs(dur - esperado) / esperado + (0.5 if tenia_eee else 0) + (0.3 if dur > esperado * 1.35 else 0)
            tomas.append((nota, wav, tenia_eee, dur))
            if nota < 0.12 and not tenia_eee:
                break  # ya es buena: no hace falta otra
        nota, wav, tenia_eee, dur = min(tomas, key=lambda x: x[0])
        if len(tomas) > 1:
            print(f"    ({len(tomas)} tomas; elegida la de {dur:.1f} s, esperado {esperado:.1f} s{', sin eee' if not tenia_eee else ''})")
        self.ritmos.append(letras / max(dur, 0.3))
        return wav

    def decir(self, texto_pantalla: str) -> np.ndarray:
        trozos = _trozos_de_frase(texto_pantalla) if self.estilo["trocear"] else [texto_pantalla]
        pausa = np.zeros(int(PAUSA_COMA * self.sr), dtype=np.float32)
        piezas, audio, t = [], [], 0.0
        for i, trozo in enumerate(trozos):
            wav = self._generar(trozo)
            piezas.append((trozo, t, t + len(wav) / self.sr))
            audio.append(wav)
            t += len(wav) / self.sr
            if i < len(trozos) - 1:
                audio.append(pausa)
                t += PAUSA_COMA
        self.ultimas_piezas = piezas
        return np.concatenate(audio)


def decir_guion(voz, frases):
    """Audios y trozos de todas las frases. Con Gemini, una sola petición por vídeo."""
    if hasattr(voz, "decir_varias"):
        try:
            res = voz.decir_varias(frases)
            return [a for a, _ in res], [p for _, p in res]
        except SystemExit:
            raise
        except Exception as error:  # si falla el corte, frase a frase
            print(f"::warning::No se pudo hacer de una vez ({error}); voy frase a frase")
    audios, trozos = [], []
    for f in frases:
        audios.append(voz.decir(f))
        trozos.append(voz.ultimas_piezas)
    return audios, trozos


def crear_motor():
    motor = (os.environ.get("VOZ_MOTOR") or "gemini").strip().lower()
    if motor == "gemini" and (os.environ.get("GEMINI_API_KEY") or "").strip():
        from motor_gemini import MotorVozGemini
        return MotorVozGemini()
    if motor == "gemini":
        print("::warning::No hay GEMINI_API_KEY: uso Chatterbox")
    return MotorVoz()
