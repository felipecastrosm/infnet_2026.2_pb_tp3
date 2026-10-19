# Metodologia: CRISP-DM e TDSP aplicados ao Solar Viável

O projeto segue o **TDSP** (Team Data Science Process) como processo de gestão do
projeto e usa as práticas analíticas do **CRISP-DM** (Cross-Industry Standard Process for
Data Mining) dentro de cada fase. Os dois métodos têm fases correspondentes, em
granularidades diferentes: o TDSP acrescenta, em torno das mesmas fases analíticas do
CRISP-DM, preocupações de gestão de equipe e de infraestrutura.

## Tabela de correspondência

| CRISP-DM | TDSP | Diretório no repositório | Status no TP3 |
|---|---|---|---|
| Business Understanding | Business Understanding | `docs/project/project_charter.md`, `docs/methodology.md` | Revisado: problema reavaliado com FastAPI, Selenium e LLM |
| Data Understanding | Data Acquisition and Understanding | `src/data_acquisition/`, `data/raw/`, `docs/data_report/data_summary_report.md` | Ampliado: Selenium (CRESESB), texto completo das notícias, coletas acumuladas |
| Data Preparation | Data Acquisition and Understanding | `src/data_processing/`, `src/repositorio.py`, `data/processed/` | Ampliado: corpus para LLM, validação na API, geração mês a mês |
| Modeling | Modeling | `src/data_processing/climate.py`, `src/data_processing/llm_prep.py` | Estimativa com longo prazo e inclinação; recursos com LLM planejados (`docs/llm_planejamento.md`) |
| Evaluation | Modeling / Model Evaluation | `tests/`, `docs/llm_planejamento.md` | Comparação NASA x CRESESB; plano de avaliação dos recursos com LLM |
| Deployment | Deployment | `app.py`, `paginas/`, `src/api/`, `requirements.txt` | App com múltiplas páginas + API FastAPI |
| (sem equivalente) | Customer Acceptance | (sem equivalente) | Não iniciado |

## Como cada fase se aplica a este projeto

**Business Understanding.** Definição do problema (falta de acesso a diagnóstico de
viabilidade solar para residências e pequenos negócios), dos ODS 7 e 13, do público-alvo e
das metas. No TP3 o problema foi reavaliado à luz das novas ferramentas: estimar com um
único ano e com o painel deitado podia enganar o usuário, e os dados ficavam presos à
interface. As metas foram ajustadas (seção 2.1 do [Project Charter](project/project_charter.md)).

**Data Acquisition and Understanding.** NASA POWER (requests), ABSOLAR e Canal Solar
(Beautiful Soup, agora com o texto completo das matérias e coletas acumuladas) e, no
TP3, o **SunData do CRESESB com Selenium**. Essa página exige preencher um formulário
cujo envio depende de JavaScript. As coletas rodam fora do app e salvam CSV/TXT em
`data/raw/`. Fontes, dicionários, estatísticas e limitações estão no
[Data Summary Report](data_report/data_summary_report.md).

**Data Preparation.** Conversão de `-999` em `NaN`; validação de medições do usuário no app
e de novo na API (Pydantic); tokenização e stopwords em português; e, no TP3, a preparação
para LLM: divisão das matérias em trechos com sobreposição e geração de fichas de local em
texto a partir dos números (`src/data_processing/llm_prep.py`).

**Modeling.** A estimativa de geração (irradiância x kWp x desempenho) passou a usar, por
padrão, o **ano típico do CRESESB com a inclinação de maior média anual**, somando a
geração mês a mês (`climate.geracao_mensal`). Os recursos com LLM (perguntas e respostas,
resumo, sentimento e relatório) estão planejados em [Planejamento de IA](llm_planejamento.md).

**Evaluation.** O app e o relatório comparam o último ano (NASA) com o longo prazo
(CRESESB): as diferenças chegaram a +11% (Recife, Manaus) e −5% (Rio), o que justificou a
mudança da estimativa padrão. Para o TP4 estão previstas avaliações com conjuntos de
perguntas de teste e notícias rotuladas à mão. Os 44 testes automatizados cobrem a API,
os parsers dos scrapers (com HTML salvo), a preparação para LLM e as páginas do app.

**Deployment.** Arquitetura em duas camadas: a **API FastAPI** (`src/api/`) serve dados e
cálculos, e o **app Streamlit com 7 páginas** (`app.py` + `paginas/`, com menu
`st.navigation`) os consome por HTTP. No deploy de processo único (Streamlit Community
Cloud), o app sobe a própria API em uma thread. Dependências fixadas em
`requirements.txt` e versionamento com Git.

**Customer Acceptance.** Validação com usuários do público-alvo (residencial e pequenos
negócios), planejada para a entrega final.
