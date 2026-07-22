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
        
        # 1. Conversión a WAV 16kHz mono usando ffmpeg
        wav_path = file_path.replace(".webm", ".wav")
        try:
            print(f"[CALIB] Convirtiendo {file_path} a WAV...")
            subprocess.run(['ffmpeg', '-y', '-i', file_path, '-ar', '16000', '-ac', '1', wav_path], 
                           check=True, capture_output=True)
            file_path = wav_path
            print(f"[CALIB] Conversión exitosa: {file_path}")
        except Exception as e:
            print(f"[CALIB] Error en conversión ffmpeg: {e}")

        try:
            # 2. Carga del audio con soundfile (consistente con el resto del proyecto)
            import numpy as np
            data, sample_rate = sf.read(file_path)
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            # === DIAGNÓSTICO DE AUDIO ===
            duration_secs = len(data) / sample_rate
            rms = np.sqrt(np.mean(data**2))
            peak = np.max(np.abs(data))
            print(f"[CALIB] 📊 Diagnóstico del audio:")
            print(f"[CALIB]   Duración: {duration_secs:.1f}s | SR: {sample_rate}Hz")
            print(f"[CALIB]   RMS: {rms:.6f} | Peak: {peak:.6f}")
            print(f"[CALIB]   Shape: {data.shape} | dtype: {data.dtype}")
            
            if rms < 0.0001:
                print(f"[CALIB] ⚠️ AUDIO PRÁCTICAMENTE VACÍO (RMS={rms:.8f}). El dispositivo de grabación no está captando sonido.")
                return False, f"El audio grabado está vacío (RMS={rms:.8f}). Asegúrate de que el navegador usa el dispositivo de audio correcto."
            # ============================

            # --- VAD Basado en Energía para limpiar la Calibración ---
            chunk_size = int(sample_rate * 0.25)  # chunks de 250ms
            if len(data) > chunk_size:
                chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
                energies = [np.mean(c**2) for c in chunks]
                
                threshold = np.max(energies) * 0.05
                clean_data = [c for c, e in zip(chunks, energies) if e > threshold]
                
                if clean_data:
                    data = np.concatenate(clean_data)
                    print(f"[CALIB] Silencios eliminados. Duración limpia: {len(data)/sample_rate:.1f}s")
                else:
                    print(f"[CALIB] ⚠️ VAD descartó TODO el audio. Usando el original.")
            # ---------------------------------------------------------

            waveform = torch.from_numpy(data).float().unsqueeze(0)
            print(f"[CALIB] Audio final listo. Muestras: {waveform.shape[1]}")

            # Re-muestreo a 16kHz si ffmpeg no lo hizo
            if sample_rate != 16000:
                print(f"[CALIB] Re-muestreando de {sample_rate} a 16000...")
                import torchaudio
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
