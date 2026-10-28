# Validação técnica — IND-013: Correlação entre competências C1–C5

**Projeto Integrador IV — UNIVESP**
**Indicador:** IND-013 — Correlação entre competências
**Edições:** ENEM 2019–2025
**Data da auditoria:** 18/10/2026
**Status:** **APROVADO TECNICAMENTE PARA ANÁLISE INTERNA**, com ressalvas acadêmicas, de publicação e de verificação independente da correlação de Spearman.

## 1. Insumos verificados

- `IND_013_correlacao_competencias.csv` (2.240 linhas de resultados);
- `IND_013_correlacao_competencias.json` (sete edições e histórico);
- `dashboard_enem_2024.json` (dashboard cumulativo da edição 2024);
- artefatos agregados de referência IND-001, IND-002, IND-009, IND-010, IND-011 e IND-012, presentes no ambiente de auditoria;
- `04_resultados_analises.schema.json`, versão 1.0.0.

Não houve releitura independente dos arquivos individuais de microdados INEP. A verificação das correlações de Spearman reais partiu dos coeficientes exportados, dos limites matemáticos das distribuições marginais e da coerência entre formatos; **não reproduziu o cálculo exato de postos a partir das frequências conjuntas originais**. Para Pearson, foi possível recompor os coeficientes do Brasil a partir das 27 UFs e os históricos a partir dos sete anos, aplicando a lei da covariância total.

## 2. Resultado quantitativo

| Item auditado | Resultado |
|---|---:|
| Verificações automatizadas | **48.201** |
| Falhas | **0** |
| Linhas no CSV | **2.240** |
| Períodos | 8 (sete anos mais 2019–2025) |
| Recortes geográficos por período | 28 (Brasil e 27 UFs) |
| Matrizes de correlação auditadas | 448 (Spearman e Pearson) |
| Coeficientes entre pares de competências (excluída a diagonal) | 4.480 |
| Pares distintos em cada recorte | 10 |
| Total de redações válidas em 2024 | 3.002.710 |
| Total histórico de participações válidas | 20.064.902 |
| Desvio máximo das correlações de Pearson recompostas a partir de subgrupos | **0,000000714** (aprox.) |

## 3. Verificações efetuadas

1. **Integridade do CSV:** delimitador `;`, campos obrigatórios, 2.240 chaves `período × UF × par` únicas, exatamente dez pares por grupo, identificação do indicador, população POP_VALID, fontes anuais e histórica e método declarado.
2. **Cobertura:** sete anos e histórico, Brasil e 27 UFs para cada período, total de 224 grupos.
3. **Denominadores:** cruzamento dos números de redações válidas com os indicadores de referência e soma das 27 UFs, além da soma dos sete anos para o histórico.
4. **Matrizes:** dimensões 5 × 5, diagonal unitária, simetria, coeficientes finitos no intervalo [−1, +1] e matrizes positivas semidefinidas (tolerância compatível com arredondamento a seis casas).
5. **CSV × JSON:** confronto de cada par, denominador e coeficientes Spearman e Pearson; conferência do campo de diferença, com tolerância de arredondamento.
6. **Reconstrução independente de Pearson por agregados:** uso das médias exatas (`soma_notas / n`), desvios-padrão de IND-011 e correlações locais para obter covariâncias combinadas. Reconstruídos Brasil a partir das UFs (para oito períodos) e histórico a partir dos anos (para 28 geografias), com 360 comparações de pares, além de verificações de variâncias combinadas.
7. **Limites estatísticos de cada par:** verificação de Spearman e Pearson contra os limites atingíveis pelas distribuições marginais do IND-012, considerando a ordenação monotônica e antimonotônica das notas e, para Spearman, os postos médios dos empates. Isso identifica valores impossíveis, mas não equivale a recalcular os coeficientes das frequências conjuntas.
8. **Dashboard 2024:** matriz nacional e estadual, pares, denominadores, sete anos e histórico em `pages.temporal.ind013`, controles de qualidade, descrição metodológica e preservação estrutural e de valores nacionais dos indicadores anteriores.
9. **Validação JSON Schema:** `04_resultados_analises.schema.json`, versão 1.0.0, sem erros.
10. **Anomalia SC/2023:** confirmação de um registro com divergência de −30 pontos na soma das competências, presente no Brasil e em SC no ano 2023 e no histórico, compatível com os IND-009, 011 e 012; sem exclusão ou imputação.

## 4. ENEM 2024 — Spearman e Pearson nacionais

| Par | Spearman | Pearson |
|---|---:|---:|
| C1–C2 | 0,630618 | 0,617871 |
| C1–C3 | 0,755738 | 0,739996 |
| C1–C4 | 0,741720 | 0,742741 |
| C1–C5 | 0,633755 | 0,610666 |
| C2–C3 | 0,741479 | 0,738179 |
| C2–C4 | 0,707868 | 0,697605 |
| C2–C5 | 0,668530 | 0,654067 |
| **C3–C4** | **0,795874** | **0,788040** |
| C3–C5 | 0,716139 | 0,693221 |
| C4–C5 | 0,743804 | 0,720164 |

**Leitura:** C3–C4 apresentou a maior correlação de Spearman de 2024. Todos os pares tiveram associação positiva. A correlação não demonstra causalidade, e as competências são avaliadas no mesmo texto, o que deve orientar a interpretação acadêmica.

## 5. Consolidado nacional 2019–2025

| Par | Spearman | Pearson |
|---|---:|---:|
| C1–C2 | 0,573274 | 0,549318 |
| C1–C3 | 0,706819 | 0,676686 |
| C1–C4 | 0,710451 | 0,722347 |
| C1–C5 | 0,575920 | 0,560843 |
| C2–C3 | 0,731162 | 0,777913 |
| C2–C4 | 0,669118 | 0,649470 |
| C2–C5 | 0,669373 | 0,659871 |
| **C3–C4** | **0,753523** | **0,737299** |
| C3–C5 | 0,695532 | 0,686088 |
| C4–C5 | 0,693851 | 0,679873 |

O histórico representa **participações**, não pessoas únicas. A UF é a **UF de aplicação da prova** (`SG_UF_PROVA`). A matriz histórica foi fornecida como cálculo sobre a distribuição conjunta combinada; Pearson foi validado por recomposição, mas essa estratégia não permite reconstruir Spearman porque os postos globais dependem das frequências conjuntas combinadas.

## 6. Integridade e divulgação

- A exceção 2023/SC (uma redação; diferença **−30**) foi conservada nos agregados e controles.
- `meta.data_status` permanece **`draft`**; a revisão acadêmica e a decisão de divulgação continuam pendentes.
- IND-013 exporta somente coeficientes, não frequências por combinação de notas; todos os grupos de cálculo possuem mais de 30 redações válidas.
- Permanecem pendências de supressão primária e complementar de células pequenas nos indicadores anteriores, especialmente IND-006 a IND-008 e IND-012. No dashboard 2024, IND-012 identifica **125 células estaduais** com contagens entre 1 e 29. O campo herdado `quality.suppression.suppressed_cells=0` não equivale à inexistência de células sensíveis.
- Foi validado o **dashboard de 2024**, não os outros seis dashboards cumulativos.
- A conferência com JSON Schema atesta o contrato estrutural, não aprovação científica nem liberação de publicação.

## 7. Conclusão e próximos passos

**IND-013 aprovado na auditoria computacional dos artefatos exportados** (48.201 verificações, zero falhas). Recomenda-se manter o status `draft` até revisão acadêmica, revisão de privacidade dos indicadores anteriores e, para validação completa de Spearman, auditoria independente de pelo menos uma amostra controlada das frequências conjuntas brutas (ou rerun dos microdados originais com SciPy em recortes selecionados).

É possível prosseguir com o **IND-014 — Variância explicada PCA**, sem executar dois scripts que alterem dashboards cumulativos em paralelo. O Streamlit não foi alterado.
