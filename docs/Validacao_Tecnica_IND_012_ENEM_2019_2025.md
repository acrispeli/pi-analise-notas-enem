# Validação Técnica — IND-012 | Distribuição dos níveis das competências C1–C5

**Projeto Integrador IV — UNIVESP**
**Período:** ENEM 2019–2025
**Data da auditoria:** 18/10/2026
**Conclusão:** **APROVADO TECNICAMENTE PARA ANÁLISE INTERNA, COM RESSALVAS DE PUBLICAÇÃO**.
**Status dos dados:** `draft` — não liberados para divulgação pública.

## 1. Escopo, fontes e definição

Foram auditados os três arquivos produzidos pela execução do IND-012:

- `IND_012_distribuicao_niveis_competencias.csv` (11.849 linhas de dados);
- `IND_012_distribuicao_niveis_competencias.json` (módulo completo, 2019–2025 e consolidado);
- `dashboard_enem_2024.json` (integração cumulativa até IND-012).

Como referências, foram usados os JSONs modulares de IND-001, IND-002, IND-009, IND-010 e IND-011; para a estrutura do dashboard, o JSON Schema v1.0.0. A população corresponde às redações válidas (`POP_VALID`), identificadas por `TP_STATUS_REDACAO=1` e `NU_NOTA_REDACAO` numérica de 0 a 1000. Cada pontuação numericamente observada de `NU_NOTA_COMP1` a `NU_NOTA_COMP5` é um nível distinto (0–200), sem arredondar nem agrupar.

A dimensão geográfica é `SG_UF_PROVA` (UF de aplicação, **não** residência). O consolidado histórico agrega **participações por edição**, não indivíduos únicos.

## 2. Procedimentos de auditoria independente dos arquivos agregados

- Conferência de 224 recortes geográficos/temporais (2019–2025 e consolidado; Brasil + 27 UFs) × 5 competências = **1.120 grupos**.
- Conferência da identidade e dos campos do CSV com as **11.849 células de frequência do JSON**; verificação de unicidade, ordenação e intervalo dos níveis.
- Recálculo de `proporcao = quantidade / n_validas`, `percentual = 100 × proporcao`, totalização das frequências até o denominador `POP_VALID` e marcação de células 1–29.
- Reconstrução **a partir das frequências** de soma de notas, média, mediana, P25, P75, IQR, variância e desvio-padrão populacional (`ddof=0`); quantis Hyndman–Fan tipo 7 com interpolação linear.
- Confronto das estatísticas reconstruídas com os controles internos e com os IND-009, IND-010 e IND-011, e da população com o IND-001 e IND-002.
- Reconciliação integral de cada pontuação Brasil = soma das 27 UFs em cada período e consolidado histórico = soma das sete edições por UF e competência, sem médias de percentuais.
- Conferência dos níveis por competência da edição 2024, séries nacionais anuais e histórico Brasil + UFs integrados no dashboard, mantendo os indicadores anteriores; validação do JSON Schema.
- Controle da ocorrência excepcional nos dados-fonte de SC/2023 e manutenção de metadados `data_status=draft`.

### Contagem de verificações

| Categoria | Verificações aprovadas |
|---|---:|
| Estrutura e população | 2.931 |
| Referências a indicadores anteriores | 14.420 |
| Anomalia da fonte (SC/2023) | 449 |
| Frequências e propriedades dos níveis | 28.178 |
| Reconstrução de estatísticas | 10.080 |
| Recálculo de proporções | 23.698 |
| Revisão de células pequenas | 12.992 |
| Reconciliação UFs e histórico | 180 |
| Correspondência CSV ↔ JSON | 165.888 |
| Integração do dashboard | 14.075 |
| Metadados e JSON Schema | 2 |
| **Total** | **272.893** |

**Resultado:** 272.893 aprovadas; **zero divergências não reconciliadas**.

## 3. Resultados nacionais — 2024

**Redações válidas:** 3.002.710.

| Competência | Moda (pontuação) | Quantidade no nível modal | Percentual |
|---|---:|---:|---:|
| C1 | 120 | 1.112.253 | 37,0416% |
| C2 | 120 | 813.185 | 27,0817% |
| C3 | 120 | 1.044.142 | 34,7733% |
| C4 | 120 | 961.588 | 32,0240% |
| C5 | 120 | 458.865 | 15,2817% |

**Interpretação:** a pontuação modal foi 120 nas cinco competências em 2024. As distribuições, contudo, não são equivalentes: a C5 tem maior heterogeneidade, consistente com o IND-011 (desvio-padrão nacional 58,1138, IQR 80). A C2 apresenta 556.774 ocorrências de 200 pontos (18,5424%); a C5 apresenta 200.196 ocorrências de zero ponto (6,6672%).

## 4. Anomalia da fonte: SC/2023

Os quatro resultados agregados associados à anomalia são coerentes: 2023/SC e 2023/BR, bem como histórico/SC e histórico/BR, registram **uma ocorrência de C3 = 10**, sem arredondar para múltiplos de 20. O diagnóstico anterior encontrou uma redação em SC/2023 com nota total 320 e competências 80, 40, 10, 120 e 40, cuja soma é 290 (diferença −30). O IND-012 preserva o registro sem correção ou exclusão. O arquivo original de microdados não foi reprocessado nesta auditoria.

## 5. Revisão de privacidade antes da publicação

O limiar operacional do projeto marca células com contagens positivas de **1 a 29**. Os valores permanecem presentes nos arquivos analíticos; a marcação, por si, não constitui supressão.

| Período | Células estaduais pequenas | Células nacionais pequenas |
|---|---:|---:|
| 2019 | 116 | 0 |
| 2020 | 123 | 0 |
| 2021 | 168 | 0 |
| 2022 | 167 | 0 |
| 2023 | 126 | 1 |
| 2024 | 125 | 0 |
| 2025 | 103 | 0 |
| Histórico 2019–2025 | 29 | 1 |
| **Total de células publicadas nos recortes** | **957** | **2** |

Em **2024**, as 125 células estaduais estão distribuídas em **C1: 58**, **C3: 36** e **C4: 31**; C2 e C5 não apresentam células estaduais positivas abaixo de 30 nesse ano. A contagem nacional de 2023 de C3 = 10 (n=1) e a mesma contagem histórica também exigem revisão.

**Pendência adicional:** o campo legado geral `quality.suppression.suppressed_cells` ainda está igual a **0**, apesar de existirem células pequenas nos indicadores. Esse campo reflete supressões efetivamente aplicadas (nenhuma), **não** inexistência de risco. A aplicação pública deverá apresentar isso sem ambiguidade, aplicar política de publicação e verificar *supressão complementar*, inclusive entre UF, Brasil, anos e consolidado histórico, para evitar inferência por subtração.

## 6. Limites de validação e encaminhamento

A auditoria reconstruiu integralmente as estatísticas a partir das frequências fornecidas e as reconciliou com os indicadores anteriores, mas **não reprocessou independentemente os milhões de registros de microdados do INEP**. Dos dashboards cumulativos, **somente o ano de 2024** foi recebido e conferido nesta etapa. O JSON Schema v1.0.0 foi aprovado para esse arquivo.

**Decisão:** aprovar IND-012 **para uso interno e continuação do desenvolvimento do projeto**. Manter `draft` e bloquear a divulgação pública de tabelas com células pequenas até revisão acadêmica/metodológica, deliberação sobre a exceção de SC/2023 e solução das medidas de privacidade e supressão complementar. O Streamlit não foi alterado.

**Reprodutibilidade:** auditoria executada pelo script `auditoria_IND012.py`, com resultado registrado em `auditoria_IND012_resultados.json`.
