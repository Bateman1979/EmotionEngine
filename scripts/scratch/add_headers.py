import os

FULL_NAME = "Valentín González Coira"
EMAIL = "cabezaburbuja@gmail.com"
SCHOOL = "EBIS Business School"
YEAR = "2026"
PROJECT = "Emotion Engine"
CONTEXT = "Trabajo de Fin de Máster (TFM)"

PYTHON_HEADER = f"""# ==============================================================================
# © {YEAR} {FULL_NAME} ({EMAIL}).
# {SCHOOL} - {CONTEXT}.
# Todos los derechos reservados.
# Este código es propiedad intelectual exclusiva del autor.
# Queda prohibida su copia, distribución o modificación sin autorización expresa.
# Proyecto: {PROJECT}
# ==============================================================================
"""

JS_CSS_HEADER = f"""/* ==============================================================================
 * © {YEAR} {FULL_NAME} ({EMAIL}).
 * {SCHOOL} - {CONTEXT}.
 * Todos los derechos reservados.
 * Este código es propiedad intelectual exclusiva del autor.
 * Queda prohibida su copia, distribución o modificación sin autorización expresa.
 * Proyecto: {PROJECT}
 * ============================================================================== */
"""

HTML_HEADER = f"""<!-- ==============================================================================
  © {YEAR} {FULL_NAME} ({EMAIL}).
  {SCHOOL} - {CONTEXT}.
  Todos los derechos reservados.
  Este código es propiedad intelectual exclusiva del autor.
  Queda prohibida su copia, distribución o modificación sin autorización expresa.
  Proyecto: {PROJECT}
  ============================================================================== -->
"""

files_to_update = [
    ("main.py", PYTHON_HEADER),
    ("backend/api/server.py", PYTHON_HEADER),
    ("backend/core/audio_handler.py", PYTHON_HEADER),
    ("backend/core/audio_segmenter.py", PYTHON_HEADER),
    ("backend/core/engine.py", PYTHON_HEADER),
    ("backend/core/voice_detector.py", PYTHON_HEADER),
    ("backend/services/calibration_manager.py", PYTHON_HEADER),
    ("backend/services/diarization.py", PYTHON_HEADER),
    ("backend/services/emotion_detection.py", PYTHON_HEADER),
    ("backend/services/identity_manager.py", PYTHON_HEADER),
    ("backend/config.py", PYTHON_HEADER),
    ("frontend/app.js", JS_CSS_HEADER),
    ("frontend/calibration.js", JS_CSS_HEADER),
    ("frontend/style.css", JS_CSS_HEADER),
    ("frontend/index.html", HTML_HEADER)
]

def update_file(filepath, header):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Marcadores de cabeceras anteriores para reemplazo
    marks = [
        "© 2026 Valentín. Todos los derechos reservados.",
        "© 2026 Valentín González Coira. Todos los derechos reservados."
    ]
    
    new_mark = f"© {YEAR} {FULL_NAME} ({EMAIL})."
    
    if new_mark in content:
        print(f"Header already up to date in {filepath}")
        return

    replaced = False
    for mark in marks:
        if mark in content:
            if filepath.endswith('.py'):
                mark_end = "# =============================================================================="
                parts = content.split(mark_end)
                if len(parts) > 2:
                    content = header + mark_end.join(parts[2:]).lstrip()
                    replaced = True
                    break
            elif filepath.endswith(('.js', '.css')):
                mark_end = "* ============================================================================== */"
                parts = content.split(mark_end)
                if len(parts) > 1:
                    content = header + mark_end.join(parts[1:]).lstrip()
                    replaced = True
                    break
            elif filepath.endswith('.html'):
                mark_end = "============================================================================== -->"
                parts = content.split(mark_end)
                if len(parts) > 1:
                    content = header + mark_end.join(parts[1:]).lstrip()
                    replaced = True
                    break
    
    if not replaced:
        # No se encontró cabecera previa para reemplazar, añadir al inicio
        if filepath.endswith('.html'):
            if content.strip().lower().startswith("<!doctype html>"):
                parts = content.split(">", 1)
                content = parts[0] + ">\n" + header + parts[1]
            else:
                content = header + content
        else:
            content = header + content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated header in {filepath}")

for filepath, header in files_to_update:
    update_file(filepath, header)

print("Done.")
