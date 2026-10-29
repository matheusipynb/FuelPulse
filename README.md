# ⛽ FuelPulse Brasil

Dashboard de preços de combustíveis no Brasil, com consulta nacional e por estado, incluindo o Distrito Federal.

O projeto utiliza dados públicos da Agência Nacional do Petróleo, Gás Natural e Biocombustíveis (ANP) para apresentar preços de revenda em uma interface responsiva, com tema azul-claro, cards interativos e comparação entre unidades da federação.

🌐 **Acesse o projeto:** https://fuelpulse-sand.vercel.app/

---

## 📋 Sobre o projeto

O FuelPulse Brasil foi desenvolvido para facilitar a consulta aos preços dos combustíveis e tornar mais clara a interpretação dos dados publicados pela ANP.

O painel apresenta a média nacional e os valores estaduais, preservando a identificação da fonte, a unidade de medida e o período da pesquisa.

A aplicação não utiliza preços fictícios como alternativa a uma falha de integração. Quando os dados não estão disponíveis, o painel informa o problema.

## ✨ Funcionalidades

- Consulta à média nacional de preços.
- Seleção de estados e Distrito Federal.
- Cards interativos por combustível.
- Detalhamento de preço médio, mínimo e máximo.
- Exibição do número de postos pesquisados, quando disponível.
- Comparação entre estados, ordenada pelo menor preço médio.
- Identificação do período da pesquisa.
- Link para o arquivo oficial utilizado na consulta.
- Consulta periódica enquanto a página está aberta.
- Cache temporário em memória.
- Página visual de status da aplicação.
- API com respostas em JSON.
- Layout responsivo com tema azul-claro.
- Tratamento de erros de consulta e leitura dos arquivos.

## 🛢️ Combustíveis

Conforme a disponibilidade na pesquisa da ANP, o painel pode apresentar:

- Gasolina comum.
- Gasolina aditivada.
- Diesel S10.
- Diesel S500.
- Etanol hidratado.
- Gás Natural Veicular (GNV).
- Gás Liquefeito de Petróleo (GLP).

> A disponibilidade pode variar conforme o combustível, a localidade e o período pesquisado. As unidades de GLP e GNV podem ser diferentes das utilizadas para os combustíveis líquidos.

## 🧰 Tecnologias

| Tecnologia | Utilização |
|---|---|
| Python | Backend e processamento dos dados |
| Flask | Rotas web e API |
| Requests | Download dos arquivos da ANP |
| OpenPyXL | Leitura das planilhas XLSX |
| HTML | Estrutura da interface |
| CSS | Tema, responsividade e animações |
| JavaScript | Consultas à API e interação com o painel |
| Git e GitHub | Controle de versão |
| Vercel | Hospedagem da aplicação |

O projeto foi desenvolvido com apoio da IDE Spck no Android.

## 📁 Estrutura

A versão atual concentra o backend, o HTML, o CSS e o JavaScript no arquivo `app.py`.

```text
fuelpulse-dashboard/
├── app.py
├── requirements.txt
├── vercel.json
└── README.md
```

### Arquivos principais

- `app.py`: integração com a ANP, processamento das planilhas, cache, rotas e interface.
- `requirements.txt`: dependências Python.
- `vercel.json`: configuração do framework na Vercel.
- `README.md`: documentação do projeto.

> Pastas como `templates/` e `public/`, caso estejam presentes no repositório por causa de versões anteriores, não são utilizadas por esta implementação.

## 📊 Fonte dos dados

Os preços são obtidos das séries históricas semanais disponibilizadas pela ANP.

### Série nacional

https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/shlp/semanal/semanal-brasil-desde-2013.xlsx

### Série estadual

https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/shlp/semanal/semanal-estados-desde-2013.xlsx

### Como os valores são selecionados

1. A aplicação baixa o arquivo da abrangência solicitada.
2. Identifica os cabeçalhos da planilha.
3. Percorre os registros e identifica a data final mais recente reconhecida.
4. Mantém os registros desse período.
5. Disponibiliza os resultados para a interface por meio da API.

A média nacional é lida diretamente do arquivo nacional. Ela não é calculada como uma média simples dos preços dos estados.

## 🔄 Atualização e cache

### Consulta à fonte

O download e o processamento acontecem sob demanda, quando a aplicação recebe uma consulta e não há um cache válido.

### Cache do servidor

Os resultados permanecem em memória por até **seis horas por instância**.

Durante esse intervalo, novas consultas podem reutilizar os dados já processados, sem baixar novamente a planilha.

### Consulta no navegador

Enquanto a página está aberta e visível, o painel consulta novamente os dados a cada **15 minutos**, respeitando o cache do servidor.

### Limitações importantes

- Não existe uma tarefa agendada de coleta nesta versão.
- O cache não é um banco de dados.
- O cache pode desaparecer quando a instância é reiniciada.
- Instâncias diferentes podem ter caches diferentes.
- O botão de consulta não ignora o prazo de validade do cache.
- A atualização depende da publicação dos arquivos pela ANP.
- Consultar o servidor não significa que uma nova pesquisa de preços foi publicada.

> O período da pesquisa e o horário de consulta ao provedor são informações diferentes. Verifique sempre a referência apresentada no painel.

## 🚀 Executar localmente

### Pré-requisitos

- Python com suporte às versões das dependências em `requirements.txt`.
- Pip.
- Conexão com a internet para consultar os arquivos da ANP.

### 1. Obtenha o código

Clone o repositório pelo endereço informado no botão **Code** do GitHub ou baixe o projeto como ZIP.

Abra um terminal na pasta que contém `app.py`.

### 2. Crie um ambiente virtual

```bash
python -m venv .venv
```

### 3. Ative o ambiente

Linux e macOS:

```bash
source .venv/bin/activate
```

Windows — Prompt de Comando:

```bat
.venvScriptsactivate.bat
```

Windows — PowerShell:

```powershell
.venvScriptsActivate.ps1
```

### 4. Instale as dependências

```bash
pip install -r requirements.txt
```

### 5. Inicie o servidor

```bash
python app.py
```

Acesse:

```text
http://127.0.0.1:5000
```

> O servidor iniciado por `python app.py` utiliza o modo de depuração para desenvolvimento local. Não o exponha diretamente como servidor público de produção.

## ☁️ Deploy na Vercel

1. Envie o projeto para um repositório no GitHub.
2. Importe o repositório na Vercel.
3. Selecione o framework Flask, caso necessário.
4. Confira se a Root Directory aponta para a pasta que contém `app.py`.
5. Mantenha `requirements.txt` e `vercel.json` nessa mesma pasta.
6. Inicie o deployment.
7. Após a publicação, teste a página inicial e as rotas da API.

A versão atual não exige uma chave de API nem variáveis de ambiente.

### Configuração utilizada

```json
{
  "$schema": "[https://openapi.vercel.sh/vercel.json](https://openapi.vercel.sh/vercel.json)",
  "framework": "flask"
}
```

## 🔌 Rotas

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Dashboard principal |
| GET | `/status` | Página visual de status |
| GET | `/api/saude` | Informações básicas da aplicação em JSON |
| GET | `/api/precos?abrangencia=brasil` | Último período reconhecido no arquivo nacional |
| GET | `/api/precos?abrangencia=estados` | Último período reconhecido no arquivo estadual |

### Consulta nacional

```text
[https://fuelpulse-sand.vercel.app/api/precos?abrangencia=brasil](https://fuelpulse-sand.vercel.app/api/precos?abrangencia=brasil)
```

### Consulta estadual

```text
[https://fuelpulse-sand.vercel.app/api/precos?abrangencia=estados](https://fuelpulse-sand.vercel.app/api/precos?abrangencia=estados)
```

A rota estadual retorna os registros disponíveis de todas as unidades da federação no período selecionado. A interface filtra o estado escolhido.

### Parâmetro inválido

Um valor de `abrangencia` diferente de `brasil` ou `estados` retorna HTTP `400`.

### Falha de integração

Quando não existe cache disponível e a consulta ou leitura da fonte falha, a API retorna HTTP `503` com uma mensagem de erro.

## 🩺 Página de status

A página `/status` apresenta:

- Nome do serviço.
- Versão do backend.
- Tempo da consulta à rota de saúde.
- Horário informado pelo servidor.
- Presença de cache nacional e estadual na instância consultada.

> A rota de saúde não baixa as planilhas. Servidor online não garante disponibilidade da ANP nem sucesso na consulta de preços.

## ⚠️ Limitações

- O projeto depende da disponibilidade dos arquivos públicos da ANP.
- Mudanças nos endereços, cabeçalhos ou formatos podem exigir ajustes.
- A primeira consulta estadual pode demorar devido ao tamanho da série histórica.
- Downloads e processamento podem atingir os limites de execução da hospedagem.
- Os arquivos nacional e estadual podem conter períodos diferentes.
- Nem todos os combustíveis possuem dados em todas as localidades.
- Não há consulta individual de postos ou pesquisa por município.
- Não há conversão de moedas ou preços internacionais.
- Não há histórico persistente, alertas ou cálculo de variação semanal.
- Os valores apresentados são resultados da pesquisa da ANP, não uma garantia do preço encontrado em qualquer posto.

## 🛠️ Solução de problemas

### Os preços não carregam

1. Abra **Detalhes da integração** no dashboard.
2. Confira a mensagem retornada.
3. Teste diretamente a rota `/api/precos`.
4. Verifique os Runtime Logs na Vercel.

### A consulta estadual demora ou excede o tempo limite

O arquivo estadual contém uma série histórica extensa.

Uma melhoria de arquitetura é processar os arquivos em uma tarefa agendada, salvar um JSON compacto em armazenamento persistente e disponibilizar esse resultado ao dashboard.

Essa melhoria ainda não está implementada.

### A pesquisa parece antiga

Confira o período informado pelo painel e o arquivo oficial da ANP.

O cache pode permanecer válido por até seis horas, e a fonte pode ainda não conter uma nova publicação.

### O cache não aparece na página de status

O cache é local a cada instância. A página de status pode ter sido atendida por uma instância diferente ou recém-iniciada.

## 🗺️ Melhorias futuras

- [ ] Processamento agendado fora da requisição web.
- [ ] Armazenamento persistente dos dados processados.
- [ ] Histórico de preços com gráficos.
- [ ] Comparação entre períodos equivalentes.
- [ ] Exportação de consultas em CSV.
- [ ] Testes automatizados para os formatos da ANP.
- [ ] Separação do HTML, CSS e JavaScript em arquivos próprios.
- [ ] Monitoramento de falhas e da idade dos dados.

## 👨‍💻 Autor

Desenvolvido por **Matheus dos Santos**.

## 📌 Aviso

O FuelPulse Brasil é um projeto independente e não possui vínculo institucional com a ANP.

A agência é a fonte dos dados utilizados. Consulte os arquivos oficiais para verificar os valores, a cobertura e o período da pesquisa.