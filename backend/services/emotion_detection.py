# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import torch
import soundfile as sf
import numpy as np
from transformers import AutoModelForAudioClassification, Wav2Vec2FeatureExtractor
import os

class EmotionAnalyzer:
    """
    Analizador de emociones estable para Español (GSI-UPM).
    Modelo optimizado para TFM con carga de pesos garantizada.
    """
    def __init__(self, model_id="gsi-upm/wav2vec_spanish_emotion-analysis"):
        print(f"\n[INFO] Cargando Motor de Emociones (Estable): {model_id}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Optimizaciones de GPU
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        
        try:
            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_id)
            
            # Carga garantizada
            self.model = AutoModelForAudioClassification.from_pretrained(
                model_id,
                use_safetensors=True if self.device == "cuda" else False
            ).to(self.device)
                
            self.model.eval()
            self.labels = self.model.config.id2label
            print(f"[INFO] Motor GSI-UPM listo. Pesos cargados al 100%.")
        except Exception as e:
            print(f"\n[ERROR CRÍTICO] Fallo en la carga del modelo GSI-UPM.")
            print(f"Detalle: {e}")
            raise e

    def analyze(self, audio_path):
        try:
            speech, sr = sf.read(audio_path)
            duration = len(speech) / sr
            
            # --- VERIFICACIÓN DE REQUISITOS ---
            print(f"[REQUISITOS] Analizando fragmento: {duration:.1f}s | Original SR: {sr}Hz")
            
            # 1. Mono conversion
            if len(speech.shape) > 1: 
                print(f"[REQUISITOS] Convirtiendo estéreo a mono...")
                speech = np.mean(speech, axis=1)

            # 2. Resampling a 16kHz (Requisito estricto de Wav2Vec2)
            if sr != 16000:
                print(f"[REQUISITOS] Re-muestreando de {sr}Hz a 16000Hz...")
                import scipy.signal as signal
                num_samples = int(len(speech) * 16000 / sr)
                speech = signal.resample(speech, num_samples)
                sr = 16000

            # 3. Verificación de energía (RMS)
            rms = np.sqrt(np.mean(speech**2))
            if rms < 0.005:
                print(f"[REQUISITOS] AVISO: Audio demasiado silencioso (RMS: {rms:.5f}).")
                # Si es puro silencio, no perdemos tiempo procesando
                if rms < 0.001: return None, None, None

            # 4. Normalización de amplitud (Peak Normalization)
            max_val = np.max(np.abs(speech))
            if max_val > 0:
                speech = speech / (max_val + 1e-9)
            
            print(f"[REQUISITOS] Calidad verificada. Procesando con GSI-UPM...")

            # Preparar entrada para el extractor de características
            inputs = self.feature_extractor(
                speech, 
                sampling_rate=16000, 
                padding=True, 
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs = torch.nn.functional.softmax(logits, dim=-1)[0]
                best_class_id = torch.argmax(logits, dim=-1).item()
            
            # Debug de todas las probabilidades
            all_probs = {self.labels[i]: f"{probs[i].item():.2f}" for i in range(len(self.labels))}
            print(f"[DEBUG] Probabilidades GSI-UPM: {all_probs}")

            emotion = self.labels[best_class_id]
            conf = probs[best_class_id].item()

            translations = {
                "alegria": "Alegría",
                "asco": "Asco",
                "ira": "Ira",
                "miedo": "Miedo",
                "neutro": "Neutro",
                "sorpresa": "Sorpresa",
                "tristeza": "Tristeza"
            }
            
            # Todas las probabilidades con etiquetas en español
            all_probs = {
                translations.get(self.labels[i].lower(), self.labels[i]): round(probs[i].item(), 4)
                for i in range(len(self.labels))
            }

            emotion_key = translations.get(emotion.lower(), emotion)
            print(f"[IA ESPAÑOL] {emotion_key.upper()} | Confianza: {conf:.1%}")
            return emotion_key, conf, all_probs

        except Exception as e:
            print(f"[ERROR IA] {e}")
            return None, None, None
