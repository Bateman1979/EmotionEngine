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
from pyannote.audio import Pipeline, Model, Inference
import os
from dotenv import load_dotenv
from backend.services.identity_manager import SpeakerManager

load_dotenv()

class Diarizer:
    """
    Identificador de interlocutores con soporte multi-hablante.
    """
    def __init__(self):
        self.speaker_manager = SpeakerManager(strict_threshold=0.48, tentative_threshold=0.60)
        token = os.getenv("HF_TOKEN")
        if not token:
            print("[ERROR] HF_TOKEN no encontrado")
            self.pipeline = None
            return
            
        try:
            print("[INFO] Cargando Pipeline y Extractor de Huellas...")
            self.pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=token)
            self.embedding_model = Model.from_pretrained("pyannote/embedding", token=token)
            
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                self.pipeline.to(self.device)
                self.embedding_model.to(self.device)
                print("[INFO] Modelos cargados en GPU.")
            else:
                self.device = torch.device("cpu")

            self.inference = Inference(self.embedding_model, window="sliding", duration=5.0, step=2.5)
            
        except Exception as e:
            print(f"[ERROR] Error al cargar modelos: {e}")
            self.pipeline = None

    def process(self, audio_path, max_speakers=None):
        """
        Analiza el audio buscando múltiples hablantes, los identifica uno a uno.
        """
        if not self.pipeline: return []
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100: return []
        
        # Sincronizar el límite con el gestor de identidades
        self.speaker_manager.max_speakers = max_speakers
            
        try:
            # 1. CARGA EN MEMORIA (Fix Windows)
            waveform, sample_rate = sf.read(audio_path)
            if len(waveform.shape) > 1: waveform = waveform.mean(axis=1)
            waveform_tensor = torch.from_numpy(waveform).float().unsqueeze(0)
            
            # 2. PIPELINE
            # Solo pasamos max_speakers. NUNCA pasamos min_speakers en tiempo real
            # porque en 2 segundos es muy probable que solo hable 1 persona.
            diarization = self.pipeline(
                {"waveform": waveform_tensor, "sample_rate": sample_rate},
                max_speakers=max_speakers
            )
            
            # 3. PROCESAR RESULTADOS (Soporte DiarizeOutput)
            annotation = diarization
            if hasattr(diarization, "speaker_diarization"):
                annotation = diarization.speaker_diarization

            # Recopilar todos los turnos válidos (mayores a 0.8s)
            all_turns = []
            for turn, _, speaker_id in annotation.itertracks(yield_label=True):
                if (turn.end - turn.start) >= 0.8:
                    all_turns.append((turn.start, turn.end, speaker_id))

            detected_segments = []
            for i, (start_s, end_s, speaker_id) in enumerate(all_turns):
                # Comprobar solapamiento con cualquier otro turno
                is_overlapping = False
                for j, (other_start, other_end, _) in enumerate(all_turns):
                    if i == j: continue
                    # Hay solapamiento si (start1 < end2) y (start2 < end1)
                    if start_s < other_end and other_start < end_s:
                        is_overlapping = True
                        break
                
                if is_overlapping:
                    continue # Descartar fragmento solapado
                
                start_sample = int(start_s * sample_rate)
                end_sample = int(end_s * sample_rate)
                chunk = waveform_tensor[:, start_sample:end_sample]
                
                embedding = self.extract_stable_embedding(chunk, sample_rate)
                
                if embedding is not None:
                    name = self.speaker_manager.get_identity(embedding, (end_s - start_s))
                    detected_segments.append({
                        "start": start_s,
                        "end": end_s,
                        "speaker": name
                    })
            
            return self.merge_segments(detected_segments)
            
        except Exception as e:
            print(f"[ERROR DIARIZACIÓN] {e}")
            return []

    def extract_stable_embedding(self, chunk_tensor, sample_rate):
        try:
            chunk_tensor = chunk_tensor.to(self.device)
            embeddings_sequence = self.inference({"waveform": chunk_tensor, "sample_rate": sample_rate})
            
            # Validación de forma robusta: evita "Mean of empty slice"
            if hasattr(embeddings_sequence, "data"):
                data = embeddings_sequence.data
                # Verificar que el array tiene filas reales (shape[0] > 0)
                if isinstance(data, np.ndarray) and data.ndim >= 1 and data.shape[0] > 0:
                    result = np.nanmean(data, axis=0)
                    # Verificar que el resultado no contiene NaN (por división por cero)
                    if result is not None and not np.any(np.isnan(result)):
                        return result

            # Fallback: ventana completa para segmentos sin datos deslizantes
            inf_whole = Inference(self.embedding_model, window="whole")
            inf_whole.to(self.device)
            result = inf_whole({"waveform": chunk_tensor, "sample_rate": sample_rate})
            if result is not None and not np.any(np.isnan(result)):
                return result
            return None
        except Exception as e:
            print(f"[ERR EMBEDDING] {e}")
            return None

    def merge_segments(self, segments):
        if not segments: return []
        merged = []
        curr = segments[0]
        for next_seg in segments[1:]:
            if next_seg['speaker'] == curr['speaker']:
                curr['end'] = next_seg['end']
            else:
                merged.append(curr)
                curr = next_seg
        merged.append(curr)
        return merged
