# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
from backend.core.audio_handler import init_stream
from backend.core.voice_detector import VoiceDetector
from backend.core.audio_segmenter import AudioSegmenter
from backend.services.emotion_detection import EmotionAnalyzer
from backend.services.diarization import Diarizer
from backend.config import CHUNK
import soundfile as sf
import numpy as np
import os
import time

# ─────────────────────────────────────────────
#  MOTOR PRINCIPAL — Arquitectura por Perfil
#  Flujo:
#  1. Captura 2s de audio.
#  2. Diariza → identifica hablante.
#  3. Acumula audio por hablante en buffer.
#  4. Cuando el buffer llega a 15s → analiza emoción y resetea.
# ─────────────────────────────────────────────

EMOTION_WINDOW_SECS = 15.0  # Analizar emoción cada 15s por hablante
STALE_THRESHOLD_SECS = 60.0 # Si un sujeto calla >60s, reiniciamos su buffer para no mezclar momentos lejanos


def run_engine(callback=None, error_callback=None, stop_event=None, max_speakers=None):
    """
    Motor principal con arquitectura de acumulación por perfil de hablante.
    """
    try:
        p, stream = init_stream()
    except Exception as e:
        err_msg = f"Error al inicializar audio: {e}"
        print(f"\n[ERROR] {err_msg}")
        if error_callback:
            error_callback(err_msg)
        return

    detector = VoiceDetector()
    segmenter = AudioSegmenter()
    diarizer  = Diarizer()
    analyzer  = EmotionAnalyzer()

    # Buffer de audio por hablante: { "Sujeto A": {"frames": [np.array,...], "duration": float} }
    speaker_buffers = {}

    print("\n" + "="*38)
    print("   MOTOR DE EMOCIONES v2 — Por Perfil")
    print("="*38)
    print("Escuchando... (Presiona Detener en la Web)")

    try:
        while True:
            if stop_event and stop_event.is_set():
                print("[INFO] Deteniendo motor por petición externa...")
                break

            # 1. Lectura de audio
            try:
                audio_chunk = stream.read(CHUNK, exception_on_overflow=False)
            except Exception as e:
                if error_callback:
                    error_callback(f"Error de lectura: {e}")
                break

            # 2. Detección de voz y segmentación
            event = detector.process_chunk(audio_chunk)
            segment_data = segmenter.process_event(event, audio_chunk)

            # Notificar estado al dashboard
            if event == "START":
                if callback:
                    callback("HABLANDO...", 0, None, None)
            elif event == "END":
                if callback:
                    callback("SILENCIO", 0, None, None)

            # 3. Procesar chunk de 2s
            if segment_data:
                chunk_file, chunk_type = segment_data
                if chunk_type != "CHUNK":
                    continue

                # 4. Diarización del chunk de 2s → quién habla y cuándo
                segments = diarizer.process(chunk_file, max_speakers=max_speakers)
                if not segments:
                    _cleanup(chunk_file)
                    continue

                # 5. Cargar audio del chunk para recortarlo por hablante
                try:
                    waveform, sr = sf.read(chunk_file)
                    if len(waveform.shape) > 1:
                        waveform = waveform.mean(axis=1)
                except Exception as e:
                    print(f"[WARN] Error leyendo chunk: {e}")
                    _cleanup(chunk_file)
                    continue

                for seg in segments:
                    start_s  = seg['start']
                    end_s    = seg['end']
                    speaker  = seg['speaker']
                    dur      = end_s - start_s

                    if dur < 0.5:
                        continue  # Ignorar micro-segmentos

                    # Notificar identidad al dashboard (sin guardar como resultado)
                    if callback:
                        callback("IDENTIFICANDO...", 0, None, speaker)

                    # Descartar al comercial — privacidad y ley
                    if speaker == "Comercial":
                        print(f"[INFO] Voz del comercial detectada. Descartando.")
                        continue

                    # 6. Extraer audio del hablante y acumular en su buffer
                    now = time.time()
                    
                    start_sample = int(start_s * sr)
                    end_sample   = min(int(end_s * sr), len(waveform))
                    audio_slice  = waveform[start_sample:end_sample]

                    if len(audio_slice) == 0 or np.max(np.abs(audio_slice)) < 0.001:
                        continue  # Silencio

                    if speaker not in speaker_buffers:
                        speaker_buffers[speaker] = {"frames": [], "duration": 0.0, "last_time": now}

                    buf = speaker_buffers[speaker]
                    
                    # Comprobar si el audio acumulado es "viejo"
                    time_diff = now - buf["last_time"]
                    if time_diff > STALE_THRESHOLD_SECS and buf["duration"] > 0:
                        print(f"[BUFFER] {speaker}: Gap temporal detectado ({time_diff:.1f}s). Reiniciando buffer.")
                        buf["frames"] = []
                        buf["duration"] = 0.0

                    buf["frames"].append(audio_slice)
                    buf["duration"] += dur
                    buf["last_time"] = now

                    print(f"[BUFFER] {speaker}: {buf['duration']:.1f}s acumulados")

                    # 7. ¿El perfil ya está graduado y tiene 15s de audio? → Emoción
                    profile = diarizer.speaker_manager.get_profile(speaker)
                    is_safe = profile is not None and profile.total_duration >= 15.0

                    if is_safe and buf["duration"] >= EMOTION_WINDOW_SECS:
                        print(f"\n[EMOCIÓN] Analizando {EMOTION_WINDOW_SECS}s de '{speaker}'...")

                        # Concatenar y guardar audio acumulado
                        combined = np.concatenate(buf["frames"])
                        emotion_file = _save_combined_audio(combined, sr, speaker)

                        # Resetear buffer para el siguiente ciclo
                        buf["frames"]   = []
                        buf["duration"] = 0.0

                        if emotion_file:
                            emotion, score, all_probs = analyzer.analyze(emotion_file)
                            if emotion and score is not None and score > 0.0:
                                if callback:
                                    callback(emotion, score, emotion_file, speaker, all_probs)
                            else:
                                print(f"[WARN] Resultado de emoción inválido para '{speaker}'.")

                _cleanup(chunk_file)

    except Exception as e:
        err_msg = f"Error crítico: {e}"
        import traceback
        traceback.print_exc()
        if error_callback:
            error_callback(err_msg)
    finally:
        try:
            stream.stop_stream()
            stream.close()
            p.terminate()
            print("[INFO] Hardware de audio liberado correctamente.")
        except:
            pass


def _save_combined_audio(waveform, sr, speaker):
    """Guarda el audio combinado de un hablante en disco para su análisis."""
    import time
    import soundfile as sf
    from backend.config import AUDIO_DIR
    
    # Crear carpeta específica para el sujeto
    speaker_name_safe = speaker.replace(' ', '_')
    speaker_dir = os.path.join(AUDIO_DIR, speaker_name_safe)
    if not os.path.exists(speaker_dir):
        os.makedirs(speaker_dir)
        print(f"[INFO] Carpeta de sujeto creada: {speaker_dir}")

    filename = os.path.join(speaker_dir, f"emotion_{int(time.time())}.wav")
    try:
        sf.write(filename, waveform, sr)
        return filename
    except Exception as e:
        print(f"[ERR] Guardando audio de emoción para {speaker}: {e}")
        return None


def _cleanup(filepath):
    """Elimina archivos temporales de chunks."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except:
        pass


if __name__ == "__main__":
    run_engine()
