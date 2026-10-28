# Validação Técnica — IND-027: Concordância da Nota Total entre Avaliadores (ENEM 2019–2025)

**Projeto:** Projeto Integrador IV — UNIVESP
**Data da auditoria:** 22/10/2026
**Indicador:** IND-027 — Concordância total
**Situação técnica:** **APROVADO NOS AGREGADOS — 5.787 verificações, 0 falhas**
**Situação para publicação:** **DRAFT** — revisão acadêmica e de privacidade complementar pendentes.

## 1. Objetivo e escopo

Analisar a consistência dos resultados publicados pelo processamento do IND-027, medindo a concordância entre as notas totais atribuídas por dois avaliadores (AV1 e AV2), por meio do **coeficiente de correlação intraclasse (ICC(A,1), concordância absoluta, medida individual)** e da **correlação linear de Pearson**.

A auditoria abrangeu os resultados já calculados em 2019–2025, Brasil e 27 unidades da Federação, e o histórico 2019–2025: **8 períodos × 28 abrangências = 224 recortes**. Foi examinado o dashboard cumulativo **de 2024**. Os arquivos de resultados foram lidos, mas os microdados originais não estão presentes neste ambiente.

## 2. Arquivos auditados

1. `IND_027_concordancia_total.csv` — 224 linhas de resultados, CSV separado por ponto e vírgula e codificação UTF-8 com BOM.
2. `IND_027_concordancia_total.json` — estrutura nacional, por UF, por ano e histórico, metadados e diagnósticos.
3. `dashboard_enem_2024.json` — integração de `pages.evaluators.icc`, `pages.temporal.ind027`, `pages.methodology.ind027` e `quality.ind027_validation`.
4. `IND_020_diferenca_total_av1_av2.json` — referência agregada anterior para conferência dos denominadores `POP_EVALUATOR`.
5. Código `pacote_ind027/src/indicadores/IND_027_concordancia_total.py` e testes `pacote_ind027/testes_IND027_sintetico.py` — inspeção e reexecução da suíte sintética.

Os arquivos auditados tiveram os seguintes resumos criptográficos SHA-256, úteis para identificar exatamente a versão examinada:

| Arquivo | SHA-256 |
|---|---|
| `IND_027_concordancia_total.csv` | `a681cff11b58db2cd2eb9af16349fd5ac7725f606bd47c322a116b972fdc7a85` |
| `IND_027_concordancia_total.json` | `3c157f6d3c6291f4d67686d12f1fc9c1e6ab0e3017a5716fe555419f29bfa73b` |
| `dashboard_enem_2024.json` | `450e4624d9866692ddff1d3c35014db4adfcfd8d03d25433462aa691858b6929` |
| `IND_020_diferenca_total_av1_av2.json` | `e57e61a6ee4db5d85b0720ddd18c64d664835fb78ebf947cab683df692c09d21` |

## 3. Definição metodológica

### 3.1 População de referência

**POP_EVALUATOR** inclui participações com `NU_NOTA_AV1` e `NU_NOTA_AV2` preenchidas e numericamente válidas entre 0 e 1.000 pontos. Não é necessário que `TP_STATUS_REDACAO = 1`; o denominador não é `POP_VALID` nem `POP_ALL`.

O indicador não utiliza amostra. Para 2019–2024, a origem das notas foi associada à UF de prova pela chave composta `NU_INSCRICAO + NU_ANO`; em 2025, notas e UF vieram da mesma linha do arquivo de resultados, conforme metadados da execução.

### 3.2 Coeficientes

O ICC de concordância absoluta e medida individual segue a expressão ANOVA com dois avaliadores:

```text
ICC(A,1) = (MSR - MSE) / [MSR + (k - 1)·MSE + k·(MSC - MSE)/n]
com k = 2 (AV1 e AV2)
```

`MSR` representa o quadrado médio entre participantes, `MSC` o quadrado médio entre avaliadores, e `MSE` o quadrado médio residual. O script utiliza momentos de primeira e segunda ordem e produtos cruzados, acumulados para cada recorte.

O **Pearson** mede a associação linear e não penaliza um deslocamento constante entre duas séries de notas da mesma forma que o ICC absoluto. A métrica histórica usa os momentos de todos os pares combinados, **não a média dos ICC anuais**.

Os números computados não distinguem erro de um avaliador de discordância legítima e não são métricas de qualidade individual de corretores.

## 4. Procedimentos de auditoria dos agregados

Foram executadas **5.787 asserções automatizadas**, divididas em:

| Categoria de checagem | Número |
|---|---:|
| Estrutura | 12 |
| Geografia | 256 |
| Tamanho privacidade | 224 |
| Denominadores | 224 |
| Metodologia | 672 |
| Privacidade | 224 |
| Coeficientes | 1,344 |
| Qualidade declarada | 24 |
| Csv json | 2,466 |
| Historico | 28 |
| Qualidade fonte | 48 |
| Ind020 | 225 |
| Dashboard | 40 |
| **Total** | **5.787** |

Principais critérios:

- Estrutura JSON: identificação correta `IND-027`, 7 anos completos, consolidado histórico, método e status `draft`.
- 27 UFs únicas e completas em cada um dos 8 períodos; soma das 27 UFs igual ao resultado nacional, para `n_pares_validos`.
- 224 chaves únicas no CSV (ano/período + UF/BR) e comparação campo a campo com os 224 recortes JSON: população, modelo, N, ICC, Pearson e situação de cálculo.
- Coeficientes numéricos finitos e dentro do intervalo teórico [-1,1], quando definidos; coerência entre coeficiente nulo e status de indefinição.
- `n_pares_validos == n_pop_evaluator` em todos os recortes, com grupos de pelo menos 30 pares.
- Conferência dos **224 denominadores contra o IND-020** anterior e da soma histórica das participações por UF e Brasil.
- Verificação da contabilidade dos arquivos-fonte declarados em `source_qa` (linhas, pares, incompletos, inválidos, ausência de junção), sem ter relido as fontes brutas.
- Comparação completa do bloco do IND-027 no dashboard 2024 contra o módulo JSON, incluindo série temporal e consolidados históricos.
- Inspeção das flags de privacidade e presença das páginas e blocos anteriores no dashboard atual (sem comparação com uma cópia anterior).

**Resultado:** 5.787 verificações aprovadas, **0 inconsistência(s)**.

## 5. Resultados nacionais validados

| Período | N pares válidos | ICC(A,1) absoluto | Pearson |
|---|---:|---:|---:|
| 2019 | 3.779.355 | 0,789894 | 0,789894 |
| 2020 | 2.674.914 | 0,779467 | 0,779467 |
| 2021 | 2.378.379 | 0,877822 | 0,877822 |
| 2022 | 2.493.442 | 0,882418 | 0,882418 |
| 2023 | 2.822.643 | 0,819130 | 0,819135 |
| 2024 | 3.167.955 | 0,858355 | 0,858357 |
| 2025 | 3.457.555 | 0,851406 | 0,851409 |
| 2019-2025 | 20.774.243 | 0,840397 | 0,840397 |

O consolidado histórico contabiliza **20.774.243 participações** em sete edições; não corresponde a uma contagem de pessoas únicas e não deve ser interpretado como média simples dos coeficientes anuais.

### 5.1 Destaques — 2024

- Pares válidos nacionais: **3.167.955**.
- ICC(A,1) Brasil: **0,858355**.
- Pearson Brasil: **0,858357**.
- Maiores ICCs entre as UFs: CE (0,886748); AL (0,880688); PE (0,874191).
- Menores ICCs entre as UFs: SP (0,815113); PR (0,823831); SC (0,841432).

Essa variação regional é apenas descritiva. Não permite atribuir causas, comparar desempenho de avaliadores individuais ou julgar a correção de uma nota.

A maior diferença absoluta observada entre ICC e Pearson nos **224 recortes** foi de **0,000095**. A proximidade dos coeficientes é compatível com pouca discrepância sistemática entre os níveis médios de AV1 e AV2, mas não demonstra concordância perfeita e não substitui análise dos pares originais.

## 6. Reexecução dos testes sintéticos

Foi reexecutado `pacote_ind027/testes_IND027_sintetico.py`, com `PYTHONPATH` apontando para os módulos do projeto. Resultado final da suíte:

```text
OK: 7 anos, 27 UFs, 224 recortes, CSV/JSON e preservação de dashboards
TODOS OS TESTES SINTÉTICOS IND-027 PASSARAM
```

O conjunto sintético verifica, entre outros casos: concordância perfeita, deslocamento entre notas, anticorrelação, casos indefinidos, comparação do ICC com ANOVA diretamente calculada, Pearson com implementação de referência, combinação de momentos para histórico, rejeição de notas fora do intervalo, grupos n<30, criação dos sete dashboards sintéticos e preservação de estruturas pré-existentes.

**Observação:** testes sintéticos validam o comportamento do código para os casos propostos; não validam por si só os valores obtidos dos microdados reais.

## 7. Integração no dashboard de 2024

O dashboard possui os seguintes objetos, com resultado consistente com o módulo do IND-027:

- `pages.evaluators.icc` — KPI de concordância nacional e por UF.
- `pages.temporal.ind027` — série histórica anual e consolidado do período.
- `pages.methodology.ind027` — formulação e limitações do método.
- `quality.ind027_validation` — status `ok`, N Brasil e flags de ausência de amostragem e revisão pendente.

Os blocos dos IND-020 a IND-026 continuam presentes no **dashboard recebido**, e a quantidade de pares de 2024 coincide com o IND-020. Como não foi disponibilizada uma versão do dashboard **anterior** à execução, não é possível provar nesta auditoria que todo o conteúdo prévio permaneceu exatamente igual byte a byte. Também não foram disponibilizados os dashboards completos dos outros seis anos para conferência direta.

## 8. Privacidade e requisitos antes da publicação

Nenhum dado individual ou identificador foi encontrado nos registros de resultado do IND-027 examinados; o módulo contém somente recortes agregados. Todos os 224 recortes têm pelo menos 30 pares. Esse limiar é uma proteção inicial, mas não comprova segurança contra reconstrução e cruzamento entre indicadores.

O próprio dashboard de 2024 contém avisos de revisão de privacidade ainda pendente de indicadores anteriores, inclusive distribuições e pequenas frequências. Portanto, o **dashboard cumulativo não deve ser publicado indiscriminadamente** sem revisão das demais seções e supressão complementar. A publicação do IND-027 permanece em modo `draft`.

## 9. Limitações desta validação

1. **Não houve recálculo independente de ICC/Pearson a partir dos milhões de pares individuais**, pois os microdados brutos necessários não foram fornecidos aqui. O JSON não exporta os seis momentos por recorte suficientes para refazer as duas métricas de modo independente.
2. As declarações de qualidade relativas a junções e arquivos-fonte foram **conferidas quanto à consistência interna**, mas não reproduzidas sobre os CSVs originais.
3. A conformidade acadêmica das escolhas de modelo ICC(A,1), o significado temporal e as limitações de inferência ainda exigem revisão pela equipe.
4. A integração completa dos dashboards de 2019–2023 e 2025 não foi auditada com os arquivos correspondentes.
5. A proteção de privacidade precisa ser avaliada sobre **todo o dashboard** e cruzamentos possíveis, não apenas sobre os resultados do IND-027.

## 10. Parecer técnico

**APROVADO na validação computacional dos agregados e nos testes sintéticos reexecutados**: as 224 linhas CSV, os 224 recortes JSON, os 224 denominadores do IND-020, as somas por UF e histórico, os coeficientes e a integração ao dashboard de 2024 estão consistentes, com zero falhas nas 5.787 verificações.

**Não é aprovação final de publicação.** O indicador continuará com `data_status = draft` até revisão acadêmica e de privacidade, e a confirmação independente dos cálculos requer acesso às notas AV1/AV2 originais ou a agregados de momentos suficientes.

## 11. Reprodutibilidade

Arquivos complementares da auditoria:

- `auditoria_IND027_real.py` — asserções sobre módulos agregados e dashboard.
- `auditoria_IND027_resultados.json` — contagem por categoria e log de inconsistências.
- `testes_IND027_reexecucao_auditoria.txt` — saída dos testes sintéticos reexecutados.

Para repetir a auditoria dos agregados, coloque `auditoria_IND027_real.py`, os quatro JSON/CSV de entrada citados e o dashboard de 2024 na mesma pasta, e execute `python auditoria_IND027_real.py`. A auditoria não grava nem altera os dashboards existentes.
