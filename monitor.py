import time
import subprocess
import csv
import datetime
import os

def get_vram():
    try:
        # Obtiene solo el valor numérico de la VRAM usada en MiB
        result = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,nounits,noheader'],
            encoding='utf-8'
        )
        # Por si hay varias GPUs, cogemos la primera
        return int(result.strip().split('\n')[0])
    except Exception as e:
        print(f"Error leyendo nvidia-smi: {e}")
        return 0

def main():
    csv_file = "vram_log.csv"
    print(f"[MONITOR] Iniciando registro de VRAM cada 2 segundos en {csv_file}...")
    
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "VRAM_MiB"])
        
        try:
            while True:
                vram = get_vram()
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([now, vram])
                file.flush()  # Forzar escritura a disco
                print(f"[{now}] VRAM Usada: {vram} MiB", end='\r')
                time.sleep(2)
        except KeyboardInterrupt:
            print(f"\n[MONITOR] Detenido. Datos guardados con éxito en {csv_file}")

if __name__ == "__main__":
    main()
