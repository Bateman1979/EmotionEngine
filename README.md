# 🎭 Emotion Engine: Real-Time Spanish Emotion Analysis

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Emotion Engine** es un sistema avanzado de análisis emocional en tiempo real diseñado específicamente para conversaciones en español. Utiliza modelos de inteligencia artificial de última generación (SOTA) para detectar, segmentar e identificar emociones en locutores individuales durante una llamada o reunión.

---

## ✨ Características Principales

*   **🎙️ Análisis en Tiempo Real**: Procesamiento continuo de audio mediante WebSockets.
*   **👥 Diarización Inteligente**: Identificación de locutores y separación de voces (vía `Pyannote.audio`).
*   **🧠 Modelo SOTA**: Clasificación emocional especializada en español utilizando `GSI-UPM Wav2Vec2`.
*   **🛡️ Privacidad y Calibración**: Sistema de filtrado de voz del comercial (propia) para centrar el análisis exclusivamente en el cliente.
*   **📊 Dashboard Interactivo**: Interfaz web moderna con visualización de probabilidades emocionales y evolución temporal.

---

## 🏗️ Arquitectura y Flujo Técnico

El sistema sigue un pipeline modular optimizado para baja latencia:

1.  **Captura (VAD)**: Detección de voz ultra-rápida con Silero.
2.  **Diarización**: Extracción de huellas acústicas y asignación de identidades.
3.  **Buffer Dinámico**: Acumulación de voz neta por sujeto para garantizar precisión.
4.  **Inferencia IA**: Clasificación emocional profunda cada 15 segundos de habla.
5.  **Broadcast**: Envío de resultados instantáneos vía WebSockets.

> [!TIP]
> Consulta la [Documentación del Pipeline Funcional](notes/PIPELINE_FUNCIONAL.md) para un análisis técnico profundo de cada fase.

---

## 🚀 Inicio Rápido

### Requisitos Previos
*   **Python 3.10+** y **FFmpeg**.
*   **VB-Audio Virtual Cable** (para capturar audio de otras apps).
*   **HF_TOKEN**: Token de Hugging Face con acceso a los modelos de Pyannote.

### Instalación
1.  Clonar el repositorio.
2.  Crear entorno virtual: `python -m venv venv` y activarlo.
3.  Instalar dependencias: `pip install -r requirements.txt`.
4.  Configurar `.env` con tu `HF_TOKEN`.

### Ejecución
```powershell
python main.py
```
Accede a la interfaz en: `http://localhost:8001`

> [!IMPORTANT]
> Lee la [Guía de Ejecución Completa](notes/GUIA_EJECUCION.md) para detalles sobre la configuración crítica del hardware de audio.

---

## 📁 Estructura del Proyecto

```text
Emotion_Engine/
├── backend/            # Lógica core, API y Servicios de IA
├── frontend/           # Interfaz web (HTML/JS/CSS)
├── notes/              # Documentación técnica y Roadmap
├── data/               # Almacenamiento de perfiles y resultados
├── scripts/            # Utilidades de desarrollo
└── main.py             # Punto de entrada de la aplicación
```

---

## 🛤️ Roadmap y Evolución
Este proyecto está en desarrollo activo como parte de un TFM. Algunas mejoras previstas incluyen:
*   Análisis dinámico de fin de turno.
*   Detección de emociones secundarias.
*   Exportación de reportes en PDF/CSV.

Puedes ver el detalle completo en el [Roadmap de Mejoras](notes/roadmap_mejoras.md).

---

## 📄 Licencia
Este proyecto está bajo la Licencia MIT. Consulta el archivo para más detalles.

---
**Desarrollado por Valentín Gozález Coira** 🚀
