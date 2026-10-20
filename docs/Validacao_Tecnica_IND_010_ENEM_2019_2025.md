# Validação Técnica — IND-010 | Mediana das competências C1–C5 (ENEM 2019–2025)

**Projeto Integrador IV — UNIVESP**  
**Data da auditoria:** 18/10/2026  
**Estado:** APROVADO TECNICAMENTE para análise interna, condicionado à revisão acadêmica e à política de divulgação.  
**Estado dos dados:** `draft`.

## 1. Escopo e arquivos

Foram auditados os arquivos fornecidos após a execução do IND-010:

- `IND_010_mediana_competencias.csv` — **1.120 linhas**;
- `IND_010_mediana_competencias.json` — módulo para sete edições e consolidado histórico;
- `dashboard_enem_2024.json` — versão **2.10.0**, já **posterior ao IND-010**, com estruturas do IND-011 integradas.

Para reconciliação, foram consultados os módulos disponíveis no projeto `IND_001_redacoes_validas.json`, `IND_002_nota_media.json` e `IND_009_media_competencias.json`, além da especificação de esquema `04_resultados_analises.schema.json`. O código corrigido `IND_010_mediana_competencias_CORRIGIDO.py` foi empregado somente para testes de algoritmo com dados sintéticos. **Os microdados originais do ENEM não foram disponibilizados nesta auditoria.**

## 2. Metodologia

O indicador calcula `MEDIAN(NU_NOTA_COMPj)` para `j=1,...,5`, entre redações da população `POP_VALID` (`TP_STATUS_REDACAO=1` e nota total válida entre 0 e 1000). Considera `SG_UF_PROVA` como local da prova, não residência. O valor da mediana é encontrado pelo acúmulo das frequências completas observadas por competência; em amostras de tamanho par, toma-se a média dos dois elementos centrais.

Os **224 recortes** correspondem a oito períodos (2019, ..., 2025 e 2019–2025) multiplicados por 28 abrangências (Brasil e 27 UFs). Cada recorte possui cinco medianas, totalizando **1.120 valores**. O indicador usa a mediana da distribuição histórica combinada, **não a média ou a mediana das medianas anuais**. O consolidado representa participações nas edições do ENEM, não pessoas únicas.

## 3. Resultado das verificações

**29.202 verificações automatizadas, com zero divergências não reconciliadas.** Esse total abrange as conferências dos arquivos agregados e 307 verificações sintéticas do algoritmo. Resultados obtidos em `/mnt/data/auditoria_IND010_resultados.json`, com código reprodutível em `/mnt/data/auditoria_IND010.py`.

| Grupo de controles | Resultado |
|---|---|
| 1.120 combinações período/UF/competência, sem duplicidade | Conforme |
| CSV contra o JSON do IND-010: mediana, N, fonte, método, escala e campos | Conforme |
| População `POP_VALID` contra IND-001, IND-002 e IND-009 | Conforme |
| População total anual (`POP_ALL`) reconciliada | Conforme |
| Brasil = soma de 27 UFs para os denominadores | Conforme |
| Histórico: N = soma de sete anos para BR e cada UF | Conforme |
| Cinco competências (C1 a C5) em todos os recortes; escala de 0–200 | Conforme |
| Integração do IND-010 em `pages.competencies.summary` e `pages.competencies.ind010` | Conforme |
| Série temporal e distribuição estadual/histórica no dashboard | Conforme |
| Médias IND-009 preservadas no dashboard de 2024 | Conforme |
| Indicadores anteriores presentes no dashboard de 2024 | Conforme — preservação estrutural |
| JSON Schema 1.0.0 do dashboard 2024 | Conforme |
| 150 distribuições sintéticas comparadas com `numpy.median` | Conforme |
| 150 conferências de `preparar_grupo`, 7 casos-limite | Conforme |
| Nacionais/UF com `1 ≤ N < 30` no IND-010 | Nenhum |

Observação metodológica: sem os microdados originais ou os histogramas completos das notas das competências, **não é possível recalcular de modo independente as 1.120 medianas reais** nem provar a mediana histórica exclusivamente a partir das medianas anuais. A reconciliação comprovada é a de estrutura, população, coerência dos agregados, integração de arquivos e implementação do cálculo em testes sintéticos.

## 4. Medianas nacionais anuais

Pontuação de 0 a 200 pontos por competência.

| Edição | C1 | C2 | C3 | C4 | C5 | Redações válidas |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 120 | 120 | 120 | 120 | 100 | 3.779.356 |
| 2020 | 120 | 120 | 120 | 120 | 100 | 2.674.914 |
| 2021 | 120 | 120 | 120 | 120 | 120 | 2.293.797 |
| 2022 | 120 | 140 | 120 | 120 | 120 | 2.363.615 |
| 2023 | 120 | 140 | 120 | 120 | 120 | 2.704.814 |
| **2024** | **120** | **160** | **120** | **120** | **120** | **3.002.710** |
| 2025 | 120 | 120 | 120 | 120 | 120 | 3.245.696 |
| **2019–2025** | **120** | **120** | **120** | **120** | **120** | **20.064.902** |

Em 2024, a C2 tem mediana de 160 e as demais quatro competências apresentam 120. O fato de as cinco medianas históricas serem 120, mesmo quando algumas medianas anuais são superiores, é matematicamente possível e não configura divergência; sua verificação independente requer as frequências combinadas das competências.

## 5. Exceção de integridade de SC/2023

A auditoria verificou que a ocorrência já identificada em Santa Catarina no ano de 2023 permanece documentada pelo módulo IND-010:

- Uma redação válida com `C1=80`, `C2=40`, `C3=10`, `C4=120`, `C5=40`;
- Soma de competências **290**; nota total **320**; diferença de **−30 pontos**;
- Campo `validas_soma_competencias_divergente = 1` em 2023;
- Campos `soma_competencias_igual_nota_total = false` e `situacao_soma_competencias = divergencias_na_fonte` em 2023;
- Nenhuma ocorrência correspondente nos demais seis anos;
- Registro mantido na população, sem imputação ou alteração dos valores originais.

A qualidade do dashboard **de 2024** apresenta zero divergências no IND-010, o que é correto para a edição de 2024. Este fato não revoga a ocorrência histórica de 2023, que está documentada no JSON modular. Não houve acesso ao dashboard de 2023 para conferir essa sinalização específica nele.

## 6. Dashboard 2024 e IND-011

O dashboard recebido apresenta `analysis_version = 2.10.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009-ind010-ind011`. Foram verificadas a existência do IND-010, a integração nacional, estadual e temporal, a preservação das médias do IND-009, a presença estrutural dos indicadores anteriores, os metadados de método e população e a estrutura do IND-011. A presença do IND-011 **não equivale à validação independente de seus resultados**; para isso devem ser auditados seu CSV e seu JSON modular.

## 7. Privacidade, limites e decisão

Não foram encontrados recortes geográficos com tamanho de população inferior a 30 no IND-010. Contudo, isso **não elimina** pendências anteriores de divulgação de células pequenas nos indicadores de frequências (por exemplo, IND-006, IND-007 e IND-008) nem substitui a análise acadêmica da política de privacidade. O campo global `quality.suppression.suppressed_cells = 0` é herdado do dashboard-base e não deve ser interpretado como liberação de todos os indicadores para publicação pública.

**Decisão:** IND-010 **APROVADO TECNICAMENTE PARA ANÁLISE INTERNA**, com as ressalvas acima. A publicação continua condicionada à revisão acadêmica e à política de divulgação; mantém-se `data_status = draft`. Nenhuma modificação foi efetuada nos arquivos enviados ou no Streamlit.
