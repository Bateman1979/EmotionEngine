# Historial de Modelos de IA 🎭

Este documento registra la evolución de los modelos de Inteligencia Artificial utilizados en el Emotion Engine, detallando las razones de cambio y el estado de cada uno en la arquitectura final.

---

## 🟢 1. Modelos de Emoción (Sentiment Analysis)

### Modelo Actual (Estable)
*   **Nombre**: `gsi-upm/wav2vec_spanish_emotion-analysis`
*   **Arquitectura**: Wav2Vec2.0 Fine-tuned (Spanish)
*   **Estado**: **ACTIVO**
*   **Razón**: Máxima estabilidad y precisión en español. Es el modelo central para la entrega final por su robustez y carga de pesos garantizada.

### Modelos Testeados y Versiones Anteriores
1.  **`UMUTeam/w2v-bert-emotion-es`**: Evaluado como candidato SOTA (W2V-BERT). Se mantiene como reserva.
2.  **`superb/wav2vec2-large-superb-er`**: Retirado por **sesgo crítico** hacia la emoción "feliz" en audio español.
3.  **`pollitoconpapass/superb-ser-finetuned-spanish-v5`**: Versión preliminar, sustituida para mejorar la generalización.

---

## 🔵 2. Modelos de Diarización (Speaker ID)

El sistema de diarización se encarga de separar quién habla y cuándo, permitiendo el análisis por perfiles independientes.

### Pipeline de Diarización
*   **Nombre**: `pyannote/speaker-diarization-3.1`
*   **Proveedor**: Pyannote Audio (via Hugging Face)
*   **Función**: Segmentación y agrupamiento de locutores en tiempo real.
*   **Configuración**: Optimizado para procesar ventanas de 2 segundos.

### Extractor de Huellas (Embeddings)
*   **Nombre**: `pyannote/embedding`
*   **Función**: Generación de vectores matemáticos (embeddings) únicos para cada voz detectada.
*   **Uso**: Permite la persistencia de identidad y el filtrado del perfil "Comercial" mediante comparación de distancia coseno.

---

## 🟣 3. Modelos de Detección de Voz (VAD)

El VAD es la primera capa del pipeline y decide cuándo activar el motor de procesamiento para ahorrar recursos y evitar procesar ruido.

### Modelo Actual
*   **Nombre**: **Silero VAD (v5)**
*   **Arquitectura**: Deep Learning optimizado para CPU/GPU.
*   **Razón de elección**: Es el estándar de la industria por su bajísima latencia y alta precisión en la distinción entre voz humana y ruido ambiental.
*   **Configuración**: Umbral de sensibilidad ajustado a 0.5 para filtrar respiraciones y ruidos de teclado.

---

## 🟠 4. Modelo de Transcripción ASR (Speech-to-Text)

Se encarga de convertir el flujo de voz consolidado (15s) en texto para mantener el historial semántico.

### Modelo Actual
*   **Nombre**: `openai/whisper-small`
*   **Arquitectura**: Transformer Sequence-to-Sequence.
*   **Estado**: **ACTIVO**
*   **Razón de elección**: Ofrece un equilibrio óptimo entre Word Error Rate (WER) en español y consumo de VRAM en inferencia. Se descarta `large-v3` para priorizar la ejecución concurrente con el LLM en la GPU de 6GB.

---

## 🟡 5. Modelo de Razonamiento (Extracción Causa Raíz)

Motor cognitivo semántico que cruza los picos emocionales (acústica) con la transcripción (semántica) para averiguar el detonante.

### Modelo Actual
*   **Nombre**: `Qwen/Qwen2.5-3B-Instruct`
*   **Arquitectura**: Large Language Model (3 mil millones de parámetros).
*   **Estado**: **ACTIVO**
*   **Razón de elección**: Supera en benchmarks a LLaMA 3.2 3B en razonamiento lógico y seguimiento de *prompts* en español.
*   **Configuración**: Cuantizado en **4-bit (NF4)** usando `bitsandbytes` para garantizar que quepa en la VRAM doméstica (< 3GB de ocupación efectiva).

---

## 🟤 6. Modelo de Generación Aumentada (RAG)

Encargado de convertir la base de conocimiento local (ej. manuales de ventas) en vectores matemáticos para realizar búsquedas por similitud semántica.

### Modelo Actual
*   **Nombre**: `all-MiniLM-L6-v2`
*   **Proveedor**: SentenceTransformers.
*   **Estado**: **ACTIVO**
*   **Razón de elección**: Es extremadamente ligero y rápido de cargar. Mapea eficientemente frases y párrafos en un espacio vectorial de 384 dimensiones, ideal para buscar contextos relevantes en milisegundos sin sobrecargar la GPU.

---

## 📈 Resumen de Capas de IA (Arquitectura Completa)

| Capa | Modelo | Función Crítica |
| :--- | :--- | :--- |
| **VAD** | Silero VAD v5 | Detección rápida de inicio/fin de habla (Ahorro de recursos) |
| **Diarización** | Pyannote 3.1 | Separación de interlocutores y segmentación de turnos |
| **Identidad** | Pyannote Embedding | Consolidación de perfiles y filtrado del "Comercial" |
| **Emoción** | GSI-UPM Wav2Vec2 | Clasificación del estado afectivo desde el tono de voz |
| **Transcripción** | OpenAI Whisper Small | Conversión de audio acústico a historial de texto |
| **RAG Embeddings** | all-MiniLM-L6-v2 | Vectorización de manuales de ventas para recuperación |
| **Causa Raíz** | Qwen2.5-3B-Instruct | Motor generativo: explica la emoción y da sugerencias |
