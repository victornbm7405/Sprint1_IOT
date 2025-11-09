from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os, csv, json

app = FastAPI(title="Mapa IoT – Motos (Dashboard com CSV vivo)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# Carregar CSV do simulador
# =====================================================
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


# =====================================================
# Renderiza os cards
# =====================================================
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


# =====================================================
# Dashboard
# =====================================================
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
