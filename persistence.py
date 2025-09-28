import os, csv, time
from typing import Dict, List

# --- diretório local para persistência em arquivo ---
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# nomes dos arquivos
F_TEL = os.path.join(DATA_DIR, "telemetria.csv")
F_CMD = os.path.join(DATA_DIR, "acionamento.csv")
F_DET = os.path.join(DATA_DIR, "deteccao.csv")

# cabeçalhos fixos (garante ordem no CSV)
HDR_TEL = ["id","id_moto","temp_c","vib","batt_pct","ts"]
HDR_CMD = ["id","id_moto","kind","reason","ts"]
HDR_DET = ["id","source","label","conf","x","y","w","h","frame_id","id_moto","region","ts"]

def _now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def _append_csv(path: str, header: List[str], row: Dict):
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        w.writerow(row)

def _read_tail_csv(path: str, limit: int, header: List[str]) -> List[Dict]:
    if not os.path.exists(path):
        return []
    rows: List[Dict] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    # ordena pelo ts desc se existir
    rows.sort(key=lambda d: d.get("ts",""), reverse=True)
    return rows[:limit]

# ------- TELEMETRIA -------
def save_telemetria_db(cur, payload) -> int:
    """Tenta salvar no Oracle, retorna id gerado. Levanta exceção se falhar."""
    cur.execute("SELECT NVL(MAX(ID),0)+1 FROM T_IOT_TELEMETRIA")
    new_id = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO T_IOT_TELEMETRIA (ID, ID_MOTO, TEMP_C, VIB, BATT_PCT)
        VALUES (:id, :id_moto, :temp, :vib, :batt)
    """, dict(id=new_id, id_moto=payload.id_moto, temp=payload.temp_c, vib=payload.vib, batt=payload.batt_pct))
    return new_id

def save_telemetria_file(payload) -> int:
    """Persistência em arquivo (CSV). Gera id incremental local simples."""
    next_id = 1
    if os.path.exists(F_TEL):
        with open(F_TEL, "r", encoding="utf-8") as f:
            next_id = sum(1 for _ in f)  # inclui header
    row = {
        "id": next_id,
        "id_moto": payload.id_moto,
        "temp_c": payload.temp_c,
        "vib": payload.vib,
        "batt_pct": payload.batt_pct,
        "ts": _now_str(),
    }
    _append_csv(F_TEL, HDR_TEL, row)
    return next_id

def list_telemetria_db(cur, limit: int):
    cur.execute("""
        SELECT ID, ID_MOTO, TEMP_C, VIB, BATT_PCT, TO_CHAR(TS,'YYYY-MM-DD HH24:MI:SS')
        FROM T_IOT_TELEMETRIA
        ORDER BY TS DESC
        FETCH FIRST :lim ROWS ONLY
    """, dict(lim=limit))
    return [
        {"id": r[0], "id_moto": r[1], "temp_c": r[2], "vib": r[3], "batt_pct": r[4], "ts": r[5]}
        for r in cur.fetchall()
    ]

def list_telemetria_file(limit: int):
    return _read_tail_csv(F_TEL, limit, HDR_TEL)

# ------- COMANDOS -------
def save_command_db(cur, payload) -> int:
    cur.execute("SELECT NVL(MAX(ID),0)+1 FROM T_IOT_ACIONAMENTO")
    new_id = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO T_IOT_ACIONAMENTO (ID, ID_MOTO, KIND, REASON)
        VALUES (:id, :id_moto, :kind, :reason)
    """, dict(id=new_id, id_moto=payload.id_moto, kind=payload.kind, reason=payload.reason))
    return new_id

def save_command_file(payload) -> int:
    next_id = 1
    if os.path.exists(F_CMD):
        with open(F_CMD, "r", encoding="utf-8") as f:
            next_id = sum(1 for _ in f)
    row = {
        "id": next_id,
        "id_moto": payload.id_moto,
        "kind": payload.kind,
        "reason": payload.reason or "",
        "ts": _now_str(),
    }
    _append_csv(F_CMD, HDR_CMD, row)
    return next_id

# ------- DETECÇÕES -------
def save_detection_db(cur, payload) -> int:
    cur.execute("SELECT NVL(MAX(ID),0)+1 FROM T_IOT_DETECCAO")
    new_id = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO T_IOT_DETECCAO
          (ID, SOURCE, LABEL, CONF, X, Y, W, H, FRAME_ID, ID_MOTO, REGION)
        VALUES
          (:id, :source, :label, :conf, :x, :y, :w, :h, :frame_id, :id_moto, :region)
    """, {
        "id": new_id,
        "source": payload.source,
        "label": payload.label,
        "conf": payload.conf,
        "x": payload.x, "y": payload.y, "w": payload.w, "h": payload.h,
        "frame_id": payload.frame_id,
        "id_moto": payload.id_moto,
        "region": payload.region
    })
    return new_id

def save_detection_file(payload) -> int:
    next_id = 1
    if os.path.exists(F_DET):
        with open(F_DET, "r", encoding="utf-8") as f:
            next_id = sum(1 for _ in f)
    row = {
        "id": next_id,
        "source": payload.source,
        "label": payload.label,
        "conf": payload.conf,
        "x": payload.x, "y": payload.y, "w": payload.w, "h": payload.h,
        "frame_id": payload.frame_id if payload.frame_id is not None else "",
        "id_moto": payload.id_moto if payload.id_moto is not None else "",
        "region": payload.region or "",
        "ts": _now_str(),
    }
    _append_csv(F_DET, HDR_DET, row)
    return next_id
