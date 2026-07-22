# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import torch
import json
import re
from transformers import AutoModelForCausalLM, AutoTokenizer
from backend.config import LLM_MODEL


class ConceptExtractor:
    """
    Extrae el concepto detonante de una emoción a partir de la transcripción contextual.
    Usa Phi-3-mini-4k-instruct (Microsoft) como LLM local.
    Carga lazy: el modelo solo se descarga/carga la primera vez que se necesita.
    """
    def __init__(self, model_id=LLM_MODEL):
        self.model_id = model_id
        self.model = None
        self.tokenizer = None
        self.device = None

    def _ensure_loaded(self):
        """Carga el modelo solo cuando se necesita por primera vez."""
        if self.model is not None:
            return

        print(f"\n[INFO] Cargando LLM para análisis de causa raíz: {self.model_id}")
        print(f"[INFO] (Primera carga: puede tardar unos minutos si se descarga el modelo)")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)

        # Intentar GPU con 4-bit (para que quepa en la RTX 2060 junto a los demás modelos)
        if torch.cuda.is_available():
            try:
                from transformers import BitsAndBytesConfig
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    quantization_config=quantization_config,
                    device_map="auto"
                )
                self.device = "cuda"
                print(f"[INFO] LLM cargado en GPU (4-bit quantization).")
            except Exception as e:
                print(f"[WARN] No se pudo cargar LLM en GPU ({e}). Usando CPU...")
                self._load_cpu()
        else:
            self._load_cpu()

        self.model.eval()

    def _load_cpu(self):
        """Carga el modelo en CPU como fallback."""
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            dtype=torch.float32,
        )
        self.device = "cpu"
        print(f"[INFO] LLM cargado en CPU (float32). Inferencia más lenta pero funcional.")

    def analyze(self, emotion, score, speaker, context_entries):
        """
        Analiza la transcripción contextual para identificar el concepto detonante.

        Args:
            emotion: Emoción detectada (ej: "Ira")
            score: Confianza de la emoción (0.0 - 1.0)
            speaker: Hablante que experimentó la emoción
            context_entries: Lista de tuplas (abs_time, speaker_name, text)
                            ordenada cronológicamente

        Returns:
            dict con: concepto_detonante, palabras_clave, severidad, razonamiento
            None si falla el análisis
        """
        self._ensure_loaded()

        # Cortafuegos: No llamar al LLM si no hay transcripción o el texto es muy corto
        if not context_entries:
            print(f"[CONCEPTO] Sin transcripción disponible para análisis.")
            return None

        pure_text = " ".join([text for _, _, text in context_entries]).strip()
        if len(pure_text) <= 5:
            print(f"[CONCEPTO] ⚠️ Transcripción insuficiente ('{pure_text}'). Omitiendo LLM.")
            return None

        # Formatear la transcripción como diálogo legible
        transcript_lines = []
        for _, spk, text in context_entries:
            role = spk
            transcript_lines.append(f"{role}: \"{text}\"")
        transcript_formatted = "\n".join(transcript_lines)

        print(f"\n[DEBUG CONCEPTO] --- TRANSCRIPCIÓN INYECTADA AL LLM ({len(context_entries)} frases) ---")
        print(transcript_formatted)
        print("-----------------------------------------------------------------")

        prompt = self._build_prompt(emotion, score, speaker, transcript_formatted)

        try:
            result_text = self._generate(prompt)
            concept = self._parse_response(result_text)

            if concept:
                concept["emotion"] = emotion
                print(f"\n[CONCEPTO] ✅ Causa raíz identificada para {speaker} ({emotion}):")
                print(f"  → {concept.get('concepto_detonante', 'N/A')}")
                print(f"  → Palabras clave: {concept.get('palabras_clave', [])}")
            else:
                print(f"[CONCEPTO] ⚠️ No se pudo parsear la respuesta del LLM.")

            return concept

        except Exception as e:
            print(f"[ERR CONCEPTO] Error en análisis LLM: {e}")
            return None

    def _build_prompt(self, emotion, score, speaker, transcript):
        """Construye el prompt para Qwen2.5 (formato ChatML)."""
        return f"""<|im_start|>system
Eres un extractor de datos JSON. Tu única salida debe ser un objeto JSON válido.<|im_end|>
<|im_start|>user
Extrae la información factual de esta transcripción:
{transcript}

Rellena y devuelve SOLO este JSON (sin formato markdown):
{{"razonamiento": "resume en 30 palabras los datos objetivos", "concepto_detonante": "dato principal", "contexto_para_rag": "resumen denso de 60 palabras", "palabras_clave": ["kw1", "kw2"], "severidad": "alta/media/baja"}}<|im_end|>
<|im_start|>assistant
{{"""

    def _generate(self, prompt):
        """Genera texto con el LLM."""
        inputs = self.tokenizer(prompt, return_tensors="pt")
        if self.device == "cuda":
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.1,       # Casi determinista
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id
            )

        # Decodificar solo los tokens nuevos (sin el prompt)
        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        
        # Si forzamos la llave de apertura en el prompt, la restauramos
        if prompt.endswith("{"):
            text = "{" + text
            
        return text

    def _parse_response(self, text):
        """
        Parsea la respuesta del LLM a un dict.
        Maneja casos donde el LLM envuelve el JSON en markdown o añade texto extra.
        """
        # Intento 1: Parseo directo
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Intento 2: Extraer JSON de bloques markdown ```json ... ```
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Intento 3: Buscar el primer objeto JSON en el texto
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Intento 4: JSON no parseable — devolver None para no contaminar la UI
        print(f"[CONCEPTO] ⚠️ Respuesta del LLM no parseable (descartada):\n{text[:200]}")
        return None
