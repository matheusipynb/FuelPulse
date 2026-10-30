import io
import math
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timezone

import openpyxl
import requests


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


def agora():
    return datetime.now(timezone.utc).isoformat()


def normalizar(valor):
    if valor is None:
        return ""

    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper().replace("-", " ")
    return re.sub(r"s+", " ", texto).strip()


NOMES_UF = {
    normalizar(nome): uf
    for uf, nome in ESTADOS.items()
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
        for formato in (
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(valor.strip(), formato).date()
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
        headers={"User-Agent": "FuelPulse/3.0"},
    )
    resposta.raise_for_status()

    if resposta.content[:2] != b"PK":
        raise ValueError(
            "A ANP não retornou uma planilha XLSX válida. "
            "Pode haver indisponibilidade temporária."
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
                    estado = normalizar(campo("estado"))
                    uf = estado if estado in ESTADOS else NOMES_UF.get(estado)

                    if not uf:
                        continue

                    local = ESTADOS[uf]
                else:
                    uf = "BR"
                    local = "Brasil"

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
            "Nenhum preço reconhecido na planilha. "
            "O formato ou os cabeçalhos da ANP podem ter mudado."
        )

    return {
        "fonte": "ANP — Levantamento de Preços de Combustíveis",
        "arquivo": url,
        "abrangencia": abrangencia,
        "consultado_em": agora(),
        "fim_pesquisa": ultima_data.isoformat(),
        "registros": sorted(
            registros.values(),
            key=lambda registro: (
                registro["local"],
                registro["produto"],
            ),
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
                        "Exibindo o último resultado desta instância."
                    ),
                )
            raise


def status_cache():
    resultado = {}

    for chave in FONTES:
        item = CACHE.get(chave)

        resultado[chave] = {
            "em_cache": item is not None,
            "consultado_em": (
                item["dados"]["consultado_em"] if item else None
            ),
        }

    return resultado