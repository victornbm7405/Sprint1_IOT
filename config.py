import os
from dotenv import load_dotenv

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PWD  = os.getenv("ORACLE_PWD")
ORACLE_DSN  = os.getenv("ORACLE_DSN")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None

def validate_env():
    missing = [k for k,v in {
        "ORACLE_USER": ORACLE_USER,
        "ORACLE_PWD": ORACLE_PWD,
        "ORACLE_DSN": ORACLE_DSN,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
