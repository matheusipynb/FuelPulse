import os
import requests
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

OPENVAN_URL = "https://openvan.camp/api/fuel/prices"

# Valores iniciais de demonstração até configurarmos a planilha semanal da ANP
PRECO_BRASIL = {
    "gasolina": 6.49,
    "diesel_s10": 6.19,
    "diesel_s500": 6.05,
    "etanol": 4.35,
    "gnv": 5.10
}

REGIOES = {
    "Norte": {
        "gasolina": 6.72, "diesel_s10": 6.38,
        "diesel_s500": 6.24, "etanol": 4.61, "gnv": 5.32
    },
    "Nordeste": {
        "gasolina": 6.58, "diesel_s10": 6.11,
        "diesel_s500": 5.98, "etanol": 4.18, "gnv": 5.05
    },
    "Centro-Oeste": {
        "gasolina": 6.41, "diesel_s10": 6.08,
        "diesel_s500": 5.95, "etanol": 4.29, "gnv": 4.98
    },
    "Sudeste": {
        "gasolina": 6.47, "diesel_s10": 6.21,
        "diesel_s500": 6.07, "etanol": 4.38, "gnv": 5.12
    },
    "Sul": {
        "gasolina": 6.38, "diesel_s10": 6.15,
        "diesel_s500": 6.01, "etanol": 4.44, "gnv": 5.08
    }
}

def agora_iso():
    return datetime.now(timezone.utc).isoformat()

def precos_mundo():
    try:
        resposta = requests.get(OPENVAN_URL, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json().get("data", [])

        paises = []
        for item in dados:
            paises.append({
                "pais": item.get("country") or item.get("name"),
                "moeda": item.get("currency"),
                "gasolina": item.get("gasoline"),
                "diesel": item.get("diesel")
            })

        return [pais for pais in paises if pais.get("pais")]
    except Exception:
        return []

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/precos")
def api_precos():
    return jsonify({
        "atualizado_em": agora_iso(),
        "fontes": [
            "ANP - Levantamento de Preços de Combustíveis",
            "OpenVan.camp Public API"
        ],
        "brasil": {
            "nacional": PRECO_BRASIL,
            "regioes": REGIOES
        },
        "mundo": precos_mundo()
    })

@app.get("/api/saude")
def saude():
    return jsonify({
        "servico": "FuelPulse",
        "status": "online",
        "hora": agora_iso()
    })