from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import os
import csv
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
# Habilitar CORS para Swagger e outros clientes
# -------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # permite todas as origens
    allow_credentials=True,
    allow_methods=["*"],   # permite todos os métodos (GET, POST, PUT, DELETE)
    allow_headers=["*"],   # permite todos os headers
)

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
# Sprint 3 — Comandos / Atuadores (T_IOT_ACIONAMENTO) com fallback + MQTT
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

    # Publicar comando via MQTT
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
# Inicia o subscriber MQTT em background
# -------------------------------------------------------
try:
    if not getattr(app.state, "_mqtt_started", False):
        from services.mqtt_subscriber import run_background
        run_background()
        app.state._mqtt_started = True
        print("MQTT subscriber iniciado.")
except Exception as e:
    print("MQTT indisponível:", e)

# =======================================================
# NOVO DASHBOARD – 4 ZONAS CARDEAIS (USANDO telemetria.csv do simulador)
# =======================================================

# Carrega CSV do simulador (mesma lógica do main novo)
def carregar_motos():
    possible_paths = [
        os.path.join("data", "telemetria.csv"),
        os.path.join(os.getcwd(), "data", "telemetria.csv"),
        os.path.join(os.getcwd(), "Sprint1_IOT-main", "data", "telemetria.csv"),
    ]
    csv_path = next((p for p in possible_paths if os.path.exists(p)), None)

    if not csv_path:
        print("❌ Nenhum arquivo de telemetria encontrado.")
        return []

    motos = {}
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    idm = int(row.get("id_moto", 0))
                    motos[idm] = {
                        "id_moto": idm,
                        "temp_c": float(row.get("temp_c", 0)),
                        "vib": float(row.get("vib", 0)),
                        "batt_pct": float(row.get("batt_pct", 0)),
                        "zona": row.get("zona", "Desconhecida"),
                        "timestamp": row.get("timestamp", ""),
                    }
                except Exception as e:
                    print("⚠️ Linha inválida no CSV:", e)
        print(f"✅ {len(motos)} motos carregadas de {csv_path}")
        return list(motos.values())
    except Exception as e:
        print("❌ Erro ao ler CSV:", e)
        return []

def statusPill(v):
    batt = float(v.get("batt_pct", 100))
    temp = float(v.get("temp_c", 25))
    vib = float(v.get("vib", 0))
    if batt < 25 or temp > 60:
        return '<span class="pill maint">manutenção</span>'
    if vib > 1.0:
        return '<span class="pill use">em uso</span>'
    return '<span class="pill stop">parada</span>'

def cards_zona(zona, motos):
    cards = []
    for v in motos:
        if v.get("zona", "").lower() == zona.lower():
            cards.append(f"""
            <div class="moto-card" onclick="mostrarDetalhes({v['id_moto']})">
                <div class="moto-head">
                    <div style="font:600 16px/1.2 system-ui">Moto #{v['id_moto']}</div>
                    {statusPill(v)}
                </div>
                <div class="muted">
                    <div><strong>Zona:</strong> {v['zona']}</div>
                    <div><strong>Bateria:</strong> {v['batt_pct']}%</div>
                    <div><strong>Temp:</strong> {v['temp_c']}°C</div>
                    <div><strong>Vib:</strong> {v['vib']}</div>
                    <div><strong>Atualização:</strong> {v['timestamp']}</div>
                </div>
            </div>
            """)
    return "\n".join(cards)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    motos = carregar_motos()

    if not motos:
        return """
        <h1 style='text-align:center;margin-top:40px;color:#444'>
        ⚠️ Nenhum dado encontrado no arquivo CSV.<br>
        Verifique se o simulador está rodando e gerando <b>data/telemetria.csv</b>.
        </h1>
        """

    total = len(motos)

    return f"""
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8"/>
<title>🏍️ Mapa IoT - 4 Zonas Cardeais</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root {{
    --card-bg:#fff;--text:#111827;--muted:#374151;--accent:#2563eb;--border:#e5e7eb;
  }}
  body {{
    font-family:Arial,Helvetica,sans-serif;margin:0;background:#f9fafb;color:var(--text);
  }}
  h1 {{
    background:var(--accent);color:white;padding:16px;text-align:center;margin:0;
  }}
  #info-bar {{
    text-align:center;
    background:#eef3ff;
    padding:8px;
    color:#333;
    font-weight:500;
  }}
  #mapa {{
    display:grid;
    grid-template-columns:1fr 1fr;
    grid-template-rows:1fr 1fr;
    height:85vh;
    border-top:2px solid var(--border);
    border-left:2px solid var(--border);
  }}
  .zona {{
    border-right:2px solid var(--border);
    border-bottom:2px solid var(--border);
    padding:12px;
    position:relative;
    overflow:auto;
  }}
  .zona h2 {{
    position:absolute;top:8px;left:12px;font-size:16px;color:#2563eb;margin:0;
  }}
  .zona-grid {{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
    gap:12px;
    margin-top:30px;
  }}
  .moto-card {{
    border:1px solid var(--border);
    border-radius:12px;
    padding:12px;
    background:var(--card-bg);
    box-shadow:0 1px 2px rgba(0,0,0,.05);
    cursor:pointer;
    transition:transform .15s;
  }}
  .moto-card:hover {{transform:scale(1.03);}}
  .moto-head {{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}}
  .pill {{
    padding:2px 8px;border-radius:999px;font:500 12px/1 system-ui;border:1px solid transparent;
  }}
  .pill.use{{background:#e6f4ff;color:#084d86;border-color:#bfe1ff}}
  .pill.stop{{background:#edf7ed;color:#0b5e0b;border-color:#cfe9cf}}
  .pill.maint{{background:#fff2f0;color:#8a1f11;border-color:#ffd8d3}}
  .muted{{font:400 13px/1.5 system-ui;color:var(--muted)}}
  #painel {{
    position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);
    display:none;align-items:center;justify-content:center;
  }}
  #painel .conteudo {{
    background:white;padding:20px;border-radius:12px;width:90%;max-width:500px;
    box-shadow:0 6px 16px rgba(0,0,0,0.3);
  }}
  #painel button {{
    background:var(--accent);border:none;color:white;padding:8px 16px;border-radius:8px;cursor:pointer;
  }}
</style>
</head>
<body>
<h1>📍 Pátio das Motos – 4 Zonas Cardeais</h1>
<div id="info-bar">🚀 {total} motos carregadas do simulador – atualização automática a cada 10s</div>

<div id="mapa">
  <div class="zona"><h2>Noroeste</h2><div class="zona-grid">{cards_zona("Noroeste", motos)}</div></div>
  <div class="zona"><h2>Nordeste</h2><div class="zona-grid">{cards_zona("Nordeste", motos)}</div></div>
  <div class="zona"><h2>Sudoeste</h2><div class="zona-grid">{cards_zona("Sudoeste", motos)}</div></div>
  <div class="zona"><h2>Sudeste</h2><div class="zona-grid">{cards_zona("Sudeste", motos)}</div></div>
</div>

<div id="painel">
  <div class="conteudo">
    <h2 id="tituloMoto">Detalhes da Moto</h2>
    <p id="textoExplicacao"></p>
    <button onclick="fecharPainel()">Fechar</button>
  </div>
</div>

<script>
const motos = {json.dumps(motos, ensure_ascii=False)};
function mostrarDetalhes(id) {{
  const m = motos.find(x => x.id_moto === id);
  if (!m) return;
  const painel = document.getElementById("painel");
  const titulo = document.getElementById("tituloMoto");
  const texto = document.getElementById("textoExplicacao");
  titulo.innerText = "Moto #" + m.id_moto + " – Zona " + m.zona;
  let explicacao = "";
  if (m.batt_pct < 25) {{
    explicacao += "⚠️ <b>Bateria crítica</b>: abaixo de 25%. Recolher para recarga.<br><br>";
  }}
  if (m.temp_c > 65) {{
    explicacao += "🔥 <b>Alta temperatura</b>: possível superaquecimento.<br><br>";
  }}
  if (m.vib > 1.0) {{
    explicacao += "🏍️ <b>Moto em uso</b>: vibração alta detectada.<br><br>";
  }}
  if (!explicacao) {{
    explicacao = "✅ Moto em boas condições.";
  }}
  texto.innerHTML = explicacao;
  painel.style.display = "flex";
}}
function fecharPainel() {{
  document.getElementById("painel").style.display = "none";
}}
setTimeout(() => location.reload(), 10000);
</script>
</body>
</html>
"""

@app.get("/")
def root():
    return {"status": "ok", "msg": "acesse /dashboard para ver o mapa das motos"}
