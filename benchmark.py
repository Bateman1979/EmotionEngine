"""
=============================================================
 BENCHMARK SCRIPT - Emotion Engine
 Mide latencias y consumo de VRAM durante una sesión en vivo.
 
 Se conecta al WebSocket del servidor como un cliente "espía"
 y registra los tiempos entre eventos para generar métricas.
 
 USO: python benchmark.py
 (Mientras main.py está corriendo y escuchando audio)
=============================================================
"""
import asyncio
import websockets
import json
import time
import csv
import subprocess
import datetime
import statistics
import signal
import sys

# Forzar UTF-8 en la consola de Windows para soportar emojis
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ── Configuración ──
WS_URL = "ws://localhost:8001/ws"
RAG_URL = "http://localhost:8001/api/rag_search?query="
OUTPUT_CSV = "benchmark_log.csv"
VRAM_INTERVAL = 3  # Segundos entre muestras de VRAM


class BenchmarkCollector:
    def __init__(self):
        # Almacenes de métricas
        self.vram_samples = []
        self.emotion_latencies = []       # Tiempo entre detección y llegada al WS
        self.concept_latencies = []       # Tiempo entre trigger y llegada del concepto
        self.rag_latencies = []           # Tiempo de respuesta del RAG
        
        # Estado interno para medir conceptos
        self.pending_concept_triggers = {}  # speaker -> timestamp del trigger
        
        # Eventos recibidos para el CSV
        self.events = []
        self.running = True
        self.start_time = time.time()
    
    def get_vram(self):
        """Lee la VRAM usada en MiB mediante nvidia-smi."""
        try:
            result = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,nounits,noheader'],
                encoding='utf-8'
            )
            return int(result.strip().split('\n')[0])
        except:
            return 0
    
    async def monitor_vram(self):
        """Muestrea la VRAM cada N segundos en background."""
        while self.running:
            vram = self.get_vram()
            now = datetime.datetime.now().strftime("%H:%M:%S")
            self.vram_samples.append(vram)
            self.events.append({
                "timestamp": now,
                "elapsed_s": round(time.time() - self.start_time, 2),
                "event_type": "VRAM_SAMPLE",
                "detail": f"{vram} MiB",
                "latency_ms": ""
            })
            await asyncio.sleep(VRAM_INTERVAL)
    
    async def listen_websocket(self):
        """Se conecta al WS del servidor y registra eventos con sus tiempos."""
        print(f"[BENCH] Conectando a {WS_URL}...")
        async with websockets.connect(WS_URL) as ws:
            print(f"[BENCH] ✅ Conectado. Escuchando eventos del motor...\n")
            while self.running:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("[BENCH] WebSocket cerrado.")
                    break
                
                recv_time = time.time()
                now = datetime.datetime.now().strftime("%H:%M:%S")
                
                try:
                    data = json.loads(msg)
                except:
                    continue
                
                msg_type = data.get("type", "")
                
                # ── Evento: Resultado de emoción ──
                if msg_type == "result":
                    result = data.get("data", {})
                    speaker = result.get("speaker", "?")
                    emotion = result.get("emotion", "?")
                    score = result.get("score", 0)
                    
                    # La latencia aquí es: tiempo desde que el engine detectó la emoción
                    # hasta que el WebSocket lo entrega al cliente.
                    # Como no tenemos el timestamp del engine en ms, medimos el tiempo
                    # de recepción del WS respecto al timestamp del resultado.
                    # Guardamos el recv_time para medir el concepto después.
                    self.pending_concept_triggers[speaker] = recv_time
                    
                    event = {
                        "timestamp": now,
                        "elapsed_s": round(recv_time - self.start_time, 2),
                        "event_type": "EMOTION",
                        "detail": f"{speaker} | {emotion} ({score:.0%})",
                        "latency_ms": "—"
                    }
                    self.events.append(event)
                    print(f"  🎭 [{now}] EMOCIÓN: {speaker} → {emotion} ({score:.0%})")
                
                # ── Evento: Concepto detonante (LLM) ──
                elif msg_type == "concept":
                    concept_data = data.get("data", {})
                    speaker = concept_data.get("speaker", "?")
                    emotion = concept_data.get("emotion", "?")
                    concepto = concept_data.get("concepto_detonante", "?")
                    
                    # Calcular latencia desde la última emoción de este speaker
                    trigger_time = self.pending_concept_triggers.get(speaker)
                    if trigger_time:
                        latency_ms = round((recv_time - trigger_time) * 1000)
                        self.concept_latencies.append(latency_ms)
                        latency_str = f"{latency_ms} ms"
                    else:
                        latency_str = "—"
                    
                    event = {
                        "timestamp": now,
                        "elapsed_s": round(recv_time - self.start_time, 2),
                        "event_type": "CONCEPT",
                        "detail": f"{speaker} | {emotion} → {concepto[:60]}",
                        "latency_ms": latency_str
                    }
                    self.events.append(event)
                    print(f"  💡 [{now}] CONCEPTO: {speaker} → \"{concepto[:60]}...\" (Latencia: {latency_str})")
    
    async def run_rag_test(self, query: str):
        """Ejecuta una consulta RAG y mide el tiempo de respuesta."""
        import aiohttp
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n  🔍 [{now_str}] RAG: Buscando \"{query}\"...")
        
        start = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{RAG_URL}{query}") as resp:
                    result = await resp.json()
        except Exception as e:
            print(f"  ❌ RAG Error: {e}")
            return
        
        latency_ms = round((time.time() - start) * 1000)
        self.rag_latencies.append(latency_ms)
        
        now_str2 = datetime.datetime.now().strftime("%H:%M:%S")
        self.events.append({
            "timestamp": now_str2,
            "elapsed_s": round(time.time() - self.start_time, 2),
            "event_type": "RAG_QUERY",
            "detail": f"\"{query}\" → {str(result.get('result', ''))[:80]}",
            "latency_ms": f"{latency_ms} ms"
        })
        print(f"  ✅ [{now_str2}] RAG completado en {latency_ms} ms")
    
    async def rag_interactive_loop(self):
        """Permite al usuario lanzar queries RAG manualmente desde la consola."""
        await asyncio.sleep(5)  # Esperar a que el WS se conecte
        print("\n" + "="*60)
        print("  Para probar el RAG, escribe una consulta y pulsa Enter.")
        print("  Escribe 'salir' para terminar el benchmark.")
        print("="*60 + "\n")
        
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                query = await loop.run_in_executor(None, lambda: input(""))
                if query.strip().lower() in ("salir", "exit", "quit", "q"):
                    self.running = False
                    break
                if query.strip():
                    await self.run_rag_test(query.strip())
            except (EOFError, KeyboardInterrupt):
                self.running = False
                break
    
    def save_csv(self):
        """Guarda todos los eventos en un CSV."""
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "elapsed_s", "event_type", "detail", "latency_ms"])
            writer.writeheader()
            writer.writerows(self.events)
        print(f"\n[BENCH] 📄 Datos guardados en {OUTPUT_CSV}")
    
    def print_summary(self):
        """Imprime un resumen estadístico de la sesión."""
        print("\n" + "="*60)
        print("         📊 RESUMEN DEL BENCHMARK")
        print("="*60)
        
        # VRAM
        if self.vram_samples:
            print(f"\n  🖥️  MEMORIA VRAM:")
            print(f"     Media:   {statistics.mean(self.vram_samples):.0f} MiB")
            print(f"     Máximo:  {max(self.vram_samples)} MiB")
            print(f"     Mínimo:  {min(self.vram_samples)} MiB")
            if len(self.vram_samples) > 1:
                print(f"     Desv.:   {statistics.stdev(self.vram_samples):.1f} MiB")
        
        # Latencia de Conceptos (Emoción → Concepto LLM)
        if self.concept_latencies:
            print(f"\n  💡 LATENCIA CONCEPTO (Emoción → Tarjeta LLM):")
            print(f"     Media:   {statistics.mean(self.concept_latencies):.0f} ms ({statistics.mean(self.concept_latencies)/1000:.1f}s)")
            print(f"     Máximo:  {max(self.concept_latencies)} ms ({max(self.concept_latencies)/1000:.1f}s)")
            print(f"     Mínimo:  {min(self.concept_latencies)} ms ({min(self.concept_latencies)/1000:.1f}s)")
            print(f"     Muestras: {len(self.concept_latencies)}")
        else:
            print(f"\n  💡 LATENCIA CONCEPTO: Sin datos (no se disparó ningún concepto).")
        
        # Latencia RAG
        if self.rag_latencies:
            print(f"\n  🔍 LATENCIA RAG:")
            print(f"     Media:   {statistics.mean(self.rag_latencies):.0f} ms")
            print(f"     Máximo:  {max(self.rag_latencies)} ms")
            print(f"     Mínimo:  {min(self.rag_latencies)} ms")
            print(f"     Muestras: {len(self.rag_latencies)}")
        else:
            print(f"\n  🔍 LATENCIA RAG: Sin datos (no se realizaron consultas).")
        
        # Contadores
        n_emotions = sum(1 for e in self.events if e["event_type"] == "EMOTION")
        n_concepts = sum(1 for e in self.events if e["event_type"] == "CONCEPT")
        duration = round(time.time() - self.start_time)
        print(f"\n  📈 RESUMEN DE SESIÓN:")
        print(f"     Duración total:    {duration}s ({duration//60}m {duration%60}s)")
        print(f"     Emociones detectadas: {n_emotions}")
        print(f"     Conceptos extraídos:  {n_concepts}")
        print(f"     Muestras VRAM:        {len(self.vram_samples)}")
        print("="*60)


async def main():
    collector = BenchmarkCollector()
    
    def signal_handler(sig, frame):
        collector.running = False
    signal.signal(signal.SIGINT, signal_handler)
    
    print("="*60)
    print("  🏁 EMOTION ENGINE — BENCHMARK")
    print("  Asegúrate de que main.py está corriendo")
    print("  y que estás reproduciendo audio.")
    print("="*60)
    
    tasks = [
        asyncio.create_task(collector.monitor_vram()),
        asyncio.create_task(collector.listen_websocket()),
        asyncio.create_task(collector.rag_interactive_loop()),
    ]
    
    # Esperar a que alguien diga "salir" o Ctrl+C
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Guardar y mostrar resultados
    collector.save_csv()
    collector.print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[BENCH] Interrumpido por el usuario.")
