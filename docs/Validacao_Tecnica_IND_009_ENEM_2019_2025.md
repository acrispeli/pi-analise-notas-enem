# Validação técnica — IND-009: Média C1–C5 (ENEM 2019–2025)

**Projeto:** Projeto Integrador IV — UNIVESP
**Data:** 18 de outubro de 2026
**Status:** **APROVADO TECNICAMENTE PARA ANÁLISE INTERNA, COM RESSALVA DE INTEGRIDADE DA FONTE.**
**Estado da publicação:** `draft` — revisão acadêmica pendente.
**Versão analítica:** `2.8.1-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009`.

## 1. Objetivo, população e definição

IND-009 calcula, separadamente para C1, C2, C3, C4 e C5, a média aritmética da pontuação individual de 0 a 200 (`NU_NOTA_COMP1` a `NU_NOTA_COMP5`). A população `POP_VALID` compreende registros com `TP_STATUS_REDACAO=1`, nota total numérica e válida entre 0 e 1000, além de competências numéricas no intervalo de 0 a 200. A dimensão territorial é `SG_UF_PROVA` (UF da prova, não UF de residência).

Em cada recorte, a média é obtida por `SUM(NU_NOTA_COMPj) / N_VALIDAS`, arredondada a quatro casas. O histórico de 2019 a 2025 utiliza a **soma das pontuações** dividida pela **soma das contagens**, e não uma média simples das médias anuais. O consolidado contabiliza participações em edições, não pessoas únicas.

## 2. Materiais examinados

- `IND_009_media_competencias.csv` (arquivo enviado na execução corrigida): 1.120 registros.
- `IND_009_media_competencias.json`: sete edições, consolidado 2019–2025, por Brasil e 27 UFs.
- `dashboard_enem_2024.json`: painel cumulativo atualizado para 2024.
- Módulos previamente fornecidos `IND_001` a `IND_008` para reconciliação independente de agregados.
- `04_resultados_analises.schema.json` como contrato estrutural do dashboard.
- Diagnóstico de 2023 informado na conversa (um registro válido em SC com diferença de −30 pontos na soma das competências).

Não foram reprocessados os CSV brutos contendo as linhas individuais (`MICRODADOS_ENEM_*` e `RESULTADOS_*`): não estão disponíveis nesta auditoria. Portanto a auditoria comprova **consistência independente entre artefatos agregados, não recálculo independente a partir dos microdados brutos**.

## 3. Síntese de verificação

**33.061 verificações automatizadas executadas; 33.061 aprovadas; zero divergências não reconciliadas.** O cálculo do número de verificações é resultado da contagem dos testes lógicos efetivamente executados, e não da contagem de registros de origem.

| Família de verificações | Testes executados |
|---|---:|
| estrutura csv | 11.202 |
| estrutura json | 2.719 |
| schema | 1 |
| controle qualidade | 2.777 |
| populacoes | 3.444 |
| consistencia nota total | 448 |
| consistencia csv json | 4.480 |
| validacao matematica | 5.600 |
| agregacao geografica | 72 |
| agregacao historica | 252 |
| dashboard | 2.027 |
| preservacao ind001 008 | 39 |
| **Total** | **33.061** |

### Escopo detalhado

- **Completude e unicidade:** 8 períodos (sete edições e histórico) × 28 geografias (Brasil e 27 UFs) × 5 competências = **1.120 chaves únicas**, sem duplicação.
- **Precisão:** em todas as chaves, recalculada a razão soma/N usando tolerância de arredondamento a quatro casas decimais; notas médias dentro de [0, 200].
- **Fontes:** conferidos os nomes das variáveis, o método, a população e os arquivos de origem previstos por ano.
- **Reconciliação:** `N_VALIDAS` confere com IND-001/002/006/007/008, e a soma de `NU_NOTA_REDACAO` informada no IND-009 confere com IND-002 nos 224 grupos.
- **Geografia:** para cada ano e histórico, os 27 totais de UF foram somados e comparados ao total Brasil, inclusive por competência e contagens/deltas de inconsistência.
- **Histórico:** reconstituído como somatórios anuais por competência e UF; nenhuma média histórica foi obtida por média simples das médias anuais.
- **CSV ↔ JSON:** somas, médias, N, variáveis, categorias de população, fontes e sinais de divergência de competência coincidem.
- **Dashboard 2024:** conferidas 5 médias nacionais, 135 médias estaduais, séries históricas nacionais, consolidados históricos por UF e campos de qualidade e metodologia. O painel satisfaz o JSON Schema v1.0.0.
- **Preservação:** verificadas estruturas e valores representativos dos indicadores IND-001 a IND-008, incluindo contagens de validade, média/mediana/desvio da nota total, percentis, histograma, status e notas 1000.

## 4. Resultados nacionais: médias em pontos (0 a 200)

| Edição | Redações válidas | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 3.779.356 | 125,0579 | 127,4024 | 119,1777 | 126,2524 | 95,0114 |
| 2020 | 2.674.914 | 123,2779 | 125,4976 | 113,6120 | 127,1436 | 100,8650 |
| 2021 | 2.293.797 | 123,6635 | 143,1166 | 119,5638 | 132,9120 | 116,8670 |
| 2022 | 2.363.615 | 125,9502 | 148,7035 | 121,1780 | 136,5481 | 120,0713 |
| 2023 | 2.704.814 | 126,8400 | 145,3633 | 123,6716 | 135,4513 | 113,3852 |
| 2024 | 3.002.710 | 126,2204 | 152,5334 | 124,4475 | 135,9954 | 119,7692 |
| 2025 | 3.245.696 | 120,6208 | 136,9705 | 119,6319 | 127,3459 | 114,1461 |
| **2019–2025** | **20.064.902** | **124,4628** | **139,1839** | **120,1834** | **131,2203** | **110,5193** |

Em 2024, C2 tem a maior média (**152,5334**), seguida de C4 (**135,9954**), C1 (**126,2204**), C3 (**124,4475**) e C5 (**119,7692**). Os resultados expressam médias descritivas dos registros válidos, não estimam efeitos causais nem pessoas únicas.

## 5. Ocorrência de integridade já identificada — SC, 2023

O diagnóstico independente executado pelo responsável pelo projeto encontrou:

| Campo | Valor |
|---|---:|
| Ano / UF | 2023 / Santa Catarina |
| Registro de dados informado | #289835 |
| Nota total de redação | 320 |
| C1, C2, C3, C4, C5 | 80, 40, 10, 120, 40 |
| Soma das cinco competências | 290 |
| Diferença (soma − nota total) | **−30** |
| Ocorrências no ano de 2023 | **1 em 2.704.814 válidas** |

O IND-009 corrigido registra **exatamente uma** divergência em SC/2023, exatamente **−30** no grupo estadual e nacional de 2023, e exatamente uma ocorrência e −30 no consolidado histórico. Todos os demais grupos registram zero. As cinco competências desse registro permanecem na população e com os valores originais, sem imputação ou alteração da nota total.

**Não é possível determinar com segurança qual campo do registro está incorreto.** O valor C3=10 merece consulta adicional ao dicionário/metodologia oficial para esclarecimento de sua granularidade, sem qualquer alteração arbitrária da fonte.

A soma das notas por competência pode diferir em −30 da soma das notas totais de redação em 2023; isso está **corretamente reconciliado como exceção da fonte**, e não como discrepância do cálculo agregado. A regra `soma_competencias_igual_nota_total` aparece como `false` e a situação como `divergencias_na_fonte` em 2023. É adequada a manutenção de alerta explícito em relatório acadêmico.

## 6. Dashboard, contrato e preservação

O IND-009 se encontra em `pages.competencies.summary`, com detalhamento estadual em `pages.competencies.ind009.by_uf`, série temporal em `pages.temporal.ind009` e método em `pages.methodology.ind009`. O bloco `quality.ind009_validation` registra estado de 2024 (sem divergências naquele ano).

O dashboard de 2024 conserva os indicadores anteriores; a versão `2.8.1` e carimbo de geração coincidem com o JSON do IND-009, mantendo `data_status=draft`. O contrato JSON Schema foi validado usando `jsonschema`.

## 7. Privacidade, ressalvas e limitações

A menor população estadual/anual do IND-009 nos artefatos foi **4.953 redações válidas** (RR/2022). Por isso, as próprias médias do IND-009 não têm grupos com população N menor que 30. Isso **não** desobriga da política de divulgação dos demais indicadores. As células pequenas em IND-006, IND-007 e IND-008 permanecem pendentes de tratamento antes da publicação pública do dashboard.

**Atenção à semântica:** `quality.suppression.suppressed_cells=0` é um campo herdado de IND-001 e não demonstra a supressão efetiva das células pequenas dos indicadores posteriores. Precisa ser apresentado sem ambiguidade ou revisto no processo de preparação do painel público.

Não foram conferidos os dashboards de 2019, 2020, 2021, 2022, 2023 e 2025 nesta entrega; somente o de 2024 foi fornecido. Tampouco foram auditadas individualmente as pontuações brutas contra arquivos oficiais. Os controles automáticos não constituem aprovação acadêmica, jurídica ou de divulgação.

## 8. Conclusão e próximos passos

**Parecer:** aprovação técnica do IND-009 **para análise interna**, com a ressalva específica de uma inconsistência na fonte de 2023 (SC) documentada e reconciliada. Não se identificou erro agregado no CSV, JSON, histórico ou dashboard 2024.

Para o andamento do projeto: registrar a anomalia no relatório científico e no controle de qualidade, obter revisão acadêmica sobre a interpretação da pontuação C3=10 e manter os dados como `draft`. O IND-010 corrigido poderá ser executado após a conclusão do IND-009; o IND-011 deverá aguardar a conclusão do IND-010 para não concorrer na atualização dos dashboards.
