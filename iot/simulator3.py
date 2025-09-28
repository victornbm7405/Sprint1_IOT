import os, time, json, random, threading
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT   = int(os.getenv("MQTT_PORT", "1883"))
MOTO_ID = 3

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        print(f"[sim{MOTO_ID}] comando recebido:", data)
    except Exception as e:
        print(f"[sim{MOTO_ID}] comando inválido:", e)

def publisher_loop():
    client = mqtt.Client(client_id=f"sim{MOTO_ID}")
    client.connect(BROKER, PORT, 60)
    while True:
        payload = {
            "id_moto": MOTO_ID,
            "temp_c": round(random.uniform(25, 55), 2),
            "vib": round(random.uniform(0.1, 4.0), 2),
            "batt_pct": round(random.uniform(30, 100), 1)
        }
        client.publish(f"mottu/motos/{MOTO_ID}/telemetry", json.dumps(payload))
        print(f"[sim{MOTO_ID}] publicou telemetria:", payload)
        time.sleep(1.8)

def main():
    client = mqtt.Client(client_id=f"sim{MOTO_ID}-sub")
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.subscribe(f"mottu/motos/{MOTO_ID}/commands")

    th = threading.Thread(target=publisher_loop, daemon=True)
    th.start()
    client.loop_forever()

if __name__ == "__main__":
    main()
