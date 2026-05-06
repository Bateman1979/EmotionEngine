# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import os
import pickle
import torch
import torchaudio
import soundfile as sf
import subprocess
from backend.config import CALIBRATION_FILE, AUDIO_DIR
from backend.services.identity_manager import SpeakerProfile

class CalibrationManager:
    def __init__(self, diarizer):
        self.diarizer = diarizer

    def is_calibrated(self):
        return os.path.exists(CALIBRATION_FILE)

    def process_calibration_audio(self, file_path):
        """
        Procesa el audio de 15s y registra la huella del comercial.
        """
        print(f"[CALIB] Procesando archivo: {file_path} (Tamaño: {os.path.getsize(file_path)} bytes)")
        
        # 1. Conversión a WAV usando ffmpeg (garantiza compatibilidad total)
        wav_path = file_path.replace(".webm", ".wav")
        try:
            print(f"[CALIB] Convirtiendo {file_path} a WAV...")
            # Sobrescribimos si ya existe (-y)
            subprocess.run(['ffmpeg', '-y', '-i', file_path, '-ar', '16000', '-ac', '1', wav_path], 
                           check=True, capture_output=True)
            file_path = wav_path
            print(f"[CALIB] Conversión exitosa: {file_path}")
        except Exception as e:
            print(f"[CALIB] Error en conversión ffmpeg: {e}")
            # Si falla, intentamos seguir con el original por si acaso

        try:
            # 2. Carga del audio
            try:
                waveform, sample_rate = torchaudio.load(file_path)
                print(f"[CALIB] Audio cargado con torchaudio. SR: {sample_rate}, Channels: {waveform.shape[0]}")
            except Exception as e:
                print(f"[CALIB] Error cargando con torchaudio: {e}. Intentando fallback...")
                import soundfile as sf
                data, sample_rate = sf.read(file_path)
                waveform = torch.from_numpy(data).float()
                if len(waveform.shape) == 1:
                    waveform = waveform.unsqueeze(0)
                else:
                    waveform = waveform.T
                print(f"[CALIB] Audio cargado con soundfile fallback.")

            # Convertir a mono si no lo hizo ffmpeg
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            
            # Re-muestreo a 16kHz si no lo hizo ffmpeg
            if sample_rate != 16000:
                print(f"[CALIB] Re-muestreando de {sample_rate} a 16000...")
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)
                sample_rate = 16000
                
            # 3. Extracción de embedding
            print("[CALIB] Extrayendo huella acústica...")
            embedding = self.diarizer.extract_stable_embedding(waveform, sample_rate)
            
            if embedding is not None:
                print("[CALIB] Huella extraída con éxito.")
                self.diarizer.speaker_manager.set_commercial_profile(embedding)
                
                # Guardamos una copia permanente para que el usuario pueda verificar la calidad
                speaker_dir = os.path.join(AUDIO_DIR, "Comercial")
                if not os.path.exists(speaker_dir):
                    os.makedirs(speaker_dir)
                
                final_sample_path = os.path.join(speaker_dir, "calibration_commercial.wav")
                if os.path.exists(wav_path):
                    import shutil
                    shutil.copy(wav_path, final_sample_path)
                    print(f"[CALIB] Muestra guardada en carpeta de sujeto: {final_sample_path}")
                
                return True, "Calibración completada con éxito."
            else:
                return False, "No se pudo extraer una huella clara del audio."
                
        except Exception as e:
            print(f"[CALIB] Error crítico: {str(e)}")
            return False, f"Error procesando calibración: {str(e)}"
        finally:
            # Intentar limpiar el wav temporal si quedó algo
            if os.path.exists(wav_path) and ".wav" in wav_path:
                try: os.remove(wav_path)
                except: pass

    def get_commercial_centroid(self):
        """Recupera el centroide del comercial si existe."""
        if os.path.exists(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, 'rb') as f:
                return pickle.load(f)
        return None
