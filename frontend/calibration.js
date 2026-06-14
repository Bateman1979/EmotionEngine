/* ==============================================================================
 * © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
 * EBIS Business School - Trabajo de Fin de Máster (TFM).
 * Todos los derechos reservados.
 * Este código es propiedad intelectual exclusiva del autor.
 * Queda prohibida su copia, distribución o modificación sin autorización expresa.
 * Proyecto: Emotion Engine
 * ============================================================================== */
// --- CALIBRATION LOGIC ---

async function checkCalibration() {
    try {
        // Añadimos un timestamp para evitar la caché del navegador
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

async function startCalibration() {
    const btn = document.getElementById('start-calib-btn');
    const instructions = document.getElementById('calib-instructions');
    const timerText = document.getElementById('timer-text');
    const progressBar = document.getElementById('progress-bar');
    const vumeterBars = document.querySelectorAll('.vumeter .bar');
    
    btn.disabled = true;
    btn.innerText = "🔴 Grabando...";
    instructions.innerText = "¡Te escuchamos! Lee el texto con naturalidad durante 30 segundos...";
    
    try {
        console.log("Solicitando micrófono...");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log("Micrófono concedido.");
        
        const mediaRecorder = new MediaRecorder(stream);
        let audioChunks = [];

        // Audio Context para el VU Meter
        const audioContext = new AudioContext();
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }
        
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        let silenceDetected = true;

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            if (silenceDetected) {
                if (typeof showToast === 'function') {
                    showToast("⚠️ No se ha detectado sonido. Asegúrate de que el micrófono funciona.", "warning");
                }
            }
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await uploadCalibration(audioBlob);
            stream.getTracks().forEach(track => track.stop());
            audioContext.close();
        };

        // Iniciar grabación
        mediaRecorder.start();
        console.log("Grabación iniciada. Estado:", mediaRecorder.state);

        function updateVUMeter() {
            if (mediaRecorder && mediaRecorder.state === "recording") {
                analyser.getByteFrequencyData(dataArray);
                // Calculamos el valor máximo en lugar del promedio para mayor reactividad
                const max = Math.max(...dataArray);
                
                if (max > 10) silenceDetected = false;

                vumeterBars.forEach((bar, i) => {
                    const factor = 1 - Math.abs(i - 2) * 0.2;
                    // Ajustamos la sensibilidad: multiplicador 0.8 para evitar saturación
                    const val = Math.min(100, Math.max(10, (max / 255) * 100 * factor * 1.2));
                    bar.style.height = `${val}%`;
                });
                requestAnimationFrame(updateVUMeter);
            } else {
                vumeterBars.forEach(bar => bar.style.height = '10%');
            }
        }
        
        // Empezamos a visualizar
        updateVUMeter();

        // Lógica del contador
        let timeLeft = 30;
        const totalDuration = 30;
        
        const interval = setInterval(() => {
            timeLeft -= 0.1;
            if (timeLeft <= 0) {
                clearInterval(interval);
                if (mediaRecorder.state === "recording") {
                    mediaRecorder.stop();
                }
                timerText.innerText = "30s";
                progressBar.style.strokeDashoffset = 0;
            } else {
                const displayTime = Math.ceil(timeLeft);
                timerText.innerText = `${displayTime}s`;
                const offset = 339.29 * (timeLeft / totalDuration);
                progressBar.style.strokeDashoffset = offset;
            }
        }, 100);

    } catch (err) {
        console.error("Error en calibración:", err);
        if (typeof showToast === 'function') {
            showToast("No se pudo acceder al micrófono: " + err.message);
        } else {
            alert("Error de micrófono: " + err.message);
        }
        btn.disabled = false;
        btn.innerText = "Reintentar Grabación";
    }
}

async function uploadCalibration(blob) {
    const instructions = document.getElementById('calib-instructions');
    instructions.innerText = "Procesando tu huella acústica... Un momento.";
    
    const formData = new FormData();
    formData.append('file', blob, 'calibration.wav');

    try {
        const response = await fetch('/api/calibrate', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            instructions.innerText = "¡Calibración completada con éxito!";
            instructions.style.color = "var(--success)";
            setTimeout(() => {
                document.getElementById('calibration-modal').classList.add('hidden');
                if (typeof showToast === 'function') {
                    showToast("Voz del comercial calibrada. El motor la ignorará.", "success");
                }
            }, 2000);
        } else {
            throw new Error(data.message || "Error desconocido");
        }
    } catch (err) {
        console.error("Error subiendo calibración:", err);
        if (typeof showToast === 'function') {
            showToast("Error al subir calibración: " + err.message);
        }
        document.getElementById('start-calib-btn').disabled = false;
        document.getElementById('start-calib-btn').innerText = "Reintentar Calibración";
    }
}
