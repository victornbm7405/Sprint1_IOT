import json
import threading
import paho.mqtt.client as mqtt
import cx_Oracle

from config import (
    ORACLE_USER, ORACLE_PWD, ORACLE_DSN,
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD
)

# Helpers com fallback Oracle → CSV
from persistence import (
    save_telemetria_db, save_telemetria_file,
    save_command_db, save_command_file
)

TOPIC_TEL = "mottu/motos/+/telemetry"
TOPIC_CMD = "mottu/motos/+/commands"

def _connect_db():
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PWD, dsn=ORACLE_DSN)

def on_connect(client, userdata, flags, reason_code, properties=None):
    print("MQTT conectado:", reason_code)
    client.subscribe(TOPIC_TEL)
    client.subscribe(TOPIC_CMD)

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except Exception as e:
        print("Payload inválido:", e, msg.payload[:200])
        return

    try:
        if "telemetry" in topic:
            class T:
                id_moto=int(data["id_moto"]); temp_c=float(data["temp_c"]); vib=float(data["vib"]); batt_pct=float(data["batt_pct"])
            try:
                conn=_connect_db(); cur=conn.cursor()
                new_id=save_telemetria_db(cur, T); conn.commit(); cur.close(); conn.close()
                print("✓ (oracle) telemetria:", data)
            except Exception as e_db:
                save_telemetria_file(T)
                print("✓ (file) telemetria:", data, "| motivo oracle:", e_db)

        elif "commands" in topic:
            class C:
                id_moto=int(data["id_moto"]); kind=str(data.get("kind","unknown")); reason=data.get("reason")
            try:
                conn=_connect_db(); cur=conn.cursor()
                new_id=save_command_db(cur, C); conn.commit(); cur.close(); conn.close()
                print("✓ (oracle) comando:", data)
            except Exception as e_db:
                save_command_file(C)
                print("✓ (file) comando:", data, "| motivo oracle:", e_db)

    except Exception as e:
        print("✗ Erro no subscriber:", e)

def run_background():
    client = mqtt.Client()
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, int(MQTT_PORT), 60)
    th = threading.Thread(target=client.loop_forever, daemon=True)
    th.start()
    return client, th
