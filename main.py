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

if __name__ == "__main__":
    import uvicorn
    # Importación absoluta desde la nueva estructura
    from backend.api.server import app
    
    print("\n" + "="*40)
    print("      EMOTION ENGINE - WEB DASHBOARD")
    print("="*40)
    print(f"URL: http://localhost:8001")
    print("Presiona Ctrl+C para detener el servidor\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
