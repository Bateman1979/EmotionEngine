/* ==============================================================================
 * © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
 * EBIS Business School - Trabajo de Fin de Máster (TFM).
 * Todos los derechos reservados.
 * Este código es propiedad intelectual exclusiva del autor.
 * Queda prohibida su copia, distribución o modificación sin autorización expresa.
 * Proyecto: Emotion Engine
 * ============================================================================== */
// --- State Management ---
let history = [];
let timelineChart;
let speakerCharts = {}; // Object to store Chart instances for each speaker
let socket;

// Mapa de colores por emoción (claves en español capitalizado, igual que emotion_detection.py)
const EMOTION_COLORS = {
    'Alegría':  '#10b981',  // verde
    'Sorpresa': '#f59e0b',  // ámbar
    'Neutro':   '#475569',  // gris
    'Asco':     '#a855f7',  // violeta
    'Miedo':    '#3b82f6',  // azul
    'Ira':      '#ef4444',  // rojo
    'Tristeza': '#6366f1',  // índigo
};

// --- DOM Elements ---
const lastEmotionEl = document.getElementById('last-emotion');
const lastScoreEl = document.getElementById('last-score');
const lastSpeakerEl = document.getElementById('last-speaker');
const lastTimeEl = document.getElementById('last-time');
const engineStatusDot = document.getElementById('engine-status-dot');
const engineStatusLabel = document.getElementById('engine-status-label');
const engineSubstatus = document.getElementById('engine-substatus');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const clockEl = document.getElementById('clock');
const profilesGrid = document.getElementById('speaker-profiles');

// --- Initialization ---
async function init() {
    updateClock();
    setInterval(updateClock, 1000);
    
    await fetchHistory();
    initTimelineChart();
    setupWebSocket();
    await checkCalibration();
    checkEngineStatus();

    startBtn.addEventListener('click', startEngine);
    stopBtn.addEventListener('click', stopEngine);
    
    document.getElementById('list-devices').addEventListener('click', listDevices);
    
    document.getElementById('start-calib-btn').addEventListener('click', startCalibration);
    document.getElementById('skip-calib-btn').addEventListener('click', () => {
        console.log("[CALIB] Saltando calibración por petición del usuario.");
        document.getElementById('calibration-modal').classList.add('hidden');
    });
}

// --- API Calls ---
async function fetchHistory() {
    try {
        const response = await fetch('/api/history');
        history = await response.json();
        updateUI();
    } catch (error) {
        console.error("Failed to fetch history:", error);
    }
}

async function checkEngineStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        updateEngineStatusUI(data.is_running);
    } catch (error) {
        console.error("Failed to check status:", error);
    }
}

async function startEngine() {
    const maxSpeakers = document.getElementById('max-speakers').value;
    
    let url = '/api/start';
    const params = new URLSearchParams();
    if (maxSpeakers) params.append('max_speakers', maxSpeakers);
    if (params.toString()) url += `?${params.toString()}`;

    startBtn.disabled = true;
    startBtn.innerHTML = "⏳ Iniciando...";
    try {
        const response = await fetch(url, { method: 'POST' });
        const data = await response.json();
        if (data.status === 'started' || data.status === 'already_running') {
            updateEngineStatusUI(true);
        }
    } catch (error) {
        showToast("Error al iniciar el motor", "error");
    } finally {
        startBtn.disabled = false;
        startBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Iniciar Análisis</span>';
    }
}

async function stopEngine() {
    stopBtn.disabled = true;
    stopBtn.innerText = "⏳ Deteniendo...";
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'stopped' || data.status === 'not_running') {
            updateEngineStatusUI(false);
        }
    } catch (error) {
        showToast("Error al detener el motor", "error");
    } finally {
        stopBtn.disabled = false;
        stopBtn.innerHTML = '<span class="btn-icon">🛑</span> Detener Análisis';
    }
}

// --- UI Updates ---
function updateUI() {
    if (history.length === 0) return;

    const latest = history[history.length - 1];
    const isPending = latest.speaker.startsWith("Identificando");
    
    // Update metrics
    if (isPending) {
        lastEmotionEl.innerText = "PROCESANDO...";
        lastScoreEl.innerText = "-";
        lastSpeakerEl.innerText = "Análisis de voz en marcha";
        engineSubstatus.innerText = "🔍 " + latest.speaker;
    } else {
        lastEmotionEl.innerText = latest.emotion.toUpperCase();
        lastScoreEl.innerText = `${Math.round(latest.score * 100)}%`;
        lastSpeakerEl.innerText = latest.speaker;
        engineSubstatus.innerText = "✅ Escuchando...";
    }
    
    lastTimeEl.innerText = latest.timestamp;

    // Update Charts
    updateTimeline();
    updateSpeakerProfiles();
}

function updateEngineStatusUI(isRunning) {
    const bar = document.getElementById('live-speaker-bar');
    if (isRunning) {
        engineStatusDot.classList.add('online');
        engineStatusLabel.innerText = "Motor Activo";
        engineSubstatus.innerText = "Escuchando...";
        startBtn.style.display = 'none';
        stopBtn.style.display = 'flex';
        bar.classList.remove('hidden');
        hideLiveSpeaker();
    } else {
        engineStatusDot.classList.remove('online');
        engineStatusLabel.innerText = "Motor Detenido";
        engineSubstatus.innerText = "Inactivo";
        startBtn.style.display = 'flex';
        stopBtn.style.display = 'none';
        bar.classList.add('hidden');
        bar.classList.remove('waiting');
    }
}

function updateClock() {
    const now = new Date();
    clockEl.innerText = now.toLocaleTimeString();
}

function showToast(msg, type = "error") {
    const toast = document.getElementById('error-toast');
    toast.innerText = msg;
    toast.style.background = type === "error" ? "var(--danger)" : "var(--info)";
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 5000);
}

// --- Live Speaker Indicator ---
let hideSpeakerTimeout = null;

function showLiveSpeaker(speaker, duration) {
    const bar = document.getElementById('live-speaker-bar');
    const nameEl = document.getElementById('live-speaker-name');
    const durationEl = document.getElementById('live-speaker-duration');
    
    nameEl.innerText = speaker;
    if (duration !== undefined && duration > 0) {
        durationEl.innerText = ` (${duration.toFixed(1)}s)`;
    } else {
        durationEl.innerText = '';
    }
    
    bar.classList.remove('hidden');
    bar.classList.remove('waiting');
    // Auto-ocultar si no llegan más eventos (silencio de 3s)
    clearTimeout(hideSpeakerTimeout);
    hideSpeakerTimeout = setTimeout(hideLiveSpeaker, 3000);
}

function hideLiveSpeaker() {
    const bar = document.getElementById('live-speaker-bar');
    const nameEl = document.getElementById('live-speaker-name');
    const durationEl = document.getElementById('live-speaker-duration');
    
    nameEl.innerText = 'Esperando voz...';
    durationEl.innerText = '';
    bar.classList.add('waiting');
}

// --- WebSocket ---
function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'status') {
            engineSubstatus.innerText = msg.value;
            if (!msg.is_active) {
                // Silencio: ocultar el indicador de hablante activo
                hideLiveSpeaker();
                lastSpeakerEl.style.opacity = "1";
            }
        } else if (msg.type === 'speaker_active') {
            showLiveSpeaker(msg.speaker, msg.duration);
            // Mostrar la última emoción conocida para este hablante
            const speakerHistory = history.filter(h => h.speaker === msg.speaker && !h.speaker.startsWith("Identificando"));
            if (speakerHistory.length > 0) {
                const latest = speakerHistory[speakerHistory.length - 1];
                lastEmotionEl.innerText = latest.emotion.toUpperCase();
                lastEmotionEl.style.color = "var(--text-primary)";
                lastScoreEl.innerText = `${Math.round(latest.score * 100)}%`;
                lastSpeakerEl.innerText = latest.speaker;
            } else {
                lastEmotionEl.innerText = "ANALIZANDO...";
                lastEmotionEl.style.color = "var(--text-secondary)";
                lastScoreEl.innerText = "-";
                lastSpeakerEl.innerText = msg.speaker;
            }
            lastSpeakerEl.style.opacity = "1";
        } else if (msg.type === 'result') {
            lastSpeakerEl.style.opacity = "1";
            lastEmotionEl.style.color = "var(--text-primary)";
            history.push(msg.data);
            updateUI();
        } else if (msg.type === 'error') {
            showToast(msg.value);
        }
    };

    socket.onclose = () => {
        setTimeout(setupWebSocket, 2000);
    };
}

// --- Timeline Chart (Stacked Area — Distribución de Emociones) ---
const EMOTION_ORDER  = ['Alegría', 'Sorpresa', 'Neutro', 'Asco', 'Miedo', 'Ira', 'Tristeza'];
const EMOTION_AREA_COLORS = {
    'Alegría':  'rgba(16,  185, 129, 0.85)',
    'Sorpresa': 'rgba(245, 158, 11,  0.85)',
    'Neutro':   'rgba(148, 163, 184, 0.85)',
    'Asco':     'rgba(168, 85,  247, 0.85)',
    'Miedo':    'rgba(59,  130, 246, 0.85)',
    'Ira':      'rgba(239, 68,  68,  0.85)',
    'Tristeza': 'rgba(99,  102, 241, 0.85)',
};

let activeSpeakerFilter = null;  // null = todos

function initTimelineChart() {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    timelineChart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    type: 'category',
                    ticks: { display: false },
                    grid:  { color: 'rgba(255,255,255,0.04)' },
                    title: { display: false }
                },
                y: {
                    stacked: false,
                    min: 0, max: 1,
                    ticks: {
                        color: '#94a3b8',
                        callback: v => `${Math.round(v * 100)}%`
                    },
                    grid:  { color: 'rgba(255,255,255,0.06)' },
                    title: { display: true, text: 'Probabilidad (%)', color: '#94a3b8' }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#f8fafc', usePointStyle: true, pointStyle: 'rectRounded', font: { size: 11 } }
                },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            const index = items[0].dataIndex;
                            const h = history.filter(item => 
                                !item.speaker.startsWith("Identificando") && 
                                item.emotion && 
                                item.all_probs && Object.keys(item.all_probs).length > 0
                            );
                            // Necesitamos aplicar el mismo filtro que en updateTimeline
                            const filtered = activeSpeakerFilter
                                ? h.filter(item => item.speaker === activeSpeakerFilter)
                                : h;
                            const last25 = filtered.slice(-25);
                            const item = last25[index];
                            return `${item.speaker} (${item.timestamp})`;
                        },
                        label: ctx => ` ${ctx.dataset.label}: ${Math.round(ctx.raw * 100)}%`
                    }
                }
            }
        }
    });
    updateTimeline();
}

function updateTimeline() {
    if (!history.length || !timelineChart) return;

    const valid = history.filter(h =>
        !h.speaker.startsWith("Identificando") &&
        h.emotion &&
        h.all_probs && Object.keys(h.all_probs).length > 0
    );
    if (!valid.length) return;

    // Filtrar por hablante activo si hay selector
    const filtered = activeSpeakerFilter
        ? valid.filter(h => h.speaker === activeSpeakerFilter)
        : valid;

    const last25 = filtered.slice(-25);
    timelineChart.data.labels = last25.map(h => h.speaker);

    // Un dataset por cada emoción (superpuestos, no apilados)
    timelineChart.data.datasets = EMOTION_ORDER.map(emotion => ({
        label: emotion,
        data: last25.map(h => h.all_probs[emotion] ?? 0),
        backgroundColor: EMOTION_AREA_COLORS[emotion].replace('0.85', '0.15'), // Menos opaco para ver capas
        borderColor: EMOTION_AREA_COLORS[emotion].replace('0.85', '1'),
        borderWidth: 2,
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.4
    }));

    timelineChart.update('none');
}

function setSpeakerFilter(speaker) {
    activeSpeakerFilter = speaker;
    updateTimeline();
}

// --- Speaker Profiles & Mini Charts ---
function updateSpeakerProfiles() {
    if (!history.length) return;

    const secureHistory = history.filter(item => !item.speaker.startsWith("Identificando"));
    
    const speakerData = {};
    secureHistory.forEach(item => {
        if (!speakerData[item.speaker]) {
            speakerData[item.speaker] = {
                emotions: {},
                count: 0,
                lastEmotion: item.emotion
            };
        }
        speakerData[item.speaker].emotions[item.emotion] = (speakerData[item.speaker].emotions[item.emotion] || 0) + 1;
        speakerData[item.speaker].count++;
        speakerData[item.speaker].lastEmotion = item.emotion;
    });

    if (Object.keys(speakerData).length > 0) {
        const emptyState = profilesGrid.querySelector('.empty-state');
        if (emptyState) emptyState.remove();
    }

    Object.keys(speakerData).forEach(speaker => {
        let card = document.getElementById(`card-${speaker.replace(/\s+/g, '-')}`);
        
        if (!card) {
            card = createSpeakerCard(speaker);
            profilesGrid.appendChild(card);
            initSpeakerMiniChart(speaker, speakerData[speaker].emotions);
            // Añadir al selector del gráfico de timeline
            const sel = document.getElementById('speaker-filter');
            if (sel && !Array.from(sel.options).find(o => o.value === speaker)) {
                const opt = document.createElement('option');
                opt.value = speaker;
                opt.text  = speaker;
                sel.appendChild(opt);
            }
        } else {
            updateSpeakerMiniChart(speaker, speakerData[speaker].emotions);
            card.querySelector('.last-emo-text').innerText = `Último estado: ${speakerData[speaker].lastEmotion}`;
        }
    });
}

function createSpeakerCard(speaker) {
    const div = document.createElement('div');
    div.id = `card-${speaker.replace(/\s+/g, '-')}`;
    div.className = 'speaker-card animated-fadeIn';
    div.innerHTML = `
        <div class="mini-pie-container">
            <canvas id="chart-${speaker.replace(/\s+/g, '-')}"></canvas>
        </div>
        <div class="speaker-info">
            <h4>${speaker}</h4>
            <p class="last-emo-text">Analizando...</p>
        </div>
    `;
    return div;
}

function initSpeakerMiniChart(speaker, emotionCounts) {
    const canvas = document.getElementById(`chart-${speaker.replace(/\s+/g, '-')}`);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    speakerCharts[speaker] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(emotionCounts),
            datasets: [{
                data: Object.values(emotionCounts),
                backgroundColor: Object.keys(emotionCounts).map(e => EMOTION_COLORS[e]),
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { display: false },
                tooltip: { enabled: true }
            }
        }
    });
}

function updateSpeakerMiniChart(speaker, emotionCounts) {
    const chart = speakerCharts[speaker];
    if (!chart) return;
    
    chart.data.labels = Object.keys(emotionCounts);
    chart.data.datasets[0].data = Object.values(emotionCounts);
    chart.data.datasets[0].backgroundColor = Object.keys(emotionCounts).map(e => EMOTION_COLORS[e]);
    chart.update();
}

async function listDevices() {
    try {
        const response = await fetch('/api/devices');
        const devices = await response.json();
        console.table(devices);
        const deviceList = devices.map(d => `${d.index}: ${d.name} (${d.max_input_channels} in)`).join('\n');
        alert("Dispositivos de audio detectados (ver consola para detalle):\n\n" + deviceList);
    } catch (error) {
        showToast("Error al listar dispositivos");
    }
}

window.onload = init;
