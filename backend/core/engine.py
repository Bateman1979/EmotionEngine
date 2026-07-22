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
from backend.services.transcriber import Transcriber
from backend.services.transcript_buffer import TranscriptManager
from backend.services.concept_extractor import ConceptExtractor
from backend.config import (
    CHUNK, TRIGGER_EMOTIONS, CONCEPT_WINDOW_BEFORE,
    CONCEPT_WINDOW_AFTER, MIN_TRANSCRIBE_SECS, CONCEPT_COOLDOWN_SECS,
    EMOTION_WINDOW_SECS, STALE_THRESHOLD_SECS
)
import soundfile as sf
import numpy as np
import os
import time
import threading

# ─────────────────────────────────────────────
#  MOTOR PRINCIPAL — Arquitectura por Perfil
#  Flujo:
#  1. Captura 2s de audio.
#  2. Diariza → identifica hablante.
#  3. Acumula audio por hablante en buffer.
#  4. Cuando el buffer llega a 15s → consolida archivo .wav
#  5. Transcribe el archivo .wav (Whisper tiene 15s de contexto)
#  6. Guarda transcripción en JSONL
#  7. Si no es Comercial, analiza emoción.
#  8. Si emoción negativa > umbral → extrae concepto detonante.
# ─────────────────────────────────────────────



def run_engine(callback=None, error_callback=None, stop_event=None, max_speakers=None, preloader=None):
    """
    Motor principal con arquitectura de acumulación por perfil de hablante.
    Integra: VAD → Segmentación → Diarización → STT (por bloque) → Emoción → Causa Raíz.
    
    Si se proporciona un preloader, usa los modelos pre-cargados para inicio instantáneo.
    """
    try:
        p, stream = init_stream()
    except Exception as e:
        err_msg = f"Error al inicializar audio: {e}"
        print(f"\n[ERROR] {err_msg}")
        if error_callback:
            error_callback(err_msg)
        return

    # Construir servicios: con preloader (instantáneo) o sin él (carga estándar)
    if preloader is not None and preloader.is_ready:
        print("[ENGINE] Usando modelos pre-cargados. Inicio instantáneo. ⚡")
        detector = VoiceDetector(model=preloader.vad_model)
        segmenter = AudioSegmenter()
        diarizer  = Diarizer(
            pipeline=preloader.diarization_pipeline,
            embedding_model=preloader.embedding_model,
            embedding_inference=preloader.embedding_inference
        )
        analyzer  = EmotionAnalyzer(
            model=preloader.emotion_model,
            feature_extractor=preloader.emotion_feature_extractor,
            labels=preloader.emotion_labels
        )
        transcriber = Transcriber(
            model=preloader.whisper_model,
            processor=preloader.whisper_processor,
            forced_decoder_ids=preloader.whisper_forced_decoder_ids
        )
    elif preloader is not None and not preloader.is_ready:
        print("[ENGINE] Esperando a que los modelos terminen de cargar...")
        if callback:
            callback("CARGANDO_MODELOS", 0, None, None)
        preloader.wait_until_ready(timeout=180)
        # Recurrir: ahora sí están listos
        print("[ENGINE] Modelos listos. Continuando con inicio.")
        detector = VoiceDetector(model=preloader.vad_model)
        segmenter = AudioSegmenter()
        diarizer  = Diarizer(
            pipeline=preloader.diarization_pipeline,
            embedding_model=preloader.embedding_model,
            embedding_inference=preloader.embedding_inference
        )
        analyzer  = EmotionAnalyzer(
            model=preloader.emotion_model,
            feature_extractor=preloader.emotion_feature_extractor,
            labels=preloader.emotion_labels
        )
        transcriber = Transcriber(
            model=preloader.whisper_model,
            processor=preloader.whisper_processor,
            forced_decoder_ids=preloader.whisper_forced_decoder_ids
        )
    else:
        print("[ENGINE] Sin preloader. Cargando modelos de forma estándar...")
        detector = VoiceDetector()
        segmenter = AudioSegmenter()
        diarizer  = Diarizer()
        analyzer  = EmotionAnalyzer()
        transcriber = Transcriber()

    transcript_manager = TranscriptManager()
    if preloader is not None and preloader.is_ready and hasattr(preloader, "concept_extractor"):
        concept_extractor = preloader.concept_extractor
        print("[INFO] ConceptExtractor inicializado con modelo pre-cargado.")
    else:
        concept_extractor = ConceptExtractor()

    # Buffer de audio por hablante: { "Sujeto A": {"frames": [np.array,...], "duration": float, "last_time": float, "first_time": float, "sr": int} }
    speaker_buffers = {}
    active_speaker = None

    print("\n" + "="*45)
    print("   MOTOR DE EMOCIONES v4 — Bloques STT (15s)")
    print("="*45)
    print("Escuchando... (Presiona Detener en la Web)")

    try:
        while True:
            if stop_event and stop_event.is_set():
                print("[INFO] Deteniendo motor por petición externa...")
                break

            now = time.time()
            # Chequeo de Timeout y Stale Buffers
            for spk, buf in speaker_buffers.items():
                if buf["duration"] >= 5.0 and (now - buf["last_time"]) >= 5.0:
                    profile = diarizer.speaker_manager.get_profile(spk)
                    # Procesamos el bloque si el perfil es el Comercial O si tiene suficiente graduación
                    is_safe = spk == "Comercial" or (profile is not None and profile.total_duration >= 15.0)
                    if is_safe:
                        _process_speaker_block(
                            spk, buf, buf.get("sr", 16000), analyzer, transcriber, 
                            transcript_manager, concept_extractor, callback,
                            reason="Timeout 5s silencio"
                        )
                elif buf["duration"] > 0 and (now - buf["last_time"]) > STALE_THRESHOLD_SECS:
                    print(f"[BUFFER] {spk}: Gap temporal detectado (>{STALE_THRESHOLD_SECS}s). Procesando y reiniciando.")
                    if buf["duration"] >= MIN_TRANSCRIBE_SECS:
                        _process_speaker_block(
                            spk, buf, buf.get("sr", 16000), analyzer, transcriber, 
                            transcript_manager, concept_extractor, callback,
                            reason="Gap temporal"
                        )
                    else:
                        buf["frames"] = []
                        buf["duration"] = 0.0

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
                        current_dur = 0.0
                        if speaker in speaker_buffers:
                            current_dur = speaker_buffers[speaker]["duration"]
                        callback("IDENTIFICANDO...", current_dur + dur, None, speaker)

                    # 6. Extraer audio del hablante
                    start_sample = int(start_s * sr)
                    end_sample   = min(int(end_s * sr), len(waveform))
                    audio_slice  = waveform[start_sample:end_sample]

                    if len(audio_slice) == 0 or np.max(np.abs(audio_slice)) < 0.001:
                        continue  # Silencio

                    # Cambio de turno
                    if active_speaker and active_speaker != speaker:
                        if active_speaker in speaker_buffers:
                            buf_prev = speaker_buffers[active_speaker]
                            if buf_prev["duration"] >= 5.0:
                                profile = diarizer.speaker_manager.get_profile(active_speaker)
                                is_safe = active_speaker == "Comercial" or (profile is not None and profile.total_duration >= 15.0)
                                if is_safe:
                                    _process_speaker_block(
                                        active_speaker, buf_prev, buf_prev.get("sr", sr),
                                        analyzer, transcriber, transcript_manager, concept_extractor, callback,
                                        reason="Cambio de turno"
                                    )
                    
                    active_speaker = speaker

                    # 7. Acumular audio en el buffer del hablante (INCLUIDO EL COMERCIAL)
                    now = time.time()

                    if speaker not in speaker_buffers:
                        speaker_buffers[speaker] = {
                            "frames": [], 
                            "duration": 0.0, 
                            "last_time": now, 
                            "first_time": now, 
                            "sr": sr
                        }

                    buf = speaker_buffers[speaker]
                    
                    if not buf["frames"]:
                        buf["first_time"] = now

                    buf["frames"].append(audio_slice)
                    buf["duration"] += dur
                    buf["last_time"] = now

                    print(f"[BUFFER] {speaker}: {buf['duration']:.1f}s acumulados")

                    # 8. ¿El perfil ya tiene 15s de audio? → Transcribir y (si no es Comercial) analizar emoción
                    profile = diarizer.speaker_manager.get_profile(speaker)
                    is_safe = speaker == "Comercial" or (profile is not None and profile.total_duration >= 15.0)

                    if is_safe and buf["duration"] >= EMOTION_WINDOW_SECS:
                        _process_speaker_block(
                            speaker, buf, sr, analyzer, transcriber, 
                            transcript_manager, concept_extractor, callback,
                            reason="Límite 15s"
                        )

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


def _process_speaker_block(speaker, buf, sr, analyzer, transcriber, transcript_manager, concept_extractor, callback, reason="Límite"):
    """
    Procesa un bloque consolidado de audio (aprox. 15s).
    Aplica Transcripción a TODOS.
    Aplica Emociones SOLO a sujetos no comerciales.
    """
    print(f"\n[BLOQUE] Procesando {buf['duration']:.1f}s de '{speaker}' ({reason})...")

    combined = np.concatenate(buf["frames"])
    block_start_time = buf["first_time"]
    
    emotion_file = _save_combined_audio(combined, sr, speaker)

    # Resetear buffer para el siguiente ciclo
    buf["frames"]   = []
    buf["duration"] = 0.0
    buf["last_time"] = time.time()
    buf["first_time"] = buf["last_time"]

    if not emotion_file:
        return

    # 1. TRANSCRIPCIÓN DEL BLOQUE CONSOLIDADO
    if not speaker.startswith("Identificando"):
        print(f"[STT] Transcribiendo archivo de '{speaker}'...")
        text_segments = transcriber.transcribe(combined, sr)
        for ts in text_segments:
            text = ts["text"].strip()
            if text:
                # Calcular tiempos absolutos
                abs_start = block_start_time + ts["start"]
                abs_end = block_start_time + ts["end"]
                transcript_manager.add(speaker, abs_start, abs_end, text)
                print(f"  📝 [TRANSCRITO] {speaker}: \"{text}\"")
    else:
        print(f"[STT] Omitiendo transcripción para perfil no consolidado ('{speaker}').")

    # 2. ANÁLISIS DE EMOCIÓN (Excepto Comercial)
    if speaker == "Comercial":
        print(f"[INFO] Bloque de 'Comercial' procesado (solo transcripción).")
        return

    # Si es un sujeto, analizamos emoción
    emotion, score, all_probs = analyzer.analyze(emotion_file)
    if emotion and score is not None and score > 0.0:
        if callback:
            callback(emotion, score, emotion_file, speaker, all_probs)
        
        block_end_time = block_start_time + (len(combined) / sr)
        # === ANÁLISIS DE CAUSA RAÍZ ===
        _check_concept_trigger(
            emotion, score, speaker,
            transcript_manager, concept_extractor, callback,
            block_end_time
        )
    else:
        print(f"[WARN] Resultado de emoción inválido para '{speaker}'.")

    # Limpieza: Si el hablante no está consolidado, borramos el audio tras analizarlo
    if speaker.startswith("Identificando"):
        _cleanup(emotion_file)


_last_concept_triggers = {}

def _check_concept_trigger(emotion, score, speaker, transcript_manager, concept_extractor, callback, trigger_time):
    """
    Evalúa si la emoción detectada debe disparar un análisis de causa raíz.
    Si procede, lanza la extracción de concepto en un hilo separado para no bloquear el motor.
    """
    if emotion not in TRIGGER_EMOTIONS:
        return
    if score < TRIGGER_EMOTIONS[emotion]:
        return

    # Ignorar fragmentos aún en proceso de identificación
    if speaker.startswith("Identificando"):
        return

    # Aplicar Cooldown por hablante para no saturar con el mismo tema
    now = time.time()
    last_trigger = _last_concept_triggers.get(speaker, 0)
    if now - last_trigger < CONCEPT_COOLDOWN_SECS:
        return
    _last_concept_triggers[speaker] = now
    # Recuperamos 20 segundos antes del trigger
    context = transcript_manager.get_all_speakers_window(
        trigger_time,
        before_secs=CONCEPT_WINDOW_BEFORE,
        after_secs=CONCEPT_WINDOW_AFTER
    )

    if not context:
        print(f"[CONCEPTO] Sin transcripción disponible para análisis de '{emotion}' en {speaker}.")
        return

    print(f"\n[CONCEPTO] 🔥 Trigger activado: {emotion} ({score:.0%}) en {speaker}. Analizando causa raíz con {CONCEPT_WINDOW_BEFORE}s de contexto...")

    # Ejecutar en hilo separado para no bloquear el motor de audio
    threading.Thread(
        target=_run_concept_extraction,
        args=(emotion, score, speaker, context, concept_extractor, callback),
        daemon=True
    ).start()


def _run_concept_extraction(emotion, score, speaker, context, concept_extractor, callback):
    """Ejecuta la extracción de concepto detonante en un hilo separado."""
    print(f"[CONCEPTO-THREAD] Iniciando extracción de concepto para {speaker} (Emoción: {emotion})...")
    try:
        concept = concept_extractor.analyze(emotion, score, speaker, context)
        if concept:
            print(f"[CONCEPTO-THREAD] Extracción exitosa. Enviando al callback...")
            if callback:
                callback("CONCEPTO", score, None, speaker, concept)
        else:
            print(f"[CONCEPTO-THREAD] Fallo: El extractor devolvió None (posible fallo de parseo o texto insuficiente).")
    except Exception as e:
        print(f"[CONCEPTO-THREAD] [ERR] Extracción de concepto falló: {e}")


def _save_combined_audio(waveform, sr, speaker):
    """Guarda el audio combinado de un hablante en disco para su análisis."""
    import time
    import soundfile as sf
    from backend.config import AUDIO_DIR
    
    # Crear carpeta específica para el sujeto (o tentative_audios si no está consolidado)
    if speaker.startswith("Identificando"):
        speaker_dir = os.path.join(AUDIO_DIR, "tentative_audios")
    else:
        speaker_name_safe = speaker.replace(' ', '_')
        speaker_dir = os.path.join(AUDIO_DIR, speaker_name_safe)
        
    if not os.path.exists(speaker_dir):
        os.makedirs(speaker_dir)

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
