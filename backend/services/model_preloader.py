# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import threading
import time
import torch
import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  PRECARGADOR DE MODELOS (Singleton)
#  Carga los 4 modelos pesados en un hilo de
#  background para que estén listos al instante
#  cuando el usuario pulse "Iniciar análisis".
# ─────────────────────────────────────────────

class ModelPreloader:
    """
    Gestiona la precarga asíncrona de modelos de IA al arrancar el servidor.
    Orden de carga (por prioridad de uso):
      1. Silero VAD (detección de voz)
      2. Pyannote Diarization + Embedding (identificación de hablantes)
      3. Whisper (transcripción)
      4. GSI-UPM wav2vec2 (emociones)
    """

    def __init__(self):

        # Estado de carga
        self._ready = threading.Event()
        self._progress = {"loaded": 0, "total": 5, "current": "", "error": None}
        self._progress_lock = threading.Lock()
        self._on_progress = None  # Callback opcional para notificaciones

        # Modelos cargados
        self.vad_model = None
        self.diarization_pipeline = None
        self.embedding_model = None
        self.embedding_inference = None
        self.whisper_model = None
        self.whisper_processor = None
        self.whisper_forced_decoder_ids = None
        self.emotion_model = None
        self.emotion_feature_extractor = None
        self.emotion_labels = None
        self.rag_service = None

        # Dispositivo
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if self.device == "cuda" else torch.float32

    def start_preloading(self, on_progress=None):
        """Lanza la precarga de modelos en un hilo de background."""
        self._on_progress = on_progress
        thread = threading.Thread(target=self._load_all, daemon=True)
        thread.start()

    def _update_progress(self, loaded, current):
        """Actualiza el estado de progreso y notifica si hay callback."""
        with self._progress_lock:
            self._progress["loaded"] = loaded
            self._progress["current"] = current
        if self._on_progress:
            try:
                self._on_progress(self.get_status())
            except Exception:
                pass

    def get_status(self):
        """Devuelve el estado actual de la precarga."""
        with self._progress_lock:
            return {
                "ready": self._ready.is_set(),
                "loaded": self._progress["loaded"],
                "total": self._progress["total"],
                "current": self._progress["current"],
                "error": self._progress["error"]
            }

    def wait_until_ready(self, timeout=180):
        """Bloquea hasta que todos los modelos estén cargados."""
        return self._ready.wait(timeout=timeout)

    @property
    def is_ready(self):
        return self._ready.is_set()

    def _load_all(self):
        """Carga secuencial de los 4 modelos."""
        start_time = time.time()
        print("\n" + "=" * 50)
        print("  🧠 PRECARGA DE MODELOS EN BACKGROUND")
        print("=" * 50)

        try:
            # 1. Silero VAD
            self._update_progress(0, "Silero VAD")
            print("[PRELOAD 1/5] Cargando Silero VAD...")
            self._load_vad()
            self._update_progress(1, "Silero VAD ✓")
            print("[PRELOAD 1/5] ✅ Silero VAD listo.")

            # 2. Pyannote (Diarización + Embedding)
            self._update_progress(1, "Pyannote Diarización")
            print("[PRELOAD 2/5] Cargando Pyannote Diarización + Embedding...")
            self._load_diarization()
            self._update_progress(2, "Pyannote ✓")
            print("[PRELOAD 2/5] ✅ Pyannote listo.")

            # 3. Whisper
            self._update_progress(2, "Whisper STT")
            print("[PRELOAD 3/5] Cargando Whisper (transcripción)...")
            self._load_whisper()
            self._update_progress(3, "Whisper ✓")
            print("[PRELOAD 3/5] ✅ Whisper listo.")

            # 4. GSI-UPM Emociones
            self._update_progress(3, "GSI-UPM Emociones")
            print("[PRELOAD 4/5] Cargando GSI-UPM (emociones)...")
            self._load_emotion()
            self._update_progress(4, "GSI-UPM ✓")
            print("[PRELOAD 4/5] ✅ GSI-UPM listo.")

            # 5. RAG Service (Sentence Transformers)
            self._update_progress(4, "Base de Conocimiento RAG")
            print("[PRELOAD 5/6] Vectorizando base de conocimiento RAG...")
            self._load_rag()
            print("[PRELOAD 5/6] ✅ RAG listo.")

            # 6. LLM (Concept Extractor)
            self._update_progress(5, "Cargando LLM Causa Raíz")
            print("[PRELOAD 6/6] Cargando LLM (Causa Raíz)...")
            self._load_llm()
            print("[PRELOAD 6/6] ✅ LLM listo.")
            
            # Fijar ready = True ANTES de enviar la notificación final
            self._ready.set()
            self._update_progress(6, "Completado ✓")

            elapsed = time.time() - start_time
            print(f"\n{'=' * 50}")
            print(f"  ✅ TODOS LOS MODELOS CARGADOS ({elapsed:.1f}s)")
            print(f"  💡 El análisis se iniciará de forma instantánea.")
            print(f"{'=' * 50}\n")

        except Exception as e:
            with self._progress_lock:
                self._progress["error"] = str(e)
            print(f"\n[ERROR PRELOAD] Fallo durante la precarga: {e}")
            import traceback
            traceback.print_exc()
            self._ready.set()
            self._update_progress(self._progress["loaded"], "Error")
        finally:
            self._ready.set()

    def _load_vad(self):
        """Carga el modelo Silero VAD."""
        from silero_vad import load_silero_vad
        self.vad_model = load_silero_vad()

    def _load_diarization(self):
        """Carga el pipeline de Pyannote y el modelo de embedding."""
        from pyannote.audio import Pipeline, Model, Inference

        token = os.getenv("HF_TOKEN")
        if not token:
            raise ValueError("HF_TOKEN no encontrado en .env")

        self.diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", token=token
        )
        self.embedding_model = Model.from_pretrained(
            "pyannote/embedding", token=token
        )

        if self.device == "cuda":
            self.diarization_pipeline.to(torch.device("cuda"))
            self.embedding_model.to(torch.device("cuda"))

        self.embedding_inference = Inference(
            self.embedding_model, window="sliding", duration=5.0, step=2.5
        )

    def _load_whisper(self):
        """Carga Whisper (modelo + procesador)."""
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        from backend.config import WHISPER_MODEL, WHISPER_LANGUAGE, WHISPER_MODEL_MAP

        model_id = WHISPER_MODEL_MAP.get(WHISPER_MODEL, f"openai/whisper-{WHISPER_MODEL}")

        self.whisper_processor = WhisperProcessor.from_pretrained(model_id)
        self.whisper_model = WhisperForConditionalGeneration.from_pretrained(
            model_id,
            dtype=self.torch_dtype,
            low_cpu_mem_usage=True,
        ).to(self.device)
        self.whisper_model.eval()

        # Ya no usamos forced_decoder_ids, usamos el método moderno en Transcriber
        self.whisper_forced_decoder_ids = None

    def _load_emotion(self):
        """Carga el modelo GSI-UPM de emociones."""
        from transformers import AutoModelForAudioClassification, Wav2Vec2FeatureExtractor

        from backend.config import EMOTION_MODEL_ID
        model_id = EMOTION_MODEL_ID
        self.emotion_feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_id)
        self.emotion_model = AutoModelForAudioClassification.from_pretrained(
            model_id,
            use_safetensors=True if self.device == "cuda" else False
        ).to(self.device)
        self.emotion_model.eval()
        self.emotion_labels = self.emotion_model.config.id2label

    def _load_rag(self):
        """Carga y vectoriza la base de conocimiento para RAG."""
        try:
            from backend.services.rag_service import RAGService
            self.rag_service = RAGService()
        except Exception as e:
            print(f"[ERROR PRELOAD] No se pudo inicializar RAG: {e}")
            raise e

    def _load_llm(self):
        """Carga el modelo LLM para la extracción de conceptos."""
        try:
            from backend.services.concept_extractor import ConceptExtractor
            self.concept_extractor = ConceptExtractor()
            self.concept_extractor._ensure_loaded()
        except Exception as e:
            print(f"[ERROR PRELOAD] No se pudo inicializar LLM: {e}")
            raise e

# Singleton global
preloader = ModelPreloader()
