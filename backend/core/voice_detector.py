# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import torch
import numpy as np
from silero_vad import load_silero_vad
from backend.config import RATE, VAD_THRESHOLD, MIN_SILENCE_CHUNKS

class VoiceDetector:
    """
    Esta clase se encarga de monitorizar el flujo de audio y detectar 
    la actividad de voz humana utilizando Silero VAD.
    """
    def __init__(self):
        # Carga el modelo de detección de voz (Voice Activity Detection)
        self.model = load_silero_vad()
        # Resetea los estados internos del modelo (importante para Silero v5)
        self.model.reset_states()
        
        # Estado actual: ¿Hay alguien hablando en este momento?
        self.hablando = False
        # Contador de bloques consecutivos de silencio
        self.cont_silencio = 0

    def process_chunk(self, audio_chunk):
        """
        Procesa un chunk de audio y determina si hay un cambio de turno.
        Devuelve: 'START' si empieza a hablar, 'END' si termina, o None.
        """
        # 1. Pre-procesamiento: Convertir el audio de bytes a un tensor de números decimales (float32)
        # Silero VAD espera valores entre -1.0 y 1.0
        audio_int16 = np.frombuffer(audio_chunk, np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # 2. Inferencia: El modelo nos da la probabilidad de que el chunk contenga voz
        with torch.no_grad():
            prob = self.model(torch.from_numpy(audio_float32), RATE).item()

        # [DEBUG] Imprimir probabilidad cada ~3 segundos (100 chunks de 512 samples)
        if not hasattr(self, '_debug_count'): self._debug_count = 0
        self._debug_count += 1
        if self._debug_count % 100 == 0:
            print(f"[DEBUG VAD] Probabilidad de voz: {prob:.4f} | Hablando: {self.hablando}")

        event = None

        # 3. Lógica de estados:
        if prob > VAD_THRESHOLD:
            # Si detectamos voz pero antes estábamos en silencio -> Inicio de turno
            if not self.hablando:
                event = "START"
                self.hablando = True
            self.cont_silencio = 0
        else:
            # Si es silencio, aumentamos el contador
            self.cont_silencio += 1
            # Si llevábamos hablando y superamos el umbral de silencio -> Fin de turno
            if self.hablando and self.cont_silencio > MIN_SILENCE_CHUNKS:
                event = "END"
                self.hablando = False
        
        return event
