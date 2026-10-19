# Solar Viável

App e API de avaliação de potencial de geração solar fotovoltaica para residências e
pequenos negócios no Brasil. Combina dados climáticos da
[NASA POWER API](https://power.larc.nasa.gov/), a irradiação de longo prazo do
[SunData (CRESESB/CEPEL)](https://cresesb.cepel.br/index.php?section=sundata), coletada com
Selenium, notícias do setor extraídas com Beautiful Soup (ABSOLAR e Canal Solar) e dados
enviados pelo próprio usuário. Projeto acadêmico (Projeto de Bloco, Infnet), alinhado ao
ODS 7 (Energia limpa e acessível) e ao ODS 13 (Ação contra a mudança global do clima).

Iniciativas que inspiraram o projeto: Atlas Brasileiro de Energia Solar (INPE), SunData (CRESESB), Global Solar Atlas, PVWatts, PVGIS, ANEEL e ABSOLAR (links no app e no Project Charter, seção 9.1).

Documentação: [Project Charter](docs/project/project_charter.md) ·
[Data Summary Report](docs/data_report/data_summary_report.md) ·
[API](docs/api.md) ·
[Planejamento de IA (LLM)](docs/llm_planejamento.md) ·
[Metodologia (CRISP-DM x TDSP)](docs/methodology.md)

## Novidades do TP3

| Requisito | Como foi atendido | Onde |
|---|---|---|
| Múltiplas páginas com menu de navegação | 7 páginas em 4 seções (`st.navigation`); parâmetros da barra lateral preservados ao trocar de página | `app.py`, `paginas/`, `src/ui.py` |
| API com FastAPI (GET e POST), documentada | 15 rotas: locais, clima, consulta ao vivo, longo prazo, estimativa, notícias, medições (POST/GET/DELETE) e LLM; Swagger em `/docs` | `src/api/`, [docs/api.md](docs/api.md) |
| Aplicação integrada à API | O app não lê `data/` diretamente: todas as páginas consultam e enviam dados por HTTP; a página *Explorar a API* testa qualquer rota | `src/api_client.py`, `paginas/` |
| Web scraping de página dinâmica (Selenium) | Preenche o formulário do SunData (envio por JavaScript) para as 10 capitais | `src/data_acquisition/cresesb_sundata.py` → `data/raw/cresesb_sundata_capitais.csv` |
| Mais dados com Beautiful Soup | Texto completo, data e tags das matérias do Canal Solar; coletas acumuladas (54 notícias, 51 com texto) | `src/data_acquisition/canalsolar_scraper.py`, `absolar_scraper.py` |
| Documentação atualizada | Charter (problema reavaliado, metas, escopo, riscos) e Data Summary Report (novas fontes) | `docs/` |
| Preparação para LLM | Corpus em trechos + fichas de local, recuperação de contexto e prompt; plano dos casos de uso | `src/data_processing/llm_prep.py`, `paginas/ia.py`, [docs/llm_planejamento.md](docs/llm_planejamento.md) |

## Páginas do app

| Seção | Página | O que faz | Rotas da API |
|---|---|---|---|
| Projeto | Início | Problema, objetivo, arquitetura e inspirações | n/a |
| Análises | Clima e geração | Compara locais e períodos; estima geração e economia; consulta ao vivo | `/locais`, `/clima`, `/clima/ao-vivo` |
| Análises | Potencial de longo prazo | Ano típico mês a mês, efeito da inclinação, NASA x CRESESB | `/irradiacao-longo-prazo`, `/estimativa`, `/clima/resumo` |
| Análises | Notícias do setor | Nuvem de palavras, frequências, publicações por semana, manchetes e textos | `/noticias` |
| Dados | Meus dados | Envio de CSV ou medição avulsa, gestão das medições e downloads | `POST/GET/DELETE /medicoes` e outras |
| Dados | Explorar a API | Lista as rotas (OpenAPI) e envia requisições | todas |
| IA | Rumo à IA (LLM) | Corpus, casos de uso planejados e demonstração da recuperação de contexto | `/llm/corpus`, `/llm/contexto` |

## Estrutura do projeto

```
.
├── app.py                                   # entrada do Streamlit: menu de navegação e conexão com a API
├── paginas/                                 # uma página por funcionalidade
├── requirements.txt / requirements-dev.txt
├── .streamlit/config.toml
├── docs/
│   ├── api.md                               # rotas da API
│   ├── llm_planejamento.md                  # plano de uso de LLMs (TP4)
│   ├── methodology.md                       # CRISP-DM x TDSP
│   ├── project/project_charter.md
│   └── data_report/data_summary_report.md
├── data/
│   ├── raw/                                 # dados coletados (NASA, CRESESB, notícias)
│   └── processed/                           # corpus para LLM (e medições enviadas, fora do Git)
├── src/
│   ├── api/                                 # FastAPI: main.py (rotas), schemas.py (Pydantic)
│   ├── api_client.py                        # cliente HTTP usado pelo app
│   ├── repositorio.py                       # leitura/gravação dos arquivos de dados (usado pela API)
│   ├── ui.py                                # funções comuns às páginas (cache, barra lateral)
│   ├── locations.py                         # capitais usadas nas coletas
│   ├── data_acquisition/                    # nasa_power_client, cresesb_sundata (Selenium), absolar_scraper, canalsolar_scraper
│   └── data_processing/                     # climate.py, text.py, llm_prep.py
└── tests/                                   # API, parsers (fixtures HTML), LLM e páginas do app
```

## Ambiente de desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate        # Windows (git bash): source .venv/Scripts/activate
pip install -r requirements-dev.txt
```

O scraper com Selenium precisa do Google Chrome instalado. O chromedriver é baixado
automaticamente pelo Selenium Manager.

## Como rodar

API e app em dois terminais:

```bash
uvicorn src.api.main:app --reload            # API em http://127.0.0.1:8000 (Swagger em /docs)
streamlit run app.py                         # app em http://localhost:8501
```

Rodar só o `streamlit run app.py` também funciona: se não encontrar a API em
`SOLAR_API_URL` (padrão `http://127.0.0.1:8000`), o app a inicia em uma thread.

Coleta de dados (scripts independentes do app; rode a partir da raiz do projeto):

```bash
python src/data_acquisition/nasa_power_client.py             # 10 capitais, últimos 365 dias
python -m src.data_acquisition.cresesb_sundata               # Selenium: longo prazo (use --mostrar para ver o Chrome)
python -m src.data_acquisition.absolar_scraper               # notícias + texto completo (acumula)
python -m src.data_acquisition.canalsolar_scraper            # notícias + texto completo (acumula)
python -m src.data_processing.llm_prep                       # regera o corpus para LLM
```

Testes:

```bash
pytest
```

## Deploy (Streamlit Community Cloud)

Aponte o [share.streamlit.io](https://share.streamlit.io) para este repositório, branch
`main` e arquivo principal `app.py`. Como o Community Cloud roda um único processo, o app
sobe a API FastAPI internamente e continua consumindo-a por HTTP. Para usar uma API
hospedada à parte, defina a variável de ambiente `SOLAR_API_URL`.

## Fluxo de Git

Branch `main` estável, commits pequenos e descritivos por funcionalidade
(scraping, API, páginas, documentação).
