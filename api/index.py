import os
import io
import requests
import pandas as pd
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ANP_XLSX_URL = os.environ.get(
    "ANP_XLSX_URL",
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-concorrencia/precos/arquivos-lpc/2026/resumo_semanal_lpc_2026-04-12-2026-04-18.xlsx"
)

OPENVAN_URL = "https://openvan.camp/api/fuel/prices"
CACHE_SEGUNDOS = 6 * 60 * 60

_cache = {"dados": None, "timestamp": 0}

PRODUTOS = {
    "GASOLINA COMUM": "gasolina",
    "OLEO DIESEL S10": "diesel_s10",
    "OLEO DIESEL": "diesel_s500",
    "ETANOL HIDRATADO": "etanol",
    "GNV": "gnv"
}

REGIOES_ESTADOS = {
    "Norte": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["DF", "GO", "MT", "MS"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"]
}

def agora():
    return datetime.now(timezone.utc).isoformat()

def baixar_anp():
    resposta = requests.get(ANP_XLSX_URL, timeout=25)
    resposta.raise_for_status()
    return pd.read_excel(io.BytesIO(resposta.content))

def normalizar_anp(df):
    df.columns = [str(c).strip().upper() for c in df.columns]

    colunas = {}
    for coluna in df.columns:
        if "PRODUTO" in coluna:
            colunas["produto"] = coluna
        elif "ESTADO" in coluna or "UF" in coluna:
            colunas["estado"] = coluna
        elif "REGI" in coluna:
            colunas["regiao"] = coluna
        elif "MÉDIA REVENDA" in coluna or "PRECO MEDIO REVENDA" in coluna:
            colunas["preco_medio"] = coluna
        elif "MÍNIMO REVENDA" in coluna or "PRECO MINIMO REVENDA" in coluna:
            colunas["preco_minimo"] = coluna
        elif "MÁXIMO REVENDA" in coluna or "PRECO MAXIMO REVENDA" in coluna:
            colunas["preco_maximo"] = coluna
        elif "NÚMERO DE POSTOS" in coluna or "NUMERO DE POSTOS" in coluna:
            colunas["postos"] = coluna

    df = df.rename(columns={
        colunas.get("produto", ""): "produto",
        colunas.get("estado", ""): "estado",
        colunas.get("regiao", ""): "regiao",
        colunas.get("preco_medio", ""): "preco_medio",
        colunas.get("preco_minimo", ""): "preco_minimo",
        colunas.get("preco_maximo", ""): "preco_maximo",
        colunas.get("postos", ""): "postos"
    })

    obrigatorias = ["produto", "estado", "preco_medio"]
    if not all(c in df.columns for c in obrigatorias):
        raise ValueError("Formato da planilha ANP não reconhecido.")

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df = df[df["produto"].isin(PRODUTOS)]
    df["combustivel"] = df["produto"].map(PRODUTOS)

    for coluna in ["preco_medio", "preco_minimo", "preco_maximo", "postos"]:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df = df.dropna(subset=["preco_medio"])

    if "regiao" not in df.columns or df["regiao"].isna().all():
        mapa = {estado: regiao for regiao, estados in REGIOES_ESTADOS.items() for estado in estados}
        df["regiao"] = df["estado"].astype(str).str.strip().str.upper().map(mapa)

    return df

def resumo_brasil(df):
    saida = {}

    for combustivel, grupo in df.groupby("combustivel"):
        saida[combustivel] = {
            "preco_medio": round(float(grupo["preco_medio"].mean()), 3),
            "preco_minimo": round(float(grupo["preco_minimo"].min()), 3) if "preco_minimo" in grupo else None,
            "preco_maximo": round(float(grupo["preco_maximo"].max()), 3) if "preco_maximo" in grupo else None,
            "postos_pesquisados": int(grupo["postos"].sum()) if "postos" in grupo else None
        }

    return saida

def resumo_regioes(df):
    saida = {}

    for regiao, grupo in df.groupby("regiao"):
        if pd.isna(regiao):
            continue

        saida[str(regiao).title()] = {}

        for combustivel, subgrupo in grupo.groupby("combustivel"):
            saida[str(regiao).title()][combustivel] = round(float(subgrupo["preco_medio"].mean()), 3)

    return saida

def estados_por_regiao(df):
    saida = {}

    for regiao, grupo in df.groupby("regiao"):
        if pd.isna(regiao):
            continue

        regiao_nome = str(regiao).title()
        saida[regiao_nome] = {}

        for estado, subgrupo in grupo.groupby("estado"):
            gasolina = subgrupo[subgrupo["combustivel"] == "gasolina"]
            diesel = subgrupo[subgrupo["combustivel"] == "diesel_s10"]

            saida[regiao_nome][str(estado).title()] = {
                "gasolina": round(float(gasolina["preco_medio"].mean()), 3) if not gasolina.empty else None,
                "diesel_s10": round(float(diesel["preco_medio"].mean()), 3) if not diesel.empty else None
            }

    return saida

def dados_anp():
    atual = datetime.now(timezone.utc).timestamp()

    if _cache["dados"] and atual - _cache["timestamp"] < CACHE_SEGUNDOS:
        return _cache["dados"]

    df = normalizar_anp(baixar_anp())

    dados = {
        "fonte": "ANP - Levantamento de Preços de Combustíveis",
        "arquivo": ANP_XLSX_URL,
        "atualizado_em": agora(),
        "brasil": resumo_brasil(df),
        "regioes": resumo_regioes(df),
        "estados": estados_por_regiao(df)
    }

    _cache["dados"] = dados
    _cache["timestamp"] = atual

    return dados

def precos_mundo():
    try:
        resposta = requests.get(OPENVAN_URL, timeout=15)
        resposta.raise_for_status()
        bruto = resposta.json().get("data", [])

        paises = []
        for item in bruto:
            paises.append({
                "pais": item.get("country") or item.get("name"),
                "moeda": item.get("currency"),
                "gasolina": item.get("gasoline"),
                "diesel": item.get("diesel"),
                "fonte": item.get("source")
            })

        return [p for p in paises if p.get("pais")]
    except Exception:
        return []

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/precos")
def api_precos():
    try:
        brasil = dados_anp()
        status_anp = "ok"
    except Exception as erro:
        brasil = {
            "fonte": "ANP",
            "atualizado_em": agora(),
            "brasil": {},
            "regioes": {},
            "estados": {},
            "erro": str(erro)
        }
        status_anp = "erro"

    return jsonify({
        "status": {
            "anp": status_anp,
            "mundo": "ok" if precos_mundo() else "indisponivel"
        },
        "brasil": brasil,
        "mundo": precos_mundo()
    })

@app.get("/api/saude")
def saude():
    return jsonify({
        "servico": "FuelPulse API",
        "status": "online",
        "hora": agora()
    })