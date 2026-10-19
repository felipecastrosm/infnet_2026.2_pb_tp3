# API do Solar Viável (FastAPI)

A API expõe os dados e cálculos do projeto por HTTP. O app Streamlit é o principal
cliente (todas as páginas consultam e enviam dados por ela), mas qualquer outro
programa, como uma planilha, outro app ou o futuro assistente com LLM, pode usá-la.

- Código: [`src/api/main.py`](../src/api/main.py) (rotas) e [`src/api/schemas.py`](../src/api/schemas.py) (modelos Pydantic)
- Acesso aos arquivos: [`src/repositorio.py`](../src/repositorio.py)
- Cliente usado pelo app: [`src/api_client.py`](../src/api_client.py)
- Testes: [`tests/test_api.py`](../tests/test_api.py)

## Como rodar

```bash
uvicorn src.api.main:app --reload            # http://127.0.0.1:8000
```

- Documentação interativa (Swagger, permite testar as rotas): http://127.0.0.1:8000/docs
- Documentação alternativa (ReDoc): http://127.0.0.1:8000/redoc
- Especificação OpenAPI (JSON): http://127.0.0.1:8000/openapi.json

O app procura a API em `SOLAR_API_URL` (padrão `http://127.0.0.1:8000`). Se ela não estiver
no ar e o endereço for local, o próprio app a inicia em uma thread (útil no Streamlit
Community Cloud). A página **Explorar a API** do app lista as rotas a partir do
`/openapi.json` e permite enviar requisições.

## Rotas

| Método | Rota | Grupo | Para que serve |
|---|---|---|---|
| GET | `/` | Geral | Boas-vindas e links |
| GET | `/saude` | Geral | Verifica se a API está no ar (usada pelo app) |
| GET | `/locais` | Locais e clima | Lista os locais (capitais + enviados por usuários) com período e irradiância média |
| GET | `/clima` | Locais e clima | Série diária de clima, filtrável por local(is) e período |
| GET | `/clima/resumo` | Locais e clima | Média, mínimo e máximo de cada variável por local |
| GET | `/clima/ao-vivo` | Locais e clima | Consulta a NASA POWER para qualquer coordenada (não salva) |
| GET | `/irradiacao-longo-prazo` | Longo prazo | Irradiação mensal típica do CRESESB, por plano de inclinação |
| GET | `/estimativa` | Estimativa | Geração (kWh) e economia (R$) de um sistema |
| GET | `/noticias` | Notícias | Notícias do setor, com busca e filtro por fonte |
| GET | `/noticias/palavras` | Notícias | Palavras mais frequentes (sem stopwords) |
| **POST** | `/medicoes` | Medições do usuário | **Envia** medições de um local |
| GET | `/medicoes` | Medições do usuário | Lista as medições enviadas |
| **DELETE** | `/medicoes/{cidade}` | Medições do usuário | Remove as medições de um local |
| GET | `/llm/corpus` | LLM | Estatísticas do corpus preparado para LLMs |
| GET | `/llm/contexto` | LLM | Recupera os trechos mais relevantes para uma pergunta e monta o prompt |

Erros seguem o padrão do FastAPI (`{"detail": ...}`): **404** para local inexistente,
**409** ao tentar enviar medições com o nome de uma capital da base, **422** para
parâmetros ou corpo inválidos e **502** quando a NASA POWER falha na consulta ao vivo.

## Detalhes e exemplos

### `GET /locais`

Parâmetro: `incluir_medicoes` (bool, padrão `true`). Resposta (lista, ordenada pela irradiância):

```json
[{"cidade": "Recife (PE)", "latitude": -8.0476, "longitude": -34.877, "origem": "nasa",
  "dias": 366, "inicio": "2025-10-17", "fim": "2026-10-17", "irradiacao_media": 6.057}]
```

### `GET /clima`

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `cidade` | texto, repetível | um ou mais locais; vazio = todos |
| `inicio`, `fim` | data (AAAA-MM-DD) | período (opcional) |
| `incluir_medicoes` | bool | inclui medições de usuários (padrão `true`) |

```bash
curl "http://127.0.0.1:8000/clima?cidade=Recife%20(PE)&cidade=Manaus%20(AM)&inicio=2026-01-01&fim=2026-01-31"
```

Cada item traz `date`, `cidade`, `latitude`, `longitude`, `ALLSKY_SFC_SW_DWN`, `T2M`,
`RH2M`, `WS10M`, `CLOUD_AMT` e `origem` (`nasa` ou `usuario`). Ausentes vêm como `null`.

### `GET /clima/ao-vivo`

`latitude` (−35 a 6), `longitude` (−75 a −30), `dias` (7 a 365, padrão 180), `nome`.
Usada pelo formulário *Consultar outro local* da página *Clima e geração*.

### `GET /irradiacao-longo-prazo`

`cidade` (repetível) e `plano` (`Plano Horizontal`, `Ângulo igual a latitude`,
`Maior média anual` ou `Maior mínimo mensal`).

```json
[{"cidade": "Curitiba (PR)", "estacao": "Curitiba", "municipio": "Curitiba", "uf": "PR",
  "distancia_km": 3.9, "plano": "Maior média anual", "inclinacao_graus": 21,
  "mensal": {"jan": 4.93, "fev": 5.01, "...": "...", "dez": 5.08}, "media_anual": 4.39, "delta": 1.56}]
```

### `GET /estimativa`

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `cidade` | (obrigatório) | local |
| `potencia_kwp` | 5,0 | potência instalada (0 a 1000) |
| `desempenho` | 0,80 | taxa de desempenho (0,5 a 0,95) |
| `tarifa` | 0,90 | R$/kWh |
| `fonte` | `cresesb` | `cresesb`: ano típico, painel na inclinação de maior média anual, mês a mês; `nasa`: média do último ano no plano horizontal (funciona também para locais enviados por usuários) |

```bash
curl "http://127.0.0.1:8000/estimativa?cidade=Fortaleza%20(CE)&potencia_kwp=4"
```

```json
{"cidade": "Fortaleza (CE)", "fonte": "cresesb", "irradiacao_media": 5.7, "potencia_kwp": 4.0,
 "desempenho": 0.8, "tarifa": 0.9, "geracao_dia_kwh": 18.24, "geracao_mes_kwh": 554.7,
 "geracao_ano_kwh": 6656.0, "economia_mes_rs": 499.23, "economia_ano_rs": 5990.76,
 "observacao": "Estação Fortaleza (8.1 km), painéis a 3° voltados para o norte."}
```

### `GET /noticias` e `GET /noticias/palavras`

`/noticias`: `fonte` (repetível: `ABSOLAR`, `Canal Solar`), `busca` (termo no título,
resumo ou texto), `limite` (1 a 500, padrão 50) e `incluir_texto` (padrão `false`).
`/noticias/palavras`: `fonte` e `top` (1 a 100).

### `POST /medicoes`

Corpo (JSON):

```json
{
  "cidade": "Meu telhado - Niterói",
  "latitude": -22.88,
  "longitude": -43.10,
  "medicoes": [
    {"date": "2026-09-01", "ALLSKY_SFC_SW_DWN": 5.2, "T2M": 24.1},
    {"date": "2026-09-02", "ALLSKY_SFC_SW_DWN": 3.8}
  ]
}
```

```bash
curl -X POST http://127.0.0.1:8000/medicoes -H "Content-Type: application/json" \
  -d '{"cidade": "Meu telhado", "medicoes": [{"date": "2026-09-01", "ALLSKY_SFC_SW_DWN": 5.2}]}'
```

Resposta **201**: `{"cidade": "Meu telhado", "recebidas": 1, "mensagem": "1 medição(ões) salva(s)."}`.
As regras de validação estão no [Data Summary Report, seção 6](data_report/data_summary_report.md#6-medições-do-usuário-fonte-5-agora-via-api).
O local passa a aparecer em `/locais`, `/clima` e `/estimativa?fonte=nasa`.

### `GET /medicoes` e `DELETE /medicoes/{cidade}`

`GET /medicoes?cidade=...` lista o que foi enviado. `DELETE /medicoes/Meu%20telhado` remove
o local (`{"cidade": ..., "removidas": n}`) ou devolve 404 se não houver medições.

### `GET /llm/corpus` e `GET /llm/contexto`

`/llm/corpus` devolve o total de documentos e palavras, por tipo e por fonte.
`/llm/contexto?pergunta=...&k=4` devolve os `k` trechos mais relevantes (busca por
palavras-chave com pesos TF-IDF) e o `prompt` pronto para o LLM. É a etapa de recuperação
do sistema de perguntas e respostas do TP4 (ver [Planejamento de IA](llm_planejamento.md)).

## Como o app usa a API

| Página do app | Rotas |
|---|---|
| Clima e geração | `GET /locais`, `GET /clima`, `GET /clima/ao-vivo` |
| Potencial de longo prazo | `GET /irradiacao-longo-prazo`, `GET /estimativa`, `GET /clima/resumo` |
| Notícias do setor | `GET /noticias` |
| Meus dados | `POST /medicoes`, `GET /medicoes`, `DELETE /medicoes/{cidade}`, `GET /clima`, `GET /noticias`, `GET /irradiacao-longo-prazo` |
| Explorar a API | `GET /openapi.json` e qualquer rota escolhida pelo usuário |
| Rumo à IA | `GET /llm/corpus`, `GET /llm/contexto` |
