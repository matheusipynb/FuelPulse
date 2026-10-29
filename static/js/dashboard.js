let dadosGlobais = null;
let graficoRegioes = null;

const nomesCombustivel = {
  gasolina: "Gasolina comum",
  diesel_s10: "Diesel S10",
  diesel_s500: "Diesel S500",
  etanol: "Etanol hidratado",
  gnv: "GNV"
};

const modal = document.getElementById("modal");
const modalTitulo = document.getElementById("modal-titulo");
const modalConteudo = document.getElementById("modal-conteudo");

function moeda(valor) {
  if (valor === null || valor === undefined) return "—";
  return `R$ ${Number(valor).toFixed(3).replace(".", ",")}`;
}

function abrirModal(titulo, html) {
  modalTitulo.textContent = titulo;
  modalConteudo.innerHTML = html;
  modal.classList.remove("hidden");
}

document.getElementById("fechar-modal").onclick = () => modal.classList.add("hidden");
modal.onclick = evento => {
  if (evento.target === modal) modal.classList.add("hidden");
};

function definirStatus(id, texto, ok) {
  const elemento = document.getElementById(id);
  elemento.textContent = texto;
  elemento.className = `badge ${ok ? "ok" : "erro"}`;
}

function criarCard(titulo, preco, detalhe, aoClicar) {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <h3>${titulo}</h3>
    <div class="preco">${preco}</div>
    <small>${detalhe}</small>
  `;
  card.onclick = aoClicar;
  return card;
}

function renderizarKpis(brasil) {
  const kpis = document.getElementById("kpis");
  kpis.innerHTML = "";

  const combustiveis = Object.entries(brasil.brasil || {});

  if (!combustiveis.length) {
    kpis.innerHTML = `<div class="kpi"><h3>Sem dados ANP</h3><strong>—</strong></div>`;
    return;
  }

  combustiveis.forEach(([chave, info], indice) => {
    const card = document.createElement("div");
    card.className = "kpi";
    card.style.animationDelay = `${indice * 0.07}s`;
    card.innerHTML = `
      <h3>${nomesCombustivel[chave] || chave}</h3>
      <strong>${moeda(info.preco_medio)}</strong>
      <p>Mín.: ${moeda(info.preco_minimo)} · Máx.: ${moeda(info.preco_maximo)}</p>
      <p>Postos: ${info.postos_pesquisados ?? "—"}</p>
    `;
    kpis.appendChild(card);
  });
}

function renderizarCardsBrasil() {
  const container = document.getElementById("cards-brasil");
  container.innerHTML = "";

  const filtro = document.getElementById("filtro-regiao").value;
  const regioes = dadosGlobais.brasil.regioes || {};

  Object.entries(regioes).forEach(([regiao, precos], indice) => {
    if (filtro !== "todos" && filtro !== regiao) return;

    const card = criarCard(
      regiao,
      moeda(precos.gasolina),
      "Gasolina média regional",
      () => abrirModal(regiao, Object.entries(precos).map(([combustivel, preco]) => `
        <p><strong>${nomesCombustivel[combustivel] || combustivel}:</strong> ${moeda(preco)}</p>
      `).join(""))
    );

    card.style.animationDelay = `${indice * 0.06}s`;
    container.appendChild(card);
  });
}

function renderizarGrafico() {
  const regioes = dadosGlobais.brasil.regioes || {};
  const nomes = Object.keys(regioes);
  const gasolina = nomes.map(regiao => regioes[regiao].gasolina ?? 0);
  const diesel = nomes.map(regiao => regioes[regiao].diesel_s10 ?? 0);

  const contexto = document.getElementById("grafico-regioes");

  if (graficoRegioes) graficoRegioes.destroy();

  graficoRegioes = new Chart(contexto, {
    type: "bar",
    data: {
      labels: nomes,
      datasets: [
        {
          label: "Gasolina",
          data: gasolina,
          backgroundColor: "#38bdf8"
        },
        {
          label: "Diesel S10",
          data: diesel,
          backgroundColor: "#4ade80"
        }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: "#e2e8f0" } }
      },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } }
      }
    }
  });
}

function renderizarEstados() {
  const estados = dadosGlobais.brasil.estados || {};
  let html = `<table><thead><tr><th>Região</th><th>Estado</th><th>Gasolina</th><th>Diesel S10</th></tr></thead><tbody>`;

  Object.entries(estados).forEach(([regiao, lista]) => {
    Object.entries(lista).forEach(([estado, precos]) => {
      html += `
        <tr>
          <td>${regiao}</td>
          <td>${estado}</td>
          <td>${moeda(precos.gasolina)}</td>
          <td>${moeda(precos.diesel_s10)}</td>
        </tr>
      `;
    });
  });

  document.getElementById("tabela-estados").innerHTML = html + "</tbody></table>";
}

function renderizarMundo() {
  const mundo = dadosGlobais.mundo || [];
  const ordenado = [...mundo]
    .filter(pais => pais.gasolina)
    .sort((a, b) => b.gasolina - a.gasolina)
    .slice(0, 30);

  let html = `<table><thead><tr><th>País</th><th>Gasolina</th><th>Diesel</th><th>Moeda</th></tr></thead><tbody>`;

  ordenado.forEach(pais => {
    html += `
      <tr>
        <td>${pais.pais}</td>
        <td>${pais.gasolina ?? "—"}</td>
        <td>${pais.diesel ?? "—"}</td>
        <td>${pais.moeda ?? "—"}</td>
      </tr>
    `;
  });

  document.getElementById("tabela-mundo").innerHTML = html + "</tbody></table>";
}

function preencherFiltro() {
  const filtro = document.getElementById("filtro-regiao");
  const regioes = Object.keys(dadosGlobais.brasil.regioes || {});

  regioes.forEach(regiao => {
    const opcao = document.createElement("option");
    opcao.value = regiao;
    opcao.textContent = regiao;
    filtro.appendChild(opcao);
  });

  filtro.onchange = renderizarCardsBrasil;
}

async function carregarDados() {
  definirStatus("status-anp", "ANP: carregando", true);
  definirStatus("status-mundo", "Mundo: carregando", true);

  try {
    const resposta = await fetch("/api/precos");
    dadosGlobais = await resposta.json();

    const anpOk = dadosGlobais.status.anp === "ok";
    const mundoOk = dadosGlobais.status.mundo === "ok";

    definirStatus("status-anp", anpOk ? "ANP: conectado" : "ANP: indisponível", anpOk);
    definirStatus("status-mundo", mundoOk ? "Mundo: conectado" : "Mundo: indisponível", mundoOk);

    renderizarKpis(dadosGlobais.brasil);
    preencherFiltro();
    renderizarCardsBrasil();
    renderizarGrafico();
    renderizarEstados();
    renderizarMundo();
  } catch (erro) {
    definirStatus("status-anp", "ANP: erro", false);
    definirStatus("status-mundo", "Mundo: erro", false);
    console.error(erro);
  }
}

document.getElementById("btn-atualizar").onclick = carregarDados;
setInterval(carregarDados, 15 * 60 * 1000);

carregarDados();