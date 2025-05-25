
# API de Gestão de Motos com QR Code — Projeto IOT

CRUD completo de Motos e Áreas com conexão ao banco Oracle.

- Cadastro de motos via leitura de QR Code com dados em JSON.
- As motos são vinculadas a uma área (ex.: Norte, Sul, Leste...).
- Gerenciamento completo de Motos.
- Gerenciamento completo de Áreas.

## Tecnologias
- Python + FastAPI
- Banco de Dados Oracle
- OpenCV + Pyzbar (Leitor de QR Code)
- Uvicorn (Servidor ASGI)

## Banco de Dados

### Tabelas:

### T_IOT_AREA
| Campo    | Tipo       | Descrição     |
|----------|------------|----------------|
| ID_AREA  | NUMBER (PK)| ID da área     |
| NM_AREA  | VARCHAR2   | Nome da área   |

### T_IOT_MOTO
| Campo     | Tipo        | Descrição                       |
|-----------|-------------|----------------------------------|
| ID_MOTO   | NUMBER (PK) | ID da moto                      |
| DS_PLACA  | VARCHAR2    | Placa da moto                   |
| NM_MODELO | VARCHAR2    | Modelo da moto                  |
| ID_AREA   | NUMBER (FK) | Área relacionada (T_IOT_AREA)   |

## Criação das tabelas
```sql
CREATE TABLE T_IOT_AREA (
    ID_AREA NUMBER PRIMARY KEY,
    NM_AREA VARCHAR2(100) NOT NULL
);

CREATE TABLE T_IOT_MOTO (
    ID_MOTO NUMBER PRIMARY KEY,
    DS_PLACA VARCHAR2(20) NOT NULL,
    NM_MODELO VARCHAR2(100) NOT NULL,
    ID_AREA NUMBER NOT NULL,
    CONSTRAINT FK_IOT_MOTO_AREA FOREIGN KEY (ID_AREA)
        REFERENCES T_IOT_AREA (ID_AREA)
);
```

## Rodando o projeto

### Instalar as dependências:
```bash
pip install -r requirements.txt
```

### Rodar a API:
```bash
uvicorn main:app --reload
```

### Acessar a documentação:
```
http://127.0.0.1:8000/docs
```

## Funcionamento do QR Code

O QR Code deve conter um JSON no seguinte formato:
```json
{
  "placa": "XYZ1234",
  "modelo": "Honda CG",
  "area": 1
}
```
- placa: Placa da moto.
- modelo: Modelo da moto.
- area: ID da área existente no banco (T_IOT_AREA).

Entre nesse site para gerar um qrcode


 https://www.qr-code-generator.com/

## Endpoints disponíveis

### Motos
| Método | Rota             | Descrição                              |
|--------|------------------|----------------------------------------|
| GET    | /motos           | Listar todas as motos                 |
| POST   | /motos/qrcode    | Cadastrar moto via QR Code            |
| PUT    | /motos/{id}      | Atualizar dados da moto               |
| DELETE | /motos/{id}      | Deletar moto                          |

### Áreas
| Método | Rota             | Descrição                              |
|--------|------------------|----------------------------------------|
| GET    | /areas           | Listar todas as áreas                 |
| POST   | /areas           | Cadastrar uma nova área               |
| PUT    | /areas/{id}      | Atualizar uma área                    |
| DELETE | /areas/{id}      | Deletar uma área                      |

## Requisitos
- Oracle Instant Client instalado e configurado no Path.
- Banco de dados Oracle acessível.
- Webcam funcionando para leitura do QR Code.

## Observações importantes
- A área (area) deve existir no banco antes de cadastrar uma moto.
- Caso não exista, use o CRUD de áreas para criar.
- A câmera fecha automaticamente após ler o QR Code.

## Status
Projeto finalizado, funcional, conectado ao banco, com leitura de QR Code e CRUD completo para Motos e Áreas.

##  Desenvolvido por:
RM 556293 Alice Teixeira Caldeira  
RM 555708 Gustavo Goulart
RM 554557 Victor Medeiros


