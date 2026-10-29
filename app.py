from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

PAGINA = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f5f7fb">
  <title>FuelPulse | Monitor de combustíveis</title>

  <style>
    :root {
      color-scheme: light;
      --fundo: #f5f7fb;
      --branco: #ffffff;
      --texto: #17243c;
      --suave: #64748b;
      --azul: #2563eb;
      --borda: #e6ebf2;
      --verde: #059669;
      --sombra: 0 8px 32px rgba(30, 55, 90, .045);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--fundo);
      color: var(--texto);
      font-family: system-ui, -apple-system, sans-serif;
      line-height: 1.5;
    }

    button, select { font: inherit; }
    button { cursor: pointer; }

    button:focus-visible, select:focus-visible, a:focus-visible {
      outline: 3px solid #93c5fd;
      outline-offset: 4px;
    }

    .topbar {
      background: rgba(255, 255, 255, .96);
      border-bottom: 1px solid var(--borda);
    }

    .nav {
      max-width: 1160px;
      margin: auto;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    .marca {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -.8px;
    }

    .logo {
      width: 39px;
      height: 39px;
      display: grid;
      place-items: center;
      background: var(--azul);
      color: white;
      border-radius: 13px;
      font-size: 22px;
      box-shadow: 0 5px 12px #2563eb22;
    }

    .marca span { color: var(--azul); }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 7px 11px;
      border-radius: 30px;
      background: #ecfdf5;
      color: #047857;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }

    .ponto {
      width: 7px;
      height: 7px;
      background: #10b981;
      border-radius: 50%;
    }

    main {
      max-width: 1160px;
      padding: 34px 24px;
      margin: auto;
    }

    .hero {
      position: relative;
      overflow: hidden;
      padding: 32px;
      background: linear-gradient(120deg, #eff6ff, #f0fdfa);
      border: 1px solid #dce9f6;
      border-radius: 24px;
      margin-bottom: 24px;
    }

    .etiqueta {
      color: var(--azul);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 1.6px;
      text-transform: uppercase;
    }

    h1 {
      margin: 9px 0;
      max-width: 640px;
      font-size: clamp(27px, 5vw, 39px);
      line-height: 1.16;
      letter-spacing: -1.4px;
    }

    .hero p {
      max-width: 590px;
      margin: 12px 0 20px;
      color: #52647c;
      font-size: 14px;
    }

    .hero-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .hero-tags span {
      padding: 6px 11px;
      background: #ffffffb5;
      border: 1px solid #ffffff;
      border-radius: 8px;
      font-size: 12px;
      color: #475569;
    }

    .aviso {
      display: flex;
      align-items: flex-start;
      gap: 11px;
      padding: 15px 18px;
      margin-bottom: 28px;
      border: 1px solid #fde5ae;
      border-radius: 14px;
      background: #fffbeb;
      color: #80591b;
      font-size: 13px;
    }

    .aviso p { margin: 0; }

    .cabecalho-secao {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin: 26px 0 16px;
    }

    h2 {
      margin: 0;
      font-size: 19px;
      letter-spacing: -.5px;
    }

    .subtitulo {
      margin: 4px 0 0;
      font-size: 12px;
      color: var(--suave);
    }

    select {
      max-width: 100%;
      background: white;
      border: 1px solid var(--borda);
      color: var(--texto);
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 13px;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }

    .card {
      text-align: left;
      width: 100%;
      color: inherit;
      background: var(--branco);
      border: 1px solid var(--borda);
      border-radius: 18px;
      padding: 21px;
      box-shadow: var(--sombra);
      transition: transform .2s, box-shadow .2s, border-color .2s;
      animation: entrada .45s ease both;
    }

    .card:nth-child(2) { animation-delay: .06s; }
    .card:nth-child(3) { animation-delay: .12s; }
    .card:nth-child(4) { animation-delay: .18s; }

    .card:hover {
      transform: translateY(-4px);
      border-color: #b5cdfb;
      box-shadow: 0 12px 30px #2563eb12;
    }

    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }

    .icone {
      display: grid;
      place-items: center;
      width: 42px;
      height: 42px;
      border-radius: 13px;
      background: #eff6ff;
      color: #2563eb;
      font-weight: 800;
      font-size: 17px;
    }

    .icone.verde { background: #ecfdf5; color: #059669; }
    .icone.roxo { background: #f5f3ff; color: #7c3aed; }
    .icone.laranja { background: #fff7ed; color: #ea580c; }

    .seta { color: #94a3b8; font-size: 19px; }
    .nome { font-size: 13px; color: #52647c; }
    .preco { margin: 4px 0; font-size: 32px; font-weight: 750; }
    .unidade { font-size: 12px; color: var(--suave); }

    .card-rodape {
      margin-top: 18px;
      padding-top: 12px;
      border-top: 1px solid #f0f3f8;
      font-size: 11px;
      color: var(--suave);
    }

    .colunas {
      display: grid;
      grid-template-columns: 1.35fr 1fr;
      gap: 20px;
      margin-top: 25px;
    }

    .painel {
      background: white;
      border: 1px solid var(--borda);
      border-radius: 20px;
      padding: 24px;
      box-shadow: var(--sombra);
    }

    .painel h2 { font-size: 17px; }

    .vazio {
      min-height: 200px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      border: 1px dashed #dbe3ef;
      border-radius: 14px;
      margin-top: 20px;
      padding: 24px 18px;
      background: #fafcff;
    }

    .vazio-icone {
      font-size: 28px;
      color: #94a3b8;
      margin-bottom: 9px;
    }

    .vazio h3 { font-size: 14px; margin: 0 0 6px; }
    .vazio p { max-width: 340px; font-size: 12px; color: var(--suave); margin: 0; }

    .linha {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 0;
      border-bottom: 1px solid #f0f3f8;
      font-size: 13px;
    }

    .linha:last-child { border-bottom: none; }
    .linha span:last-child { color: var(--suave); font-size: 12px; }

    .metodologia {
      margin-top: 24px;
      padding: 21px 24px;
      border: 1px solid var(--borda);
      border-radius: 18px;
      background: #edf2f8;
    }

    .metodologia h2 { font-size: 15px; }
    .metodologia p { margin: 8px 0 0; font-size: 12px; color: #52647c; }

    footer {
      display: flex;
      justify-content: space-between;
      gap: 15px;
      flex-wrap: wrap;
      padding: 24px 0 0;
      font-size: 11px;
      color: var(--suave);
    }

    footer a { color: var(--azul); text-decoration: none; }

    dialog {
      width: min(460px, calc(100% - 32px));
      max-height: calc(100vh - 48px);
      border: 1px solid var(--borda);
      border-radius: 23px;
      padding: 28px;
      color: var(--texto);
      box-shadow: 0 24px 90px #17243c33;
    }

    dialog::backdrop {
      background: #15243b66;
      backdrop-filter: blur(4px);
    }

    .modal-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 15px;
    }

    .fechar {
      background: #f1f5f9;
      border: none;
      border-radius: 10px;
      width: 34px;
      height: 34px;
      color: #475569;
    }

    .modal-descricao {
      margin: 18px 0;
      color: var(--suave);
      font-size: 14px;
    }

    .nota {
      margin: 18px 0 0;
      padding: 13px;
      background: #eff6ff;
      border-radius: 12px;
      font-size: 12px;
      color: #315b9f;
    }

    @keyframes entrada {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 900px) {
      .cards { grid-template-columns: repeat(2, 1fr); }
      .colunas { grid-template-columns: 1fr; }
    }

    @media (max-width: 520px) {
      .nav { padding: 16px; }
      .marca { font-size: 20px; }
      main { padding: 20px 16px; }
      .hero { padding: 24px 21px; border-radius: 20px; }
      .cabecalho-secao { align-items: flex-start; flex-direction: column; }
      select { width: 100%; }
      .cards { gap: 12px; }
      .card { padding: 16px; }
      .nome { font-size: 12px; }
      .preco { font-size: 29px; }
      .card-rodape { font-size: 10px; }
      .painel { padding: 20px; }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
      }
    }
  </style>
</head>

<body>
  <header class="topbar">
    <nav class="nav" aria-label="Cabeçalho">
      <div class="marca">
        <div class="logo" aria-hidden="true">↗</div>
        <div>Fuel<span>Pulse</span></div>
      </div>

      <div class="badge">
        <span class="ponto" aria-hidden="true"></span>
        Prévia visual
      </div>
    </nav>
  </header>

  <main>
    <section class="hero">
      <div class="etiqueta">Inteligência em combustíveis</div>
      <h1>Mais clareza para acompanhar os preços.</h1>
      <p>
        Um espaço para consultar combustíveis, explorar regiões
        e acompanhar o mercado brasileiro e internacional.
      </p>
      <div class="hero-tags">
        <span>Brasil e mundo</span>
        <span>Comparação regional</span>
        <span>Informações por combustível</span>
      </div>
    </section>

    <aside class="aviso">
      <span aria-hidden="true">ⓘ</span>
      <p>
        Painel em desenvolvimento. A integração com as fontes de
        preços ainda não está ativa. Nenhum valor fictício é exibido.
      </p>
    </aside>

    <section aria-labelledby="titulo-brasil">
      <div class="cabecalho-secao">
        <div>
          <h2 id="titulo-brasil">Panorama de combustíveis</h2>
          <p class="subtitulo" id="local-selecionado">
            Brasil · Visão nacional
          </p>
        </div>

        <select id="regiao" aria-label="Selecionar região">
          <option value="Brasil">Brasil · Todas as regiões</option>
          <option>Norte</option>
          <option>Nordeste</option>
          <option>Centro-Oeste</option>
          <option>Sudeste</option>
          <option>Sul</option>
        </select>
      </div>

      <div class="cards">
        <button class="card" type="button" data-combustivel="gasolina">
          <div class="card-top">
            <span class="icone" aria-hidden="true">G</span>
            <span class="seta" aria-hidden="true">↗</span>
          </div>
          <div class="nome">Gasolina comum</div>
          <div class="preco">—</div>
          <div class="unidade">R$/litro</div>
          <div class="card-rodape">Ver informações do combustível</div>
        </button>

        <button class="card" type="button" data-combustivel="s10">
          <div class="card-top">
            <span class="icone verde" aria-hidden="true">D</span>
            <span class="seta" aria-hidden="true">↗</span>
          </div>
          <div class="nome">Diesel S10</div>
          <div class="preco">—</div>
          <div class="unidade">R$/litro</div>
          <div class="card-rodape">Ver informações do combustível</div>
        </button>

        <button class="card" type="button" data-combustivel="s500">
          <div class="card-top">
            <span class="icone laranja" aria-hidden="true">D</span>
            <span class="seta" aria-hidden="true">↗</span>
          </div>
          <div class="nome">Diesel S500</div>
          <div class="preco">—</div>
          <div class="unidade">R$/litro</div>
          <div class="card-rodape">Ver informações do combustível</div>
        </button>

        <button class="card" type="button" data-combustivel="etanol">
          <div class="card-top">
            <span class="icone roxo" aria-hidden="true">E</span>
            <span class="seta" aria-hidden="true">↗</span>
          </div>
          <div class="nome">Etanol hidratado</div>
          <div class="preco">—</div>
          <div class="unidade">R$/litro</div>
          <div class="card-rodape">Ver informações do combustível</div>
        </button>
      </div>
    </section>

    <div class="colunas">
      <section class="painel">
        <h2>Evolução de preços</h2>
        <p class="subtitulo">Espaço reservado ao histórico de pesquisas</p>

        <div class="vazio">
          <div class="vazio-icone" aria-hidden="true">▥</div>
          <h3>Histórico ainda não conectado</h3>
          <p>
            O gráfico será exibido quando houver uma série de
            preços reais disponível. Não usamos curvas simuladas.
          </p>
        </div>
      </section>

      <section class="painel">
        <h2>Informações da consulta</h2>
        <p class="subtitulo">Transparência sobre os dados exibidos</p>

        <div class="linha">
          <span>Abrangência</span>
          <span id="abrangencia">Brasil</span>
        </div>
        <div class="linha">
          <span>Fonte de preços</span>
          <span>Não conectada</span>
        </div>
        <div class="linha">
          <span>Período da pesquisa</span>
          <span>Indisponível</span>
        </div>
        <div class="linha">
          <span>Última sincronização</span>
          <span>Não realizada</span>
        </div>
      </section>
    </div>

    <section class="painel" style="margin-top: 24px">
      <h2>Mercado internacional</h2>
      <p class="subtitulo">Comparação entre países</p>
      <div class="vazio" style="min-height: 155px">
        <div class="vazio-icone" aria-hidden="true">◎</div>
        <h3>Comparação global em preparação</h3>
        <p>
          Os preços deverão incluir moeda, unidade e data de
          referência antes de serem comparados.
        </p>
      </div>
    </section>

    <section class="metodologia">
      <h2>Como interpretar o painel</h2>
      <p>
        O símbolo “—” indica que o preço não está disponível,
        e não que o combustível custa zero. A escolha de uma região
        altera o contexto da interface, mas ainda não consulta preços.
      </p>
    </section>

    <footer>
      <span>FuelPulse · Monitor de combustíveis</span>
      <a href="/api/saude">Status da aplicação ↗</a>
    </footer>
  </main>

  <dialog id="detalhes" aria-labelledby="modal-titulo">
    <div class="modal-top">
      <h2 id="modal-titulo">Combustível</h2>
      <button class="fechar" id="fechar" aria-label="Fechar detalhes">✕</button>
    </div>

    <p class="modal-descricao" id="modal-descricao"></p>

    <div class="linha">
      <span>Localidade</span>
      <span id="modal-regiao">Brasil</span>
    </div>
    <div class="linha">
      <span>Preço médio</span>
      <span>Indisponível</span>
    </div>
    <div class="linha">
      <span>Unidade</span>
      <span>R$/litro</span>
    </div>
    <div class="linha">
      <span>Período de referência</span>
      <span>Indisponível</span>
    </div>

    <p class="nota">
      Este card está pronto visualmente. Os valores serão preenchidos
      após a integração com uma fonte de dados validada.
    </p>
  </dialog>

  <script>
    const combustiveis = {
      gasolina: {
        nome: "Gasolina comum",
        descricao: "Detalhamento reservado à gasolina comum."
      },
      s10: {
        nome: "Diesel S10",
        descricao: "Detalhamento reservado ao diesel S10, separado do diesel S500."
      },
      s500: {
        nome: "Diesel S500",
        descricao: "Detalhamento reservado ao diesel S500, separado do diesel S10."
      },
      etanol: {
        nome: "Etanol hidratado",
        descricao: "Detalhamento reservado ao etanol hidratado."
      }
    };

    const seletor = document.getElementById("regiao");
    const dialog = document.getElementById("detalhes");

    seletor.addEventListener("change", () => {
      const local = seletor.value;
      document.getElementById("local-selecionado").textContent =
        local === "Brasil" ? "Brasil · Visão nacional" : local + " · Visão regional";
      document.getElementById("abrangencia").textContent = local;
    });

    document.querySelectorAll("[data-combustivel]").forEach(card => {
      card.addEventListener("click", () => {
        const item = combustiveis[card.dataset.combustivel];
        document.getElementById("modal-titulo").textContent = item.nome;
        document.getElementById("modal-descricao").textContent = item.descricao;
        document.getElementById("modal-regiao").textContent = seletor.value;
        dialog.showModal();
      });
    });

    document.getElementById("fechar").addEventListener("click", () => {
      dialog.close();
    });

    dialog.addEventListener("click", event => {
      const area = dialog.getBoundingClientRect();
      if (
        event.clientX < area.left || event.clientX > area.right ||
        event.clientY < area.top || event.clientY > area.bottom
      ) {
        dialog.close();
      }
    });
  </script>
</body>
</html>
"""


@app.get("/")
def home():
    return render_template_string(PAGINA)


@app.get("/api/saude")
def saude():
    return jsonify({
        "status": "ok",
        "servico": "FuelPulse",
        "versao": "visual-claro-01",
        "dados_de_precos": "nao_conectados"
    })


if __name__ == "__main__":
    app.run(debug=True)