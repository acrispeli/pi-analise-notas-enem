# Validação técnica IND-031 — Perda por competência (900–980)

**Projeto:** Projeto Integrador IV — UNIVESP
**Período analisado:** ENEM 2019 a 2025 e histórico 2019–2025
**Data da auditoria:** 22 de outubro de 2026
**Estado da análise:** `draft`; resultados reais agregados, com revisão acadêmica e de privacidade ainda pendentes.

## 1. Objetivo e arquivos examinados

A auditoria conferiu `IND_031_*.csv`, `IND_031_*.json` e o bloco correspondente no arquivo `dashboard_enem_2024.json` enviado. Foram examinados **6.505 registros de CSV**, distribuídos por **224 recortes** (2019–2025 e histórico × Brasil e 27 UFs). O dashboard de 2024 passou no contrato `04_resultados_analises.schema.json` disponível no projeto.

## 2. Parecer computacional

- **78.688 verificações programáticas executadas**, com **0 falhas** nas condições efetivamente testadas.
- Os testes incluíram consistência de campos entre CSV e JSON, somatórios, percentuais, abrangência territorial e histórica, e equivalência integral dos blocos de Brasil e UFs com o dashboard enviado para 2024.
- Este parecer **não é um recálculo independente a partir dos microdados**. Os microdados originais não foram disponibilizados nesta auditoria. Verificações sobre a mesma agregação detectam inconsistências internas, mas não comprovam, por si, a validade do cálculo original.

## 3. Método e resultados

População `POP_NEAR`: redações válidas com **900 ≤ `NU_NOTA_REDACAO` ≤ 980**, excluindo a nota 1000. Para cada uma das competências C1–C5 calcula-se a perda `200 − NU_NOTA_Ci`, a média, a mediana empírica e a soma de pontos perdidos. As médias nacionais e históricas são agregadas ponderando todas as participações; as medianas não devem ser agregadas por média das medianas.

| Ano | `POP_NEAR` BR | Perda média C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 172.548 | 34,226 | 3,888 | 13,020 | 7,810 | 12,070 |
| 2020 | 183.343 | 34,796 | 3,090 | 16,037 | 7,379 | 8,256 |
| 2021 | 163.747 | 37,133 | 1,330 | 24,629 | 7,230 | 5,407 |
| 2022 | 197.083 | 37,359 | 1,097 | 25,335 | 7,090 | 5,150 |
| 2023 | 288.602 | 37,359 | 1,848 | 18,227 | 6,745 | 7,485 |
| 2024 | 291.111 | 38,778 | 3,591 | 22,262 | 6,478 | 5,537 |
| 2025 | 173.533 | 38,201 | 7,249 | 22,534 | 6,131 | 4,314 |
| 2019–2025 | 1.469.967 | 37,027 | 3,067 | 20,316 | 6,924 | 6,814 |

Em **2024, Brasil**, `POP_NEAR = 291.111`. A maior perda média é da **C1 (38,778 pontos)**, seguida por C3 (22,262), C4 (6,478), C5 (5,537) e C2 (3,591). Isso descreve apenas redações próximas da nota máxima e **não deve ser generalizado para todas as redações do ENEM**.

## 4. Controles específicos aprovados

1. **6.505 linhas CSV** correspondem a cinco competências no total `POP_NEAR` e em cada faixa dos 224 recortes.
2. Em cada recorte, as somas de redações das faixas reproduzem `n_near` e as somas de pontos perdidos por faixa reproduzem o total de cada competência.
3. Em cada competência, `média × quantidade` reproduz a soma de perdas dentro da precisão dos decimais exportados; valores de perda média/mediana estão em 0–200.
4. A soma de perdas das cinco competências é coerente com os limites de nota por faixa (cada redação perde, no total, `1000 − nota_final`).
5. Populações válidas coincidem com IND-030; em 2024 a diferença `n_high − n_near` confere com a contagem de notas 1000 do IND-008, no Brasil e nas 27 UFs.
6. Denominadores geográficos e totais históricos fecham, e as saídas nacionais/UF de 2024 são iguais às incorporadas ao dashboard.

## 5. Pendências de metadados e privacidade

**Problema de rótulo/intervalo:** em **184 dos 224 recortes**, há uma linha da faixa `960–980` marcada com `limite_superior=980` e `superior_inclusivo=true`, mas também existe uma linha separada `980`. As contagens permanecem aritmeticamente coerentes; **a descrição formal das faixas, porém, se sobrepõe**. Quando 980 for apresentado em faixa própria, a faixa anterior deve ser representada como **`960–<980` e `superior_inclusivo=false`**. Quando a faixa 980 estiver unida à anterior por proteção, o limite superior inclusivo pode ser mantido.

**Risco por diferença com IND-030:** existem **112 recortes** com contagem positiva inferior a 30 da nota 1000 inferível por `n_high − n_near`; 2024/AL é um exemplo (resultado 1). A proteção isolada dos grupos não é suficiente diante do conjunto de arquivos e do IND-008.

**Parecer: APROVADO na aritmética e consistência agregada; CORREÇÃO DE METADADOS e REVISÃO DE PRIVACIDADE necessárias antes de publicar.** Recomenda-se corrigir o código gerador e reprocessar o indicador, não apenas editar os arquivos gerados, para garantir consistência futura.
