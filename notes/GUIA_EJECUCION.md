# Guía de Ejecución: Emotion Engine 🎭 (v5 - Arquitectura Completa)

Esta guía detalla los pasos necesarios para poner en marcha el sistema de análisis emocional en tiempo real, optimizado con una arquitectura modular, inferencia en cascada (Acústica + Semántica) y soporte de ejecución local en hardware de consumo (*Edge AI*).

---

## 🚀 1. Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

*   **Python 3.10+**: Lenguaje base del sistema.
*   **FFmpeg**: Esencial para el procesamiento de audio. Debe estar en el `PATH` del sistema.
*   **VB-Audio Virtual Cable**: [Descargar aquí](https://vb-audio.com/Cable/). Necesario para capturar audio de aplicaciones (Zoom, Teams, etc.).
*   **Hardware (GPU)**: Tarjeta gráfica NVIDIA (ej. RTX 2060 o superior) con al menos 6GB de VRAM y **CUDA Toolkit** instalado para soportar la cuantización en 4-bit.
*   **HF_TOKEN**: Un token de Hugging Face con acceso a los modelos de Pyannote. 
    > [!IMPORTANT]
    > Debes ir a la web de Hugging Face con tu cuenta y **aceptar las condiciones de uso** de estos dos modelos para que el token funcione correctamente:
    > 1. `pyannote/speaker-diarization-3.1`
    > 2. `pyannote/segmentation-3.0`

---

## 🛠️ 2. Configuración del Entorno

1.  **Entorno Virtual**:
    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```
2.  **Dependencias**:
    ```powershell
    pip install -r requirements.txt
    ```
3.  **Variables de Entorno**:
    Crea un archivo `.env` en la raíz y pega tu token:
    ```text
    HF_TOKEN=tu_token_de_hugging_face
    ```
4.  **Base de Conocimiento (RAG)**:
    Puedes añadir manuales de ventas, guiones o información de producto en el archivo `data/knowledge_base.txt`. El sistema RAG (*Retrieval-Augmented Generation*) lo leerá automáticamente.

---

## 📁 3. Estructura del Proyecto

El sistema está organizado de forma modular para facilitar su mantenimiento:

*   `main.py`: Punto de entrada principal (servidor web FastAPI y WebSockets).
*   `monitor.py`: Script independiente para registrar y auditar el consumo de VRAM de la GPU.
*   `backend/`:
    *   `api/`: Controladores de los *endpoints*.
    *   `core/`: Motor principal (`engine.py`), pre-cargador de modelos (`preloader.py`) y orquestación de audio (VAD Silero).
    *   `services/`: Modelos de IA (Pyannote Diarization, GSI-UPM Emoción, Whisper STT, Qwen2.5 Causa Raíz, RAG) y `identity_manager.py`.
    *   `config.py`: Parámetros globales y umbrales.
*   `frontend/`: Interfaz de usuario interactiva (HTML/JS/CSS).
*   `data/`: Almacenamiento de logs, audios temporales, base de conocimiento RAG y perfiles de locutores consolidados.
*   `notes/`: Documentación técnica e historial de versiones.

---

## 🎙️ 4. Configuración de Audio (Crítico)

El sistema separa tu voz del resto de interlocutores mediante hardware virtual:

1.  **Configuración en Windows**:
    *   Salida predeterminada de Windows: **CABLE Input**.
    *   Entrada de Windows: Tu **Micrófono real**.
2.  **En la aplicación de llamada (Zoom/Teams)**:
    *   Salida de audio: **CABLE Input**.
    *   De esta forma, el audio de los clientes pasará por el cable virtual y el motor podrá procesarlo de manera limpia.

---

## 🚀 5. Ejecución del Sistema

Para iniciar el sistema de forma óptima (con pre-carga de los 5 modelos de IA), ejecuta:
```powershell
python main.py
```
Acceso a la interfaz en tu navegador: `http://localhost:8001`

*(Opcional)* Si quieres monitorear el consumo de tu tarjeta gráfica (VRAM) en tiempo real y guardar un log, abre otra terminal y ejecuta:
```powershell
python monitor.py
```

---

## 🔄 6. Flujo de Trabajo y Funcionalidades

1.  **Carga de Modelos**: Al arrancar `main.py`, la interfaz mostrará un estado de "Cargando Modelos". El sistema cargará en la GPU: VAD, Pyannote, Wav2Vec2, Whisper y Qwen2.5 cuantizado. Esto toma un par de minutos la primera vez.
2.  **Calibración Inicial**: La primera vez, usa la web para grabar 15s de tu voz. Se guardará como "Comercial" para ser ignorada en los análisis emocionales, protegiendo tu privacidad.
3.  **Configuración de Límite de Hablantes**: En el panel lateral puedes fijar un "Límite de Hablantes (Máx.)" (ej. `1` si hablas con un solo cliente) para evitar voces fantasma.
4.  **Sistema de Identidades Graduadas**:
    *   Cuando alguien nuevo hable, verás que aparece como **"Identificando..."** (Perfil Tentativo).
    *   Una vez acumule **15 segundos netos de voz**, se convertirá en un "Sujeto X" consolidado y comenzará a recibir análisis emocional.
5.  **Análisis Combinado (Emoción + Causa Raíz)**:
    *   El motor acústico evaluará el tono constantemente.
    *   Si detecta un pico negativo (Ira, Tristeza), invocará a Qwen2.5 y al RAG para leer las transcripciones previas e indicar **por qué** el cliente se siente así, sugiriendo además una respuesta basada en tu manual de ventas.

---

## 🆘 7. Solución de Problemas

*   **Error "CUDA Out of Memory"**: Indica que tu GPU no tiene los 6GB libres necesarios. Cierra navegadores pesados o aplicaciones que consuman VRAM antes de iniciar `main.py`.
*   **Error "Permission Denied" en audio**: Cierra otras aplicaciones que puedan estar bloqueando el micrófono o el VB-Cable de manera exclusiva.
*   **No se detectan sujetos / Siempre dice Silencio**: Asegúrate de que el audio de la llamada está llegando realmente a **CABLE Input**.
*   **Error de BitsAndBytes (Falta DLL o librería)**: Asegúrate de tener instalado el CUDA Toolkit compatible con tu versión de PyTorch de Windows.
*   **Identidades duplicadas (Sujeto A, Sujeto B... cuando solo hay un cliente)**: Asegúrate de establecer el **Límite de Hablantes** a 1 antes de iniciar el motor para forzar a la red neuronal a agrupar todo en un solo perfil.
