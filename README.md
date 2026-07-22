# 🎭 Emotion Engine: Análisis Emocional en Tiempo Real con Extracción de Causa Raíz

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C.svg)](https://pytorch.org/)
[![Hugging Face](https://img.shields.io/badge/🤗_Hugging_Face-Models-FFD21E.svg)](https://huggingface.co/)

**Emotion Engine** es un sistema de inteligencia artificial en tiempo real que analiza las emociones de los interlocutores en una conversación en español, identifica el **concepto detonante** que las provoca mediante un LLM local y sugiere **recomendaciones tácticas** extraídas de una base de conocimiento propia (RAG).

Todo el procesamiento se ejecuta **localmente en hardware doméstico** (GPU con 6 GB VRAM), sin depender de APIs en la nube, garantizando la privacidad total de los datos.

> **Trabajo de Fin de Máster** — EBIS Business School  
> **Autor:** Valentín González Coira

---

## ✨ Características Principales

| Capa | Tecnología | Función |
|:---|:---|:---|
| 🎙️ **VAD** | Silero VAD v5 | Detección ultra-rápida de inicio/fin de habla |
| 👥 **Diarización** | Pyannote 3.1 | Separación e identificación de interlocutores |
| 🔒 **Privacidad** | Pyannote Embedding | Calibración del "Comercial" (excluido del análisis emocional) |
| 🧠 **Emoción** | GSI-UPM Wav2Vec2 | Clasificación acústica de 7 emociones en español |
| 📝 **Transcripción** | OpenAI Whisper Small | Conversión de voz a texto (STT) en tiempo real |
| 🤖 **Causa Raíz** | Qwen2.5-3B-Instruct (NF4) | LLM local cuantizado: extrae el *por qué* de la emoción |
| 📚 **RAG** | all-MiniLM-L6-v2 | Búsqueda semántica en base de conocimiento para recomendaciones |
| 📊 **Dashboard** | FastAPI + WebSockets | Interfaz web interactiva con curvas emocionales en vivo |

---

## 🏗️ Arquitectura en Cascada

El sistema implementa un **pipeline de 7 capas** orquestado de forma asíncrona:

```
Micrófono → Silero VAD → Pyannote Diarización → Buffer por Hablante (15s)
                                                        ↓
                                            ┌───────────┴───────────┐
                                            │                       │
                                    Whisper (ASR)          Wav2Vec2 (Emoción)
                                            │                       │
                                            └───────────┬───────────┘
                                                        ↓
                                              ¿Pico emocional?
                                                   │ Sí
                                                   ↓
                                          Qwen2.5 (Causa Raíz)
                                                   ↓
                                          RAG (Recomendación)
                                                   ↓
                                          Dashboard (WebSocket)
```

**Flujo clave:**
1. El **VAD** detecta actividad vocal y activa la captura.
2. **Pyannote** asigna cada fragmento a un hablante (diarización).
3. Se **acumula audio** por sujeto en buffers individuales de 15 segundos.
4. Al completar la ventana, se ejecutan en paralelo **Whisper** (transcripción) y **Wav2Vec2** (emoción).
5. Si la emoción supera un umbral, el **LLM (Qwen2.5)** analiza las últimas transcripciones para extraer el concepto detonante.
6. El **servicio RAG** busca la recomendación más relevante en la base de conocimiento.
7. Todo se envía al **Dashboard** en milisegundos vía WebSocket.

> [!TIP]
> Consulta la [Documentación del Pipeline Funcional](notes/PIPELINE_FUNCIONAL.md) para un análisis técnico profundo de cada fase.

---

## 🚀 Inicio Rápido

### Requisitos Previos
*   **Python 3.10+** y **FFmpeg** instalado en el PATH.
*   **GPU NVIDIA** con ≥ 6 GB VRAM (probado en RTX 2060).
*   **VB-Audio Virtual Cable** (para capturar audio del sistema).
*   **Token de Hugging Face** con acceso a los modelos gated de Pyannote.

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/Bateman1979/AIP.git
cd AIP

# 2. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar el token de Hugging Face
cp .env.example .env
# Editar .env y pegar tu HF_TOKEN (ver instrucciones en .env.example)
```

### Ejecución
```powershell
python main.py
```
Accede a la interfaz en: **http://localhost:8001**

> [!IMPORTANT]
> Lee la [Guía de Ejecución Completa](notes/GUIA_EJECUCION.md) para detalles sobre la configuración del hardware de audio y la calibración de privacidad.

---

## 📁 Estructura del Proyecto

```text
Emotion_Engine/
├── backend/
│   ├── api/
│   │   └── server.py                 # Servidor FastAPI + WebSocket
│   ├── core/
│   │   ├── engine.py                 # Orquestador principal del pipeline
│   │   ├── audio_segmenter.py        # Segmentación de audio en bloques
│   │   └── voice_detector.py         # Interfaz con Silero VAD
│   └── services/
│       ├── calibration_manager.py    # Calibración de privacidad (Comercial)
│       ├── concept_extractor.py      # LLM Qwen2.5 (Causa Raíz)
│       ├── diarization.py            # Pipeline Pyannote (Diarización)
│       ├── emotion_detection.py      # Wav2Vec2 GSI-UPM (Emoción)
│       ├── identity_manager.py       # Gestión de perfiles graduados
│       ├── model_preloader.py        # Precarga concurrente de modelos
│       ├── rag_service.py            # Motor RAG (SentenceTransformers)
│       ├── transcriber.py            # Whisper ASR (Speech-to-Text)
│       └── transcript_buffer.py      # Buffer circular de transcripciones
├── frontend/
│   ├── index.html                    # Dashboard principal
│   ├── app.js                        # Lógica WebSocket y gráficos
│   ├── calibration.js                # Flujo de calibración de privacidad
│   └── style.css                     # Estilos del dashboard
├── data/
│   └── knowledge/
│       └── knowledge.txt             # Base de conocimiento para RAG
├── notes/                            # Documentación técnica del TFM
│   ├── GUIA_EJECUCION.md
│   ├── PIPELINE_FUNCIONAL.md
│   ├── model_history.md
│   └── tfm_indice_memoria.md
├── benchmark.py                      # Script de benchmarking de latencia
├── monitor.py                        # Monitor de telemetría VRAM
├── main.py                           # Punto de entrada de la aplicación
├── requirements.txt
├── .env.example                      # Plantilla de configuración
└── .gitignore
```

---

## 🧠 Modelos de IA Utilizados

| Modelo | Fuente | Función | Tamaño en VRAM |
|:---|:---|:---|:---|
| Silero VAD v5 | Silero Team | Detección de voz | ~50 MB |
| pyannote/speaker-diarization-3.1 | Pyannote | Diarización | ~300 MB |
| pyannote/embedding | Pyannote | Embeddings de identidad | ~100 MB |
| gsi-upm/wav2vec_spanish_emotion-analysis | UPM (Madrid) | Emoción acústica | ~380 MB |
| openai/whisper-small | OpenAI | Transcripción ASR | ~460 MB |
| Qwen/Qwen2.5-3B-Instruct | Alibaba/Qwen | Causa Raíz (LLM) | ~2.5 GB (NF4) |
| all-MiniLM-L6-v2 | SentenceTransformers | Embeddings RAG | ~90 MB |

> [!NOTE]
> Todos los modelos se ejecutan **localmente** en la GPU. El LLM (Qwen2.5) se cuantiza en 4-bit (NF4) mediante `bitsandbytes` para caber en 6 GB de VRAM junto al resto del pipeline.

Consulta el [Historial de Modelos](notes/model_history.md) para ver la evolución y justificación de cada selección.

---

## 🛤️ Líneas de Mejora Futuras

*   Integración completa de RAG con bases de datos dinámicas.
*   Optimización a formatos ONNX o TensorRT.
*   Soporte multilingüe real.
*   Refinamiento de la inferencia emocional (emociones mixtas).
*   Panel de KPIs y exportación de sesiones.

---

## 📄 Propiedad Intelectual

**© 2026 Valentín González Coira — Todos los derechos reservados.**

Este proyecto ha sido desarrollado como parte de un Trabajo de Fin de Máster (TFM) en EBIS Business School. Queda prohibida la reproducción, distribución o modificación total o parcial de este código sin la autorización expresa y por escrito del autor.

---
**Desarrollado por Valentín González Coira** 🚀
