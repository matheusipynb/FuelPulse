from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>FuelPulse — Diagnóstico</title>
        <style>
            body {
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                background: #070b14;
                color: #e2e8f0;
                font-family: system-ui, sans-serif;
            }
            main {
                margin: 20px;
                padding: 32px;
                max-width: 500px;
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 20px;
            }
            h1 { color: #4ade80; }
            a { color: #38bdf8; }
        </style>
    </head>
    <body>
        <main>
            <h1>FuelPulse online!</h1>
            <p>O Flask respondeu à rota principal.</p>
            <p>Versão de diagnóstico: deploy-check-01</p>
            <a href="/api/saude">Testar API</a>
        </main>
    </body>
    </html>
    """


@app.get("/api/saude")
def saude():
    return jsonify({
        "status": "ok",
        "servico": "FuelPulse",
        "versao": "deploy-check-01"
    })


if __name__ == "__main__":
    app.run(debug=True)