# ==============================================================================
# © 2026 Valentín González Coira (cabezaburbuja@gmail.com).
# EBIS Business School - Trabajo de Fin de Máster (TFM).
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: Emotion Engine
# ==============================================================================
import os
import sys
import warnings
import torch

# Suprimir avisos de librerías que no afectan al funcionamiento actual
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote.audio.core.io")

# Optimizaciones de rendimiento para GPUs Ampere o superiores (evita el warning de pyannote)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# Aseguramos que la raíz del proyecto esté en el path para las importaciones absolutas
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import subprocess
import time

def free_port(port):
    """Busca y destruye cualquier proceso 'zombie' que esté ocupando el puerto en Windows."""
    try:
        # Busca quién tiene el puerto en modo escucha
        result = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
        for line in result.splitlines():
            if 'LISTENING' in line:
                # El PID es la última columna
                pid = line.strip().split()[-1]
                print(f"[!] El puerto {port} estaba bloqueado por el proceso {pid}. Liberando...")
                subprocess.call(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1)  # Dar tiempo al OS para liberar el socket
                break
    except subprocess.CalledProcessError:
        pass  # El puerto ya está libre

if __name__ == "__main__":
    import uvicorn
    # Importación absoluta desde la nueva estructura
    from backend.api.server import app
    
    # Liberar puerto si quedó colgado de una ejecución anterior
    free_port(8001)
    
    print("\n" + "="*40)
    print("      EMOTION ENGINE - WEB DASHBOARD")
    print("="*40)
    print(f"URL: http://localhost:8001")
    print("Presiona Ctrl+C para detener el servidor\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
