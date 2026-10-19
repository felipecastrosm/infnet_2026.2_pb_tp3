# Planejamento de IA: uso de LLMs no Solar Viável (TP4)

Este documento registra como os dados coletados até o TP3 serão usados com LLMs
(modelos de linguagem) na próxima etapa, e o que já foi preparado para isso.

## 1. Por que usar LLM neste projeto

O público do Solar Viável é leigo. Gráficos de irradiância e tabelas de kWh ainda exigem
interpretação, e as notícias do setor são longas e técnicas (tarifas, leilões, regulação).
Um LLM pode **explicar** os números em linguagem simples, **responder dúvidas** com base
nos dados do projeto e **resumir** o noticiário. Isso reduz ainda mais a barreira de
informação do ODS 7.

**Princípio de projeto:** os **números continuam vindo da API** (cálculos
determinísticos e testados). O LLM explica, resume, classifica e conversa, mas não calcula
nem inventa valores, e toda resposta cita a fonte dos dados que usou.

## 2. Inventário: que dados temos e para que servem com LLM

| Dado | Volume (TP3) | Formato | Aptidão para LLM | Uso previsto |
|---|---|---|---|---|
| Texto completo das notícias (ABSOLAR, Canal Solar) | 54 matérias, ~24,6 mil palavras | CSV (`texto`) + TXT | Alta (texto corrido em português, com data, fonte e link) | Resumo, sentimento, contexto para perguntas e respostas |
| Títulos, resumos, categorias e tags | 54 itens | CSV | Alta (metadados curtos) | Filtros na recuperação de contexto, classificação |
| Série diária NASA POWER | 3.660 linhas | CSV / `GET /clima` | Baixa em forma bruta (tabela grande) | Convertida em **fichas de local** em texto; números exatos via API |
| Longo prazo CRESESB | 10 capitais x 4 planos | CSV / `GET /irradiacao-longo-prazo` | Média | Entra nas fichas e no relatório de viabilidade |
| Estimativa de geração e economia | sob demanda | `GET /estimativa` | Alta como insumo estruturado (JSON) | Relatório de viabilidade |
| Medições do usuário | variável | `GET /medicoes` | Média | Comparar o local do usuário com a referência no relatório |

## 3. O que já está pronto (TP3)

| Item | Onde | Situação |
|---|---|---|
| Coleta do **texto completo** das matérias (antes só manchetes no Canal Solar) | `src/data_acquisition/canalsolar_scraper.py` | Pronto |
| Coletas acumuladas (o acervo cresce a cada execução) | scrapers ABSOLAR e Canal Solar | Pronto |
| **Corpus em trechos** (≤ 220 palavras, 40 de sobreposição, título em cada trecho, com fonte, link e data) | `src/data_processing/llm_prep.py` → `data/processed/corpus_llm.jsonl` | 163 documentos |
| **Fichas de local**: números de clima e longo prazo convertidos em texto | `llm_prep.fichas_locais` | 10 fichas |
| **Recuperador de linha de base** (palavras-chave com pesos TF-IDF) | `llm_prep.buscar` | Pronto (será trocado) |
| **Modelo de prompt** para perguntas e respostas, com regras (português, só o contexto, citar [n], admitir quando não sabe) | `llm_prep.PROMPT_QA` | Pronto |
| Rotas `GET /llm/corpus` e `GET /llm/contexto` | `src/api/main.py` | Prontas |
| Página **Rumo à IA**, com demonstração da recuperação e do prompt gerado | `paginas/ia.py` | Pronta |

Exemplo real de **ficha de local** (gerada a partir dos dados):

> Potencial solar da capital Curitiba (PR). Entre 17/10/2025 e 17/10/2026, a irradiação
> solar média medida por satélite (NASA POWER) foi de 4,31 kWh/m² por dia (o mesmo que
> horas de sol pleno por dia), […] Na base de longo prazo do CRESESB (estação Curitiba, a
> 3,9 km), com os painéis inclinados a 21° voltados para o norte, a irradiação média anual
> é de 4,39 kWh/m²/dia, variando de 3,52 (jun) a 5,08 (dez). Um sistema de 5,0 kWp […]
> geraria cerca de 534 kWh por mês em média.

## 4. Casos de uso planejados

### 4.1 Perguntas e respostas sobre energia solar (RAG)

| | |
|---|---|
| Pergunta de negócio | "Vale a pena colocar solar em Curitiba?", "O que é o leilão de baterias e me afeta?" |
| Entrada | pergunta do usuário + `k` trechos recuperados do corpus (notícias + fichas) |
| Fluxo | pergunta → recuperação (`/llm/contexto`) → prompt com contexto numerado → LLM → resposta com citações [n] e links |
| Saída | resposta curta em português + lista de fontes |
| Rota planejada | `POST /llm/perguntar` · página nova *Pergunte ao Solar Viável* (chat com `st.chat_input`) |
| Avaliação | conjunto de ~20 perguntas com resposta esperada: acerto do recuperador (o trecho certo está entre os `k`?), fidelidade (a resposta usa só o contexto?), clareza para leigos |

### 4.2 Resumo de notícias

| | |
|---|---|
| Entrada | texto completo de uma matéria (média de 622 palavras no Canal Solar) |
| Saída | 3 frases de resumo + "o que isso muda para quem quer instalar solar" |
| Rota planejada | `POST /llm/resumo` (com cache: cada matéria é resumida uma vez e guardada em `data/processed/`) |
| Onde aparece | página *Notícias do setor*, no lugar do texto extraído longo |
| Avaliação | leitura manual de uma amostra (fidelidade e utilidade) |

### 4.3 Classificação de sentimento

| | |
|---|---|
| Entrada | título + texto da matéria |
| Saída (JSON) | `{"sentimento": "positivo" \| "neutro" \| "negativo", "para_quem": "consumidor", "justificativa": "..."}` |
| Detalhe | sentimento **do ponto de vista de quem quer instalar** (ex.: reajuste de tarifa = positivo para o retorno do investimento, mas negativo para o consumidor em geral). O prompt fixa esse ponto de vista |
| Rota planejada | `POST /llm/sentimento` (em lote, resultado guardado como coluna nova das notícias) |
| Onde aparece | página *Notícias*: termômetro do setor por semana e filtro por sentimento |
| Avaliação | rotular à mão ~30 matérias e medir a concordância (acurácia/F1) com o LLM; considerar o viés pró-solar das fontes |

### 4.4 Relatório de viabilidade (geração de texto)

| | |
|---|---|
| Entrada | ficha do local + JSON de `GET /estimativa` (geração e economia) + parâmetros do usuário (kWp, tarifa) + medições do usuário, se houver |
| Saída | relatório de 1 página em linguagem simples: potencial do local, geração e economia esperadas, sazonalidade (pior e melhor mês), efeito da inclinação, próximos passos (orçamento com instalador, regras da ANEEL) |
| Regra | todo número do relatório vem do JSON da API; o prompt proíbe criar números |
| Rota planejada | `POST /llm/relatorio` · botão "Gerar relatório" na página *Potencial de longo prazo*, com download em Markdown/PDF |
| Avaliação | conferir automaticamente se cada número citado existe no JSON de entrada |

## 5. Arquitetura prevista

```
pergunta ──► GET /llm/contexto ──► trechos [1..k] ──► prompt (PROMPT_QA) ──► LLM ──► resposta + fontes
                   │                                                         ▲
                   └── corpus_llm.jsonl (notícias + fichas)                  │
                                          GET /estimativa (números exatos) ──┘ (relatório)
```

A chamada ao LLM ficará **na API** (rotas `POST /llm/*`), não no app. Assim a chave do
provedor não vai para o navegador, as respostas podem ser guardadas em cache e o app
continua sendo apenas um cliente.

## 6. O que aprendemos com o recuperador de linha de base

A demonstração da página *Rumo à IA* mostra os limites da busca por palavras-chave, o que
orienta as mudanças do TP4:

| Pergunta | Resultado do recuperador atual | Ajuste planejado |
|---|---|---|
| "O que é o leilão de baterias?" | Matérias certas sobre o leilão (bom) | Nenhum |
| "Como está o custo da energia solar no Brasil?" | Matérias da IRENA/ABSOLAR sobre custo (bom) | Nenhum |
| "Qual capital tem a maior irradiação solar?" | Fichas de local, mas só `k` delas e empatadas | Para perguntas comparativas, mandar **todas** as fichas (são curtas, ~127 palavras) ou responder com a API (`/locais`) |
| "Quanto um sistema de 5 kWp gera em Curitiba?" | Matéria sobre baterias em Curitiba, não a ficha de Curitiba | Busca semântica (embeddings) + filtro pelo metadado `cidade`; para "quanto gera", chamar `/estimativa` (função/ferramenta) em vez de buscar texto |

Mudanças previstas: (1) **embeddings** multilíngues para a busca semântica, guardados com
o corpus; (2) **filtros por metadados** (`tipo`, `cidade`, `fonte`, `data`); (3) para
perguntas numéricas, o LLM chama as rotas da API como **ferramentas** (*function
calling*), em vez de procurar números no texto.

## 7. Escolha do modelo (critérios)

O modelo será escolhido no TP4 entre as ferramentas apresentadas na disciplina, com
estes critérios: bom desempenho em **português**; janela de contexto suficiente para
~4 a 8 trechos (≈ 2 mil palavras); suporte a **saída estruturada (JSON)** para sentimento;
suporte a ferramentas (*function calling*) para consultar a API; e custo e latência
compatíveis com um app gratuito, usando cache para resumos e sentimentos.

## 8. Riscos e cuidados

| Risco | Mitigação |
|---|---|
| Alucinação (inventar fatos ou números) | Responder só com o contexto; números só da API; citar fontes; dizer "não sei" quando faltar contexto |
| Viés pró-solar das fontes | Explicitar a fonte em cada resposta; no sentimento, fixar o ponto de vista e avaliar contra rótulos manuais |
| Desatualização | Datas em cada trecho; recoleta periódica (coletas acumuladas); o prompt pede para mencionar a data |
| Custo e latência | Cache de resumos e sentimentos; processar em lote; limitar `k` |
| Privacidade | Medições do usuário não identificam pessoas; não enviar dados pessoais ao LLM |
| Direitos autorais | Resumos curtos com link para a matéria original; o texto completo não é republicado pelo LLM |

## 9. Próximos passos (TP4)

1. Escolher o modelo e configurar a chave como segredo (variável de ambiente / `st.secrets`), nunca no Git.
2. Gerar embeddings do corpus e trocar `llm_prep.buscar` pela busca semântica com filtros.
3. Implementar `POST /llm/perguntar`, `/llm/resumo`, `/llm/sentimento` e `/llm/relatorio`, com testes (LLM simulado nos testes).
4. Criar a página de chat e integrar resumo, sentimento e relatório às páginas existentes.
5. Montar o conjunto de avaliação (perguntas de teste e notícias rotuladas) e medir os resultados.
