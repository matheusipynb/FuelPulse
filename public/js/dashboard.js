let graficoRegioes = null;

const nomes = {
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

function status(texto, ok) {
  const elemento = document.getElementById("status");
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

function renderizarBrasil(dados) {
  const container = document.getElementById("cards-brasil");
  container.innerHTML = "";

  Object.entries(dados.brasil.nacional).forEach(([chave, valor], indice) => {
    const card = criarCard(
      nomes[chave] || chave,
      moeda(valor),
      "Preço médio nacional",
      () => abrirModal(nomes[chave] || chave, `
        <p><strong>Preço nacional:</strong> ${moeda(valor)}</p>
        <p><strong>Atualizado:</strong> ${new Date(dados.atualizado_em).toLocaleString("pt-BR")}</p>
        <p><strong>Fonte:</strong> ANP / base demonstrativa</p>
      `)
    );

    card.style.animationDelay = `${indice * 0.08}s`;
    container.appendChild(card);
  });
}

function renderizarGrafico(dados) {
  const regioes = dados.brasil.regioes;
  const labels = Object.keys(regioes);
  const gasolina = labels.map(regiao => regioes[regiao].gasolina);
  const diesel = labels.map(regiao => regioes[regiao].diesel_s10);

  const contexto = document.getElementById("grafico-regioes");

  if (graficoRegioes) graficoRegioes.destroy();

  graficoRegioes = new Chart(contexto, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Gasolina", data: gasolina, backgroundColor: "#38bdf8" },
        { label: "Diesel S10", data: diesel, backgroundColor: "#4ade80" }
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

function renderizarMundo(dados) {
  const mundo = [...(dados.mundo || [])]
    .filter(pais => pais.gasolina)
    .sort((a, b) => b.gasolina - a.gasolina)
    .slice(0, 25);

  let html = `
    <table>
      <thead>
        <tr>
          <th>País</th>
          <th>Gasolina</th>
          <th>Diesel</th>
          <th>Moeda</th>
        </tr>
      </thead>
      <tbody>
  `;

  mundo.forEach(pais => {
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

async function carregar() {
  status("Atualizando...", true);

  try {
    const resposta = await fetch("/api/precos");
    const dados = await resposta.json();

    status("Atualizado automaticamente", true);

    renderizarBrasil(dados);
    renderizarGrafico(dados);
    renderizarMundo(dados);
  } catch (erro) {
    status("Erro ao atualizar", false);
    console.error(erro);
  }
}

document.getElementById("btn-atualizar").onclick = carregar;
setInterval(carregar, 15 * 60 * 1000);

carregar();