# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import pyaudio
from backend.config import FORMAT, CHANNELS, RATE, CHUNK

def find_vbcable_device(p):
    """Busca el cable virtual (generalmente para interlocutores)."""
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if "CABLE Output" in dev['name']:
            return i, dev['name']
    return None, None

def find_mic_device(p):
    """Busca el micrófono físico (para el comercial)."""
    # Priorizamos dispositivos que digan 'Microphone' o 'Micrófono' y no sean el Virtual Cable
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        name = dev['name']
        if ("Microphone" in name or "Micrófono" in name) and "CABLE" not in name:
            return i, name
    return None, None

def init_stream():
    """
    Inicializa el flujo de audio. 
    Por defecto intenta usar VB-Cable para captar la conversación completa.
    """
    p = pyaudio.PyAudio()
    
    vb_idx, vb_name = find_vbcable_device(p)
    mic_idx, mic_name = find_mic_device(p)
    
    print(f"\n[AUDIO] Dispositivos detectados:")
    print(f"  - VB-Cable: {vb_name if vb_name else 'No encontrado'}")
    print(f"  - Micrófono: {mic_name if mic_name else 'No encontrado'}")

    # Seleccionamos el dispositivo. 
    # Si el usuario quiere filtrar al comercial, el motor DEBE oír al comercial.
    # Si VB-Cable está configurado para oír 'Todo' (Mixed), usamos ese.
    # Si no, por ahora priorizamos VB-Cable pero informamos.
    
    device_index = vb_idx if vb_idx is not None else mic_idx
    
    if device_index is None:
        raise Exception("No se encontró ningún dispositivo de entrada válido (Micrófono o VB-Cable).")

    selected_name = p.get_device_info_by_index(device_index)['name']
    print(f"[AUDIO] Usando dispositivo: {selected_name}\n")

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK)
    
    return p, stream
