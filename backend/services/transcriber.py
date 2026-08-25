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
            # NOTA: Pasar listas de palabras sueltas como prompt_ids en WhisperForConditionalGeneration
            # rompe drásticamente la distribución de probabilidad del decodificador, causando
            # alucinaciones severas y bucles ("y la gran desgracia de la vida...").
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
                    
                # Nota: repetition_penalty nativo rompe la generación de Whisper, 
                # así que dependemos exclusivamente del filtro post-procesado.
                
                predicted_ids = self.model.generate(
                    input_features,
                    **gen_kwargs
                )

            # Decodificar texto
            text = self.processor.batch_decode(
                predicted_ids, skip_special_tokens=True
            )[0].strip()

            # --- Filtros de Limpieza ---
            clean_text = text.replace(".", "").replace(",", "").replace("!", "").replace("¡", "").strip()
            
            # 1. Descartar frases minúsculas sin sentido o alucinaciones comunes de silencio
            if len(clean_text) <= 6:
                return []
                
            # 2. Descartar alucinaciones de bucle (ej: "Díaz, Díaz, Díaz..." o "de la, de la")
            words = clean_text.lower().split()
            
            # Descartar frases muy cortas que solo son conectores comunes repetidos
            if len(words) <= 3 and all(w in ['de', 'la', 'el', 'y', 'que', 'en', 'a', 'los'] for w in words):
                return []
                
            if len(words) > 3:
                unique_words = set(words)
                # Si hay muy poca variedad de palabras en una frase, es un bucle
                if len(unique_words) <= 2:
                    return []

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
