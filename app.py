import io
import math
import re
import time
import threading
import unicodedata
from datetime import date, datetime, timezone

import openpyxl
import requests
from flask import Flask, jsonify, render_template_string, request


app = Flask(__name__)

BASE_ANP = (
    "https://www.gov.br/anp/pt-br/assuntos/"
    "precos-e-defesa-da-concorrencia/precos/"
    "precos-revenda-e-de-distribuicao-combustiveis/"
    "shlp/semanal/"
)

FONTES = {
    "brasil": BASE_ANP + "semanal-brasil-desde-2013.xlsx",
    "estados": BASE_ANP + "semanal-estados-desde-2013.xlsx",
}

TTL = 6 * 60 * 60
CACHE = {}
LOCKS = {chave: threading.Lock() for chave in FONTES}

ESTADOS = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}


def normalizar(valor):
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"s+", " ", texto.upper().replace("-", " ")).strip()


NOMES_UF = {
    normalizar(nome): uf for uf, nome in ESTADOS.items()
}

PRODUTOS = {
    "GASOLINA": "Gasolina comum",
    "GASOLINA COMUM": "Gasolina comum",
    "GASOLINA C COMUM": "Gasolina comum",
    "GASOLINA ADITIVADA": "Gasolina aditivada",
    "ETANOL": "Etanol hidratado",
    "ETANOL HIDRATADO": "Etanol hidratado",
    "OLEO DIESEL S10": "Diesel S10",
    "OLEO DIESEL S 10": "Diesel S10",
    "DIESEL S10": "Diesel S10",
    "OLEO DIESEL": "Diesel S500",
    "OLEO DIESEL S500": "Diesel S500",
    "DIESEL S500": "Diesel S500",
    "GNV": "GNV",
    "GLP": "GLP",
    "GLP 13 KG": "GLP",
}


def agora():
    return datetime.now(timezone.utc).isoformat()


def numero(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        if isinstance(valor, str):
            valor = valor.strip().replace("R$", "").replace(" ", "")
            if "," in valor:
                valor = valor.replace(".", "").replace(",", ".")
        resultado = float(valor)
        return resultado if math.isfinite(resultado) else None
    except (TypeError, ValueError):
        return None


def ler_data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                pass
    return None


def detectar_cabecalho(linha):
    mapa = {}

    for indice, valor in enumerate(linha):
        texto = normalizar(valor)

        if texto in ("PRODUTO", "COMBUSTIVEL"):
            mapa["produto"] = indice
        elif texto in ("ESTADO", "ESTADOS", "UF"):
            mapa["estado"] = indice
        elif texto in ("DATA INICIAL", "DATA INICIO"):
            mapa["inicio"] = indice
        elif texto == "DATA FINAL":
            mapa["fim"] = indice
        elif "UNIDADE" in texto:
            mapa["unidade"] = indice
        elif "PRECO" in texto and "MEDIO" in texto and "REVENDA" in texto:
            mapa["medio"] = indice
        elif "PRECO" in texto and "MINIMO" in texto and "REVENDA" in texto:
            mapa["minimo"] = indice
        elif "PRECO" in texto and "MAXIMO" in texto and "REVENDA" in texto:
            mapa["maximo"] = indice
        elif (
            ("POSTOS" in texto or "OBSERVACOES" in texto)
            and "NUMERO" in texto
        ):
            mapa["postos"] = indice

    obrigatorios = {"produto", "inicio", "fim", "medio"}
    return mapa if obrigatorios.issubset(mapa) else None


def carregar_anp(abrangencia):
    url = FONTES[abrangencia]

    resposta = requests.get(
        url,
        timeout=(10, 60),
        headers={"User-Agent": "FuelPulse/2.0"},
    )
    resposta.raise_for_status()

    if resposta.content[:2] != b"PK":
        raise ValueError(
            "A ANP não retornou um arquivo XLSX válido. "
            "Pode haver indisponibilidade ou bloqueio temporário."
        )

    arquivo = openpyxl.load_workbook(
        io.BytesIO(resposta.content),
        read_only=True,
        data_only=True,
    )

    ultima_data = None
    registros = {}

    try:
        for aba in arquivo.worksheets:
            cabecalho = None

            for linha in aba.iter_rows(values_only=True):
                if cabecalho is None:
                    cabecalho = detectar_cabecalho(linha)
                    continue

                def campo(nome):
                    indice = cabecalho.get(nome)
                    return (
                        linha[indice]
                        if indice is not None and indice < len(linha)
                        else None
                    )

                fim = ler_data(campo("fim"))
                if fim is None:
                    continue
                if ultima_data is not None and fim < ultima_data:
                    continue

                produto = PRODUTOS.get(normalizar(campo("produto")))
                medio = numero(campo("medio"))
                inicio = ler_data(campo("inicio"))

                if not produto or medio is None or medio <= 0 or not inicio:
                    continue

                if abrangencia == "estados":
                    valor_estado = normalizar(campo("estado"))
                    uf = (
                        valor_estado
                        if valor_estado in ESTADOS
                        else NOMES_UF.get(valor_estado)
                    )
                    if not uf:
                        continue
                    local = ESTADOS[uf]
                else:
                    uf, local = "BR", "Brasil"

                if ultima_data is None or fim > ultima_data:
                    ultima_data = fim
                    registros = {}

                unidade = str(campo("unidade") or "").strip()
                if not unidade:
                    unidade = (
                        "R$/m³" if produto == "GNV"
                        else "R$/13 kg" if produto == "GLP"
                        else "R$/litro"
                    )

                registros[(uf, produto)] = {
                    "uf": uf,
                    "local": local,
                    "produto": produto,
                    "medio": medio,
                    "minimo": numero(campo("minimo")),
                    "maximo": numero(campo("maximo")),
                    "postos": numero(campo("postos")),
                    "unidade": unidade,
                    "inicio": inicio.isoformat(),
                    "fim": fim.isoformat(),
                }
    finally:
        arquivo.close()

    if not registros:
        raise ValueError(
            "Nenhum preço reconhecido no arquivo. "
            "Os cabeçalhos ou o formato da ANP podem ter mudado."
        )

    return {
        "fonte": "ANP — Levantamento de Preços de Combustíveis",
        "arquivo": url,
        "abrangencia": abrangencia,
        "consultado_em": agora(),
        "fim_pesquisa": ultima_data.isoformat(),
        "registros": sorted(
            registros.values(),
            key=lambda r: (r["local"], r["produto"])
        ),
    }


def obter_dados(abrangencia):
    anterior = CACHE.get(abrangencia)

    if anterior and time.time() - anterior["tempo"] < TTL:
        return dict(anterior["dados"], desatualizado=False)

    with LOCKS[abrangencia]:
        anterior = CACHE.get(abrangencia)

        if anterior and time.time() - anterior["tempo"] < TTL:
            return dict(anterior["dados"], desatualizado=False)

        try:
            dados = carregar_anp(abrangencia)
            CACHE[abrangencia] = {
                "tempo": time.time(),
                "dados": dados,
            }
            return dict(dados, desatualizado=False)

        except Exception:
            if anterior:
                return dict(
                    anterior["dados"],
                    desatualizado=True,
                    aviso=(
                        "Falha na nova consulta à ANP. "
                        "Exibindo o último resultado disponível nesta instância."
                    ),
                )
            raise


@app.get("/api/precos")
def api_precos():
    abrangencia = request.args.get("abrangencia", "brasil")

    if abrangencia not in FONTES:
        return jsonify(erro="Abrangência inválida."), 400

    try:
        return jsonify(obter_dados(abrangencia))
    except Exception as erro:
        app.logger.exception("Falha na consulta ANP")
        return jsonify(
            erro="Não foi possível carregar os preços da ANP.",
            detalhe=str(erro),
            arquivo=FONTES[abrangencia],
        ), 503


@app.get("/api/saude")
def saude():
    return jsonify(
        status="ok",
        servico="FuelPulse Brasil",
        versao="brasil-02",
        hora=agora(),
        fontes={
            chave: {
                "em_cache": chave in CACHE,
                "consultado_em": (
                    CACHE[chave]["dados"]["consultado_em"]
                    if chave in CACHE else None
                ),
            }
            for chave in FONTES
        },
    )


@app.get("/")
def home():
    return render_template_string(PAGINA, estados=ESTADOS)


@app.get("/status")
def pagina_status():
    return render_template_string(STATUS)


CSS = """
:root{
  color-scheme:light;
  --azul:#1873df;
  --texto:#173958;
  --suave:#607c96;
  --borda:#cde1f6;
}
*{box-sizing:border-box}
body{
  margin:0;font-family:system-ui,-apple-system,sans-serif;
  background:linear-gradient(140deg,#f0f8ff,#e1efff);
  color:var(--texto);min-height:100vh;line-height:1.5
}
a{color:var(--azul)}
header{background:#ffffffde;border-bottom:1px solid var(--borda)}
nav,main{max-width:1140px;margin:auto;padding:22px}
nav{display:flex;align-items:center;justify-content:space-between;gap:15px}
.marca{font-size:25px;font-weight:850;letter-spacing:-1px}
.marca span{color:var(--azul)}
.selo{font-size:12px;padding:7px 12px;border-radius:25px;background:#e4f1ff;color:#286499}
.hero{
  background:linear-gradient(120deg,#d9ecff,#f7fcff);
  padding:30px;border:1px solid #bfdafa;border-radius:24px;margin-bottom:22px
}
.etiqueta{font-size:11px;font-weight:800;letter-spacing:1.7px;color:var(--azul)}
h1{font-size:clamp(28px,5vw,40px);line-height:1.15;letter-spacing:-1px;margin:12px 0}
h2{font-size:20px;margin:0}
h3{font-size:14px;margin:0}
.hero p,.nota,.sub{color:var(--suave);font-size:13px}
.hero p{max-width:640px}
.painel{
  padding:24px;margin-bottom:22px;background:#ffffffed;
  border:1px solid var(--borda);border-radius:20px;box-shadow:0 8px 28px #2266aa08
}
.controles{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}
button,select,input{font:inherit}
button{cursor:pointer}
select,input,.acao{
  padding:11px 13px;border:1px solid var(--borda);
  border-radius:11px;background:#f7fbff;color:var(--texto)
}
.acao{background:var(--azul);color:white;border-color:var(--azul)}
button:disabled{opacity:.55;cursor:wait}
.status{
  padding:14px 16px;background:#eaf4ff;color:#3d678f;
  border-radius:12px;font-size:13px;margin:15px 0;overflow-wrap:anywhere
}
.status.erro{background:#fff0ed;color:#9e4337}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.card{
  text-align:left;padding:20px;border:1px solid var(--borda);
  border-radius:18px;background:linear-gradient(145deg,#fff,#f1f8ff);
  color:var(--texto);transition:transform .2s,box-shadow .2s;animation:entrar .35s both
}
.card:hover{transform:translateY(-4px);box-shadow:0 12px 28px #1677e81a}
.icone{
  display:grid;place-items:center;width:40px;height:40px;
  border-radius:12px;background:#e2efff;color:var(--azul);font-weight:800;margin-bottom:14px
}
.preco{font-size:30px;font-weight:800;color:#155faa;margin:6px 0}
.unidade{font-size:12px;color:var(--suave)}
.card-nota{margin-top:14px;padding-top:11px;border-top:1px solid #deebf8;font-size:11px}
.tabela{overflow:auto;margin-top:15px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:13px 10px;border-bottom:1px solid #e2edf8;white-space:nowrap}
th{font-size:12px;color:var(--suave)}
tr.selecionado{background:#eaf4ff}
details{font-size:12px;margin:12px 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere}
footer{font-size:12px;color:var(--suave);padding:0 0 25px}
dialog{
  width:min(470px,calc(100% - 32px));max-height:85vh;
  background:#fbfdff;color:var(--texto);border:1px solid var(--borda);
  border-radius:22px;padding:25px
}
dialog::backdrop{background:#17395870;backdrop-filter:blur(4px)}
.modal-top{display:flex;justify-content:space-between;align-items:center;gap:12px}
.fechar{border:0;border-radius:10px;background:#e3efff;color:#315f8b;padding:9px 12px}
.linha{display:flex;justify-content:space-between;gap:15px;padding:13px 0;border-bottom:1px solid #e1edf8;font-size:13px}
button:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{
  outline:3px solid #86bafa;outline-offset:3px
}
@keyframes entrar{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){
  nav,main{padding:16px}
  .hero,.painel{padding:20px}
  .card{padding:15px}
  .preco{font-size:26px}
  .controles select,.controles input{width:100%}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


PAGINA = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#eaf4ff">
<title>FuelPulse Brasil — Preços de combustíveis</title>
<style>
""" + CSS + """
</style>
</head>
<body>
<header>
<nav>
  <div class="marca">↗ Fuel<span>Pulse</span></div>
  <span class="selo">Brasil e estados</span>
</nav>
</header>

<main>
<section class="hero">
  <div class="etiqueta">MONITOR BRASILEIRO DE COMBUSTÍVEIS</div>
  <h1>Os preços do Brasil,<br>com mais clareza.</h1>
  <p>
    Consulte a média nacional e os preços por estado.
    Dados da ANP com período de referência, unidade e fonte.
  </p>
</section>

<section class="painel">
  <h2>Panorama de preços</h2>
  <p class="sub">
    Selecione Brasil ou uma unidade da federação.
    A primeira consulta estadual pode levar mais tempo.
  </p>

  <div class="controles">
    <select id="local" aria-label="Selecionar localidade">
      <option value="BR">Brasil — Média nacional</option>
      {% for uf, nome in estados.items() %}
      <option value="{{ uf }}">{{ nome }} — {{ uf }}</option>
      {% endfor %}
    </select>
    <button class="acao" id="consultar">Consultar fonte</button>
  </div>

  <div id="status" class="status" role="status">Preparando consulta...</div>
  <div class="cards" id="cards"></div>
  <p class="nota" id="referencia"></p>
  <a id="arquivo" hidden target="_blank" rel="noopener">Abrir arquivo oficial da ANP ↗</a>

  <details id="diagnostico" hidden>
    <summary>Detalhes da integração</summary>
    <pre id="erro"></pre>
  </details>
</section>

<section class="painel">
  <h2>Comparação entre estados</h2>
  <p class="sub">
    Ordenação do menor para o maior preço médio.
    Somente dados da mesma pesquisa estadual são comparados.
  </p>
  <div class="controles">
    <select id="produto" aria-label="Combustível">
      <option>Gasolina comum</option>
      <option>Gasolina aditivada</option>
      <option>Diesel S10</option>
      <option>Diesel S500</option>
      <option>Etanol hidratado</option>
      <option>GNV</option>
      <option>GLP</option>
    </select>
    <button class="acao" id="comparar">Carregar comparação</button>
  </div>

  <div class="status" id="status-estados" role="status">
    Toque em “Carregar comparação” para consultar o arquivo estadual.
  </div>
  <div class="tabela">
    <table>
      <thead>
        <tr>
          <th>Estado</th><th>Média</th><th>Mínimo</th>
          <th>Máximo</th><th>Unidade</th>
        </tr>
      </thead>
      <tbody id="tabela"></tbody>
    </table>
  </div>
</section>

<section class="painel nota">
  <h2>Sobre os dados</h2>
  <p>
    Fonte: ANP — Levantamento de Preços de Combustíveis.
    Os valores são os publicados pela agência. A média nacional
    não é recalculada a partir das médias estaduais.
  </p>
  <p>
    As datas dos arquivos nacional e estadual podem ser diferentes.
    Cada área informa seu próprio período. A data da consulta ao
    servidor não representa uma nova pesquisa de preços.
  </p>
  <p>
    O painel consulta o último período encontrado no arquivo oficial.
    Uma consulta bem-sucedida não garante que a ANP já publicou a
    semana mais recente do calendário. Verifique sempre a referência.
  </p>
  <p>
    Cache em memória por até seis horas por instância.
    Com esta página aberta, consultas são repetidas a cada 15 minutos,
    respeitando esse cache. Não há coleta agendada quando ninguém acessa.
  </p>
  <p>
    “—” significa dado ausente. Ausência de preço não significa zero.
    GLP e GNV podem ter unidades diferentes dos combustíveis líquidos.
    Esta versão não armazena histórico nem calcula variação semanal.
  </p>
</section>

<footer>
  FuelPulse Brasil · <a href="/status">Status da aplicação ↗</a>
</footer>
</main>

<dialog id="modal" aria-labelledby="modal-titulo">
  <div class="modal-top">
    <h2 id="modal-titulo"></h2>
    <button class="fechar" id="fechar" aria-label="Fechar">✕</button>
  </div>
  <div id="modal-conteudo"></div>
</dialog>

<script>
const el = id => document.getElementById(id);
const memoria = {};
let pedidos = {};
let sequencia = 0;

function criar(tag, conteudo, classe) {
  const elemento = document.createElement(tag);
  elemento.textContent = conteudo;
  if (classe) elemento.className = classe;
  return elemento;
}

function valor(n) {
  return n == null ? "—" : Number(n).toLocaleString("pt-BR", {
    minimumFractionDigits:2,
    maximumFractionDigits:3
  });
}

function dia(iso) {
  if (!iso) return "—";
  const partes = iso.split("-");
  return partes.length === 3 ? partes.reverse().join("/") : iso;
}

function periodo(r) {
  return dia(r.inicio) + " a " + dia(r.fim);
}

function mensagem(id, texto, erro=false) {
  el(id).textContent = texto;
  el(id).className = "status" + (erro ? " erro" : "");
}

async function buscar(tipo) {
  if (pedidos[tipo]) return pedidos[tipo];

  pedidos[tipo] = (async () => {
    const resposta = await fetch(
      "/api/precos?abrangencia=" + tipo,
      {cache:"no-store"}
    );

    const bruto = await resposta.text();
    let dados;

    try {
      dados = JSON.parse(bruto);
    } catch {
      throw new Error(
        "O servidor não retornou JSON. Pode ter ocorrido limite de tempo " +
        "na leitura da planilha. Confira os Runtime Logs da Vercel."
      );
    }

    if (!resposta.ok) {
      throw new Error(
        (dados.erro || "Falha na consulta.") + " " + (dados.detalhe || "")
      );
    }

    memoria[tipo] = dados;
    return dados;
  })();

  try {
    return await pedidos[tipo];
  } finally {
    delete pedidos[tipo];
  }
}

function mostrarDetalhes(r) {
  el("modal-titulo").textContent = r.produto;
  el("modal-conteudo").replaceChildren();

  const itens = [
    ["Localidade", r.local],
    ["Preço médio", valor(r.medio)],
    ["Preço mínimo", valor(r.minimo)],
    ["Preço máximo", valor(r.maximo)],
    ["Unidade", r.unidade],
    ["Postos pesquisados", r.postos == null ? "—" : Math.round(r.postos).toLocaleString("pt-BR")],
    ["Pesquisa", periodo(r)],
    ["Fonte", "ANP"]
  ];

  itens.forEach(([rotulo, conteudo]) => {
    const linha = criar("div", "", "linha");
    linha.append(criar("span", rotulo), criar("span", conteudo));
    el("modal-conteudo").append(linha);
  });

  el("modal").showModal();
}

function renderizarCards(dados, uf) {
  el("cards").replaceChildren();

  const registros = dados.registros.filter(r => r.uf === uf);

  if (!registros.length) {
    mensagem(
      "status",
      "Nenhum preço disponível para esta localidade na pesquisa mais recente.",
      true
    );
    return;
  }

  registros.forEach((r, indice) => {
    const card = criar("button", "", "card");
    card.type = "button";
    card.style.animationDelay = `${indice * .04}s`;

    card.append(
      criar("div", r.produto.charAt(0), "icone"),
      criar("h3", r.produto),
      criar("div", valor(r.medio), "preco"),
      criar("div", r.unidade, "unidade"),
      criar("div", "Ver detalhes e período ↗", "card-nota")
    );

    card.onclick = () => mostrarDetalhes(r);
    el("cards").append(card);
  });

  const r = registros[0];
  mensagem(
    "status",
    dados.desatualizado
      ? dados.aviso
      : r.local + " · Pesquisa: " + periodo(r),
    dados.desatualizado
  );

  el("referencia").textContent =
    "Fonte: ANP · Fim da pesquisa: " + dia(r.fim) +
    " · Consulta ao provedor: " +
    new Date(dados.consultado_em).toLocaleString("pt-BR");

  el("arquivo").href = dados.arquivo;
  el("arquivo").hidden = false;
}

async function carregarLocal() {
  const id = ++sequencia;
  const uf = el("local").value;
  const tipo = uf === "BR" ? "brasil" : "estados";

  el("cards").replaceChildren();
  el("referencia").textContent = "";
  el("arquivo").hidden = true;
  el("diagnostico").hidden = true;
  el("consultar").disabled = true;

  mensagem(
    "status",
    tipo === "estados"
      ? "Lendo a série estadual da ANP. A primeira consulta pode demorar..."
      : "Consultando a série nacional da ANP..."
  );

  try {
    const dados = await buscar(tipo);
    if (id !== sequencia) return;
    renderizarCards(dados, uf);
    if (tipo === "estados") renderizarTabela();
  } catch (erro) {
    if (id !== sequencia) return;
    mensagem("status", "Não foi possível carregar os preços.", true);
    el("erro").textContent = erro.message;
    el("diagnostico").hidden = false;
  } finally {
    if (id === sequencia) el("consultar").disabled = false;
  }
}

function renderizarTabela() {
  const dados = memoria.estados;
  if (!dados) return;

  const produto = el("produto").value;
  const registros = dados.registros
    .filter(r => r.produto === produto)
    .sort((a,b) => a.medio - b.medio);

  el("tabela").replaceChildren();

  if (!registros.length) {
    mensagem("status-estados", "Sem dados para este combustível no último período.", true);
    return;
  }

  registros.forEach(r => {
    const linha = document.createElement("tr");

    if (r.uf === el("local").value) linha.className = "selecionado";

    [
      r.local + " · " + r.uf,
      valor(r.medio), valor(r.minimo), valor(r.maximo), r.unidade
    ].forEach(conteudo => linha.append(criar("td", conteudo)));

    el("tabela").append(linha);
  });

  mensagem(
    "status-estados",
    (dados.desatualizado ? dados.aviso + " " : "") +
    produto + " · Pesquisa: " + periodo(registros[0]) +
    " · " + registros.length + " unidades da federação com dados",
    dados.desatualizado
  );
}

async function carregarComparacao() {
  el("comparar").disabled = true;
  mensagem("status-estados", "Consultando o arquivo estadual da ANP...");

  try {
    await buscar("estados");
    renderizarTabela();
  } catch (erro) {
    mensagem("status-estados", erro.message, true);
  } finally {
    el("comparar").disabled = false;
  }
}

el("local").onchange = carregarLocal;
el("consultar").onclick = carregarLocal;
el("comparar").onclick = carregarComparacao;
el("produto").onchange = renderizarTabela;
el("fechar").onclick = () => el("modal").close();

carregarLocal();

setInterval(() => {
  if (!document.hidden) {
    carregarLocal();
    if (memoria.estados && el("local").value === "BR") {
      carregarComparacao();
    }
  }
}, 15 * 60 * 1000);
</script>
</body>
</html>
"""


STATUS = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Status — FuelPulse Brasil</title>
<style>
""" + CSS + """
</style>
</head>
<body>
<main style="max-width:760px">
  <p><a href="/">← Voltar ao dashboard</a></p>

  <section class="hero">
    <div class="etiqueta">CENTRAL DE STATUS</div>
    <h1>FuelPulse Brasil</h1>
    <div class="status" id="situacao" role="status">Verificando...</div>
    <button class="acao" id="verificar">Verificar novamente</button>
  </section>

  <section class="painel">
    <h2>Informações do servidor</h2>
    <div id="informacoes"></div>
  </section>

  <section class="painel">
    <h2>Consultas mantidas em memória</h2>
    <div id="fontes"></div>
    <p class="nota">
      O cache é local a cada instância da aplicação.
      Ele pode desaparecer ao reiniciar ou quando uma nova instância é criada.
    </p>
  </section>

  <p class="nota">
    Servidor online não significa que a ANP esteja disponível.
    Este teste não baixa as planilhas nem valida preços.
  </p>

  <footer><a href="/api/saude">Ver resposta técnica em JSON ↗</a></footer>
</main>

<script>
const el = id => document.getElementById(id);

function linha(container, rotulo, conteudo) {
  const div = document.createElement("div");
  div.className = "linha";

  const esquerda = document.createElement("span");
  esquerda.textContent = rotulo;

  const direita = document.createElement("span");
  direita.textContent = conteudo;

  div.append(esquerda, direita);
  container.append(div);
}

async function verificar() {
  el("verificar").disabled = true;
  el("situacao").className = "status";
  el("situacao").textContent = "Consultando aplicação...";
  el("informacoes").replaceChildren();
  el("fontes").replaceChildren();

  try {
    const inicio = performance.now();
    const resposta = await fetch("/api/saude", {cache:"no-store"});
    if (!resposta.ok) throw new Error("HTTP " + resposta.status);

    const dados = await resposta.json();
    if (dados.status !== "ok") throw new Error("Status inesperado.");

    el("situacao").textContent = "Servidor respondeu normalmente";

    linha(el("informacoes"), "Serviço", dados.servico);
    linha(el("informacoes"), "Versão", dados.versao);
    linha(
      el("informacoes"), "Tempo desta consulta",
      Math.round(performance.now() - inicio) + " ms"
    );
    linha(
      el("informacoes"), "Horário do servidor",
      new Date(dados.hora).toLocaleString("pt-BR")
    );

    Object.entries(dados.fontes).forEach(([nome, info]) => {
      linha(
        el("fontes"),
        nome === "brasil" ? "Série nacional" : "Série estadual",
        info.em_cache
          ? "Em memória · " + new Date(info.consultado_em).toLocaleString("pt-BR")
          : "Sem cache nesta instância"
      );
    });
  } catch (erro) {
    el("situacao").className = "status erro";
    el("situacao").textContent =
      "Não foi possível confirmar o funcionamento: " + erro.message;
  } finally {
    el("verificar").disabled = false;
  }
}

el("verificar").onclick = verificar;
verificar();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True)