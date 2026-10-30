from flask import Flask, jsonify, render_template, request

from services.anp import (
    ESTADOS,
    FONTES,
    agora,
    obter_dados,
    status_cache,
)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="public",
    static_url_path="",
)


@app.get("/")
def home():
    return render_template("index.html", estados=ESTADOS)


@app.get("/status")
def pagina_status():
    return render_template("status.html")


@app.get("/api/saude")
def saude():
    return jsonify(
        status="ok",
        servico="FuelPulse Brasil",
        versao="organizado-01",
        hora=agora(),
        fontes=status_cache(),
    )


@app.get("/api/precos")
def precos():
    abrangencia = request.args.get("abrangencia", "brasil")

    if abrangencia not in FONTES:
        return jsonify(erro="Abrangência inválida."), 400

    try:
        return jsonify(obter_dados(abrangencia))
    except Exception as erro:
        app.logger.exception("Falha na consulta à ANP")
        return jsonify(
            erro="Não foi possível carregar os preços da ANP.",
            detalhe=str(erro),
            arquivo=FONTES[abrangencia],
        ), 503


if __name__ == "__main__":
    app.run(debug=True)