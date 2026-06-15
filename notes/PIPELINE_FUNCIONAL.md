# Documentación Funcional: Pipeline de Análisis Emocional 🧠🎙️

Este documento describe el flujo técnico y lógico que sigue el **Emotion Engine** desde el momento en que se inicia la aplicación hasta que se entrega el primer resultado de análisis emocional en la interfaz.

---

## 🏗️ Fase 1: Arranque e Inicialización

Cuando ejecutas `python main.py`, el sistema realiza los siguientes pasos previos:

1.  **Carga de Modelos**:
    *   **Silero VAD**: Se carga en memoria para la detección de voz ultra-rápida.
    *   **Pyannote Diarization**: Se conecta con Hugging Face para cargar los modelos de segmentación y embedding de locutores.
    *   **GSI-UPM Wav2Vec2**: Se inicializa el modelo de clasificación de emociones (especializado en español).
2.  **Levantamiento del Servidor**:
    *   Se inicia un servidor **FastAPI** en el puerto 8001.
    *   Se habilitan los **WebSockets** para comunicación bidireccional en tiempo real con el frontend.
    *   Se monta la carpeta `data/audio` para servir los fragmentos analizados.

---

## 🎧 Fase 2: Captura y Detección (VAD)

Una vez que el usuario pulsa **"Iniciar Análisis"** en la web:

1.  **Apertura del Stream**: El `AudioHandler` busca el dispositivo "VB-Cable" y abre un flujo de audio a 16kHz (mono).
2.  **Detección de Voz (Silero)**:
    *   El motor procesa el audio en "chunks" de milisegundos.
    *   Si el nivel de energía y la probabilidad de voz superan el umbral (`VAD_THRESHOLD`), el sistema marca el inicio de un evento de habla.
3.  **Segmentación Temporal**: El `AudioSegmenter` agrupa estos chunks hasta completar un bloque de aproximadamente **2 segundos**. Este bloque se guarda temporalmente en disco.

---

## 👥 Fase 3: Diarización e Identificación

Con el bloque de 2 segundos listo, entra en juego la **Diarización**:

1.  **Extracción de Características**: El modelo analiza el fragmento y detecta cuántas voces hay y en qué milisegundos exactos habla cada una.
2.  **Cálculo de Embeddings**: Se genera una "huella acústica" matemática de cada voz detectada.
3.  **Comparación de Identidad (Sistema de Dos Niveles v5)**:
    *   **Prioridad 0 - Filtrado de Comercial**: El `IdentityManager` compara la huella con la calibración del comercial. Si coincide, el audio se descarta (no se procesa su emoción).
    *   **Prioridad 1 - Perfiles Graduados**: Se compara con los sujetos ya confirmados (Sujeto A, B...) usando un umbral estricto. Si se alcanza el límite máximo de hablantes, el umbral se flexibiliza dinámicamente para evitar perfiles duplicados.
    *   **Prioridad 2 - Perfiles Tentativos**: Si no encaja con los graduados, se busca entre voces temporales (umbral permisivo). Los perfiles tentativos similares se consolidan continuamente. Al acumular **15 segundos**, se "gradúan" y reciben un nombre oficial (ej. Sujeto A).
    *   **Prioridad 3 - Nuevo Perfil**: Si es una voz completamente nueva, se crea como perfil tentativo a la espera de más muestras.

---

## 🧪 Fase 4: Acumulación y Análisis Emocional

Este es el paso crítico para garantizar la precisión:

1.  **Buffer por Hablante**: El motor mantiene un buffer de audio independiente para cada sujeto detectado.
2.  **Criterio de Ventana (15s)**:
    *   El sistema no analiza emociones en fragmentos de 2s (sería impreciso).
    *   Espera a que un sujeto específico haya acumulado **15 segundos** de voz neta (pueden ser en turnos separados).
3.  **Clasificación de Emociones (Wav2Vec2)**:
    *   Al llegar a los 15s, se concatena el audio y se envía al modelo `GSI-UPM`.
    *   El modelo devuelve un vector de probabilidades: **Alegría, Tristeza, Ira, Miedo, Neutro, etc.**
    *   Se selecciona la emoción con mayor confianza.

---

## 📊 Fase 5: Reporte de Resultados

1.  **Persistencia**: El resultado se guarda en `data/results.json` junto con la ruta al archivo de audio analizado.
2.  **Broadcast vía WebSocket**: El servidor envía un objeto JSON al frontend con:
    *   Nombre del Sujeto.
    *   Emoción detectada.
    *   Porcentaje de confianza.
    *   Distribución de todas las probabilidades.
3.  **Actualización de UI**: El dashboard recibe el mensaje y actualiza instantáneamente los gráficos de evolución temporal y el registro detallado.

---

## 💡 Resumen del Ciclo de Vida
`Arranque` ➡️ `VAD (Voz)` ➡️ `Diarización (¿Quién?)` ➡️ `Buffer (Acumular 15s)` ➡️ `IA (Emoción)` ➡️ `Dashboard`
