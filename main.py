from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import cx_Oracle
import cv2
from pyzbar.pyzbar import decode

# --- .env / configuração segura ---
from config import (
    ORACLE_USER, ORACLE_PWD, ORACLE_DSN, validate_env,
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD
)
validate_env()

# --- Persistência com fallback (Oracle → CSV) ---
from persistence import (
    save_telemetria_db, save_telemetria_file, list_telemetria_db, list_telemetria_file,
    save_command_db, save_command_file, save_detection_db, save_detection_file
)

app = FastAPI(title="IOT + QR + Telemetria (Sprint 3)")


# -------------------------------------------------------
# Utilitário de conexão por requisição
# -------------------------------------------------------
def get_connection():
    """Abre uma conexão nova com Oracle usando variáveis do .env."""
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PWD, dsn=ORACLE_DSN)


# -------------------------------------------------------
# Modelos existentes (tabelas T_IOT_*)
# -------------------------------------------------------
class Moto(BaseModel):
    id: int
    placa: str
    modelo: str
    area: int


class Area(BaseModel):
    id: int
    nome: str


# -------------------------------------------------------
# Sprint 3 — Modelos IoT adicionais
# -------------------------------------------------------
class TelemetryIn(BaseModel):
    id_moto: int = Field(..., ge=1)
    temp_c: float
    vib: float
    batt_pct: float


class CommandIn(BaseModel):
    id_moto: int = Field(..., ge=1)
    kind: str  # lock, unlock, horn, led_on, led_off
    reason: Optional[str] = None


class DetectionIn(BaseModel):
    source: str  # yolo, aruco, qr, etc.
    label: str
    conf: float
    x: int
    y: int
    w: int
    h: int
    frame_id: Optional[int] = None
    id_moto: Optional[int] = None
    region: Optional[str] = None


# -------------------------------------------------------
# CRUD — MOTOS (T_IOT_MOTO)
# -------------------------------------------------------
@app.get("/motos", response_model=List[Moto])
def listar_motos():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ID_MOTO, DS_PLACA, NM_MODELO, ID_AREA FROM T_IOT_MOTO")
        motos = [Moto(id=r[0], placa=r[1], modelo=r[2], area=r[3]) for r in cur.fetchall()]
        cur.close(); conn.close()
        return motos
    except Exception as e:
        print(f"❌ Erro no GET de motos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/motos/qrcode", response_model=Moto)
def cadastrar_moto_qrcode():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="❌ Não foi possível acessar a câmera")

    dados_lidos = None
    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        for codigo in decode(frame):
            dados_lidos = codigo.data.decode("utf-8")
            cv2.imshow("QR Code Detectado - Fechando...", frame)
            cv2.waitKey(1000)
            cap.release()
            cv2.destroyAllWindows()
            break

        cv2.imshow("Leitor de QR Code", frame)

        if dados_lidos:
            break

        if cv2.waitKey(1) & 0xFF == ord("q"):
            cap.release()
            cv2.destroyAllWindows()
            raise HTTPException(status_code=400, detail="❌ Leitura cancelada")

    try:
        dados = json.loads(dados_lidos)
        placa = dados["placa"]
        modelo = dados["modelo"]
        area = dados["area"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"❌ QR Code inválido ou mal formatado: {e}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT NVL(MAX(ID_MOTO), 0) + 1 FROM T_IOT_MOTO")
        id_moto = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO T_IOT_MOTO (ID_MOTO, DS_PLACA, NM_MODELO, ID_AREA)
            VALUES (:id, :placa, :modelo, :area)
            """,
            {"id": id_moto, "placa": placa, "modelo": modelo, "area": area},
        )
        conn.commit()
        return Moto(id=id_moto, placa=placa, modelo=modelo, area=area)
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro no POST de moto: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close(); conn.close()


@app.put("/motos/{id}", response_model=Moto)
def atualizar_moto(id: int, moto: Moto):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM T_IOT_MOTO WHERE ID_MOTO = :id", {"id": id})
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Moto não encontrada")

        cur.execute(
            """
            UPDATE T_IOT_MOTO
               SET DS_PLACA = :placa,
                   NM_MODELO = :modelo,
                   ID_AREA   = :area
             WHERE ID_MOTO  = :id
            """,
            {"placa": moto.placa, "modelo": moto.modelo, "area": moto.area, "id": id},
        )
        conn.commit()
        return moto
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro no PUT de moto: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close(); conn.close()


@app.delete("/motos/{id}")
def deletar_moto(id: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM T_IOT_MOTO WHERE ID_MOTO = :id", {"id": id})
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Moto não encontrada")

        cur.execute("DELETE FROM T_IOT_MOTO WHERE ID_MOTO = :id", {"id": id})
        conn.commit()
        return {"detail": "Moto deletada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro no DELETE de moto: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close(); conn.close()


# -------------------------------------------------------
# CRUD — ÁREAS (T_IOT_AREA)
# -------------------------------------------------------
@app.get("/areas", response_model=List[Area])
def listar_areas():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT ID_AREA, NM_AREA FROM T_IOT_AREA")
        areas = [Area(id=r[0], nome=r[1]) for r in cur.fetchall()]
        cur.close(); conn.close()
        return areas
    except Exception as e:
        print(f"❌ Erro no GET de áreas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/areas", response_model=Area)
def cadastrar_area(area: Area):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM T_IOT_AREA WHERE ID_AREA = :id", {"id": area.id})
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Área já existe com esse ID")

        cur.execute(
            "INSERT INTO T_IOT_AREA (ID_AREA, NM_AREA) VALUES (:id, :nome)",
            {"id": area.id, "nome": area.nome},
        )
        conn.commit()
        return area
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro no POST de área: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close(); conn.close()


@app.put("/areas/{id}", response_model=Area)
def atualizar_area(id: int, area: Area):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM T_IOT_AREA WHERE ID_AREA = :id", {"id": id})
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Área não encontrada")

        cur.execute(
            "UPDATE T_IOT_AREA SET NM_AREA = :nome WHERE ID_AREA = :id",
            {"nome": area.nome, "id": id},
        )
        conn.commit()
        return area
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro no PUT de área: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close(); conn.close()


@app.delete("/areas/{id}")
def deletar_area(id: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM T_IOT_AREA WHERE ID_AREA = :id", {"id": id})
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="Área não encontrada")

        cur.execute("DELETE FROM T_IOT_AREA WHERE ID_AREA = :id", {"id": id})
        conn.commit()
        return {"detail": "Área deletada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro no DELETE de área: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close(); conn.close()


# -------------------------------------------------------
# Sprint 3 — Telemetria (T_IOT_TELEMETRIA) com fallback
# -------------------------------------------------------
@app.post("/telemetria", status_code=201)
def publicar_telemetria(payload: TelemetryIn):
    # tenta Oracle; se falhar (ex.: ORA-28000), grava em CSV
    try:
        conn = get_connection()
        cur = conn.cursor()
        new_id = save_telemetria_db(cur, payload)
        conn.commit()
        cur.close(); conn.close()
        return {"id": new_id, "ok": True, "backend": "oracle"}
    except Exception as e:
        print("POST /telemetria: fallback para arquivo ->", e)
        new_id = save_telemetria_file(payload)
        return {"id": new_id, "ok": True, "backend": "file"}


@app.get("/telemetria")
def listar_telemetria(limit: int = 50):
    try:
        conn = get_connection()
        cur = conn.cursor()
        rows = list_telemetria_db(cur, limit)
        cur.close(); conn.close()
        return {"backend": "oracle", "items": rows}
    except Exception as e:
        print("GET /telemetria: lendo de arquivo ->", e)
        return {"backend": "file", "items": list_telemetria_file(limit)}


# -------------------------------------------------------
# Sprint 3 — Comandos / Atuadores (T_IOT_ACIONAMENTO) com fallback
# -------------------------------------------------------
@app.post("/commands", status_code=201)
def acionar(payload: CommandIn):
    used_backend = "oracle"
    try:
        conn = get_connection()
        cur = conn.cursor()
        new_id = save_command_db(cur, payload)
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        print("POST /commands: fallback para arquivo ->", e)
        new_id = save_command_file(payload)
        used_backend = "file"

    # Publica também no MQTT para os simuladores/atuadores
    try:
        import paho.mqtt.client as mqtt
        client = mqtt.Client()
        if MQTT_USERNAME and MQTT_PASSWORD:
            client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        client.connect(MQTT_BROKER, int(MQTT_PORT), 60)
        topic = f"mottu/motos/{payload.id_moto}/commands"
        client.publish(topic, json.dumps({
            "id_moto": payload.id_moto,
            "kind": payload.kind,
            "reason": payload.reason
        }))
        client.disconnect()
    except Exception as pub_err:
        print("Aviso: falha ao publicar comando MQTT:", pub_err)

    return {"id": new_id, "ok": True, "backend": used_backend}


# -------------------------------------------------------
# Sprint 3 — Detecções de Visão (T_IOT_DETECCAO) com fallback
# -------------------------------------------------------
@app.post("/deteccoes", status_code=201)
def registrar_deteccao(payload: DetectionIn):
    try:
        conn = get_connection()
        cur = conn.cursor()
        new_id = save_detection_db(cur, payload)
        conn.commit()
        cur.close(); conn.close()
        return {"id": new_id, "ok": True, "backend": "oracle"}
    except Exception as e:
        print("POST /deteccoes: fallback para arquivo ->", e)
        new_id = save_detection_file(payload)
        return {"id": new_id, "ok": True, "backend": "file"}


# -------------------------------------------------------
# Inicia o subscriber MQTT em background (uma única vez)
# -------------------------------------------------------
try:
    if not getattr(app.state, "_mqtt_started", False):
        from services.mqtt_subscriber import run_background
        run_background()
        app.state._mqtt_started = True
        print("MQTT subscriber iniciado.")
except Exception as e:
    print("MQTT indisponível:", e)


# -------------------------------------------------------
# Dashboard simples (HTML) em /dashboard
# -------------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <title>Dashboard – Telemetria</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;margin:24px;}
    h1{margin:0 0 8px}
    .badge{display:inline-block;padding:4px 8px;border-radius:8px;background:#eee;margin-left:8px;font-size:12px}
    table{border-collapse:collapse;width:100%;margin-top:12px}
    th,td{border:1px solid #ddd;padding:8px;font-size:14px}
    th{background:#f8f8f8;text-align:left}
    .err{color:#c00}
  </style>
</head>
<body>
  <h1>Telemetria <span id="backend" class="badge">—</span></h1>
  <div id="meta" style="margin:6px 0 14px;color:#666;font-size:13px">atualizando...</div>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Moto</th><th>Temp (°C)</th><th>Vib</th><th>Bateria (%)</th><th>Timestamp</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <script>
    async function fetchData(){
      try{
        const r = await fetch('/telemetria?limit=20');
        const data = await r.json();
        document.getElementById('backend').textContent = 'backend: ' + (data.backend || '?');
        const tb = document.getElementById('tbody');
        tb.innerHTML = '';
        (data.items || []).forEach(it => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${it.id}</td>
            <td>${it.id_moto}</td>
            <td>${(+it.temp_c).toFixed(2)}</td>
            <td>${(+it.vib).toFixed(3)}</td>
            <td>${(+it.batt_pct).toFixed(1)}</td>
            <td>${it.ts || ''}</td>`;
          tb.appendChild(tr);
        });
        document.getElementById('meta').textContent = 'Leituras: ' + (data.items?.length || 0) + ' • ' + new Date().toLocaleTimeString();
      }catch(e){
        document.getElementById('meta').innerHTML = '<span class="err">erro ao carregar</span>';
      }
    }
    fetchData();
    setInterval(fetchData, 2000);
  </script>
</body>
</html>
    """
