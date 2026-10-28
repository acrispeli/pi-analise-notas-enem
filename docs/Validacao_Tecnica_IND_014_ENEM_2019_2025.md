# Validação técnica — IND-014: Variância explicada por PCA

**Projeto Integrador IV — UNIVESP**
**Indicador:** IND-014 — Variância explicada PCA (competências C1–C5)
**Edições:** ENEM 2019–2025 e consolidado histórico
**Data da auditoria:** 18/10/2026
**Status:** **APROVADO TECNICAMENTE PARA ANÁLISE INTERNA**, com pendências acadêmicas, de privacidade e de verificação dos microdados brutos.

## 1. Arquivos e referências usados

- `IND_014_variancia_explicada_pca.csv` — 1.120 linhas, delimitador ponto e vírgula.
- `IND_014_variancia_explicada_pca.json` — sete anos, histórico 2019–2025 e modelos com estatísticas, autovetores e matrizes de Pearson.
- `dashboard_enem_2024.json` — dashboard cumulativo do ano de 2024, versão `2.13.0` e status `draft`.
- Referências agregadas da execução anterior: `IND_009_media_competencias.json`, `IND_011_dispersao_competencias.json` e `IND_013_correlacao_competencias.json`.
- `04_resultados_analises.schema.json` — JSON Schema versão 1.0.0.

Os microdados originais do INEP não foram disponibilizados nesta auditoria, nem foi realizado reprocessamento independente dos registros individuais. Os resultados desta avaliação se referem à correção matemática e à consistência dos **artefatos exportados**. Foram utilizados modelos completos por ano e UF, e não apenas os percentuais do CSV.

## 2. Resultado quantitativo

| Item | Resultado |
|---|---:|
| Verificações automatizadas | **60.819** |
| Falhas registradas | **0** |
| Linhas no CSV | **1.120** |
| Períodos | **8** (2019–2025 e histórico) |
| Geografias em cada período | **28** (Brasil e 27 UFs) |
| Modelos PCA examinados | **224** |
| Componentes por modelo | **5** |
| Participações com redações válidas — Brasil, 2024 | **3.002.710** |
| Participações com redações válidas — histórico 2019–2025 | **20.064.902** |
| Maior desvio absoluto na reconstrução de correlações e autovalores mediante agrupamento | **0,000000000071**, aproximadamente |
| Maior desvio na reconstrução da matriz por autovetores | **0,000000000231**, aproximadamente |
| Maior desvio entre matriz Pearson IND-014 e coeficientes arredondados do IND-013 | **0,000000500**, aproximadamente |
| Maior diferença entre desvio-padrão completo do IND-014 e valores arredondados a quatro casas no IND-011 | **0,000049985**, aproximadamente |

As tolerâncias consideram que os arquivos anteriores guardam Pearson com seis casas, o desvio-padrão com quatro casas e o modelo PCA com aproximadamente dez casas decimais. As 60.819 verificações não representam 60.819 replicações independentes da análise: incluem as numerosas identidades e confrontos de campos dos 224 modelos.

## 3. Procedimentos de auditoria

1. **Cobertura e denominadores:** presença dos sete anos, histórico, Brasil e 27 UFs; cinco componentes por recorte; ausência de duplicação de chaves `período × UF × componente`; conferência dos 1.120 registros do CSV. Os denominadores conferiram com os IND-009, IND-011 e IND-013; o total nacional confere com a soma das UFs e o histórico com a soma dos anos.
2. **CSV versus JSON:** valores de variância explicada, percentual explicado, proporção/percentual acumulado, autovalor padronizado, variância explicada e denominadores confrontados integralmente.
3. **Recomposição espectral:** para cada recorte, obtiveram-se a matriz Pearson `R`, a matriz dos autovetores `V` e os autovalores `λ`. Reconstituiu-se `R = Vᵀ diag(λ) V`, verificando todas as entradas e a ortogonalidade dos vetores. A soma dos autovalores é cinco, que é o traço da matriz de correlação de cinco variáveis padronizadas.
4. **Variância individual/acumulada:** verificadas `variancia_explicada = λ/5`, percentuais, acumulados e o total de 100%. Verificada a relação entre autovalor populacional e `explained_variance` da convenção amostral do PCA (`n/(n−1)`). Valores singulares confrontados com `sqrt(n × λ)`.
5. **Compatibilidade com indicadores anteriores:** médias exatas recomputadas a partir dos somatórios de IND-009; desvios-padrão reconciliados com IND-011 e correlações de Pearson comparadas com IND-013, respeitando os arredondamentos de cada indicador.
6. **Reconstrução nacional a partir das 27 UFs:** combinadas médias, covariâncias populacionais e variâncias de cada UF mediante ponderação pelos respectivos números de redações. Recalculadas matrizes de Pearson e autovalores para o Brasil em todos os oito períodos, sem fazer médias de PCAs ou de coeficientes.
7. **Reconstrução histórica independente a partir dos sete anos:** repetida a combinação de momentos para o Brasil e cada uma das 27 UFs, recalculando as matrizes e os autovalores do histórico 2019–2025. A recomposição coincidiu com o histórico exportado, dentro das tolerâncias numéricas.
8. **Dashboard de 2024:** conferidas as cinco componentes nacionais, as 27 UFs, as séries anuais e o histórico em `pages.temporal.ind014`, os metadados e `quality.ind014_validation`. Verificada preservação estrutural de indicadores anteriores e preservação dos coeficientes nacionais de Pearson e Spearman do IND-013.
9. **Contrato JSON:** validação por JSON Schema v1.0.0 aprovada.
10. **Qualidade da fonte 2023/SC:** mantido exatamente um registro com `soma(C1..C5) − nota_total = −30` em SC e Brasil em 2023 e no histórico, sem exclusão nem imputação.

## 4. ENEM 2024 — Brasil

**Base:** 3.002.710 participações com redações válidas.

| Componente | Percentual explicado | Percentual acumulado |
|---|---:|---:|
| PC1 | 76,108951% | 76,108951% |
| PC2 | 8,157055% | 84,266006% |
| PC3 | 7,076776% | 91,342781% |
| PC4 | 4,589947% | 95,932729% |
| PC5 | 4,067271% | 100,000000% |

**Leitura:** PC1 concentra aproximadamente 76,11% da variância das cinco notas padronizadas; as três primeiras componentes explicam conjuntamente aproximadamente 91,34%. Os percentuais descrevem compressibilidade estatística, não uma avaliação oficial de redações nem uma relação causal. Os pesos e a interpretação de cada eixo são matéria do IND-015.

## 5. Evolução temporal e consolidado histórico — Brasil

| Edição | Redações válidas | PC1 | PC1+PC2+PC3 |
|---|---:|---:|---:|
| 2019 | 3.779.356 | 71,923868% | 90,919594% |
| 2020 | 2.674.914 | 73,459758% | 92,636733% |
| 2021 | 2.293.797 | 71,800476% | 89,664205% |
| 2022 | 2.363.615 | 72,850882% | 90,282987% |
| 2023 | 2.704.814 | 76,896959% | 92,196739% |
| 2024 | 3.002.710 | 76,108951% | 91,342781% |
| 2025 | 3.245.696 | 75,102838% | 91,560265% |
| **Histórico 2019–2025** | **20.064.902** | **73,703497%** | **91,159287%** |

**Nota metodológica:** o histórico não é média das proporções dos sete anos. A PCA foi recomposta a partir da matriz de correlação da população histórica de participações, obtida pelo agrupamento dos momentos anuais. A análise da mesma pessoa em diferentes anos, quando houver, corresponde a participações distintas. A UF é `SG_UF_PROVA` (UF de aplicação da prova).

Os modelos de cada ano e UF são ajustados separadamente; a posição e o sentido dos eixos podem variar. Portanto, não se devem comparar diretamente pesos de PC2 e PC3 entre recortes sem verificar a estabilidade das direções.

## 6. Qualidade, limitações e publicação

- **SC/2023:** a única divergência conhecida entre soma das competências e nota total permanece contabilizada nos indicadores de qualidade: uma redação; diferença de −30 pontos. Não é possível concluir a partir destes agregados qual campo da fonte está incorreto.
- **Amostragem:** os artefatos indicam processamento sem amostragem, abrangendo todas as redações `POP_VALID`; esta afirmação sobre a execução foi verificada apenas pela coerência dos agregados, não mediante a releitura independente dos microdados.
- **Revisão dos seis outros dashboards:** foi auditado integralmente apenas `dashboard_enem_2024.json`. As outras seis saídas cumulativas listadas no módulo não foram disponibilizadas nesta etapa.
- **Escopo da validação independente:** matriz, autovalores, autovetores, variâncias e fusões históricas foram reconstruídos a partir de estatísticas agregadas exportadas. Isso é uma verificação matemática forte, mas não descarta erros sistemáticos já presentes na extração dos microdados.
- **Privacidade:** permanece `meta.data_status = draft`. IND-014 só fornece resultados agregados por grupos grandes; entretanto, os indicadores anteriores ainda têm células com contagem de 1 a 29. Em 2024, o IND-012 registra 125 células estaduais desse tipo; `quality.suppression.suppressed_cells = 0` não significa que estejam seguras para divulgação.
- **Revisão acadêmica:** definir cautelosamente a interpretação de PCA, a comparabilidade dos recortes e os nomes dos eixos após auditar IND-015. PCA é exploratória e não representa pontuação oficial do ENEM.

## 7. Conclusão

**IND-014 aprovado tecnicamente para uso analítico interno**, com **60.819 verificações e nenhuma divergência** nos arquivos fornecidos. A correspondência do modelo PCA com os dados de entrada agregados e a recomposição nacional/histórica foram confirmadas. A publicação segue condicionada à revisão acadêmica, aos procedimentos de supressão de células dos indicadores anteriores e, idealmente, à replicação dos cálculos em recortes selecionados diretamente dos microdados.

**Próximo indicador:** IND-015 — Loadings PCA. O script previamente preparado reutiliza o JSON modular aprovado do IND-014; execute-o somente depois de terminar todos os demais processos que escrevem dashboards cumulativos. O Streamlit não foi alterado.
