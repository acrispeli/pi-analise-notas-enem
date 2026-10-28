# Validação técnica — IND-008: Notas 1000 (ENEM 2019–2025)

**Projeto Integrador IV — UNIVESP**
**Indicador:** IND-008 — Notas 1000
**Resultado:** **APROVADO para análise interna**, **não liberado para publicação pública**
**Situação acadêmica:** `draft`, pendente de revisão e aprovação
**Fontes da auditoria:** arquivos agregados produzidos pelo processamento local e script gerador; não houve reprocessamento independente dos microdados originais.

## 1. Escopo

Foi auditada a quantidade de redações cuja `NU_NOTA_REDACAO` é **exatamente 1000**, restrita às redações válidas (`TP_STATUS_REDACAO = 1`, nota interpretável entre 0 e 1000). A proporção utiliza **redações válidas** como denominador. A unidade geográfica é `SG_UF_PROVA` (UF da aplicação da prova, não UF de residência).

- Edições: 2019, 2020, 2021, 2022, 2023, 2024 e 2025.
- Localidades: Brasil e 27 UFs.
- Consolidação histórica: soma das participações dos sete anos, não de pessoas únicas.
- Artefatos de entrada recebidos: `IND_008_notas_1000.csv`, `IND_008_notas_1000.json`, `dashboard_enem_2024.json`.
- Referências auxiliares disponíveis para cruzamento: módulos JSON IND-001, IND-002, IND-003, IND-004, IND-005, IND-006 e IND-007; `04_resultados_analises.schema.json`.

## 2. Resultados nacionais

| Ano | Redações válidas | Redações com nota 1000 | Percentual sobre válidas |
|---|---:|---:|---:|
| 2019 | 3.779.356 | 53 | 0,0014% |
| 2020 | 2.674.914 | 28 | 0,0010% |
| 2021 | 2.293.797 | 22 | 0,0010% |
| 2022 | 2.363.615 | 32 | 0,0014% |
| 2023 | 2.704.814 | 60 | 0,0022% |
| 2024 | 3.002.710 | 12 | 0,0004% |
| 2025 | 3.245.696 | 10 | 0,0003% |
| **Histórico 2019–2025** | **20.064.902** | **217** | **0,0011%** |

O consolidado de 2019–2025 apresenta **30.821.888 registros totais** (`POP_ALL`), **20.064.902 redações válidas** (`POP_VALID`) e **217 notas 1000**. O percentual histórico é recalculado como `100 * 217 / 20.064.902`, arredondado a quatro casas decimais: **0,0011%**.

Os valores são extremamente pequenos; por isso, não arredondar indiscriminadamente a duas casas percentuais, o que produziria `0,00%` e poderia ocultar o resultado.

## 3. Auditoria automatizada independente dos agregados

**7.972 verificações, 0 falhas**, distribuídas em:

| Tipo | Quantidade |
|---|---:|
| Estrutura do CSV/JSON e grupos | 1.604 |
| Limites e consistência básica das contagens | 1.344 |
| Correspondência CSV × JSON | 1.344 |
| Recálculo independente de proporção e percentual | 448 |
| Flags de revisão de privacidade | 224 |
| Cruzamentos com IND-001, IND-006 e IND-007 | 1.792 |
| Somatórios Brasil = 27 UFs | 24 |
| Metadados de qualidade e validação | 784 |
| Somatórios históricos por ano e UF | 87 |
| Integração de 2024 e séries históricas no dashboard | 295 |
| Preservação dos resultados anteriores no dashboard | 25 |
| Validação pelo JSON Schema v1.0.0 | 1 |
| **Total** | **7.972** |

Critérios confirmados:

1. O CSV contém **224 linhas**: 8 períodos × 28 unidades geográficas (Brasil e 27 UFs), com uma linha por grupo e sem duplicatas.
2. O CSV, o JSON do IND-008 e a seção `pages.overview.ind008` do dashboard concordam integralmente nos grupos comparáveis, incluindo 2024.
3. As proporções são obtidas de `n_notas_1000 / n_validas` com oito casas decimais; os percentuais de `100 * n_notas_1000 / n_validas` com quatro casas decimais.
4. Para cada ano e no histórico, as 27 UFs somam exatamente o Brasil quanto a registros totais, redações válidas e redações nota 1000.
5. Os totais históricos por UF e Brasil reproduzem a soma aritmética das sete edições.
6. As populações `POP_ALL` e `POP_VALID` coincidem com o IND-001 e com o IND-007; o denominador `POP_VALID` também coincide com o IND-006.
7. A quantidade de notas 1000 nunca excede a contagem da faixa final `[900,1000]` do IND-006 (observação: essa verificação é necessária, mas não identifica por si só notas exatamente 1000).
8. O dashboard conserva os KPIs e dados de IND-001 a IND-007 nos elementos auditados e incorpora o IND-008 em `pages.overview.kpis.perfect_scores`, `pages.overview.ind008`, `pages.temporal.ind008`, `pages.methodology.ind008` e `quality.ind008_validation`.
9. O documento `dashboard_enem_2024.json` satisfaz formalmente `04_resultados_analises.schema.json` (draft 2020-12, schema version 1.0.0).
10. O status de divulgação continua `draft`.

**Limitação importante:** as contagens agregadas e sua integração foram validadas, assim como a expressão do método no script. Não houve uma segunda execução independente sobre os arquivos brutos originais para confirmar quais linhas têm nota exatamente igual a 1000; logo, não se trata de certificação independente dos microdados.

## 4. Células pequenas e supressão antes de publicar

O script identifica `requer_revisao_privacidade = True` quando `1 <= n_notas_1000 <= 29`.

| Período | Células estaduais positivas inferiores a 30 |
|---|---:|
| 2019 | 17 |
| 2020 | 15 |
| 2021 | 10 |
| 2022 | 13 |
| 2023 | 17 |
| 2024 | 10 |
| 2025 | 6 |
| **Anos separados** | **88** |
| Consolidado histórico 2019–2025 | 20 |
| **Células estaduais em todos os recortes** | **108** |

Adicionalmente, as próprias contagens nacionais anuais de **2020 (28)**, **2021 (22)**, **2024 (12)** e **2025 (10)** são positivas e inferiores a 30. Elas também exigem decisão de divulgação segundo a política definida pelo projeto.

A publicação deve considerar **supressão primária e complementar**. Ocultar apenas células estaduais pode permitir recomposição de valores por diferença com Brasil, outros estados ou somas históricas. Não divulgar em Streamlit ou dashboard público esses recortes sem tratamento explícito da política de privacidade.

**Atenção à semântica do dashboard:** `quality.suppression.suppressed_cells = 0` permanece do indicador-base IND-001 e **não deve ser interpretado como “nenhuma pendência de supressão no painel”**. Para o IND-008, `quality.ind008_validation.celulas_uf_positivas_inferiores_30 = 10` em 2024 e `pages.overview.ind008.privacy_review_required = true`. Antes de divulgação, recomenda-se distinguir a métrica de supressão do IND-001 do estado global dos demais indicadores ou atualizar o sumário global de privacidade.

## 5. Resultado final e próximos passos

**Aprovado tecnicamente para análise interna**: não foram encontradas divergências nas 7.972 verificações efetuadas. **Não publicar ainda**, devido às células pequenas e à revisão acadêmica pendente.

Próximas ações recomendadas:

1. Guardar este relatório em `docs/` no repositório.
2. Definir e aplicar supressão primária e complementar antes de ativar visualização pública do IND-008 (e dos indicadores 006 e 007, que possuem alertas análogos).
3. Manter `data_status: "draft"` até validação acadêmica e revisão de divulgação.
4. Prosseguir com o catálogo de indicadores apenas após assegurar que não haja dois scripts gravando simultaneamente os dashboards.

*Documento produzido a partir dos arquivos agregados disponíveis nesta sessão. A consistência dos agregados não equivale à auditoria da extração original a partir dos microdados.*
