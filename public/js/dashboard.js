"use strict";

const el = id => document.getElementById(id);
const memoria = {};
const pedidos = {};

let sequencia = 0;

/* Estilos exclusivos do indicador de carregamento. */

const estilosCarregamento = document.createElement("style");

estilosCarregamento.textContent = `
  .status.carregando {
    position: relative;
    padding-left: 46px;
  }

  .status.carregando::before {
    content: "";
    position: absolute;
    left: 16px;
    top: 50%;

    width: 16px;
    height: 16px;
    margin-top: -8px;

    box-sizing: border-box;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;

    animation: fuelpulse-girar .75s linear infinite;
  }

  @keyframes fuelpulse-girar {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .status.carregando::before {
      animation: none !important;
    }
  }
`;

document.head.append(estilosCarregamento);

/* Utilitários. */

function criar(tag, conteudo, classe) {
  const elemento = document.createElement(tag);
  elemento.textContent = conteudo;

  if (classe) {
    elemento.className = classe;
  }

  return elemento;
}

function valor(numero) {
  return numero == null
    ? "—"
    : Number(numero).toLocaleString("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 3
      });
}

function dia(iso) {
  if (!iso) {
    return "—";
  }

  const partes = iso.split("-");

  return partes.length === 3
    ? partes.reverse().join("/")
    : iso;
}

function periodo(registro) {
  return dia(registro.inicio) + " a " + dia(registro.fim);
}

function mensagem(id, texto, erro = false, carregando = false) {
  const elemento = el(id);

  elemento.textContent = texto;
  elemento.className = "status";

  if (erro) {
    elemento.classList.add("erro");
  }

  if (carregando) {
    elemento.classList.add("carregando");
  }
}

/* Consulta à API, evitando requisições simultâneas da mesma série. */

async function buscar(tipo) {
  if (pedidos[tipo]) {
    return pedidos[tipo];
  }

  pedidos[tipo] = (async () => {
    const resposta = await fetch(
      "/api/precos?abrangencia=" + encodeURIComponent(tipo),
      {
        cache: "no-store"
      }
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
        (dados.erro || "Falha na consulta.") +
        " " +
        (dados.detalhe || "")
      );
    }

    if (!Array.isArray(dados.registros)) {
      throw new Error(
        "A resposta não contém uma lista válida de preços."
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

/* Detalhes do combustível. */

function mostrarDetalhes(registro) {
  el("modal-titulo").textContent = registro.produto;
  el("modal-conteudo").replaceChildren();

  const itens = [
    ["Localidade", registro.local],
    ["Preço médio", valor(registro.medio)],
    ["Preço mínimo", valor(registro.minimo)],
    ["Preço máximo", valor(registro.maximo)],
    ["Unidade", registro.unidade],
    [
      "Postos pesquisados",
      registro.postos == null
        ? "—"
        : Math.round(registro.postos).toLocaleString("pt-BR")
    ],
    ["Pesquisa", periodo(registro)],
    ["Fonte", "ANP"]
  ];

  itens.forEach(([rotulo, conteudo]) => {
    const linha = criar("div", "", "linha");

    linha.append(
      criar("span", rotulo),
      criar("span", conteudo)
    );

    el("modal-conteudo").append(linha);
  });

  el("modal").showModal();
}

/* Cards. */

function renderizarCards(dados, uf) {
  el("cards").replaceChildren();

  const registros = dados.registros.filter(
    registro => registro.uf === uf
  );

  if (!registros.length) {
    mensagem(
      "status",
      "Nenhum preço disponível para esta localidade na pesquisa mais recente.",
      true
    );

    return;
  }

  registros.forEach((registro, indice) => {
    const card = criar("button", "", "card");

    card.type = "button";
    card.style.animationDelay = `${indice * 0.04}s`;

    card.append(
      criar("div", registro.produto.charAt(0), "icone"),
      criar("h3", registro.produto),
      criar("div", valor(registro.medio), "preco"),
      criar("div", registro.unidade, "unidade"),
      criar(
        "div",
        "Ver detalhes e período ↗",
        "card-nota"
      )
    );

    card.addEventListener("click", () => {
      mostrarDetalhes(registro);
    });

    el("cards").append(card);
  });

  const primeiro = registros[0];

  mensagem(
    "status",
    dados.desatualizado
      ? dados.aviso
      : primeiro.local + " · Pesquisa: " + periodo(primeiro),
    Boolean(dados.desatualizado)
  );

  el("referencia").textContent =
    "Fonte: ANP · Fim da pesquisa: " +
    dia(primeiro.fim) +
    " · Consulta ao provedor: " +
    new Date(dados.consultado_em).toLocaleString("pt-BR");

  el("arquivo").href = dados.arquivo;
  el("arquivo").hidden = false;
}

/* Consulta da localidade selecionada. */

async function carregarLocal() {
  const id = ++sequencia;
  const uf = el("local").value;
  const tipo = uf === "BR" ? "brasil" : "estados";

  el("cards").replaceChildren();
  el("cards").setAttribute("aria-busy", "true");

  el("referencia").textContent = "";
  el("arquivo").hidden = true;
  el("diagnostico").hidden = true;
  el("consultar").disabled = true;

  mensagem(
    "status",
    tipo === "estados"
      ? "Lendo a série estadual da ANP. A primeira consulta pode demorar..."
      : "Consultando a série nacional da ANP. Aguarde...",
    false,
    true
  );

  try {
    const dados = await buscar(tipo);

    if (id !== sequencia) {
      return;
    }

    renderizarCards(dados, uf);

    if (memoria.estados && !el("comparar").disabled) {
      renderizarTabela();
    }
  } catch (erro) {
    if (id !== sequencia) {
      return;
    }

    mensagem(
      "status",
      "Não foi possível carregar os preços.",
      true
    );

    el("erro").textContent = erro.message;
    el("diagnostico").hidden = false;
  } finally {
    if (id === sequencia) {
      el("consultar").disabled = false;
      el("cards").setAttribute("aria-busy", "false");
    }
  }
}

/* Tabela comparativa. */

function renderizarTabela() {
  const dados = memoria.estados;

  if (!dados) {
    return;
  }

  const produto = el("produto").value;

  const registros = dados.registros
    .filter(registro => registro.produto === produto)
    .sort((a, b) => a.medio - b.medio);

  el("tabela").replaceChildren();

  if (!registros.length) {
    mensagem(
      "status-estados",
      "Sem dados para este combustível no último período.",
      true
    );

    return;
  }

  registros.forEach(registro => {
    const linha = document.createElement("tr");

    if (registro.uf === el("local").value) {
      linha.className = "selecionado";
    }

    [
      registro.local + " · " + registro.uf,
      valor(registro.medio),
      valor(registro.minimo),
      valor(registro.maximo),
      registro.unidade
    ].forEach(conteudo => {
      linha.append(criar("td", conteudo));
    });

    el("tabela").append(linha);
  });

  mensagem(
    "status-estados",
    (dados.desatualizado ? dados.aviso + " " : "") +
    produto +
    " · Pesquisa: " +
    periodo(registros[0]) +
    " · " +
    registros.length +
    " unidades da federação com dados",
    Boolean(dados.desatualizado)
  );
}

/* Consulta estadual para comparação. */

async function carregarComparacao() {
  if (el("comparar").disabled) {
    return;
  }

  el("comparar").disabled = true;
  el("tabela").setAttribute("aria-busy", "true");

  mensagem(
    "status-estados",
    "Consultando os estados na ANP. Preparando a comparação...",
    false,
    true
  );

  try {
    await buscar("estados");
    renderizarTabela();
  } catch (erro) {
    mensagem(
      "status-estados",
      erro.message +
      (el("tabela").children.length
        ? " A tabela anterior foi mantida."
        : ""),
      true
    );
  } finally {
    el("comparar").disabled = false;
    el("tabela").setAttribute("aria-busy", "false");
  }
}

/* Eventos da interface. */

el("local").addEventListener("change", carregarLocal);

el("consultar").addEventListener("click", carregarLocal);

el("comparar").addEventListener("click", carregarComparacao);

el("produto").addEventListener("change", () => {
  if (!el("comparar").disabled) {
    renderizarTabela();
  }
});

el("fechar").addEventListener("click", () => {
  el("modal").close();
});

el("modal").addEventListener("click", evento => {
  const area = el("modal").getBoundingClientRect();

  if (
    evento.clientX < area.left ||
    evento.clientX > area.right ||
    evento.clientY < area.top ||
    evento.clientY > area.bottom
  ) {
    el("modal").close();
  }
});

/* Primeira consulta e atualização periódica. */

carregarLocal();

setInterval(() => {
  if (document.hidden) {
    return;
  }

  carregarLocal();

  if (memoria.estados && el("local").value === "BR") {
    carregarComparacao();
  }
}, 15 * 60 * 1000);