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
import warnings
import logging

# Silenciar los logs informativos de pytorch_lightning (como el aviso de upgrade de checkpoint)
logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)

# Ocultar todo tipo de warnings para mantener la terminal limpia
warnings.filterwarnings("ignore", message=".*Mean of empty slice.*")
warnings.filterwarnings("ignore", message=".*invalid value encountered in divide.*")
warnings.filterwarnings("ignore", message=".*Lightning automatically upgraded.*")
warnings.filterwarnings("ignore", message=".*Model has been trained with a task-dependent loss function.*")
warnings.filterwarnings("ignore", message=".*TensorFloat-32.*")
warnings.filterwarnings("ignore", message=".*degrees of freedom is <= 0.*")
warnings.filterwarnings("ignore", message=".*Found keys that are not in the model state dict.*")
warnings.filterwarnings("ignore", message=".*Redirecting import of pytorch_lightning.*")
warnings.filterwarnings("ignore", message=".*You have multiple `ModelCheckpoint` callback states.*")
warnings.filterwarnings("ignore", message=".*forced_decoder_ids.*")
warnings.filterwarnings("ignore", message=".*attention mask is not set.*")
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

# --- Diarización (Identificación de Hablantes) ---
DIARIZATION_STRICT_THRESHOLD = 0.50   # Distancia máxima para reconocer un perfil graduado (menor = más estricto)
DIARIZATION_TENTATIVE_THRESHOLD = 0.55 # Distancia máxima para fusionar perfiles tentativos entre sí
DIARIZATION_GRADUATION_TIME = 15.0     # Segundos de audio acumulado para graduar un perfil tentativo
DIARIZATION_COMMERCIAL_THRESHOLD = 0.55 # Tolerancia para reconocer la voz del comercial calibrado (más estricto para evitar suplantaciones)
DIARIZATION_TENTATIVE_MAX_AGE = 60.0   # Segundos antes de purgar un perfil tentativo inactivo

# --- Rutas y Almacenamiento ---
DATA_DIR = "data"
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")
SPEAKERS_FILE = os.path.join(DATA_DIR, "speakers.pkl")
CALIBRATION_FILE = os.path.join(DATA_DIR, "calibration.pkl")
TRANSCRIPTS_FILE = os.path.join(DATA_DIR, "transcripts.jsonl")
KNOWLEDGE_BASE_FILE = os.path.join(DATA_DIR, "knowledge", "knowledge.txt")

# --- Transcripción (STT) ---
WHISPER_MODEL = "small"          # Opciones: tiny, base, small, medium, large-v3
WHISPER_LANGUAGE = "es"          # Forzar español
MIN_TRANSCRIBE_SECS = 1.0       # No transcribir segmentos menores a 1s
WHISPER_VOCAB_HINT = (
    "Dios, teísmo, ateísmo, agnosticismo, deísmo, panteísmo, panteísmo, epistemología, ontología, "
    "metafísica, teleología, teodicea, cosmología, contingencia, trascendencia, inmanencia, dogma, "
    "apologética, exégesis, argumento cosmológico, motor inmóvil, primera causa, argumento teleológico, "
    "diseño inteligente, ajuste fino, fine-tuning, principio antrópico, argumento ontológico, "
    "argumento moral, problema del mal, libre albedrío, determinismo, empirismo, falsabilidad, "
    "navaja de Ockham, silogismo, premisa, axioma, falacia, tautología, reduccionismo, solipsismo, "
    "Tomás de Aquino, cinco vías, Aristóteles, Immanuel Kant, Friedrich Nietzsche, Baruch Spinoza, "
    "René Descartes, David Hume, Bertrand Russell, Richard Dawkins, William Lane Craig, Alvin Plantinga, "
    "Big Bang, mecánica cuántica, termodinámica, entropía, evolución, darwinismo, multiverso, "
    "abiogénesis, singularidad, omnipotencia, omnisciencia, omnipresencia, revelación, milagro"
)

WHISPER_MODEL_MAP = {            # Mapeo de nombres cortos a IDs de HuggingFace
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large-v3": "openai/whisper-large-v3",
}

# --- Análisis de Causa Raíz ---
TRIGGER_EMOTIONS = {             # Emociones que disparan el análisis + umbral mínimo
    "Ira": 0.70,
    "Tristeza": 0.70,
    "Miedo": 0.60,
    "Asco": 0.60,
    "Alegria": 0.60,
    "Sorpresa": 0.60,
    "Neutro": 1.00,
}
CONCEPT_WINDOW_BEFORE = 60      # Segundos de contexto ANTES del pico emocional
CONCEPT_WINDOW_AFTER = 0        # 0 = Estrategia A (inmediata, sin esperar)
CONCEPT_COOLDOWN_SECS = 0       # Segundos de espera mínima antes de volver a analizar la causa raíz del mismo hablante (0 para desactivar)

# --- LLM (Extracción de Conceptos) ---
LLM_MODEL = "Qwen/Qwen2.5-3B-Instruct"

# --- Ventanas y Segmentación ---
EMOTION_WINDOW_SECS = 15.0       # Analizar/transcribir cada 15s por hablante
STALE_THRESHOLD_SECS = 15.0      # Si un sujeto calla >15s, procesamos lo que tenga y reiniciamos
CHUNKS_PER_SECOND = 31
CHUNK_WINDOW_SECS = 2            # Emitir un chunk cada 2 segundos

# --- Modelos de IA ---
EMOTION_MODEL_ID = "gsi-upm/wav2vec_spanish_emotion-analysis"
RAG_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
