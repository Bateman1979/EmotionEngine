# Historial de Modelos de IA 🎭

Este documento registra la evolución de los modelos de Inteligencia Artificial utilizados en el Emotion Engine, detallando las razones de cambio y el estado de cada uno.

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

## 📈 Resumen de Capas de IA

| Capa | Modelo | Función Crítica |
| :--- | :--- | :--- |
| **VAD** | Silero VAD v5 | Detección de inicio/fin de habla |
| **Diarización** | Pyannote 3.1 | Separación de interlocutores |
| **Identidad** | Pyannote Embedding | Reconocimiento y filtrado de "Comercial" |
| **Emoción** | GSI-UPM Wav2Vec2 | Clasificación del estado emocional |
