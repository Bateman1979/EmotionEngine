# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import os
import wave
import time
import pyaudio
from backend.config import AUDIO_DIR, RATE, CHANNELS, FORMAT, CHUNKS_PER_SECOND, CHUNK_WINDOW_SECS

# Número de chunks por segundo (RATE / CHUNK ≈ 31 chunks/s)
CHUNK_WINDOW_SIZE = CHUNKS_PER_SECOND * CHUNK_WINDOW_SECS  # ~62 chunks

class AudioSegmenter:
    """
    Emite ventanas de audio de 2 segundos de forma continua mientras hay voz activa.
    No tiene concepto de FINAL/EARLY: cada ventana es un chunk para el motor.
    """
    def __init__(self):
        self.frames = []
        self.is_recording = False

        if not os.path.exists(AUDIO_DIR):
            os.makedirs(AUDIO_DIR)
            print(f"[INFO] Carpeta '{AUDIO_DIR}' creada.")

    def process_event(self, event, audio_chunk):
        """
        Gestiona la acumulación de audio.
        Retorna:
            - (filename, "CHUNK") cada vez que se acumulan 2 segundos de voz.
            - None en otros casos.
        """
        if event == "START":
            self.is_recording = True
            self.frames = [audio_chunk]
            return None

        elif event == "END":
            self.is_recording = False
            filename = None
            # Emitir fragmento residual si tiene al menos 0.5s para no perder finales
            if len(self.frames) >= (CHUNKS_PER_SECOND * 0.5):
                filename = self.save_segment()
                
            self.frames = []
            if filename:
                return (filename, "FINAL_CHUNK")
            return None

        elif self.is_recording:
            self.frames.append(audio_chunk)

            # Emitir ventana cada 2 segundos (62 chunks)
            if len(self.frames) >= CHUNK_WINDOW_SIZE:
                filename = self.save_segment()
                self.frames = []  # Reset para el siguiente chunk de 2s
                return (filename, "CHUNK")

        return None

    def save_segment(self):
        """Guarda los frames acumulados en un archivo .wav temporal."""
        if not self.frames:
            return None

        timestamp = int(time.time() * 1000)  # ms para evitar colisiones
        filename = os.path.join(AUDIO_DIR, f"chunk_{timestamp}.wav")

        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        return filename
