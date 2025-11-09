# iot/simulator_base.py
import csv, os, random, time

class MotoSimulator:
    def __init__(self, id_moto: int, zona: str, mode: str):
        self.id_moto = id_moto
        self.zona = zona
        self.mode = mode
        self.csv_path = os.path.join("data", "telemetria.csv")
        if not os.path.exists("data"):
            os.makedirs("data")

    def gerar_dado(self):
        """Gera dado coerente com a zona / modo"""
        if self.mode == "em_uso":
            vib = random.uniform(1.2, 2.0)
            batt = random.uniform(60, 100)
            temp = random.uniform(35, 55)
        elif self.mode == "bateria_baixa":
            vib = random.uniform(0, 0.3)
            batt = random.uniform(5, 25)
            temp = random.uniform(30, 45)
        elif self.mode == "temperatura_alta":
            vib = random.uniform(0.3, 0.8)
            batt = random.uniform(40, 80)
            temp = random.uniform(65, 90)
        else:  # normal/parada
            vib = random.uniform(0, 0.2)
            batt = random.uniform(80, 100)
            temp = random.uniform(25, 40)

        return {
            "id_moto": self.id_moto,
            "zona": self.zona,
            "temp_c": round(temp, 2),
            "vib": round(vib, 2),
            "batt_pct": round(batt, 1),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def registrar(self, dado):
        """Grava os dados num CSV simples"""
        file_exists = os.path.exists(self.csv_path)
        with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=dado.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(dado)

    def run(self):
        """Loop contínuo para gerar telemetria"""
        print(f"🏍️ Simulador {self.id_moto} iniciado na zona {self.zona} ({self.mode})")
        while True:
            dado = self.gerar_dado()
            self.registrar(dado)
            print(dado)
            time.sleep(3)
