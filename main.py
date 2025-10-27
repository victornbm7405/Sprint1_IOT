from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
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

# -------------------------------------------------------
# Dashboard estilizado em /dashboard
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
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root{--card-bg:#fff;--text:#111827;--muted:#374151;--accent:#2563eb;--border:#e5e7eb}
    body{font-family:Arial,Helvetica,sans-serif;margin:20px;background:#f9fafb;color:var(--text)}
    h1,h2{margin:0 0 12px 0}
    h1{color:var(--accent);text-align:center}
    .card{margin:auto;padding:20px;max-width:1000px;background:var(--card-bg);border-radius:12px;box-shadow:0 4px 8px rgba(0,0,0,0.1)}
    canvas{margin-top:20px}
    /* Patio */
    #alert-center{display:none;border:1px solid #f2c46d;background:#fff9e6;color:#7a4c00;padding:12px;border-radius:8px;margin:0 0 12px 0}
    #moto-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
    .moto-card{border:1px solid var(--border);border-radius:12px;padding:12px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.05)}
    .moto-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
    .pill{padding:2px 8px;border-radius:999px;font:500 12px/1 system-ui;border:1px solid transparent}
    .pill.use{background:#e6f4ff;color:#084d86;border-color:#bfe1ff}
    .pill.stop{background:#edf7ed;color:#0b5e0b;border-color:#cfe9cf}
    .pill.maint{background:#fff2f0;color:#8a1f11;border-color:#ffd8d3}
    .muted{font:400 13px/1.5 system-ui;color:var(--muted)}
  </style>
</head>
<body>
  <div class="card">
    <h1>📊 Dashboard de Telemetria</h1>
    <canvas id="grafico"></canvas>
  </div>

  <div class="card" style="margin-top:16px">
    <h2 style="font:600 20px/1.2 system-ui">Visão do Pátio</h2>
    <div id="alert-center" aria-live="polite"></div>
    <div id="moto-grid"></div>
  </div>

  <script>
    // ==========================
    // GRÁFICO: atualiza sem recriar
    // ==========================
    let chart;
    async function fetchChart() {
      try {
        const r = await fetch('/telemetria?limit=20');
        const data = await r.json();
        const items = Array.isArray(data) ? data : (data.items || []);
        const labels = items.map((_, i) => i + 1);
        const valores = items.map(it => it.temp_c);

        const ctx = document.getElementById('grafico').getContext('2d');
        if (!chart) {
          chart = new Chart(ctx, {
            type: 'line',
            data: {
              labels: labels,
              datasets: [{
                label: 'Temperatura (°C)',
                data: valores,
                borderColor: 'rgb(37,99,235)',
                backgroundColor: 'rgba(37,99,235,0.2)',
                fill: true,
                tension: 0.25
              }]
            },
            options: {animation:false,responsive:true,maintainAspectRatio:true}
          });
        } else {
          chart.data.labels = labels;
          chart.data.datasets[0].data = valores;
          chart.update('none');
        }
      } catch (e) {
        console.warn('Falha ao atualizar gráfico:', e);
      }
    }
    fetchChart();
    setInterval(fetchChart, 5000);

    // ==========================
    // VISÃO DE PÁTIO (status+alertas)
    // ==========================
    const CANDIDATE_ENDPOINTS = [
      "/telemetria?limit=200",
      "/telemetria/ultimas?limit=200",
      "/telemetria/live?limit=200"
    ];
    const POLL_MS = 5000;
    const TH = { TEMP_ALTA: 60, BATT_BAIXA: 30, VIB_USO: 1.0 };

    function calcStatus(t) {
      if ((t.batt_pct ?? 100) < TH.BATT_BAIXA || (t.temp_c ?? 0) > TH.TEMP_ALTA) return "manutenção";
      if ((t.vib ?? 0) > TH.VIB_USO) return "em uso";
      return "parada";
    }
    function calcAlerts(t) {
      const a = [];
      if ((t.batt_pct ?? 100) < TH.BATT_BAIXA) a.push(`Bateria baixa (${t.batt_pct}%)`);
      if ((t.temp_c ?? 0) > TH.TEMP_ALTA) a.push(`Temperatura alta (${t.temp_c}°C)`);
      return a;
    }
    function fmtTs(ts) {
      try { return new Date(ts).toLocaleString(); } catch { return ts || ""; }
    }
    function pickRegion(t) {
      if (t.region) return t.region;
      const id = Number(t.id_moto || t.id || 0);
      return ["Pátio A","Pátio B","Pátio C"][id % 3];
    }
    function latestByMoto(list) {
      const map = new Map();
      for (const x of list) {
        const id = x.id_moto ?? x.id ?? x.motoId ?? x.moto_id;
        if (id == null) continue;
        const prev = map.get(id);
        const tsX = new Date(x.ts || x.timestamp || 0).getTime();
        const tsPrev = prev ? new Date(prev.ts || prev.timestamp || 0).getTime() : -1;
        if (!prev || tsX >= tsPrev) map.set(id, x);
      }
      return Array.from(map, ([id, v]) => ({ id_moto: id, ...v }));
    }
    async function fetchAny(urls) {
      for (const u of urls) {
        try {
          const r = await fetch(u);
          if (!r.ok) continue;
          const j = await r.json();
          return j;
        } catch {}
      }
      throw new Error("Nenhum endpoint de telemetria respondeu.");
    }
    function normalizeList(raw) {
      const arr = Array.isArray(raw) ? raw : (raw?.items || raw?.data || []);
      return arr.map(x => ({
        id_moto: x.id_moto ?? x.id ?? x.motoId ?? x.moto_id,
        temp_c: x.temp_c ?? x.temp ?? x.temperatura,
        vib: x.vib ?? x.vibracao ?? x.vibration,
        batt_pct: x.batt_pct ?? x.bateria ?? x.battery_pct ?? x.battery,
        ts: x.ts ?? x.timestamp ?? x.datahora ?? x.time,
        region: x.region ?? x.patio ?? x.setor
      })).filter(x => x.id_moto != null);
    }
    function statusPill(s) {
      const cls = s === "em uso" ? "pill use" : (s === "parada" ? "pill stop" : "pill maint");
      return `<span class="${cls}">${s}</span>`;
    }
    function renderCards(latest) {
      const grid = document.getElementById("moto-grid");
      grid.innerHTML = latest.map(t => {
        const s = calcStatus(t);
        const alerts = calcAlerts(t);
        const region = pickRegion(t);
        return `
          <div class="moto-card">
            <div class="moto-head">
              <div style="font:600 16px/1.2 system-ui">Moto #${t.id_moto}</div>
              ${statusPill(s)}
            </div>
            <div class="muted">
              <div><strong>Região:</strong> ${region}</div>
              <div><strong>Bateria:</strong> ${t.batt_pct ?? "—"}%</div>
              <div><strong>Temp:</strong> ${t.temp_c ?? "—"}°C</div>
              <div><strong>Vib:</strong> ${t.vib ?? "—"}</div>
              <div><strong>Atualizado:</strong> ${fmtTs(t.ts)}</div>
            </div>
            ${alerts.length ? `<div style="margin-top:8px;font:500 12px/1.5 system-ui;color:#7a1a0a">
                ${alerts.map(a => `• ${a}`).join("<br>")}
              </div>` : ``}
          </div>
        `;
      }).join("");
    }
    function renderAlertCenter(latest) {
      const allAlerts = latest.flatMap(t => calcAlerts(t).map(msg => ({ id: t.id_moto, msg })));
      const box = document.getElementById("alert-center");
      if (!allAlerts.length) {
        box.style.display = "none";
        box.innerHTML = "";
        return;
      }
      box.style.display = "block";
      box.innerHTML = `<strong>Alertas em tempo real</strong><br>${allAlerts.map(a => `Moto #${a.id}: ${a.msg}`).join("<br>")}`;
    }
    async function tickPatio() {
      try {
        const raw = await fetchAny(CANDIDATE_ENDPOINTS);
        const norm = normalizeList(raw);
        const latest = latestByMoto(norm);
        renderCards(latest);
        renderAlertCenter(latest);
      } catch (e) {
        console.warn("Falha ao atualizar visão de pátio:", e.message);
      }
    }
    tickPatio();
    setInterval(tickPatio, POLL_MS);
  </script>
</body>
</html>
    """
