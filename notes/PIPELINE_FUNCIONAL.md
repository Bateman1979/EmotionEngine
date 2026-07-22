# Documentación Funcional: Pipeline de Análisis Emocional 🧠🎙️

Este documento describe el flujo técnico y lógico que sigue el **Emotion Engine** en su estado actual, desde el momento en que se inicia la aplicación hasta la extracción de la causa raíz emocional mediante Modelos de Lenguaje Grandes (LLMs).

---

## 🏗️ Fase 1: Arranque e Inicialización

Cuando ejecutas `python main.py`, el sistema realiza los siguientes pasos previos:

1.  **Precarga de Modelos (`model_preloader.py`)**:
    *   **Silero VAD**: Detección de voz ultra-rápida.
    *   **Pyannote Diarization**: Segmentación y cálculo de *embeddings* (huellas acústicas) de locutores.
    *   **GSI-UPM Wav2Vec2**: Clasificación de emociones (especializado en español).
    *   **Whisper (OpenAI)**: Reconocimiento Automático del Habla (ASR) para transcripción.
    *   **Qwen2.5-3B-Instruct (LLM)**: Extracción de conceptos y causas raíz en modo 4-bit (bitsandbytes).
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
3.  **Segmentación Temporal**: El `AudioSegmenter` agrupa estos chunks hasta completar un bloque inicial de aproximadamente **2 segundos**. Este bloque se guarda temporalmente en disco.

---

## 👥 Fase 3: Diarización e Identificación

Con el bloque de 2 segundos listo, entra en juego la **Diarización**:

1.  **Extracción de Características**: El modelo analiza el fragmento temporal y detecta cuántas voces hay y sus tiempos exactos.
2.  **Comparación de Identidad (`IdentityManager`)**:
    *   **Prioridad 0 - Filtrado de Comercial**: Se compara la huella con la calibración del comercial. Si coincide, no se procesa su emoción (solo STT).
    *   **Prioridad 1 - Perfiles Graduados**: Se compara con sujetos confirmados (Sujeto A, B...).
    *   **Prioridad 2 - Perfiles Tentativos**: Si no encaja, se busca entre voces temporales, consolidándolas poco a poco hasta que alcanzan 15 segundos y se "gradúan".
3.  **Buffering por Hablante**: El audio se recorta y se envía al buffer temporal del hablante específico. El motor no analiza cada 2 segundos para evitar inestabilidad semántica y emocional.

---

## 🧪 Fase 4: Consolidación (15s) y Transcripción

El sistema aplica una estrategia de "Bloques Consolidados" de 15 segundos para dar suficiente contexto a los modelos.

1.  **Ventana de 15s o Cambio de Turno/Silencio**: Cuando el buffer de un sujeto acumula 15s de voz real (o hay un silencio largo / cambio de turno), el bloque se cierra y se guarda como `.wav`.
2.  **Transcripción (Whisper ASR)**:
    *   El bloque de audio se envía a Whisper.
    *   El texto extraído se guarda en un **Transcript Manager** cronológico, registrando los tiempos absolutos de inicio y fin, así como el autor de cada frase.
    *   La transcripción no se realiza para perfiles que aún son "tentativos" ("Identificando...").

---

## 📊 Fase 5: Análisis Emocional Acústico

1.  **Clasificación de Emociones (Wav2Vec2)**:
    *   Si el sujeto **no es el Comercial**, el bloque de audio consolidado se envía al modelo `GSI-UPM`.
    *   El modelo devuelve un vector de probabilidades (Alegría, Tristeza, Ira, Miedo, Neutro, etc.) y selecciona la emoción con mayor confianza.
2.  **Actualización UI Básica**: Se envía un evento por WebSocket al dashboard para actualizar la gráfica de emociones del sujeto.

---

## 🔍 Fase 6: Análisis de Causa Raíz (Concept Extractor)

Si la emoción detectada en la Fase 5 es considerada "intensa" o detonante (ej. Tristeza, Ira, Sorpresa) y supera cierto umbral de confianza:

1.  **Recuperación de Contexto (RAG-like)**: Se solicitan al Transcript Manager los últimos ~60 segundos de transcripciones cronológicas de **todos los interlocutores** (contexto conversacional).
2.  **Inferencia Semántica (LLM)**: En un hilo separado para no bloquear el audio, el texto se inyecta en un *prompt dinámico* dirigido a Qwen2.5.
3.  **Extracción del Concepto**: El LLM analiza *qué* se estaba diciendo justo en el momento en que se produjo la emoción acústica y extrae un resumen corto (ej. "Preocupación por los plazos de entrega").
4.  **Tarjeta de Insights**: El concepto detonante viaja vía WebSocket al frontend, donde se renderiza como una alerta valiosa para el usuario.

---

## 💡 Resumen del Ciclo de Vida v5
`Audio (Stream)` ➡️ `VAD (2s)` ➡️ `Diarización (Sujeto A)` ➡️ `Buffer (15s)` ➡️ `Whisper (STT)` ➡️ `Wav2Vec2 (Emoción)` ➡️ `[Si hay Trigger] Qwen (Causa Raíz)` ➡️ `Dashboard (Conceptos)`
