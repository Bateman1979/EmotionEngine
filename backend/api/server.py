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

# --- Loop management for async/sync interop ---
loop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop
    loop = asyncio.get_event_loop()
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

@app.get("/api/calibration_status")
async def calibration_status():
    # Comprobación directa para evitar esperas mientras cargan los modelos
    return {"calibrated": os.path.exists(CALIBRATION_FILE)}

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
