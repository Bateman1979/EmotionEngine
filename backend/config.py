# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import pyaudio
import os

# --- Configuración de Audio ---
# PyAudio utiliza estos valores para abrir el stream de sonido
FORMAT = pyaudio.paInt16  # Formato de 16 bits (estándar para voz)
CHANNELS = 1              # Mono
RATE = 16000              # Frecuencia de muestreo (16kHz es el ideal para Silero VAD)
CHUNK = 512               # Tamaño de cada bloque de audio procesado

# --- Lógica de Detección de Turnos ---
# MIN_SILENCE_CHUNKS: Cuántos bloques de silencio seguidos deben pasar para dar por terminado un turno.
# 1000ms (1 segundo) es suficiente para detectar el fin de una frase sin esperar demasiado.
MIN_SILENCE_CHUNKS = (1000 / 32) 

# VAD_THRESHOLD: Sensibilidad del modelo (0.0 a 1.0). 
# Un valor más alto significa que debe estar muy seguro de que es voz.
VAD_THRESHOLD = 0.5

# --- Rutas y Almacenamiento ---
DATA_DIR = "data"
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
SPEAKERS_FILE = os.path.join(DATA_DIR, "speakers.pkl")
CALIBRATION_FILE = os.path.join(DATA_DIR, "calibration.pkl")
