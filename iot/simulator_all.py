import csv, os, time, random
from datetime import datetime

# =============================
# Caminho fixo da pasta "data" que fica junto do main.py
# =============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # volta 1 nível
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATA_PATH = os.path.join(DATA_DIR, "telemetria.csv")

# =============================
# Define as 4 motos (uma por zona)
# =============================
motos = [
    {"id_moto": 1, "zona": "Nordeste"},   # em uso
    {"id_moto": 2, "zona": "Noroeste"},   # superaquecendo
    {"id_moto": 3, "zona": "Sudeste"},    # parada
    {"id_moto": 4, "zona": "Sudoeste"},   # bateria fraca
]

# =============================
# Cria cabeçalho se arquivo não existir
# =============================
if not os.path.exists(DATA_PATH):
    with open(DATA_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id_moto", "temp_c", "vib", "batt_pct", "zona", "timestamp"])

print(f"✅ Gravando telemetria consolidada em: {DATA_PATH}\n")

# =============================
# Loop principal de gravação
# =============================
while True:
    with open(DATA_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for m in motos:
            if m["zona"] == "Nordeste":  # em uso
                temp_c = random.uniform(40, 50)
                vib = random.uniform(1.0, 1.5)
                batt_pct = random.uniform(60, 100)
            elif m["zona"] == "Noroeste":  # superaquecendo
                temp_c = random.uniform(65, 85)
                vib = random.uniform(0.4, 0.8)
                batt_pct = random.uniform(50, 80)
            elif m["zona"] == "Sudoeste":  # bateria fraca
                temp_c = random.uniform(30, 40)
                vib = random.uniform(0.2, 0.6)
                batt_pct = random.uniform(5, 25)
            else:  # Sudeste - parada
                temp_c = random.uniform(30, 35)
                vib = random.uniform(0.1, 0.4)
                batt_pct = random.uniform(70, 100)

            timestamp = datetime.now().isoformat(timespec="seconds")
            writer.writerow([m["id_moto"], f"{temp_c:.2f}", f"{vib:.2f}", f"{batt_pct:.2f}", m["zona"], timestamp])

    print(f"📡 Nova linha gravada para {len(motos)} motos ({datetime.now().strftime('%H:%M:%S')})")
    time.sleep(5)
