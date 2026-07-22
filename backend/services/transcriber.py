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
from transformers import WhisperForConditionalGeneration, WhisperProcessor
from backend.config import WHISPER_MODEL, WHISPER_LANGUAGE, WHISPER_MODEL_MAP



class Transcriber:
    """
    Servicio de transcripción de voz a texto en tiempo real.
    Usa Whisper vía transformers (inferencia directa, sin pipeline).
    Evita la dependencia de av/PyAV que causa problemas con Control de Aplicaciones.
    """
    def __init__(self, model_size=WHISPER_MODEL, language=WHISPER_LANGUAGE, 
                 model=None, processor=None, forced_decoder_ids=None):
        self.language = language
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if self.device == "cuda" else torch.float32

        # Si se proporcionan modelos pre-cargados, reutilizarlos
        if model is not None and processor is not None:
            self.model = model
            self.processor = processor
            self.forced_decoder_ids = forced_decoder_ids or self.processor.get_decoder_prompt_ids(
                language=self.language, task="transcribe"
            )
            # from backend.config import WHISPER_VOCAB_HINT
            # if WHISPER_VOCAB_HINT and self.processor:
            #     self.prompt_ids = self.processor.get_prompt_ids(WHISPER_VOCAB_HINT, return_tensors="pt").to(self.device)
            # else:
            self.prompt_ids = None
            
            print(f"[INFO] Transcriber inicializado con modelo pre-cargado en {self.device.upper()}.")
            return

        # Carga estándar (fallback)
        model_id = WHISPER_MODEL_MAP.get(model_size, f"openai/whisper-{model_size}")
        print(f"\n[INFO] Cargando motor de transcripción (Whisper: {model_id})...")

        try:
            self.processor = WhisperProcessor.from_pretrained(model_id)
            self.model = WhisperForConditionalGeneration.from_pretrained(
                model_id,
                dtype=self.torch_dtype,
                low_cpu_mem_usage=True,
            ).to(self.device)
            self.model.eval()

            # Obtener el token de idioma para forzar español
            self.forced_decoder_ids = self.processor.get_decoder_prompt_ids(
                language=self.language, task="transcribe"
            )

            # from backend.config import WHISPER_VOCAB_HINT
            # if WHISPER_VOCAB_HINT and self.processor:
            #     self.prompt_ids = self.processor.get_prompt_ids(WHISPER_VOCAB_HINT, return_tensors="pt").to(self.device)
            # else:
            self.prompt_ids = None

            print(f"[INFO] Transcriber cargado en {self.device.upper()}.")
        except Exception as e:
            print(f"[ERROR] Fallo al cargar Whisper: {e}")
            self.model = None
            self.processor = None

    def transcribe(self, audio_array, sample_rate=16000):
        """
        Transcribe un fragmento de audio.

        Args:
            audio_array: numpy array (float32 o float64, mono)
            sample_rate: frecuencia de muestreo (debe ser 16000 para Whisper)

        Returns:
            list[dict]: Lista de segmentos con formato:
                [{"start": float, "end": float, "text": str}, ...]
        """
        if self.model is None or self.processor is None:
            return []

        try:
            # Whisper espera float32
            if audio_array.dtype != np.float32:
                audio_array = audio_array.astype(np.float32)

            # Procesar audio → features
            inputs = self.processor(
                audio_array,
                sampling_rate=sample_rate,
                return_attention_mask=True,
                return_tensors="pt"
            )
            input_features = inputs.input_features.to(self.device, dtype=self.torch_dtype)
            attention_mask = inputs.attention_mask.to(self.device) if "attention_mask" in inputs else None

            # Generar tokens
            with torch.no_grad():
                gen_kwargs = {
                    "language": self.language,
                    "task": "transcribe"
                }
                if attention_mask is not None:
                    gen_kwargs["attention_mask"] = attention_mask
                if hasattr(self, 'prompt_ids') and self.prompt_ids is not None:
                    gen_kwargs["prompt_ids"] = self.prompt_ids[0] if self.prompt_ids.dim() > 1 else self.prompt_ids
                    
                predicted_ids = self.model.generate(
                    input_features,
                    **gen_kwargs
                )

            # Decodificar texto
            text = self.processor.batch_decode(
                predicted_ids, skip_special_tokens=True
            )[0].strip()

            # --- Filtro básico ---
            # Descartar frases minúsculas de 1-2 letras (ej: "y", "eh", ".")
            clean_text = text.replace(".", "").replace(",", "").replace("!", "").replace("¡", "").strip()
            if len(clean_text) <= 2:
                text = ""

            if text:
                return [{
                    "start": 0.0,
                    "end": len(audio_array) / sample_rate,
                    "text": text
                }]

            return []

        except Exception as e:
            print(f"[ERR STT] {e}")
            return []
