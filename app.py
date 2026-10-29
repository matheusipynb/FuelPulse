import io
import math
import re
import time
import threading
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
import openpyxl
import xlrd
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

ANP_PAGE = (
    "https://www.gov.br/anp/pt-br/assuntos/"
    "precos-e-defesa-da-concorrencia/precos/"
    "levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"
)

CACHE_TTL = 3600
CACHE = {}
LOCK = threading.Lock()

PAISES = {
    "germany": "Alemanha",
    "france": "França",
    "spain": "Espanha",
    "italy": "Itália",
}

PRODUTOS = {
    "GASOLINA COMUM": "Gasolina comum",
    "GASOLINA": "Gasolina comum",
    "GASOLINA C COMUM": "Gasolina comum",
    "GASOLINA ADITIVADA": "Gasolina aditivada",
    "ETANOL HIDRATADO": "Etanol hidratado",
    "ETANOL": "Etanol hidratado",
    "OLEO DIESEL S10": "Diesel S10",
    "DIESEL S10": "Diesel S10",
    "OLEO DIESEL S500": "Diesel S500",
    "DIESEL S500": "Diesel S500",
    "OLEO DIESEL": "Diesel",
    "GNV": "GNV",
    "GLP": "GLP",
}

REGIOES = {
    "NORTE", "NORDESTE", "CENTRO OESTE", "SUDESTE", "SUL"
}


def normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper().replace("-", " ")
    return re.sub(r"s+", " ", texto).strip()


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


def baixar(url):
    resposta = requests.get(
        url,
        timeout=(8, 25),
        headers={"User-Agent": "FuelPulse/1.0"},
    )
    resposta.raise_for_status()
    return resposta


def obter_cache(chave, carregar):
    atual = time.time()
    anterior = CACHE.get(chave)

    if anterior and atual - anterior["tempo"] < CACHE_TTL:
        return dict(anterior["dados"], cache_antigo=False)

    with LOCK:
        anterior = CACHE.get(chave)
        if anterior and time.time() - anterior["tempo"] < CACHE_TTL:
            return dict(anterior["dados"], cache_antigo=False)

        try:
            dados = carregar()
            CACHE[chave] = {"tempo": time.time(), "dados": dados}
            return dict(dados, cache_antigo=False)
        except Exception:
            if anterior:
                return dict(
                    anterior["dados"],
                    cache_antigo=True,
                    aviso="Falha ao atualizar; exibindo a última consulta em memória."
                )
            raise


def descobrir_planilha():
    html = baixar(ANP_PAGE).text
    soup = BeautifulSoup(html, "html.parser")
    candidatos = []

    for link in soup.find_all("a", href=True):
        titulo = normalizar(link.get_text(" ", strip=True))
        href = urljoin(ANP_PAGE, link["href"])
        caminho = urlparse(href).path.lower()

        if (
            "PRECOS MEDIOS SEMANAIS" in titulo
            and re.search(r".xlsx?(?:/.*)?$", caminho)
            and urlparse(href).hostname == "www.gov.br"
        ):
            anteriores = link.find_all_previous(string=True, limit=100)
            contexto = " ".join(str(s) for s in reversed(anteriores))
            periodos = re.findall(
                r"(d{1,2}/d{1,2}/d{4})s*as*"
                r"(d{1,2}/d{1,2}/d{4})",
                contexto
            )

            if periodos:
                inicio, fim = periodos[-1]
                try:
                    ordem = datetime.strptime(fim, "%d/%m/%Y")
                except ValueError:
                    continue
                candidatos.append((ordem, href, f"{inicio} a {fim}"))

    if not candidatos:
        raise ValueError(
            "Não foi possível localizar a planilha semanal na página da ANP."
        )

    candidatos.sort(key=lambda item: item[0], reverse=True)
    _, url, periodo = candidatos[0]
    return url, periodo


def ler_abas(conteudo):
    if conteudo[:2] == b"PK":
        arquivo = openpyxl.load_workbook(
            io.BytesIO(conteudo), read_only=True, data_only=True
        )
        try:
            for aba in arquivo.worksheets:
                yield aba.title, list(aba.iter_rows(values_only=True))
        finally:
            arquivo.close()
    else:
        arquivo = xlrd.open_workbook(file_contents=conteudo)
        for aba in arquivo.sheets():
            yield aba.name, [
                aba.row_values(i) for i in range(aba.nrows)
            ]


def detectar_cabecalho(linha):
    textos = [normalizar(c) for c in linha]
    mapa = {}

    for i, texto in enumerate(textos):
        if texto in ("PRODUTO", "COMBUSTIVEL"):
            mapa["produto"] = i
        elif "PRECO" in texto and "MEDIO" in texto and "REVENDA" in texto:
            mapa["medio"] = i
        elif "PRECO" in texto and "MINIMO" in texto and "REVENDA" in texto:
            mapa["minimo"] = i
        elif "PRECO" in texto and "MAXIMO" in texto and "REVENDA" in texto:
            mapa["maximo"] = i
        elif (
            ("POSTOS" in texto or "OBSERVACOES" in texto)
            and ("NUMERO" in texto or texto == "POSTOS")
        ):
            mapa["postos"] = i
        elif texto in ("REGIAO", "REGIOES"):
            mapa["regiao"] = i
        elif texto in ("ESTADO", "ESTADOS", "UF"):
            mapa["estado"] = i
        elif texto in ("MUNICIPIO", "MUNICIPIOS"):
            mapa["municipio"] = i
        elif "UNIDADE" in texto:
            mapa["unidade"] = i

    return mapa if "produto" in mapa and "medio" in mapa else None


def interpretar_planilha(conteudo):
    registros = []
    vistos = set()

    for nome_aba, linhas in ler_abas(conteudo):
        aba = normalizar(nome_aba)
        cabecalho = None
        ultima_localidade = None

        for linha in linhas:
            novo = detectar_cabecalho(linha)
            if novo:
                cabecalho = novo
                ultima_localidade = None
                continue

            if not cabecalho:
                continue

            def campo(nome):
                indice = cabecalho.get(nome)
                return (
                    linha[indice]
                    if indice is not None and indice < len(linha)
                    else None
                )

            produto = normalizar(campo("produto"))
            nome_produto = PRODUTOS.get(produto)
            medio = numero(campo("medio"))

            if not nome_produto or medio is None or medio <= 0:
                continue

            # Evita misturar dados municipais, estaduais e nacionais.
            if "municipio" in cabecalho:
                continue
            elif "estado" in cabecalho:
                nivel = "Estado"
                local = campo("estado")
            elif "regiao" in cabecalho:
                nivel = "Região"
                local = campo("regiao")
            elif "BRASIL" in aba or "NACIONAL" in aba:
                nivel = "Brasil"
                local = "Brasil"
            else:
                continue

            local = str(local).strip() if local is not None else ""
            if not local:
                local = ultima_localidade
            if not local:
                continue

            ultima_localidade = local

            if normalizar(local) == "BRASIL":
                nivel, local = "Brasil", "Brasil"

            unidade = str(campo("unidade") or "").strip()
            if not unidade:
                unidade = "R$/m³" if nome_produto == "GNV" else (
                    "R$/13 kg" if nome_produto == "GLP" else "R$/litro"
                )

            chave = (nivel, normalizar(local), nome_produto)
            if chave in vistos:
                continue
            vistos.add(chave)

            registros.append({
                "nivel": nivel,
                "local": local.title() if local != "Brasil" else local,
                "produto": nome_produto,
                "medio": medio,
                "minimo": numero(campo("minimo")),
                "maximo": numero(campo("maximo")),
                "postos": numero(campo("postos")),
                "unidade": unidade,
            })

    if not registros:
        raise ValueError(
            "Planilha baixada, mas os cabeçalhos não foram reconhecidos. "
            "O formato da ANP pode ter mudado."
        )

    return registros


def carregar_brasil():
    url, periodo = descobrir_planilha()
    conteudo = baixar(url).content
    registros = interpretar_planilha(conteudo)

    return {
        "fonte": "ANP — Levantamento de Preços de Combustíveis",
        "pagina_fonte": ANP_PAGE,
        "arquivo": url,
        "periodo": periodo,
        "consultado_em": agora(),
        "registros": registros,
    }


def carregar_pais(slug):
    url = f"https://fuelwide.com/api/fuel-prices/{slug}"
    bruto = baixar(url).json()
    observacoes = []

    for item in bruto.get("observations", []):
        if item.get("fuelType") not in ("petrol95", "diesel", "lpg"):
            continue
        preco = numero(item.get("price"))
        if preco is None:
            continue

        fonte = item.get("source") or {}

        observacoes.append({
            "produto": {
                "petrol95": "Gasolina 95",
                "diesel": "Diesel",
                "lpg": "GLP",
            }[item["fuelType"]],
            "preco": preco,
            "moeda": item.get("currency"),
            "unidade": item.get("unit"),
            "data": item.get("observedAt"),
            "atrasado": bool(item.get("stale")),
            "atribuicao": item.get("attribution") or fonte.get("name"),
            "fonte_url": fonte.get("url"),
            "base": item.get("priceBasis"),
        })

    if not observacoes:
        raise ValueError("O provedor não retornou preços disponíveis para este país.")

    return {
        "pais": PAISES[slug],
        "consultado_em": agora(),
        "observacoes": observacoes,
    }


@app.get("/")
def home():
    return render_template_string(PAGINA)


@app.get("/api/saude")
def saude():
    return jsonify(
        status="ok",
        servico="FuelPulse",
        versao="dados-01",
        hora=agora(),
    )


@app.get("/api/precos")
def api_precos():
    try:
        dados = obter_cache("brasil", carregar_brasil)
        return jsonify(dados)
    except Exception as erro:
        app.logger.exception("Falha na integração ANP")
        return jsonify(
            erro="Não foi possível consultar os preços da ANP.",
            detalhe=str(erro),
            fonte=ANP_PAGE,
        ), 503


@app.get("/api/mundo")
def api_mundo():
    slug = request.args.get("pais", "germany")
    if slug not in PAISES:
        return jsonify(erro="País não suportado."), 400

    try:
        dados = obter_cache(
            f"pais:{slug}",
            lambda: carregar_pais(slug)
        )
        return jsonify(dados)
    except Exception as erro:
        app.logger.exception("Falha na integração internacional")
        return jsonify(
            erro="Preços internacionais indisponíveis.",
            detalhe=str(erro),
        ), 503


PAGINA = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#eaf4ff">
<title>FuelPulse — Preços de combustíveis</title>
<style>
:root {
  color-scheme:light;
  --azul:#176fe0;
  --texto:#173958;
  --suave:#5e7891;
  --borda:#cde1f6;
}
* { box-sizing:border-box; }
body {
  margin:0;
  font-family:system-ui,-apple-system,sans-serif;
  background:linear-gradient(145deg,#eff8ff,#e3efff);
  color:var(--texto);
  min-height:100vh;
}
button,select { font:inherit; }
button { cursor:pointer; }
a { color:var(--azul); }
header { background:#ffffffd9; border-bottom:1px solid var(--borda); }
nav,main { max-width:1160px; margin:auto; padding:22px; }
nav { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.marca { font-size:25px; font-weight:850; letter-spacing:-1px; }
.marca span { color:var(--azul); }
.selo {
  font-size:12px; color:#24649e; background:#e4f1ff;
  border-radius:30px; padding:7px 12px;
}
.hero {
  padding:30px; border-radius:24px;
  background:linear-gradient(120deg,#d8ebff,#f2faff);
  border:1px solid #bddafa; margin-bottom:22px;
}
h1 { font-size:clamp(27px,5vw,39px); line-height:1.15; letter-spacing:-1px; margin:10px 0; }
.hero p { color:var(--suave); font-size:14px; max-width:620px; }
.etiqueta { font-size:11px; letter-spacing:1.8px; color:var(--azul); font-weight:800; }
h2 { margin:0; font-size:20px; }
h3 { margin:0; font-size:15px; }
.sub { font-size:12px; color:var(--suave); margin:6px 0; }
.painel {
  background:#ffffffed; border:1px solid var(--borda);
  border-radius:20px; padding:24px; margin-bottom:22px;
  box-shadow:0 8px 28px #2266aa08;
}
.controles { display:flex; flex-wrap:wrap; gap:10px; margin:18px 0; }
select,button.acao {
  padding:11px 13px; border-radius:11px;
  border:1px solid var(--borda); background:#f6faff; color:var(--texto);
}
button.acao { background:var(--azul); color:white; border-color:var(--azul); }
button:disabled { opacity:.6; cursor:wait; }
.status {
  padding:13px 15px; background:#eaf4ff; color:#365f85;
  border-radius:12px; font-size:13px; margin:14px 0;
  overflow-wrap:anywhere;
}
.status.erro { background:#fff0ef; color:#a03434; }
.cards { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
.card {
  text-align:left; background:linear-gradient(145deg,#fff,#f3f9ff);
  border:1px solid var(--borda); border-radius:17px;
  padding:20px; color:var(--texto);
  transition:transform .2s,box-shadow .2s; animation:entrar .35s both;
}
.card:hover { transform:translateY(-4px); box-shadow:0 12px 25px #1677e819; }
.icone {
  width:39px; height:39px; background:#e3f0ff; border-radius:12px;
  display:grid; place-items:center; color:var(--azul);
  font-weight:800; margin-bottom:15px;
}
.preco { font-size:29px; font-weight:800; color:#155faa; margin:7px 0; }
.unidade { font-size:12px; color:var(--suave); }
.rodape-card { margin-top:15px; padding-top:11px; border-top:1px solid #dfebf7; font-size:11px; }
.barra { margin-top:14px; height:6px; background:#e5effa; border-radius:9px; overflow:hidden; }
.barra span { display:block; height:100%; background:#58a4f4; }
.tabela { overflow:auto; margin-top:18px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { padding:13px 10px; text-align:left; border-bottom:1px solid #e6eff8; white-space:nowrap; }
th { color:var(--suave); font-size:12px; }
.nota { font-size:12px; line-height:1.7; color:var(--suave); }
details { font-size:12px; margin-top:10px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; }
footer { font-size:12px; color:var(--suave); padding:5px 0 25px; }
dialog {
  width:min(480px,calc(100% - 32px)); max-height:85vh;
  border:1px solid var(--borda); border-radius:22px; padding:25px;
  color:var(--texto); background:#fbfdff;
}
dialog::backdrop { background:#12385870; backdrop-filter:blur(4px); }
.modal-top { display:flex; justify-content:space-between; gap:14px; align-items:center; }
.fechar { border:0; background:#e6f1ff; color:#315e88; padding:8px 12px; border-radius:9px; }
.linha { display:flex; justify-content:space-between; gap:14px; padding:13px 0; border-bottom:1px solid #e3edf8; font-size:13px; }
@keyframes entrar { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
@media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){
  nav,main{padding:16px}
  .hero,.painel{padding:20px}
  .card{padding:15px}
  .preco{font-size:25px}
  .controles select{width:100%}
}
@media(prefers-reduced-motion:reduce){
  *{animation:none!important;transition:none!important}
}
</style>
</head>
<body>
<header>
  <nav>
    <div class="marca">↗ Fuel<span>Pulse</span></div>
    <span class="selo">Monitor de combustíveis</span>
  </nav>
</header>

<main>
<section class="hero">
  <div class="etiqueta">BRASIL E MERCADO INTERNACIONAL</div>
  <h1>Preços com contexto.<br>Informação com fonte.</h1>
  <p>
    Consulte médias de combustíveis, explore localidades e veja
    o período da pesquisa. Sem preços simulados.
  </p>
</section>

<section class="painel">
  <h2>Preços no Brasil</h2>
  <p class="sub">Fonte: ANP · Levantamento semanal de preços</p>

  <div class="controles">
    <select id="nivel" aria-label="Abrangência"></select>
    <select id="local" aria-label="Localidade"></select>
    <button class="acao" id="atualizar">Consultar atualização</button>
  </div>

  <div class="status" id="status" role="status">Consultando a ANP...</div>
  <div class="cards" id="cards"></div>

  <p class="nota" id="metadados"></p>
  <a id="arquivo" target="_blank" rel="noopener" hidden>Baixar planilha oficial ↗</a>

  <details id="diagnostico" hidden>
    <summary>Detalhes do erro de integração</summary>
    <pre id="erro-detalhe"></pre>
  </details>
</section>

<section class="painel">
  <h2>Comparação entre localidades</h2>
  <p class="sub">Ordenação pela média publicada para o combustível selecionado</p>
  <div class="controles">
    <select id="produto" aria-label="Combustível para comparação"></select>
  </div>
  <div class="tabela">
    <table>
      <thead><tr><th>Localidade</th><th>Média</th><th>Mínimo</th><th>Máximo</th><th>Unidade</th></tr></thead>
      <tbody id="comparacao"></tbody>
    </table>
  </div>
</section>

<section class="painel">
  <h2>Mercado internacional</h2>
  <p class="sub">Países selecionados · Provedor: FuelWide</p>
  <div class="controles">
    <select id="pais" aria-label="País">
      <option value="germany">Alemanha</option>
      <option value="france">França</option>
      <option value="spain">Espanha</option>
      <option value="italy">Itália</option>
    </select>
    <button class="acao" id="atualizar-mundo">Consultar país</button>
  </div>
  <div id="status-mundo" class="status" role="status">Selecione um país e consulte os preços.</div>
  <div class="tabela">
    <table>
      <thead><tr><th>Combustível</th><th>Preço</th><th>Moeda/unidade</th><th>Referência</th></tr></thead>
      <tbody id="mundo"></tbody>
    </table>
  </div>
  <div id="creditos" class="nota"></div>
</section>

<section class="painel nota">
  <h2>Metodologia e atualização</h2>
  <p>
    Brasil: médias, mínimos e máximos são lidos da planilha da ANP,
    sem recalcular a média nacional a partir dos estados.
    O período da pesquisa é diferente do horário da consulta.
  </p>
  <p>
    A aplicação procura a planilha mais recente e mantém cache em
    memória por até uma hora por instância. Com a página aberta,
    consulta novamente a cada 15 minutos. Não há uma tarefa
    persistente executando quando ninguém acessa o site.
  </p>
  <p>
    Internacional: moeda, unidade, referência e crédito são informados
    pelo provedor. Gasolina 95 internacional não é apresentada como
    produto idêntico à gasolina comum brasileira. Não há conversão
    cambial nem ranking conjunto entre Brasil e exterior.
  </p>
  <p>
    Não há histórico persistente nesta versão. Se uma fonte mudar de
    formato ou ficar indisponível, o painel informa a falha.
    Campos ausentes aparecem como “—”, nunca como zero.
  </p>
</section>

<footer>FuelPulse · <a href="/api/saude">Status da aplicação</a></footer>
</main>

<dialog id="modal" aria-labelledby="titulo-modal">
  <div class="modal-top">
    <h2 id="titulo-modal"></h2>
    <button class="fechar" id="fechar" aria-label="Fechar">✕</button>
  </div>
  <div id="conteudo-modal"></div>
</dialog>

<script>
let dados = null;
const el = id => document.getElementById(id);

function texto(tag, conteudo, classe) {
  const item = document.createElement(tag);
  item.textContent = conteudo;
  if (classe) item.className = classe;
  return item;
}

function numero(valor) {
  return valor == null ? "—" : Number(valor).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 3
  });
}

function data(valor) {
  if (!valor) return "—";
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? valor : d.toLocaleString("pt-BR");
}

function opcoes(elemento, valores, escolhido) {
  elemento.replaceChildren();
  valores.forEach(valor => {
    const opcao = new Option(valor, valor);
    elemento.add(opcao);
  });
  if (valores.includes(escolhido)) elemento.value = escolhido;
}

function status(id, mensagem, erro = false) {
  el(id).textContent = mensagem;
  el(id).className = "status" + (erro ? " erro" : "");
}

async function consultar(url) {
  const resposta = await fetch(url, {cache: "no-store"});
  const conteudo = await resposta.json();
  if (!resposta.ok) {
    const erro = new Error(conteudo.erro || "Falha na consulta.");
    erro.detalhe = conteudo.detalhe || "";
    throw erro;
  }
  return conteudo;
}

function preencherLocais() {
  const antigo = el("local").value;
  const locais = [...new Set(
    dados.registros
      .filter(r => r.nivel === el("nivel").value)
      .map(r => r.local)
  )].sort((a,b) => a.localeCompare(b, "pt-BR"));

  opcoes(el("local"), locais, antigo);
  renderizar();
}

function abrirDetalhes(registro) {
  el("titulo-modal").textContent = registro.produto;
  const container = el("conteudo-modal");
  container.replaceChildren();

  const itens = [
    ["Localidade", registro.local],
    ["Preço médio", numero(registro.medio)],
    ["Preço mínimo", numero(registro.minimo)],
    ["Preço máximo", numero(registro.maximo)],
    ["Unidade", registro.unidade],
    ["Postos/observações", registro.postos == null ? "—" : numero(registro.postos)],
    ["Pesquisa", dados.periodo],
    ["Fonte", "ANP"]
  ];

  itens.forEach(([chave, valor]) => {
    const linha = texto("div", "", "linha");
    linha.append(texto("span", chave), texto("span", valor));
    container.append(linha);
  });

  el("modal").showModal();
}

function renderizar() {
  if (!dados) return;

  const registros = dados.registros.filter(
    r => r.nivel === el("nivel").value && r.local === el("local").value
  );

  el("cards").replaceChildren();

  registros.forEach((r, i) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "card";
    card.style.animationDelay = `${i * .04}s`;

    card.append(
      texto("div", r.produto.charAt(0), "icone"),
      texto("h3", r.produto),
      texto("div", numero(r.medio), "preco"),
      texto("div", r.unidade, "unidade"),
      texto("div", "Toque para ver mínimo, máximo e fonte ↗", "rodape-card")
    );

    card.onclick = () => abrirDetalhes(r);
    el("cards").append(card);
  });

  const antigo = el("produto").value;
  const produtos = [...new Set(
    dados.registros.filter(r => r.nivel === el("nivel").value)
      .map(r => r.produto)
  )].sort();

  opcoes(el("produto"), produtos, antigo);
  comparar();
}

function comparar() {
  if (!dados) return;

  const linhas = dados.registros.filter(
    r => r.nivel === el("nivel").value &&
         r.produto === el("produto").value
  ).sort((a,b) => a.medio - b.medio);

  el("comparacao").replaceChildren();

  linhas.forEach(r => {
    const tr = document.createElement("tr");
    [
      r.local, numero(r.medio), numero(r.minimo),
      numero(r.maximo), r.unidade
    ].forEach(valor => tr.append(texto("td", valor)));
    el("comparacao").append(tr);
  });
}

async function carregarBrasil() {
  el("atualizar").disabled = true;
  status("status", "Consultando a publicação mais recente da ANP...");
  el("diagnostico").hidden = true;

  try {
    dados = await consultar("/api/precos");

    const niveis = ["Brasil", "Região", "Estado"].filter(
      nivel => dados.registros.some(r => r.nivel === nivel)
    );

    opcoes(el("nivel"), niveis, el("nivel").value);
    preencherLocais();

    status(
      "status",
      dados.cache_antigo
        ? dados.aviso
        : "Dados carregados · Pesquisa: " + dados.periodo,
      dados.cache_antigo
    );

    el("metadados").textContent =
      "Fonte: " + dados.fonte +
      " · Consulta ao provedor: " + data(dados.consultado_em);

    el("arquivo").href = dados.arquivo;
    el("arquivo").hidden = false;
  } catch (erro) {
    status(
      "status",
      erro.message + (dados ? " Os dados anteriores continuam visíveis." : ""),
      true
    );
    el("diagnostico").hidden = false;
    el("erro-detalhe").textContent = erro.detalhe || erro.message;
  } finally {
    el("atualizar").disabled = false;
  }
}

async function carregarMundo() {
  el("atualizar-mundo").disabled = true;
  el("mundo").replaceChildren();
  el("creditos").replaceChildren();
  status("status-mundo", "Consultando o país selecionado...");

  try {
    const resultado = await consultar(
      "/api/mundo?pais=" + encodeURIComponent(el("pais").value)
    );

    status(
      "status-mundo",
      resultado.pais + " · " +
      (resultado.cache_antigo ? resultado.aviso : "Consulta concluída"),
      resultado.cache_antigo
    );

    resultado.observacoes.forEach(r => {
      const tr = document.createElement("tr");
      [
        r.produto,
        numero(r.preco),
        (r.moeda || "—") + "/" + (r.unidade || "—"),
        (r.data || "—") + (r.atrasado ? " · Dado atrasado" : "")
      ].forEach(valor => tr.append(texto("td", valor)));

      el("mundo").append(tr);

      const credito = texto(
        "p",
        r.produto + ": " + (r.atribuicao || "Fonte não informada") +
        " · Base: " + (r.base || "não informada")
      );

      if (r.fonte_url && /^https?:\\/\\//i.test(r.fonte_url)) {
        const link = texto("a", " · Fonte original ↗");
        link.href = r.fonte_url;
        link.target = "_blank";
        link.rel = "noopener";
        credito.append(link);
      }
      el("creditos").append(credito);
    });
  } catch (erro) {
    status("status-mundo", erro.message + " " + (erro.detalhe || ""), true);
  } finally {
    el("atualizar-mundo").disabled = false;
  }
}

el("nivel").onchange = preencherLocais;
el("local").onchange = renderizar;
el("produto").onchange = comparar;
el("atualizar").onclick = carregarBrasil;
el("atualizar-mundo").onclick = carregarMundo;
el("pais").onchange = carregarMundo;
el("fechar").onclick = () => el("modal").close();

carregarBrasil();
carregarMundo();

setInterval(() => {
  if (!document.hidden) {
    carregarBrasil();
    carregarMundo();
  }
}, 15 * 60 * 1000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True)