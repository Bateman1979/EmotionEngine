# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import json
import os
from datetime import datetime
from backend.config import TRANSCRIPTS_FILE


class TranscriptManager:
    """
    Gestor de transcripciones con almacenamiento persistente en JSONL.
    Permite añadir segmentos de texto con timestamps de inicio/fin y hablante,
    y consultar ventanas temporales.
    """
    def __init__(self, file_path=TRANSCRIPTS_FILE):
        self.file_path = file_path
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        # Si el archivo no existe, lo creamos vacío
        if not os.path.exists(self.file_path):
            open(self.file_path, 'a').close()

    def add(self, speaker, abs_start, abs_end, text):
        """
        Añade un fragmento transcrito al archivo JSONL.

        Args:
            speaker: Nombre del hablante (ej: "Sujeto A", "Comercial")
            abs_start: Timestamp absoluto de inicio (time.time())
            abs_end: Timestamp absoluto de fin (time.time())
            text: Texto transcrito
        """
        if not text or not text.strip():
            return

        start_str = datetime.fromtimestamp(abs_start).strftime('%H:%M:%S')
        end_str = datetime.fromtimestamp(abs_end).strftime('%H:%M:%S')

        entry = {
            "speaker": speaker,
            "start": abs_start,
            "end": abs_end,
            "timestamp": f"{start_str} - {end_str}",
            "text": text.strip()
        }

        try:
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[ERR] Guardando transcripción en archivo: {e}")

    def get_all_speakers_window(self, center_time, before_secs=20, after_secs=0):
        """
        Devuelve la transcripción de TODOS los hablantes en la ventana temporal,
        ordenada cronológicamente.

        Args:
            center_time: Timestamp central del pico emocional
            before_secs: Segundos antes del centro
            after_secs: Segundos después del centro

        Returns:
            list[tuple]: [(abs_time, speaker, text), ...] ordenada cronológicamente.
                         Lista vacía si no hay transcripciones en la ventana.
        """
        start_window = center_time - before_secs
        end_window = center_time + after_secs
        entries = []

        try:
            if not os.path.exists(self.file_path):
                return []
                
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        
                        # Ignorar fragmentos del perfil "Identificando..." para no ensuciar el contexto
                        if "Identificando" in data["speaker"]:
                            continue

                        # Verificamos si el segmento cae dentro de la ventana (usamos el end para estar seguros)
                        # También sirve si el start está dentro de la ventana.
                        if (start_window <= data["start"] <= end_window) or \
                           (start_window <= data["end"] <= end_window) or \
                           (data["start"] <= start_window and data["end"] >= end_window):
                            entries.append((data["start"], data["speaker"], data["text"]))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[ERR] Leyendo transcripciones: {e}")
            return []

        # Ordenar cronológicamente
        entries.sort(key=lambda x: x[0])
        return entries
