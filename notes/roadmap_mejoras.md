# Roadmap: Posibles Mejoras y Evolución Técnica 🚀

Este documento detalla las líneas de investigación y desarrollo futuro para optimizar el **Emotion Engine**, centrándose en la precisión del análisis y la fluidez del procesamiento.

---

## 🎙️ 1. Optimizaciones en la Ventana de Análisis

Actualmente, el sistema utiliza una ventana fija de 15 segundos de voz neta acumulada para garantizar la precisión del modelo Wav2Vec2.

*   **Análisis Dinámico de Fin de Turno**: 
    *   **Propuesta**: Implementar una lógica que permita disparar la inferencia en fragmentos de entre **5 y 15 segundos**.
    *   **Condición**: Solo se activará si el sistema detecta de forma positiva un "Fin de Turno" (silencio prolongado > 2s) o un cambio de interlocutor claro.
    *   **Objetivo**: Reducir la latencia en la entrega de resultados cuando el hablante termina su intervención antes de los 15s.

---

## 🧠 2. Refinamiento de la Inferencia Emocional

Para mejorar la utilidad de los datos entregados al usuario y evitar falsos positivos.

*   **Umbral Mínimo de Certidumbre (Confidence Threshold)**:
    *   **Propuesta**: No mostrar resultados cuya probabilidad máxima sea inferior a un umbral (ej. < 45%).
    *   **Lógica**: Si el modelo no está seguro, el sistema debería reportar "Incierto" o "Neutro" para evitar confundir al usuario con predicciones de baja calidad.
*   **Detección de Emoción Secundaria**:
    *   **Propuesta**: Mostrar en la interfaz no solo la emoción dominante, sino también la segunda con mayor probabilidad.
    *   **Valor añadido**: En conversaciones complejas, las emociones suelen ser mixtas (ej. "Ira" con un componente de "Tristeza"). Esto proporcionaría un análisis mucho más rico para el TFM.

---

## 👥 3. Gestión Avanzada de Identidades

*   **Detección de Solapamiento (Overlapping)**: Implementar una lógica capaz de identificar momentos donde comercial y cliente hablan a la vez, evitando que esas huellas mezcladas ensucien los perfiles individuales.

---

## 📊 4. Visualización y Reporte

*   **Exportación de Sesiones**: Botón para descargar un resumen en PDF o CSV con el "Mapa Emocional" de la reunión.
*   **Dashboard de KPIs**: Añadir métricas como "Ratio de Interrupción" y "Balance de Participación" entre comercial y cliente.

---

> [!NOTE]
> Estas mejoras están orientadas a convertir el prototipo actual en un producto de grado industrial, maximizando la fiabilidad de las métricas obtenidas.
