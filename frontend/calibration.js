/* ==============================================================================
 * © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
 * EBIS Business School - Trabajo de Fin de Máster (TFM).
 * Todos los derechos reservados.
 * Este código es propiedad intelectual exclusiva del autor.
 * Queda prohibida su copia, distribución o modificación sin autorización expresa.
 * Proyecto: Emotion Engine
 * ============================================================================== */
// --- CALIBRATION LOGIC ---
// La grabación se realiza en el BACKEND vía PyAudio (mismo dispositivo que el análisis).
// El progreso llega vía WebSocket (sin polling).

async function checkCalibration() {
    try {
        const response = await fetch('/api/calibration_status?t=' + Date.now());
        const data = await response.json();
        console.log("[CALIB] Estado recibido del servidor:", data.calibrated);
        if (!data.calibrated) {
            showCalibrationModal();
        }
    } catch (error) {
        console.error("Failed to check calibration:", error);
    }
}

function showCalibrationModal() {
    document.getElementById('calibration-modal').classList.remove('hidden');
}

// Handler global para eventos de calibración que llegan vía WebSocket
function handleCalibrationEvent(data) {
    const instructions = document.getElementById('calib-instructions');
    const btn = document.getElementById('start-calib-btn');
    const vumeterBars = document.querySelectorAll('.vumeter .bar');
    const timerText = document.getElementById('timer-text');
    const progressBar = document.getElementById('progress-bar');

    switch (data.event) {
        case 'recording':
            console.log("[CALIB] Grabando desde:", data.device);
            instructions.innerText = `Grabando desde ${data.device}...`;
            break;

        case 'progress':
            // Animar VU meter con variación visual
            vumeterBars.forEach((bar, i) => {
                const factor = 1 - Math.abs(i - 2) * 0.15;
                const noise = Math.random() * 30 + 20;
                const val = Math.min(100, Math.max(10, noise * factor));
                bar.style.height = `${val}%`;
            });
            // Actualizar barra circular
            const remaining = 30 * (1 - data.progress / 100);
            timerText.innerText = `${Math.ceil(remaining)}s`;
            progressBar.style.strokeDashoffset = 339.29 * (1 - data.progress / 100);
            break;

        case 'processing':
            instructions.innerText = "Procesando huella acústica...";
            vumeterBars.forEach(bar => bar.style.height = '10%');
            timerText.innerText = "⏳";
            break;

        case 'done':
            vumeterBars.forEach(bar => bar.style.height = '10%');
            timerText.innerText = "30s";
            progressBar.style.strokeDashoffset = 0;
            if (data.success) {
                instructions.innerText = "¡Calibración completada con éxito!";
                instructions.style.color = "var(--success)";
                setTimeout(() => {
                    document.getElementById('calibration-modal').classList.add('hidden');
                    if (typeof showToast === 'function') {
                        showToast("Voz del comercial calibrada. El motor la ignorará.", "success");
                    }
                }, 2000);
            } else {
                instructions.innerText = "Error: " + (data.message || "Fallo desconocido");
                btn.disabled = false;
                btn.innerText = "Reintentar Grabación";
            }
            break;

        case 'error':
            vumeterBars.forEach(bar => bar.style.height = '10%');
            instructions.innerText = "Error: " + (data.message || "Fallo desconocido");
            btn.disabled = false;
            btn.innerText = "Reintentar Grabación";
            break;
    }
}

async function startCalibration() {
    const btn = document.getElementById('start-calib-btn');
    const instructions = document.getElementById('calib-instructions');
    const timerText = document.getElementById('timer-text');
    
    btn.disabled = true;
    btn.innerText = "🔴 Grabando...";
    instructions.innerText = "Iniciando grabación desde el servidor...";
    timerText.innerText = "30s";
    
    try {
        const startResponse = await fetch('/api/calibrate_start', { method: 'POST' });
        const startData = await startResponse.json();
        
        if (startData.status === 'error') {
            throw new Error(startData.message);
        }
        // A partir de aquí, los eventos llegan vía WebSocket → handleCalibrationEvent()

    } catch (err) {
        console.error("Error en calibración:", err);
        if (typeof showToast === 'function') {
            showToast("Error en calibración: " + err.message);
        }
        btn.disabled = false;
        btn.innerText = "Reintentar Grabación";
    }
}
