# Data Summary Report: Solar Viável (TP3)

Este relatório descreve as fontes de dados do projeto, como foram coletadas, seu
conteúdo, sua qualidade e o objetivo de uso de cada uma no aplicativo e na API.

> **O que mudou no TP3:** nova fonte coletada com **Selenium** (CRESESB/SunData, seção 3);
> Canal Solar com **texto completo** das matérias, data de publicação e tags (seção 5);
> coletas de notícias **acumuladas** entre execuções; medições do usuário agora
> **enviadas pela API** e guardadas (seção 6); novo **corpus para LLM** (seção 7); NASA
> POWER atualizada até 17/10/2026; e todos os dados passam a ser servidos pela **API
> FastAPI** (seção 8).

## 1. Visão geral das fontes

| # | Fonte | Tipo | Como é obtida | Arquivo | Uso |
|---|---|---|---|---|---|
| 1 | NASA POWER API | Série temporal diária (API JSON) | `src/data_acquisition/nasa_power_client.py` (requests) | `data/raw/nasa_power_capitais.csv` (e `sample_nasa_power.csv`, do TP1) | Página *Clima e geração*; rotas `/locais`, `/clima`, `/clima/resumo`, `/clima/ao-vivo`, `/estimativa?fonte=nasa` |
| 2 | **CRESESB/SunData (TP3)** | Médias mensais de longo prazo (página dinâmica com formulário) | `src/data_acquisition/cresesb_sundata.py` (**Selenium** + Beautiful Soup) | `data/raw/cresesb_sundata_capitais.csv` | Página *Potencial de longo prazo*; rotas `/irradiacao-longo-prazo`, `/estimativa` (padrão) |
| 3 | ABSOLAR, notícias | Texto semiestruturado (HTML) | `src/data_acquisition/absolar_scraper.py` (Beautiful Soup) | `data/raw/absolar_noticias.csv`, `absolar_corpus.txt` | Página *Notícias*; rota `/noticias`; corpus LLM |
| 4 | Canal Solar, notícias | Texto semiestruturado (HTML) | `src/data_acquisition/canalsolar_scraper.py` (Beautiful Soup) | `data/raw/canalsolar_noticias.csv`, **`canalsolar_corpus.txt` (TP3)** | Página *Notícias*; rota `/noticias`; corpus LLM |
| 5 | Medições do usuário | Série temporal (CSV ou formulário) | Página *Meus dados* → `POST /medicoes` | `data/processed/medicoes_usuarios.csv` (fora do Git) | Aparecem como locais em `/locais` e `/clima` |
| 6 | **Corpus para LLM (TP3)** | Documentos de texto (derivado) | `src/data_processing/llm_prep.py` | `data/processed/corpus_llm.jsonl` | Página *Rumo à IA*; rotas `/llm/corpus`, `/llm/contexto` |

Todas as coletas rodam **fora do app**, em scripts próprios. A API lê os arquivos salvos e o
app consome a API. Por isso o app é rápido e continua funcionando mesmo se uma fonte sair do
ar. A exceção é a consulta ao vivo opcional à NASA POWER para uma coordenada arbitrária,
que também passa pela API.

## 2. NASA POWER (fonte 1)

| Item | Descrição |
|---|---|
| Mantenedor | NASA Langley Research Center (LARC) |
| Site / documentação | https://power.larc.nasa.gov/ · https://power.larc.nasa.gov/docs/services/api/ |
| Dicionário de parâmetros | https://power.larc.nasa.gov/docs/methodology/parameters/ |
| Endpoint | `https://power.larc.nasa.gov/api/temporal/daily/point` |
| Autenticação | Não exige chave para consultas básicas |
| Licença/uso | Dados públicos da NASA, gratuitos (termos no site oficial) |
| Granularidade | Diária, por ponto (lat/lon); grade de ~0,5° x 0,625° |
| Cobertura | Global; série desde 1981 com defasagem de poucos dias |

**Coleta (atualizada no TP3):** 10 capitais brasileiras (`src/locations.py`), últimos
365 dias: **3.660 linhas**, de 17/10/2025 a 17/10/2026. Formato "longo": uma linha por
cidade e dia.

### Dicionário de dados: `nasa_power_capitais.csv`

| Coluna | Unidade | Definição | Relevância para o problema |
|---|---|---|---|
| `date` | AAAA-MM-DD | Dia da observação | Eixo temporal |
| `cidade` | texto | Nome da capital (UF) | Chave de comparação |
| `latitude`, `longitude` | graus | Coordenadas consultadas | Localização |
| `ALLSKY_SFC_SW_DWN` | kWh/m²/dia | Irradiância solar de ondas curtas na superfície (céu real, com nuvens) | Principal indicador do potencial de geração (equivale às "horas de sol pleno") |
| `T2M` | °C | Temperatura do ar a 2 m | Painéis perdem eficiência com calor excessivo |
| `RH2M` | % | Umidade relativa a 2 m | Indício de nebulosidade e chuva |
| `WS10M` | m/s | Velocidade do vento a 10 m | Resfria os painéis |
| `CLOUD_AMT` | % | Cobertura de nuvens | Impacta diretamente a irradiância |

### Estatísticas descritivas (todas as cidades, 3.660 dias-cidade)

| Variável | Média | Mín. | Máx. | Valores ausentes |
|---|---|---|---|---|
| `ALLSKY_SFC_SW_DWN` | 5,00 | 0,26 | 9,11 | 70 (1,9%) |
| `T2M` | 23,52 | 7,16 | 32,87 | 10 (0,3%) |
| `RH2M` | 75,46 | 23,88 | 97,52 | 10 (0,3%) |
| `WS10M` | 3,30 | 0,65 | 11,17 | 10 (0,3%) |
| `CLOUD_AMT` | 60,15 | 0,48 | 99,98 | 790 (21,6%) |

Irradiância média por cidade no período: Recife 6,06, Fortaleza 5,83, Brasília 5,41,
Salvador 5,28, Belo Horizonte 5,00, Manaus 4,79, Porto Alegre 4,52, Rio de Janeiro 4,47,
São Paulo 4,38 e Curitiba 4,31 kWh/m²/dia. Os ausentes de irradiância se concentram nos
últimos dias da série (defasagem da NASA), e os de `CLOUD_AMT`, nos últimos ~2,5 meses.

## 3. CRESESB/SunData: irradiação de longo prazo (fonte 2, nova no TP3, Selenium)

| Item | Descrição |
|---|---|
| Mantenedor | CRESESB (Centro de Referência para as Energias Solar e Eólica Sérgio de S. Brito), do CEPEL/Eletrobras |
| Página | https://cresesb.cepel.br/index.php?section=sundata (SunData v3.0) |
| Origem dos números | Base do Atlas Brasileiro de Energia Solar, 2ª edição (INPE, 2017): 17 anos de imagens de satélite, ~72.000 pontos no território brasileiro |
| Conteúdo | Para as até 3 estações mais próximas da coordenada: irradiação solar diária **média de cada mês** (kWh/m²/dia), no plano horizontal e em 3 inclinações (igual à latitude, maior média anual e maior mínimo mensal) |
| Conduta | O site não tem `robots.txt` (404); 10 consultas no total, com pausa de 2 s entre elas |

**Por que Selenium.** Esses dados não ficam em uma URL que dê para baixar direto. A página
exige preencher um formulário. O botão *Buscar* é um `<button type="button">` que
executa JavaScript (`js/rer_init.js`): o script valida a coordenada, converte e preenche
campos ocultos (`latitude`, `longitude`) e só então envia o formulário. O resultado vem em
tabelas acompanhadas de gráficos montados por JavaScript. O script
`cresesb_sundata.py` abre um Chrome sem interface (*headless*), preenche latitude,
hemisfério e longitude como um usuário, clica em *Buscar*, espera as tabelas aparecerem
(`WebDriverWait`) e passa o HTML para o Beautiful Soup extrair os números.

> Tentativa descartada: o primeiro candidato foi o botão *Carregar mais* do feed do Canal
> Solar (carregamento assíncrono). Ele devolve **HTTP 403** ao navegador automatizado
> (inclusive com o Chrome visível). Por respeito ao bloqueio, essa abordagem foi
> abandonada em favor do SunData, que além disso é uma fonte mais útil para o problema.

**Coleta:** 10 capitais x estações próximas x 4 planos = **120 linhas**. Para cada capital,
a coluna `estacao_referencia` marca a estação usada no app: a mais próxima **em terra**.
O SunData às vezes devolve pontos de grade no oceano, sem UF.

### Dicionário de dados: `cresesb_sundata_capitais.csv`

| Coluna | Unidade | Definição |
|---|---|---|
| `cidade`, `latitude`, `longitude` | texto, graus | Capital e coordenada consultada (as mesmas da NASA) |
| `ordem_proximidade` | 1 a 3 | Posição da estação na lista de mais próximas |
| `estacao`, `municipio`, `uf`, `pais` | texto | Identificação do ponto de grade/estação (vazios para pontos no oceano) |
| `lat_estacao`, `lon_estacao` | graus | Coordenadas da estação (sul e oeste negativos) |
| `distancia_km` | km | Distância até a coordenada consultada |
| `plano` | texto | `Plano Horizontal`, `Ângulo igual a latitude`, `Maior média anual` ou `Maior mínimo mensal` |
| `inclinacao_graus` | ° | Inclinação do painel (voltado para o norte) |
| `jan` … `dez` | kWh/m²/dia | Irradiação diária média do mês |
| `media_anual`, `delta` | kWh/m²/dia | Média do ano e diferença entre o maior e o menor mês |
| `estacao_referencia` | booleano | Estação usada pelo app/API para a capital |

### Resultados (estação de referência)

| Capital | Estação (dist.) | Horizontal | Maior média anual (inclinação) | Ganho com inclinação | NASA, último ano (horizontal) | Último ano x longo prazo |
|---|---|---|---|---|---|---|
| Fortaleza (CE) | Fortaleza (8,1 km) | 5,69 | 5,70 (3°) | +0,2% | 5,83 | +2,4% |
| Recife (PE) | Olinda (6,0 km) | 5,46 | 5,48 (5°) | +0,4% | 6,06 | +10,9% |
| Brasília (DF) | Brasília (3,7 km) | 5,28 | 5,47 (18°) | +3,6% | 5,41 | +2,4% |
| Salvador (BA) | Salvador (6,1 km) | 5,36 | 5,41 (9°) | +0,9% | 5,28 | −1,6% |
| Belo Horizonte (MG) | Belo Horizonte (2,3 km) | 5,13 | 5,36 (20°) | +4,5% | 5,00 | −2,5% |
| Rio de Janeiro (RJ) | Rio de Janeiro (7,8 km) | 4,73 | 4,93 (20°) | +4,2% | 4,47 | −5,4% |
| Porto Alegre (RS) | Porto Alegre (4,9 km) | 4,43 | 4,67 (22°) | +5,4% | 4,52 | +1,9% |
| São Paulo (SP) | São Paulo (5,8 km) | 4,43 | 4,64 (21°) | +4,7% | 4,38 | −1,2% |
| Manaus (AM) | Manaus (3,6 km) | 4,32 | 4,33 (4°) | +0,2% | 4,79 | +10,8% |
| Curitiba (PR) | Curitiba (3,9 km) | 4,19 | 4,39 (21°) | +4,8% | 4,31 | +2,9% |

Leituras: (1) o ganho com a inclinação cresce com a distância do Equador, chegando a ~5%
no Sul e Sudeste e ficando quase nulo no Nordeste e Norte; (2) o último ano medido pela
NASA ficou até ~11% acima do normal em Recife e Manaus e ~5% abaixo no Rio. Isso confirma
que estimar com um único ano pode enganar o usuário, o que motivou adotar o longo prazo
como padrão da estimativa.

## 4. ABSOLAR: notícias (fonte 3)

| Item | Descrição |
|---|---|
| Organização | Associação Brasileira de Energia Solar Fotovoltaica |
| Página raspada | https://www.absolar.org.br/noticias/ |
| Método | `requests` + Beautiful Soup (`lxml`): lista de notícias, depois a página de cada matéria (`<article>`) para o texto completo |
| Conduta | `robots.txt` sem restrições; `User-Agent` identificado; pausa de 1 s entre requisições |
| Volume (TP3) | **24 notícias** (01/06/2026 a 19/10/2026), 21 com texto, ~6,0 mil palavras |

**Melhorias do TP3:** a listagem não tem paginação, então as coletas passaram a ser
**acumuladas**: notícias novas são somadas às antigas, sem duplicar pelo link. Itens sem
`<time>` na listagem recebem a data que vem no corpo da matéria ("Data: dd/mm/aaaa").

**Dicionário:** `titulo`, `data` (AAAA-MM-DD), `url`, `categoria` (seção do site:
`associados`, `noticias-externas`, `videos`, `home`, `giro-absolar`), `resumo` (trecho
da listagem) e `texto` (corpo da matéria). `absolar_corpus.txt` reúne título e texto.

## 5. Canal Solar: notícias com texto completo (fonte 4, ampliada no TP3)

| Item | Descrição |
|---|---|
| Veículo | Canal Solar, portal de notícias do setor solar |
| Páginas raspadas | https://canalsolar.com.br/noticias/ (listagem) e **(TP3) a página de cada matéria** |
| Método | `requests` + Beautiful Soup: cards da listagem; na matéria, parágrafos de `.cs-article__content`, `meta[property=article:published_time]` e classes `tag-*` do `<article>` |
| Conduta | `robots.txt` permite as rotas de notícias; pausa de 1 s; cabeçalho `Accept-Language: pt-BR` (o site redireciona para a versão em inglês conforme o idioma) |
| Volume (TP3) | **30 matérias** (15 do TP2 + 15 novas), **todas com texto completo**, ~18,7 mil palavras (média de 622 por matéria), publicadas de 15/09 a 16/10/2026 |

**Dicionário:** `titulo`, `url`, `categoria` (Mercado & Investimentos 15, Política &
Regulação 7, Mercado Internacional 4, Projetos & Aplicações 2, Segurança Pública 2),
`resumo` (linha fina), `autor`, **`data` (publicação, TP3)**, **`tags` (separadas por `;`,
TP3)**, **`texto` (corpo, TP3)** e `coletado_em`. Legendas de foto ("Foto: …") são
descartadas. `canalsolar_corpus.txt` reúne título e texto.

## 6. Medições do usuário (fonte 5, agora via API)

No TP2 os CSVs enviados ficavam só na sessão do navegador. No TP3, a página *Meus dados*
valida o CSV no app (`parse_uploaded_csv`) e o **envia à API** (`POST /medicoes`), que valida
de novo com Pydantic e guarda em `data/processed/medicoes_usuarios.csv`. Também é possível
enviar uma medição avulsa por formulário.

| Campo | Regra de validação na API |
|---|---|
| `cidade` | 2 a 80 caracteres; não pode ser o nome de uma capital da base (409) |
| `latitude` / `longitude` | opcionais; −35 a 6 / −75 a −30 (território brasileiro) |
| `medicoes[].date` | data válida (AAAA-MM-DD) |
| `medicoes[].ALLSKY_SFC_SW_DWN` | obrigatório, 0 a 12 kWh/m²/dia |
| `T2M`, `RH2M`, `WS10M`, `CLOUD_AMT` | opcionais, em faixas físicas plausíveis |
| lote | 1 a 5.000 medições; a mesma data para o mesmo local substitui a anterior |

Esses dados passam a aparecer para todos os usuários (origem `usuario`) e podem ser
removidos (`DELETE /medicoes/{cidade}`). O arquivo fica fora do Git (`.gitignore`).

## 7. Corpus para LLM (derivado, novo no TP3)

`src/data_processing/llm_prep.py` transforma as fontes em documentos curtos para uso
com LLMs na próxima etapa (detalhes em [Planejamento de IA](../llm_planejamento.md)).

| Tipo | Origem | Qtde. | Palavras por documento | Construção |
|---|---|---|---|---|
| `noticia` | ABSOLAR (40 trechos) e Canal Solar (113) | 153 | média 201 (59 a 242) | Texto dividido em janelas de até 220 palavras com 40 de sobreposição, com o título em cada trecho |
| `ficha_local` | NASA POWER + CRESESB | 10 | ~127 | Resumo em linguagem natural dos números de cada capital (irradiação, temperatura, nuvens, melhor e pior mês, longo prazo, geração de um sistema de 5 kWp) |

**Dicionário (`corpus_llm.jsonl`, um JSON por linha):** `id` (hash estável), `tipo`,
`fonte`, `titulo`, `url`, `data`, `cidade` (só nas fichas), `texto`, `n_palavras`.
Total: **163 documentos, ~32 mil palavras**.

## 8. Acesso aos dados pela API (TP3)

Os dados acima são expostos pela API FastAPI (`src/api/main.py`), documentada em
[docs/api.md](../api.md) e no Swagger (`/docs`). O app Streamlit não lê `data/`
diretamente: todas as páginas buscam e enviam dados pela API.

## 8.1 Iniciativas e projetos relacionados (inspiração)

| Iniciativa | Instituição | O que inspirou no Solar Viável |
|---|---|---|
| [Atlas Brasileiro de Energia Solar](https://www.gov.br/pt-br/servicos/obter-dados-do-atlas-brasileiro-de-energia-solar-atlas-solar) | INPE/LABREN | Comparação do potencial solar entre regiões do Brasil (17 anos de imagens de satélite) |
| [SunData](https://cresesb.cepel.br/index.php?section=sundata) | CRESESB/CEPEL | Fonte de dados de longo prazo e plano inclinado (TP3) |
| [Global Solar Atlas](https://globalsolaratlas.info/) | Banco Mundial/ESMAP e Solargis | Diagnóstico rápido de pré-viabilidade por localização |
| [PVWatts](https://pvwatts.nlr.gov/pvwatts.php) | NREL/NLR (EUA) | Estimativa de geração a partir de potência (kWp) e taxa de desempenho |
| [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/en/) | Comissão Europeia (JRC) | Estimativa fotovoltaica gratuita com premissas explícitas |
| [Micro e Minigeração Distribuída](https://www.gov.br/aneel/pt-br/assuntos/geracao-distribuida) | ANEEL | Contexto regulatório da geração solar própria |
| [Infográfico do mercado](https://www.absolar.org.br/mercado/infografico/) | ABSOLAR | Panorama do setor solar brasileiro |

## 9. Objetivos de uso dos dados

1. **Comparar potencial solar** entre locais e períodos (NASA POWER) e em um ano típico (CRESESB).
2. **Estimar geração e economia** de um sistema residencial: geração = irradiância
   (kWh/m²/dia) x potência (kWp) x taxa de desempenho (padrão 0,80). Por padrão, usa o
   longo prazo com a inclinação de maior média anual, somando a geração mês a mês.
3. **Mostrar o efeito da inclinação e da sazonalidade** (melhor e pior mês), para o usuário
   entender a variação da conta de luz ao longo do ano.
4. **Contextualizar** a decisão com o que o setor está discutindo (tarifas, armazenamento,
   leilão de baterias, regulação), por meio de nuvem de palavras, estatísticas e texto das notícias.
5. **Permitir que o usuário traga seus próprios dados** e os compare com os da NASA.
6. **(TP4)** Servir de base para perguntas e respostas, resumos, classificação de
   sentimento e relatórios gerados por LLM.

## 10. Qualidade e limitações

- **Ausentes (NASA):** `-999` vira `NaN`. `CLOUD_AMT` tem 21,6% de ausentes; por isso a
  estimativa usa `ALLSKY_SFC_SW_DWN`, que já incorpora o efeito das nuvens (1,9% de
  ausentes, ignorados nas médias).
- **Satélite x estação:** NASA (grade de ~0,5°) e CRESESB (Atlas, ~10 km) são estimativas
  por satélite com metodologias diferentes. A diferença entre elas mistura a anomalia do
  último ano com a diferença de método.
- **CRESESB:** representa um ano típico (média histórica), não um ano específico, e a
  estação de referência fica a até ~8 km da coordenada. As inclinações supõem painéis
  voltados para o norte.
- **Modelo de geração simplificado:** não considera orientação diferente do norte,
  sombreamento nem degradação dos painéis.
- **Notícias:** 54 itens, um retrato de algumas semanas. A amostra cresce a cada coleta
  acumulada, mas ainda não é uma série histórica. Mudanças no HTML exigem ajustar os
  seletores (os testes dos parsers acusam a quebra).
- **Viés das fontes:** ABSOLAR e Canal Solar representam o setor solar e tendem a uma
  visão favorável à fonte. Isso deve ser considerado na classificação de sentimento do TP4.
- **Medições do usuário:** não há autenticação; qualquer cliente da API pode enviar ou
  remover dados. É aceitável para o protótipo acadêmico, mas é preciso tratar antes de um uso real.
- **Direitos:** o app exibe título, link, linha fina e o texto extraído (com link para a
  fonte) para fins acadêmicos. Os textos são usados para análise e preparação de LLM, e as
  respostas do TP4 devem citar a fonte.
