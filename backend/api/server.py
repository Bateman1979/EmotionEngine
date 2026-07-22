# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import asyncio
import json
import threading
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import datetime
import shutil
import pyaudio
from backend.core.engine import run_engine
from backend.config import RESULTS_FILE, AUDIO_DIR, CALIBRATION_FILE
from backend.services.diarization import Diarizer
from backend.services.calibration_manager import CalibrationManager
from backend.services.model_preloader import preloader as model_preloader

# --- Loop management for async/sync interop ---
loop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop
    loop = asyncio.get_event_loop()
    
    # Iniciar precarga de modelos de IA en background
    def on_preload_progress(status):
        """Notifica al frontend el progreso de carga vía WebSocket."""
        if loop:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "model_loading",
                    "data": status
                }),
                loop
            )
    
    model_preloader.start_preloading(on_progress=on_preload_progress)
    
    yield
    # Clean up if needed
    if state.is_running:
        state.stop_engine()

app = FastAPI(lifespan=lifespan)

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                pass

manager = ConnectionManager()

# --- Engine State ---
class EngineState:
    def __init__(self):
        self.thread = None
        self.is_running = False
        self.stop_event = threading.Event()
        self.history = self.load_history()

    def load_history(self):
        if os.path.exists(RESULTS_FILE):
            try:
                with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_history(self):
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=4)

    def start_engine(self, callback, error_callback, max_speakers=None):
        if not self.is_running:
            self.stop_event.clear()
            self.is_running = True
            self.thread = threading.Thread(
                target=run_engine,
                args=(callback, error_callback, self.stop_event, max_speakers),
                kwargs={"preloader": model_preloader},
                daemon=True
            )
            self.thread.start()
            return True
        return False

    def stop_engine(self):
        if self.is_running:
            self.stop_event.set()
            self.is_running = False
            # We don't join because it might take a few seconds
            return True
        return False

state = EngineState()
diarizer_instance = None 
calibration_mgr = None

def get_diarizer():
    global diarizer_instance, calibration_mgr
    if diarizer_instance is None:
        diarizer_instance = Diarizer()
        calibration_mgr = CalibrationManager(diarizer_instance)
    return diarizer_instance, calibration_mgr

# --- Engine Callbacks ---
def engine_callback(emotion, score, filepath, speaker=None, all_probs=None):
    if emotion == "CARGANDO_MODELOS":
        if loop:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "model_loading", "data": model_preloader.get_status()}),
                loop
            )
        return

    if emotion == "HABLANDO...":
        if loop:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "status", "value": "🎙️ Alguien está hablando...", "is_active": True}),
                loop
            )
        return

    if emotion == "IDENTIFICANDO...":
        if loop and speaker:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "speaker_active", "speaker": speaker, "duration": score}),
                loop
            )
        return

    if emotion == "CONCEPTO":
        # Resultado del análisis de causa raíz (LLM)
        if loop and speaker and all_probs:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({
                    "type": "concept",
                    "data": {
                        "speaker": speaker,
                        "emotion": all_probs.get("emotion", ""),
                        "score": round(float(score), 2),
                        "concepto_detonante": all_probs.get("concepto_detonante", ""),
                        "contexto_para_rag": all_probs.get("contexto_para_rag", ""),
                        "palabras_clave": all_probs.get("palabras_clave", []),
                        "severidad": all_probs.get("severidad", ""),
                        "razonamiento": all_probs.get("razonamiento", ""),
                        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                    }
                }),
                loop
            )
        return

    if emotion == "SILENCIO":
        if loop:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast({"type": "status", "value": "😶 Silencio / Procesando...", "is_active": False}),
                loop
            )
        return
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    result = {
        "timestamp": timestamp,
        "speaker": speaker if speaker else "Desconocido",
        "emotion": emotion,
        "score": round(float(score), 2),
        "all_probs": all_probs or {},
        "file": filepath
    }
    
    state.history.append(result)
    state.save_history()
    
    if loop:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "result", "data": result}),
            loop
        )

def error_callback(msg):
    if loop:
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "error", "value": msg}),
            loop
        )

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- Routes ---

@app.get("/api/history")
async def get_history():
    return state.history

@app.get("/api/status")
async def get_status():
    return {"is_running": state.is_running}

@app.get("/api/models_status")
async def get_models_status():
    return model_preloader.get_status()

@app.get("/api/rag_search")
async def rag_search(query: str):
    if model_preloader.rag_service is None:
        return {"query": query, "result": "El RAG aún se está cargando. Inténtalo en unos segundos."}
    
    result = model_preloader.rag_service.search(query)
    return {"query": query, "result": result}

@app.get("/api/devices")
async def get_devices():
    p = pyaudio.PyAudio()
    devices = []
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        devices.append({
            "index": i,
            "name": dev['name'],
            "max_input_channels": dev['maxInputChannels']
        })
    p.terminate()
    return devices

@app.post("/api/start")
async def start_api(max_speakers: int = None):
    if state.start_engine(engine_callback, error_callback, max_speakers):
        return {"status": "started"}
    return {"status": "already_running"}

@app.post("/api/stop")
async def stop_api():
    if state.stop_engine():
        return {"status": "stopped"}
    return {"status": "not_running"}

@app.post("/api/reset_data")
async def reset_data():
    from backend.config import DATA_DIR, AUDIO_DIR
    import shutil
    try:
        state.stop_engine()
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if item == "knowledge":
                continue
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        
        os.makedirs(AUDIO_DIR, exist_ok=True)
        state.history = []
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/calibration_status")
async def calibration_status():
    # Comprobación directa para evitar esperas mientras cargan los modelos
    return {"calibrated": os.path.exists(CALIBRATION_FILE)}

# --- Calibración vía PyAudio (mismo dispositivo que el análisis) ---
import wave
import numpy as np
from backend.config import FORMAT, CHANNELS, RATE, CHUNK
from backend.core.audio_handler import find_vbcable_device, find_mic_device

calibration_recording = False

def _send_calib_event(event_type, **kwargs):
    """Envía un evento de calibración al frontend vía WebSocket."""
    if loop:
        msg = {"type": "calibration", "event": event_type, **kwargs}
        asyncio.run_coroutine_threadsafe(manager.broadcast(msg), loop)

def _record_calibration_thread(duration_secs=30):
    """Graba audio desde PyAudio (VB-Cable) en un hilo de background."""
    global calibration_recording
    calibration_recording = True
    
    p = pyaudio.PyAudio()
    vb_idx, vb_name = find_vbcable_device(p)
    mic_idx, mic_name = find_mic_device(p)
    device_index = vb_idx if vb_idx is not None else mic_idx
    
    if device_index is None:
        _send_calib_event("error", message="No se encontró dispositivo de audio.")
        calibration_recording = False
        p.terminate()
        return
    
    selected_name = p.get_device_info_by_index(device_index)['name']
    print(f"[CALIB] Grabando desde: {selected_name} durante {duration_secs}s...")
    _send_calib_event("recording", device=selected_name)
    
    try:
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, input_device_index=device_index,
                        frames_per_buffer=CHUNK)
        
        frames = []
        total_chunks = int(RATE / CHUNK * duration_secs)
        last_pct = 0
        
        for i in range(total_chunks):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            pct = int((i / total_chunks) * 100)
            # Solo enviar al WebSocket cada 10% para no saturar
            if pct >= last_pct + 10:
                last_pct = pct
                _send_calib_event("progress", progress=pct)
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Guardar como WAV
        wav_path = os.path.join(AUDIO_DIR, "calibration_recording.wav")
        wf = wave.open(wav_path, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        print(f"[CALIB] Grabación completada. Archivo: {wav_path} ({os.path.getsize(wav_path)} bytes)")
        _send_calib_event("processing")
        
        # Procesar calibración
        _, cal_mgr = get_diarizer()
        success, message = cal_mgr.process_calibration_audio(wav_path)
        
        _send_calib_event("done", success=success, message=message)
        
    except Exception as e:
        print(f"[CALIB] Error en grabación: {e}")
        _send_calib_event("error", message=str(e))
        try:
            p.terminate()
        except:
            pass
    finally:
        calibration_recording = False

@app.post("/api/calibrate_start")
async def calibrate_start():
    """Inicia la grabación de calibración desde PyAudio (VB-Cable) en un hilo de background."""
    if calibration_recording:
        return {"status": "error", "message": "Ya hay una grabación en curso."}
    
    thread = threading.Thread(target=_record_calibration_thread, daemon=True)
    thread.start()
    return {"status": "recording"}

# Mantenemos el endpoint antiguo como fallback por compatibilidad
@app.post("/api/calibrate")
async def calibrate(file: UploadFile = File(...)):
    temp_path = os.path.join(AUDIO_DIR, "temp_calibration.webm")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        _, cal_mgr = get_diarizer()
        success, message = cal_mgr.process_calibration_audio(temp_path)
        
        if success:
            return {"status": "success"}
        else:
            return {"status": "error", "message": message}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# Serve the audio files
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# Serve the frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
