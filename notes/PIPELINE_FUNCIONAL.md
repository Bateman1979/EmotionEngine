# Documentación Funcional: Pipeline de Análisis Emocional 🧠🎙️

Este documento describe el flujo técnico y lógico que sigue el **Emotion Engine** en su estado actual (v5 final), desde el momento en que se inicia la aplicación hasta la extracción de la causa raíz emocional y la sugerencia de recomendaciones mediante el sistema RAG.

---

## 🏗️ Fase 1: Arranque e Inicialización

Cuando ejecutas `python main.py`, el sistema realiza los siguientes pasos previos:

1.  **Precarga Concurrente de Modelos (`model_preloader.py`)**:
    Se lanzan 6 hilos en background para cargar los modelos sin bloquear la interfaz:
    *   **Silero VAD**: Detección de voz ultra-rápida.
    *   **Pyannote Diarization**: Segmentación y cálculo de *embeddings* (huellas acústicas) de locutores.
    *   **Whisper (OpenAI)**: Reconocimiento Automático del Habla (ASR) para transcripción.
    *   **GSI-UPM Wav2Vec2**: Clasificación de emociones (especializado en español).
    *   **SentenceTransformers (all-MiniLM)**: Motor de vectorización para el sistema RAG (Base de Conocimiento).
    *   **Qwen2.5-3B-Instruct (LLM)**: Extracción de conceptos y causas raíz, cargado en modo cuantizado a 4-bit (NF4) mediante `bitsandbytes`.
2.  **Levantamiento del Servidor**:
    *   Se inicia un servidor **FastAPI** en el puerto 8001.
    *   Se habilitan los **WebSockets** para comunicación bidireccional en tiempo real con el frontend.
    *   Se monta la carpeta `data/audio` para servir los fragmentos analizados.

---

## 🎧 Fase 2: Captura y Detección (VAD)

Una vez que el usuario pulsa **"Iniciar Análisis"** en la web:

1.  **Apertura del Stream**: El `AudioHandler` abre un flujo de audio a 16kHz (mono), capturando desde el micrófono virtual o físico.
2.  **Detección de Voz (Silero)**:
    *   El motor procesa el audio en "chunks" de milisegundos.
    *   Si el nivel de energía y la probabilidad de voz superan el umbral (`VAD_THRESHOLD`), el sistema marca el inicio de un evento de habla.
3.  **Segmentación Temporal**: El `AudioSegmenter` agrupa estos chunks hasta completar un bloque inicial de aproximadamente **2 segundos**. Este bloque temporal se guarda en disco.

---

## 👥 Fase 3: Diarización e Identificación Biométrica

Con el bloque de 2 segundos listo, entra en juego la **Diarización**:

1.  **Extracción de Características**: El pipeline Pyannote analiza el fragmento y detecta cuántas voces hay, extrayendo sus huellas acústicas (embeddings normalizados).
2.  **Comparación de Identidad (`IdentityManager`)**:
    *   **Prioridad 0 - Filtrado del Comercial**: Se compara la huella con el perfil guardado en `calibration.pkl`. Si coincide, se excluye del análisis de emociones para ahorrar VRAM.
    *   **Prioridad 1 - Perfiles Graduados**: Se compara con sujetos confirmados mediante un umbral estricto (ej. "Sujeto A").
    *   **Prioridad 2 - Perfiles Tentativos**: Si no encaja, se busca entre voces temporales ("Identificando..."). Cuando un tentativo acumula **15 segundos netos** de habla, consolida su perfil y se "gradúa", activando el análisis completo.
3.  **Buffering por Hablante**: El audio se recorta y se envía al buffer temporal específico de ese hablante.

---

## 🧪 Fase 4: Consolidación y Transcripción ASR

El sistema aplica una estrategia de "Ventana Deslizante" para dar suficiente contexto semántico a los modelos.

1.  **Cierre de Bloque (15s)**: Cuando el buffer de un sujeto alcanza los 15 segundos netos (o tras un silencio de 5s), el bloque se cierra y consolida.
2.  **Transcripción (Whisper)**:
    *   El bloque de audio se inyecta en el modelo Whisper Small.
    *   El texto extraído se guarda en un **Transcript Buffer** circular, registrando tiempos absolutos de inicio y fin.
    *   *(Nota: La transcripción se realiza para todos los hablantes graduados, incluyendo al comercial, para mantener el contexto de la conversación intacto).*

---

## 📊 Fase 5: Análisis Emocional Acústico

1.  **Clasificación (GSI-UPM Wav2Vec2)**:
    *   Si el sujeto **NO es el Comercial**, el bloque de audio consolidado se envía al modelo Wav2Vec2.
    *   El modelo devuelve un vector *Softmax* con las probabilidades de 7 emociones básicas.
2.  **Actualización Visual**: Se emite un evento WebSocket al Dashboard para pintar la distribución de emociones (barras curvas) del sujeto.

---

## 🧠 Fase 6: Causa Raíz (LLM) y Sugerencias (RAG)

Si la emoción detectada en la Fase 5 es considerada detonante (ej. Tristeza, Ira, Sorpresa) y supera el umbral de confianza, se activa el motor cognitivo:

1.  **Extracción de Contexto Semántico**: Se solicitan al Transcript Buffer los últimos ~60 segundos de transcripciones (cubriendo tanto al comercial como al cliente).
2.  **Inferencia Causa Raíz (Qwen2.5)**: 
    *   El texto se inyecta en un prompt `ChatML` estructurado, pidiendo al LLM cuantizado que extraiga el "concepto detonante" y un resumen del problema en formato JSON.
    *   Este proceso se realiza en un hilo paralelo (*daemon*) para **no interrumpir la captura de audio en vivo**.
3.  **Recuperación RAG (Retrieval-Augmented Generation)**:
    *   El contexto extraído por el LLM se envía al `RAGService`.
    *   Se vectoriza mediante SentenceTransformers y se busca (vía similitud coseno) la recomendación táctica más relevante dentro del archivo `data/knowledge/knowledge.txt`.
4.  **Tarjeta de Insights**: El concepto, junto a la recomendación del manual, viaja vía WebSocket al frontend y se renderiza en una tarjeta accionable para el usuario.

---

## 💡 Resumen del Ciclo de Vida v5 Final

```text
1. 🎙️ Audio (Stream en vivo) 
2. ✂️ VAD (Detección de voz, 2s)
3. 👥 Pyannote (Diarización y Asignación)
4. ⏳ Buffering (Acumulación hasta 15s)
5. 📝 Whisper (Transcripción / STT)
6. 🎭 Wav2Vec2 (Clasificación Emocional)
    │
    └─> [Si Pico Emocional] 
          │
          ├─> 🧠 Qwen2.5 (Extracción de Causa Raíz)
          │
          ├─> 📚 RAG (Búsqueda de recomendación táctica)
          │
          └─> 💻 Dashboard (Alerta y Recomendación en pantalla)
```
