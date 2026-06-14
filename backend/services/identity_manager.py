# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import numpy as np
import os
import pickle
from scipy.spatial.distance import cosine
from backend.config import SPEAKERS_FILE, CALIBRATION_FILE


class SpeakerProfile:
    """Representa a un hablante y su evolución sonora."""
    def __init__(self, embedding, initial_duration, name=None):
        self.centroid = embedding / np.linalg.norm(embedding)
        self.total_duration = initial_duration
        self.name = name  # None = tentativo, "Sujeto X" = graduado
        self.samples_count = 1

    def update(self, new_embedding, duration):
        """Fusiona y perfecciona el perfil con el nuevo audio."""
        new_embedding = new_embedding / np.linalg.norm(new_embedding)
        # Mezcla ponderada: el perfil evoluciona pero mantiene una base sólida
        weight = min(0.3, 1.0 / (self.samples_count + 1))
        self.centroid = (self.centroid * (1 - weight)) + (new_embedding * weight)
        self.centroid = self.centroid / np.linalg.norm(self.centroid)
        self.total_duration += duration
        self.samples_count += 1

    @property
    def is_graduated(self):
        return self.name is not None and not self.name.startswith("Tentativo")


class SpeakerManager:
    """
    Gestor de identidades v5: Sistema de dos niveles.
    - Nivel 1 (Tentativos): Fragmentos sin confirmar, se fusionan agresivamente.
    - Nivel 2 (Graduados): Perfiles seguros con ≥15s, se comparan estrictamente.
    """
    def __init__(self,
                 strict_threshold=0.48,    # Para comparar con perfiles graduados
                 tentative_threshold=0.60, # Para fusionar perfiles tentativos entre sí
                 graduation_time=15.0,
                 max_speakers=None):
        self.strict_threshold    = strict_threshold
        self.tentative_threshold = tentative_threshold
        self.graduation_time     = graduation_time
        self.max_speakers        = max_speakers
        self.profiles            = []   # Lista de SpeakerProfile (tentativos + graduados)
        self.commercial_profile  = None
        self.speaker_counter     = 0
        self.load_identities()
        self.load_calibration()

    def get_identity(self, embedding, duration):
        if embedding is None or np.isnan(embedding).any():
            return "Identificando..."
        
        embedding = embedding / np.linalg.norm(embedding)

        # ── Prioridad 0: ¿Es el Comercial calibrado? ──────────────────────────
        if self.commercial_profile:
            dist = cosine(embedding, self.commercial_profile.centroid)
            if dist < self.strict_threshold:
                self.commercial_profile.update(embedding, duration)
                return "Comercial"

        # ── Prioridad 1: Comparar con perfiles GRADUADOS (umbral estricto) ────
        graduated = [p for p in self.profiles if p.is_graduated]
        best_grad, min_grad_dist = self._best_match(embedding, graduated)

        # Ajuste dinámico: si ya llegamos al máximo de hablantes, somos más permisivos
        # para evitar crear perfiles extra innecesarios.
        current_threshold = self.strict_threshold
        if self.max_speakers and len(graduated) >= self.max_speakers:
            current_threshold = 0.65 # Umbral muy permisivo para forzar la unión

        if best_grad and min_grad_dist < current_threshold:
            best_grad.update(embedding, duration)
            return best_grad.name

        # ── Prioridad 2: Comparar con perfiles TENTATIVOS (umbral permisivo) ──
        tentatives = [p for p in self.profiles if not p.is_graduated]
        best_tent, min_tent_dist = self._best_match(embedding, tentatives)

        if best_tent and min_tent_dist < self.tentative_threshold:
            best_tent.update(embedding, duration)
            # ¿Listo para graduarse?
            if best_tent.total_duration >= self.graduation_time:
                self.speaker_counter += 1
                best_tent.name = f"Sujeto {chr(64 + self.speaker_counter)}"
                print(f"\n[ID] ¡{best_tent.name} graduado! ({best_tent.total_duration:.1f}s acumulados)")
                self.save_identities()
            return best_tent.name if best_tent.is_graduated else f"Identificando... ({best_tent.total_duration:.1f}s)"

        # ── Prioridad 3: Demasiado diferente a todo → nuevo perfil tentativo ──
        new_profile = SpeakerProfile(embedding, duration)
        self.profiles.append(new_profile)
        # Intentar consolidar perfiles tentativos similares entre sí
        self._consolidate_tentatives()
        print(f"[ID] Nuevo perfil tentativo #{len(self.profiles)} ({duration:.1f}s)")
        return f"Identificando... ({duration:.1f}s)"

    def _best_match(self, embedding, profiles):
        """Devuelve (mejor perfil, distancia mínima) de una lista dada."""
        best, min_dist = None, 1.0
        for p in profiles:
            d = cosine(embedding, p.centroid)
            if d < min_dist:
                min_dist = d
                best = p
        return best, min_dist

    def _consolidate_tentatives(self):
        """
        Compara los perfiles tentativos entre sí y fusiona los que son similares.
        Reduce la proliferación de perfiles duplicados.
        """
        changed = True
        while changed:
            changed = False
            tentatives = [p for p in self.profiles if not p.is_graduated]
            for i, p1 in enumerate(tentatives):
                for p2 in tentatives[i+1:]:
                    dist = cosine(p1.centroid, p2.centroid)
                    if dist < self.tentative_threshold:
                        # Fusionar p2 en p1 (el más antiguo / con más muestras)
                        dominant = p1 if p1.samples_count >= p2.samples_count else p2
                        recessive = p2 if dominant is p1 else p1
                        # Actualizar el centroide del dominante con el del recesivo
                        dominant.update(recessive.centroid, recessive.total_duration)
                        dominant.samples_count += recessive.samples_count - 1
                        self.profiles.remove(recessive)
                        print(f"[ID] Perfiles tentativos consolidados → {len(self.profiles)} perfiles activos")
                        changed = True
                        break
                if changed:
                    break

    def get_profile(self, name):
        """Devuelve el perfil de un hablante por su nombre."""
        if self.commercial_profile and self.commercial_profile.name == name:
            return self.commercial_profile
        for p in self.profiles:
            if p.name == name:
                return p
        return None

    def set_commercial_profile(self, embedding):
        """Establece la huella del comercial tras la calibración."""
        self.commercial_profile = SpeakerProfile(embedding, 15.0, name="Comercial")
        self.save_calibration()
        print("[ID] Perfil del COMERCIAL registrado correctamente.")

    def load_identities(self):
        """Carga los perfiles graduados persistidos."""
        if os.path.exists(SPEAKERS_FILE):
            try:
                with open(SPEAKERS_FILE, 'rb') as f:
                    data = pickle.load(f)
                    known = data.get('known_speakers', {})
                    self.speaker_counter = data.get('counter', 0)
                    for name, centroid in known.items():
                        prof = SpeakerProfile(centroid, 20.0, name=name)
                        self.profiles.append(prof)
                print(f"[MEMORIA] {len(known)} perfiles graduados cargados.")
            except Exception as e:
                print(f"[WARN] Error cargando identidades: {e}")

    def save_identities(self):
        """Persiste solo los perfiles graduados."""
        known = {p.name: p.centroid for p in self.profiles if p.is_graduated}
        try:
            with open(SPEAKERS_FILE, 'wb') as f:
                pickle.dump({'known_speakers': known, 'counter': self.speaker_counter}, f)
        except Exception as e:
            print(f"[ERR] Guardando identidades: {e}")

    def load_calibration(self):
        """Carga la huella acústica del comercial."""
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, 'rb') as f:
                    centroid = pickle.load(f)
                    self.commercial_profile = SpeakerProfile(centroid, 15.0, name="Comercial")
                print("[MEMORIA] Huella del comercial cargada.")
            except Exception as e:
                print(f"[WARN] Error cargando calibración: {e}")

    def save_calibration(self):
        """Guarda la huella del comercial."""
        if self.commercial_profile:
            try:
                with open(CALIBRATION_FILE, 'wb') as f:
                    pickle.dump(self.commercial_profile.centroid, f)
            except Exception as e:
                print(f"[ERR] Guardando calibración: {e}")
