from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import cx_Oracle
import cv2
from pyzbar.pyzbar import decode
import json

app = FastAPI()

# 📦 Conexão com o Oracle
dsn = cx_Oracle.makedsn("oracle.fiap.com.br", 1521, service_name="ORCL")
connection = cx_Oracle.connect(user="rm554557", password="Fiap25", dsn=dsn)


# 📄 Modelo de dados
class Moto(BaseModel):
    id: int
    placa: str
    modelo: str
    area: int


# 🚀 GET - Listar motos
@app.get("/motos", response_model=List[Moto])
def listar_motos():
    cursor = connection.cursor()
    cursor.execute("SELECT ID_MOTO, DS_PLACA, NM_MODELO, ID_AREA FROM T_MOTTU_MOTO")
    motos = []
    for id_moto, placa, modelo, area in cursor.fetchall():
        motos.append(Moto(id=id_moto, placa=placa, modelo=modelo, area=area))
    cursor.close()
    return motos


# 🚀 POST - Cadastrar moto via QR Code com JSON
@app.post("/motos/qrcode", response_model=Moto)
def cadastrar_moto_qrcode():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="❌ Não foi possível acessar a câmera")

    dados_lidos = None

    while True:
        ret, frame = cap.read()

        if not ret:
            continue

        for codigo in decode(frame):
            dados_lidos = codigo.data.decode('utf-8')
            cv2.imshow("QR Code Detectado - Fechando...", frame)
            cv2.waitKey(1000)
            cap.release()
            cv2.destroyAllWindows()
            break

        cv2.imshow('Leitor de QR Code', frame)

        if dados_lidos:
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
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

    cursor = connection.cursor()
    cursor.execute("SELECT NVL(MAX(ID_MOTO), 0) + 1 FROM T_MOTTU_MOTO")
    id_moto = cursor.fetchone()[0]

    try:
        cursor.execute(
            "INSERT INTO T_MOTTU_MOTO (ID_MOTO, DS_PLACA, NM_MODELO, ID_AREA) VALUES (:id, :placa, :modelo, :area)",
            {"id": id_moto, "placa": placa, "modelo": modelo, "area": area}
        )
        connection.commit()
    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()

    return Moto(id=id_moto, placa=placa, modelo=modelo, area=area)


# 🚀 PUT - Atualizar moto
@app.put("/motos/{id}", response_model=Moto)
def atualizar_moto(id: int, moto: Moto):
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM T_MOTTU_MOTO WHERE ID_MOTO = :id", {"id": id})
    if cursor.fetchone() is None:
        cursor.close()
        raise HTTPException(status_code=404, detail="Moto não encontrada")

    try:
        cursor.execute(
            "UPDATE T_MOTTU_MOTO SET DS_PLACA = :placa, NM_MODELO = :modelo, ID_AREA = :area WHERE ID_MOTO = :id",
            {"placa": moto.placa, "modelo": moto.modelo, "area": moto.area, "id": id}
        )
        connection.commit()
    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()

    return moto


# 🚀 DELETE - Remover moto
@app.delete("/motos/{id}")
def deletar_moto(id: int):
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM T_MOTTU_MOTO WHERE ID_MOTO = :id", {"id": id})
    if cursor.fetchone() is None:
        cursor.close()
        raise HTTPException(status_code=404, detail="Moto não encontrada")

    try:
        cursor.execute("DELETE FROM T_MOTTU_MOTO WHERE ID_MOTO = :id", {"id": id})
        connection.commit()
    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()

    return {"detail": "Moto deletada com sucesso"}
