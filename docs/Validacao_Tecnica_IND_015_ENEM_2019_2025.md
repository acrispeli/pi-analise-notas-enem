# Validação técnica — IND-015: Loadings PCA

**Projeto Integrador IV — UNIVESP**  
**Indicador:** IND-015 — Loadings PCA das competências C1–C5  
**Edições:** ENEM 2019–2025, Brasil e 27 UFs, e consolidado histórico  
**Data da auditoria:** 18/10/2026  
**Status:** **APROVADO TECNICAMENTE PARA ANÁLISE INTERNA**. Permanece `data_status = draft`, sem liberação para publicação.

## 1. Objetivo e arquivos examinados

O IND-015 responde quais competências têm maior peso em cada uma das cinco componentes principais extraídas pelo IND-014. Foram examinados os artefatos:

- `IND_015_loadings_pca.csv` — **5.600 linhas** de resultados, separadas por ponto e vírgula.
- `IND_015_loadings_pca.json` — resultados anuais e históricos por Brasil/UF e matrizes 5 × 5.
- `IND_014_variancia_explicada_pca.json` — **referência agregada já validada**, contendo autovetores, autovalores e matrizes de Pearson.
- `dashboard_enem_2024.json` — integração cumulativa mais recente, versão `2.14.0-ind001-...-ind015`, `data_status=draft`.
- `04_resultados_analises.schema.json` — contrato JSON Schema v1.0.0.

**Limite da auditoria:** não foram fornecidos/reprocessados os microdados originais do INEP nesta etapa. O IND-015, por projeto, **reutiliza** os modelos calculados pelo IND-014; portanto, a verificação foi independente quanto à matemática dos coeficientes e à exportação, mas depende da correção da base e dos modelos agregados do IND-014. Apenas o dashboard de 2024 foi disponibilizado para inspeção.

## 2. Resultado quantitativo da auditoria

| Item | Valor |
|---|---:|
| Verificações automatizadas | **194.051** |
| Divergências registradas | **0** |
| Registros CSV conferidos | **5.600** |
| Períodos | **8** (2019–2025 e histórico) |
| Recortes geográficos em cada período | **28** (Brasil e 27 UFs) |
| Matrizes/modelos de PCA verificados | **224** |
| Coeficientes PCA por modelo | **25** (5 componentes × 5 competências) |
| Redações válidas no Brasil, 2024 | **3.002.710** |
| Participações históricas, Brasil 2019–2025 | **20.064.902** |
| Erros de correspondência IND-014 × IND-015 | **0** |
| Maior diferença observada entre recomputações matemáticas | **~0,000000030**, dentro das tolerâncias por arredondamento |

As 194.051 verificações são asserções automatizadas de campos e relações matemáticas; **não** são 194.051 replicações independentes do PCA.

## 3. Metodologia de validação

1. **Cobertura de dados:** estrutura de 7 edições + 1 histórico, Brasil + 27 UFs por período, 5 PCs × 5 competências por recorte; conferência de chaves únicas e exatidão das 5.600 linhas do CSV.
2. **CSV versus JSON:** confrontados denominador `n_validas`, competência, período, UF, autovalores, proporções de variância, coeficiente PCA assinado, módulo do coeficiente, correlação competência–PC, contribuição percentual, população e origem do arquivo.
3. **Coerência com IND-014:** confrontados os 5.600 coeficientes com os **autovetores originais** de `modelo.components` do IND-014; as frações de variância e os autovalores também coincidiram.
4. **Contribuições:** para cada componente `PC_k` e competência `C_j`, recalculado `contribuicao_pct = 100 × coeficiente_pca²`. Todas as linhas das matrizes somam 100% com tolerância ao arredondamento.
5. **Correlações competência–PC:** confrontadas as correlações publicadas com `coeficiente_pca × sqrt(autovalor_padronizado)`. Importante: *coeficiente PCA* e *correlação competência–PC* são grandezas diferentes.
6. **Álgebra linear:** para cada um dos 224 modelos, conferidas normas unitárias, ortogonalidade dos cinco autovetores e reconstrução da matriz de Pearson por `R = Vᵀ diag(λ) V`.
7. **Decomposição espectral independente:** realizada nova `numpy.linalg.eigh(R)` para cada matriz Pearson, com classificação decrescente por autovalor e convenção de sinal idêntica à declarada. Os novos autovalores e autovetores reproduziram os resultados publicados dentro das tolerâncias numéricas.
8. **Consolidado histórico e UF:** denominadores estaduais somam o total Brasil, e a soma das participações anuais corresponde aos totais históricos. Loadings históricos conferidos com o **modelo histórico distinto** do IND-014; não são médias dos loadings anuais.
9. **Dashboard:** verificados loadings, correlações e contribuições da matriz nacional de 2024, das 27 UFs, dos sete anos nacionais e do histórico nacional/estadual em `pages.competencies.pca` e `pages.temporal.ind015`. A variância explicada do IND-014 continua preservada.
10. **Contrato e qualidade:** dashboard válido contra JSON Schema v1.0.0. Alertas de dados de SC/2023 e revisão de privacidade mantidos.

## 4. Principais resultados — Brasil, ENEM 2024

**Base:** 3.002.710 participações com redações válidas. A PCA utilizou as cinco competências padronizadas e explica 91,342781% da variância nas três primeiras componentes.

### Matriz dos coeficientes PCA (*autovetores*)

| Competência | PC1 | PC2 | PC3 | PC4 | PC5 |
|---|---:|---:|---:|---:|---:|
| C1 | +0,436059 | +0,709933 | −0,074362 | −0,546834 | −0,035938 |
| C2 | +0,435141 | −0,425766 | +0,707660 | −0,287951 | −0,213721 |
| C3 | +0,466812 | +0,102746 | +0,175568 | +0,432878 | +0,743857 |
| C4 | +0,465465 | +0,127068 | −0,154087 | +0,597923 | −0,621242 |
| C5 | +0,431201 | −0,536670 | −0,662661 | −0,270486 | +0,117335 |

*Valores arredondados a seis casas decimais para apresentação. A orientação de cada PC é convencional: multiplicar todos os seus pesos por −1 representa a mesma componente.*

### Variância explicada e competência de maior carga absoluta

| Componente | Variância explicada | Competência dominante | Parcela quadrática da dominante |
|---|---:|---|---:|
| PC1 | 76,108951% | **C3** | **21,79%** |
| PC2 | 8,157055% | **C1** | **50,40%** |
| PC3 | 7,076776% | **C2** | **50,08%** |
| PC4 | 4,589947% | **C4** | **35,75%** |
| PC5 | 4,067271% | **C3** | **55,33%** |

**Interpretação cautelosa:**

- **PC1**: pesos **positivos e próximos entre C1–C5**; descreve uma dimensão comum de desempenho nas cinco competências, com pesos um pouco maiores para C3/C4. Sua grande variância explicada não significa que 76% da qualidade de uma redação provenha de determinada habilidade.
- **PC2**: maior peso absoluto de **C1 (+0,709933)**, contrastado sobretudo com **C5 (−0,536670)** e C2 (−0,425766). Trata-se de contraste matemático entre competências padronizadas, não de relação causal.
- **PC3**: peso elevado de **C2 (+0,707660)** em contraste com **C5 (−0,662661)**. Em 2024 C2 é a dominante desta componente; no **histórico agregado** a principal carga da PC3 é C5, indicando que a interpretação das direções pode mudar entre recortes.

## 5. Consolidado histórico — Brasil, 2019–2025

**População:** 20.064.902 participações com redações válidas.

| Componente | Variância explicada histórica | Competência dominante | Contribuição da dominante |
|---|---:|---|---:|
| PC1 | 73,703497% | C3 | 22,33% |
| PC2 | 10,107236% | C1 | 52,22% |
| PC3 | 7,348554% | C5 | 61,40% |
| PC4 | 4,920738% | C4 | 66,45% |
| PC5 | 3,919974% | C3 | 64,56% |

A PC1 é dominada por C3 em 2019–2024 e no histórico, enquanto a componente PC3 tem sua maior carga em C2 em 2024, diferindo do histórico; em 2025 também há mudanças na ordem dos maiores pesos. **Cada ano e UF tem seu próprio modelo PCA**, de modo que componentes de mesma posição não devem ser equiparadas automaticamente entre períodos. Autovalores de PC2 e PC3 são relativamente próximos em alguns recortes, o que também recomenda cautela com interpretações rígidas.

Os dados históricos contabilizam **participações, não pessoas únicas**. `SG_UF_PROVA` indica a UF de realização da prova, não necessariamente a UF de residência.

## 6. Alertas de fonte e privacidade

- **Exceção SC/2023:** um registro preservado com `soma(C1..C5) − NU_NOTA_REDACAO = −30`. A divergência está mantida na contagem de SC e Brasil em 2023 e no consolidado histórico, sem exclusão nem alteração de notas. Ela já era conhecida e não é um erro novo introduzido pelo IND-015.
- **Células pequenas dos indicadores anteriores:** o dashboard de 2024 continua informando **125 células estaduais** do IND-012 com contagens entre 1 e 29. A revisão de privacidade e a política de supressão complementar seguem pendentes. `quality.suppression.suppressed_cells=0` não é autorização de publicação.
- **Qualidade estatística:** PCA é exploratória, não causal e não faz parte do sistema oficial de notas do INEP. O sinal absoluto dos autovetores é arbitrário; apenas sua orientação é fixada por convenção na execução.
- **Escopo:** confrontaram-se agregados e modelos já exportados com recomputações matemáticas. Isso não substitui a reexecução independente dos microdados originais nem a revisão acadêmica da interpretação dos PCs.
- **Dashboards examinados:** foi inspecionado `dashboard_enem_2024.json`; os outros seis dashboards listados pelo módulo IND-015 não foram recebidos e não foram auditados individualmente nesta etapa.

## 7. Conclusão

**IND-015 aprovado tecnicamente para análise interna**, com **194.051 verificações automatizadas e zero divergências**. Os coeficientes e respectivas contribuições/correlações são consistentes com o IND-014 e com as identidades matemáticas da PCA, inclusive na reconstrução espectral independente das 224 matrizes. O CSV, o JSON e a integração cumulativa no dashboard de 2024 estão coerentes.

**Publicação não autorizada nesta etapa:** é indispensável completar a revisão acadêmica e a revisão de privacidade/supressão dos indicadores anteriores. O Streamlit permanece sem alterações.
