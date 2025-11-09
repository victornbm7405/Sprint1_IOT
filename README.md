# 🚀 Sprint 4 Telemetria

---

## 📖 Proposta do Projeto
Este projeto foi desenvolvido como parte da disciplina **Disruptive Architectures: IoT, IoB & Generative AI**.  
A proposta é criar uma infraestrutura IoT para **gerenciamento de motos**, com **leitura de QR Code**, **telemetria em tempo real** e **dashboard interativo**.

O sistema é composto por:
- **Simuladores IoT** → publicam dados de telemetria (temperatura, vibração, bateria).  
- **Subscriber MQTT** → recebe os dados e armazena no banco Oracle ou em CSV (fallback).  
- **API REST (FastAPI)** → expõe endpoints para consulta, CRUD de motos/áreas, comandos e detecções.  
- **Dashboard Web** → exibe dados de telemetria em tempo real (gráfico interativo com Chart.js).  

---

## 📂 Estrutura do Projeto
```
Sprint1_IOT-main/
│── main.py              # API principal (FastAPI + Dashboard)
│── config.py            # Configurações (.env → Oracle/MQTT)
│── persistence.py       # Persistência (Oracle → CSV fallback)
│── leitor_qrcode.py     # Leitura de QR Code com OpenCV
│── teste_conexao.py     # Teste de conexão ao Oracle
│── requirements.txt     # Dependências do projeto
│── .env / .env.example  # Variáveis de ambiente
│
├── services/
│   └── mqtt_subscriber.py   # Subscriber MQTT
│
├── iot/
│   ├── simulator_base.py        # Simulador IoT (telemetria)
│   ├── simulator_all.py
│   
│
├── data/                # CSVs de fallback
│   ├── telemetria.csv
│   ├── acionamento.csv
│   └── deteccao.csv
```

---

## 🛠️ Tecnologias Utilizadas
- **Python 3.10+**
- **FastAPI** (framework backend / API REST)
- **Uvicorn** (servidor ASGI)
- **Pydantic** (validação de dados)
- **OpenCV + pyzbar** (leitura de QR Codes)
- **paho-mqtt** (comunicação MQTT)
- **cx_Oracle** (integração com banco Oracle)
- **Chart.js** (gráficos no dashboard web)
- **CSV** (fallback de persistência local)

---

## ⚙️ Passo a Passo para Rodar

### 1) Clonar repositório
```powershell
git clone https://github.com/SEU-USUARIO/SEU-REPO.git
cd Sprint1_IOT-main
```

### 2) Criar ambiente virtual e instalar dependências
```powershell
pip install -r requirements.txt
```

### 3) Configurar variáveis de ambiente
Copiar o arquivo `.env.example` para `.env` e preencher as variáveis do Oracle/MQTT:
```powershell
copy .env.example .env
```

### 4) Rodar o subscriber MQTT
```powershell
python -m services.mqtt_subscriber
```

### 5) Rodar os simuladores IoT
Em 1 terminal diferente:
```powershell
python iot/simulator_all.py

```

### 6) Rodar a API principal
```powershell
uvicorn main:app --reload
```

### 7) Acessar no navegador
- Swagger Docs → http://127.0.0.1:8000/docs  
- Dashboard → http://127.0.0.1:8000/dashboard  

---

## Exemplo de JSONS

-Endpoint: POST /deteccoes
{
  "source": "yolo",
  "label": "capacete",
  "conf": 0.95,
  "x": 100,
  "y": 150,
  "w": 80,
  "h": 80,
  "frame_id": 12,
  "id_moto": 1,
  "region": "Zona Norte"
}

Endpoint: POST /commands
{
  "id_moto": 1,
  "kind": "lock",
  "reason": "Trava de segurança acionada remotamente"
}



## 📊 Resultados Parciais
- Os simuladores publicam telemetria em tópicos MQTT.  
- O subscriber recebe e persiste os dados em **Oracle** (quando disponível) ou em **CSVs** de fallback:  
  - `data/telemetria.csv` → leituras de sensores  
  - `data/acionamento.csv` → comandos  
  - `data/deteccao.csv` → eventos de visão computacional  
- O dashboard exibe gráficos interativos de temperatura em tempo real.  
- O Swagger permite testar endpoints para CRUD, telemetria, comandos e detecções.

---

## 👨‍💻 Integrantes

Desenvolvido por: 
RM 556293 Alice Teixeira Caldeira 
RM 555708 Gustavo Goulart 
RM 554557 Victor Medeiros
