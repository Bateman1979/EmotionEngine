# Guía de Ejecución: Emotion Engine 🎭

Esta guía detalla los pasos necesarios para poner en marcha el sistema de análisis emocional en tiempo real, optimizado con una arquitectura modular y profesional.

---

## 🚀 1. Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

*   **Python 3.10+**: Lenguaje base del sistema.
*   **FFmpeg**: Esencial para el procesamiento de audio. Debe estar en el `PATH`.
*   **VB-Audio Virtual Cable**: [Descargar aquí](https://vb-audio.com/Cable/). Necesario para capturar audio de aplicaciones (Zoom, Teams, etc.).
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

---

## 📁 3. Estructura del Proyecto

El sistema está organizado de forma modular para facilitar su mantenimiento:

*   `main.py`: Punto de entrada principal (servidor web).
*   `backend/`:
    *   `api/`: Servidor FastAPI y gestión de WebSockets.
    *   `core/`: Motor de audio y orquestación del análisis (VAD Silero, segmentación).
    *   `services/`: Modelos de IA (Pyannote Diarization, GSI-UPM Emoción) y gestión de identidades.
    *   `config.py`: Parámetros globales.
*   `frontend/`: Interfaz de usuario moderna (HTML/JS/CSS).
*   `scripts/`: Herramientas adicionales y utilidades.
*   `data/`: Almacenamiento de logs, audios y perfiles de locutores (`speakers.pkl`).
*   `notes/`: Documentación técnica e historial de modelos.

> [!TIP]
> Para más detalles sobre el flujo interno de datos, consulta el [Pipeline Funcional](PIPELINE_FUNCIONAL.md) o el [Historial de Modelos](notes/model_history.md).

---

## 🎙️ 4. Configuración de Audio (Crítico)

El sistema separa tu voz del resto de interlocutores mediante hardware virtual:

1.  **Configuración en Windows**:
    *   Salida predeterminada de Windows: **CABLE Input**.
    *   Entrada de Windows: Tu **Micrófono real**.
2.  **En la aplicación de llamada (Zoom/Teams)**:
    *   Salida de audio: **CABLE Input**.
    *   De esta forma, el audio de los clientes pasará por el cable virtual y el motor podrá procesarlo en exclusiva.

---

### Ejecución
Para iniciar el sistema, ejecuta:
```powershell
python main.py
```
Acceso en tu navegador: `http://localhost:8001`

---

## 🔄 6. Flujo de Trabajo y Funcionalidades

1.  **Calibración Inicial**: La primera vez, usa la web para grabar 15s de tu voz. Se guardará como "Comercial" para ser ignorada en el análisis, protegiendo tu privacidad y centrando la métrica en el cliente.
2.  **Configuración de Límite de Hablantes (Nuevo)**:
    *   En el panel lateral verás una opción **"Límite de Hablantes (Máx.)"**.
    *   Úsala si sabes cuántas personas hay en la reunión (ej. pon `1` si hablas con un solo cliente). Esto ayuda a la IA a evitar la fragmentación de identidades (que no detecte voces fantasma). Si lo dejas vacío, el sistema intentará auto-detectar.
3.  **Análisis**: Pulsa **"Iniciar Análisis"**. El motor segmentará el audio continuamente y realizará un análisis emocional profundo cada 15s de voz acumulada neta por sujeto.
4.  **Resultados**: Visualiza en tiempo real las probabilidades emocionales y la evolución temporal en el panel de control interactivo.

---

## 🆘 7. Solución de Problemas

*   **Error "Permission Denied" en audio**: Cierra otras aplicaciones que puedan estar bloqueando el micrófono o el VB-Cable de manera exclusiva.
*   **No se detectan sujetos / Siempre dice Silencio**: Asegúrate de que el audio de la llamada está llegando realmente a **CABLE Input**. Puedes verificarlo viendo las barras verdes en el mezclador de volumen de Windows.
*   **Error descargando modelos (HttpError / Unauthorized)**: Verifica que tu `HF_TOKEN` es válido y asegúrate de haber aceptado manualmente las condiciones en Hugging Face tanto para `pyannote/speaker-diarization-3.1` como para `pyannote/segmentation-3.0`.
*   **Identidades duplicadas (Sujeto A, Sujeto B... cuando solo hay un cliente)**: Asegúrate de establecer el **Límite de Hablantes** a 1 antes de iniciar el motor para forzar a la red neuronal a agrupar todas las voces no-comerciales en un solo perfil.
