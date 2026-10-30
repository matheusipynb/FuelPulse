"use strict";

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

  const controlador = new AbortController();
  const limite = setTimeout(() => controlador.abort(), 20000);
  const inicio = performance.now();

  try {
    const resposta = await fetch("/api/saude", {
      cache: "no-store",
      signal: controlador.signal
    });

    if (!resposta.ok) {
      throw new Error("HTTP " + resposta.status);
    }

    const dados = await resposta.json();

    if (dados.status !== "ok") {
      throw new Error("Status inesperado.");
    }

    el("situacao").textContent = "Servidor respondeu normalmente";

    linha(el("informacoes"), "Serviço", dados.servico);
    linha(el("informacoes"), "Versão", dados.versao);

    linha(
      el("informacoes"),
      "Tempo desta consulta",
      Math.round(performance.now() - inicio) + " ms"
    );

    linha(
      el("informacoes"),
      "Horário do servidor",
      new Date(dados.hora).toLocaleString("pt-BR")
    );

    Object.entries(dados.fontes).forEach(([nome, info]) => {
      linha(
        el("fontes"),
        nome === "brasil" ? "Série nacional" : "Série estadual",
        info.em_cache
          ? "Em memória · " +
            new Date(info.consultado_em).toLocaleString("pt-BR")
          : "Sem cache nesta instância"
      );
    });
  } catch (erro) {
    el("situacao").className = "status erro";
    el("situacao").textContent = erro.name === "AbortError"
      ? "Tempo limite excedido nesta consulta."
      : "Não foi possível confirmar o funcionamento: " + erro.message;
  } finally {
    clearTimeout(limite);
    el("verificar").disabled = false;
  }
}

el("verificar").addEventListener("click", verificar);
verificar();