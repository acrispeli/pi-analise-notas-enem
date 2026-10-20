# Validação Técnica — IND-018: Tamanho dos clusters (ENEM 2019–2025)

> **Parecer:** APROVADO TECNICAMENTE PARA ANÁLISE INTERNA, com ressalvas metodológicas. **Não equivale à autorização para publicação externa.**

## 1. Identificação e escopo

- **Projeto:** Projeto Integrador IV — UNIVESP.
- **Indicador:** `IND-018` — **Tamanho dos clusters**, prioridade P1.
- **Objetivo:** quantificar e calcular a participação percentual de cada perfil do IND-017 na **população completa de redações válidas (`POP_VALID`)**.
- **Método declarado:** padronização C1–C5 segundo IND-014; classificação por distância euclidiana quadrática até os centroides K-Means já treinados no IND-017, sem novo treinamento. Empates resolvidos pelo menor `cluster_id` (regra declarada; atribuição individual não refeita nesta auditoria).
- **Abrangência:** Brasil e **27 UFs** de aplicação (`SG_UF_PROVA`), anos 2019–2025 e histórico 2019–2025. Por UF são **26 estados e Distrito Federal**.
- **Fontes principais recebidas:** `IND_018_tamanho_clusters.csv`, `IND_018_tamanho_clusters.json`, `dashboard_enem_2024.json`.
- **Referências cruzadas disponíveis:** módulos IND-001, IND-014 e IND-017; JSON Schema `04_resultados_analises.schema.json`.
- **Versão declarada:** `2.17.0-ind001-...-ind018`, esquema do módulo `ind018-module-1.0.0`; `meta.data_status = draft`.

## 2. Parecer executivo

- **36.161 verificações aprovadas; 0 divergências.**
- **224 recortes**: (7 anos + 1 histórico) × (Brasil + 27 UFs).
- **896 linhas de perfis** no CSV; quatro perfis por recorte, todos com `k=4`.
- **Menor célula populacional:** 268 redações (**RR / 2022 / P1**), superior ao limiar mínimo adotado de 30.
- **Concordância dos denominadores com o IND-001**, para todos os recortes; conferência dos centroides e do tamanho amostral contra IND-017 e das médias/escalas contra IND-014.
- **CSV, JSON modular e dashboard cumulativo de 2024** correspondem nos conteúdos relevantes auditados.
- **Anomalia singular SC/2023** preservada, sem exclusão: `soma(C1..C5) − NU_NOTA_REDACAO = -30` para uma participação.

**Importante:** a consistência aritmética dos resultados agregados não prova que as 3.002.710 redações foram corretamente atribuídas pelo classificador. A contagem individual exigiria nova leitura independente dos microdados originais, não realizada nesta rodada.

## 3. Resultados nacionais — ENEM 2024

**População total:** 3.002.710 redações válidas. **Amostra de treinamento do IND-017:** 4.000.

| Perfil | N POP_VALID | % POP_VALID | % na amostra IND-017 | Diferença população − amostra |
|---|---:|---:|---:|---:|
| P1 | 488.360 | 16,264% | 16,575% | -0,311 p.p. |
| P2 | 938.855 | 31,267% | 32,525% | -1,258 p.p. |
| P3 | 817.796 | 27,235% | 26,550% | 0,685 p.p. |
| P4 | 757.699 | 25,234% | 24,350% | 0,884 p.p. |
| **Total** | **3.002.710** | **100%** | **100%** | — |

O perfil **P2** representa a maior participação populacional em 2024: **31,27%**. Os percentuais da amostra de treinamento IND-017 **não** devem substituir os percentuais populacionais do IND-018. A classificação não é oficial do INEP.

### Perfil médio de cada grupo nas cinco competências — Brasil 2024

Valores dos **centroides de treinamento do IND-017** (0–200 em cada competência). Não são notas médias populacionais recalculadas no IND-018; servem como descrição dos centros utilizados para classificar todas as redações.

| Perfil | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| P1 | 94,600 | 110,106 | 78,914 | 91,825 | 42,112 |
| P2 | 116,249 | 130,869 | 112,191 | 118,770 | 92,513 |
| P3 | 129,906 | 168,682 | 129,096 | 141,224 | 139,134 |
| P4 | 156,427 | 188,275 | 165,031 | 181,520 | 180,205 |

Os grupos P1–P4 estão ordenados internamente pela soma dos centroides. C1–C5 participam conjuntamente da distância no espaço padronizado; a semelhança em somente uma competência não determina o cluster.

### Exemplo por UF: São Paulo, 2024

**UF de aplicação da prova**, não de residência. 476.463 redações válidas.

| Perfil | N POP_VALID | % POP_VALID | % na amostra IND-017 | Diferença população − amostra |
|---|---:|---:|---:|---:|
| P1 | 67.126 | 14,088% | 13,825% | 0,263 p.p. |
| P2 | 158.116 | 33,185% | 33,725% | -0,540 p.p. |
| P3 | 131.647 | 27,630% | 27,525% | 0,105 p.p. |
| P4 | 119.574 | 25,096% | 24,925% | 0,171 p.p. |

Os centroides e a padronização de São Paulo foram ajustados separadamente. **Não se deve somar o P1 das 27 UFs para obter o P1 nacional**, nem presumir que rótulos iguais designem perfis equivalentes.

## 4. Consolidado histórico — Brasil, 2019–2025

**População:** 20.064.902 participações com redações válidas, sem identificação única de pessoas. O histórico tem **modelo K-Means próprio**, treinado em 4.000 observações, e não representa simplesmente uma soma de clusters anuais.

| Perfil | N POP_VALID | % POP_VALID | % na amostra histórica | Diferença população − amostra |
|---|---:|---:|---:|---:|
| P1 | 1.503.406 | 7,493% | 8,350% | -0,857 p.p. |
| P2 | 6.277.461 | 31,286% | 31,475% | -0,189 p.p. |
| P3 | 7.469.945 | 37,229% | 37,750% | -0,521 p.p. |
| P4 | 4.814.090 | 23,993% | 22,425% | 1,568 p.p. |
| **Total** | **20.064.902** | **100%** | **100%** | — |

### Quantidades por ano

| Ano | N de redações válidas | P1 | P2 | P3 | P4 |
|---|---:|---:|---:|---:|---:|
| 2019 | 3.779.356 | 8,65% | 30,13% | 42,38% | 18,85% |
| 2020 | 2.674.914 | 15,89% | 24,47% | 38,35% | 21,28% |
| 2021 | 2.293.797 | 22,42% | 39,42% | 18,89% | 19,26% |
| 2022 | 2.363.615 | 12,12% | 38,50% | 26,94% | 22,43% |
| 2023 | 2.704.814 | 13,41% | 36,51% | 25,58% | 24,50% |
| 2024 | 3.002.710 | 16,26% | 31,27% | 27,24% | 25,23% |
| 2025 | 3.245.696 | 20,31% | 36,41% | 25,37% | 17,91% |

**Os percentuais de P1, P2, P3 e P4 entre anos não constituem uma série temporal de categorias invariantes**, porque cada ano possui modelo e centroides próprios. Uma comparação substantiva entre períodos exige alinhamento dos perfis ou modelo comum; a listagem é uma descrição independente de cada ano.

## 5. Bateria de testes e rastreabilidade

| Eixo de verificação | Testes | Resultado |
|---|---:|---|
| Aritmetica populacional | 3.584 | Aprovado |
| Arquivos e versoes | 30 | Aprovado |
| Atributos clusters | 6.272 | Aprovado |
| Csv integridade | 13.441 | Aprovado |
| Dashboard 2024 | 717 | Aprovado |
| Esquema dashboard | 1 | Aprovado |
| Geografia | 40 | Aprovado |
| Historico e anomalias | 52 | Aprovado |
| Pca e ind017 | 11.648 | Aprovado |
| Populacao ind001 | 224 | Aprovado |
| Preservacao | 152 | Aprovado |
| **Total** | **36.161** | **0 divergências** |

### Regras conferidas

1. **Cobertura:** sete anos, uma série histórica, 28 unidades geográficas por período, quatro clusters por recorte, sem chaves CSV duplicadas.
2. **Integridade:** identificação, versão, estado `draft`, esquema JSON do dashboard e formato CSV em 14 colunas; cobertura das 896 combinações período–UF–perfil.
3. **Contagens e proporções:** soma dos quatro perfis igual à `POP_VALID`, percentuais reproduzidos diretamente de `N_cluster / N_validas`, somas iguais a 100% dentro da tolerância de arredondamento.
4. **Reutilização dos modelos:** tamanho da amostra, k, notas dos centroides e atributos de IND-017 iguais aos declarados na saída IND-018; transformação inversa de `z-score` para notas usando médias/desvios do IND-014 consistente.
5. **Fontes de população:** todos os 224 denominadores de Brasil/UF/ano/histórico também coincidem com o IND-001.
6. **Histórico e geografia:** totais de UFs reconciliam com Brasil para **população total**, e totais anuais reconciliam com o histórico para **total de participações**. Não se espera que os grupos locais tenham a mesma composição dos grupos nacionais.
7. **Dashboard 2024:** `pages.competencies.clusters.sizes` e painéis temporais/metodológicos do IND-018, indicadores de qualidade, e preservação verificável da página anterior do IND-017.
8. **Privacidade básica:** menor grupo populacional tem 268 participações; os artefatos de IND-018 não exportam registros individuais.
9. **Anomalia preexistente:** registro singular de SC/2023 preservado; nenhuma imputação ou ajuste para mascarar a diferença de -30 pontos.

**Tolerâncias numéricas** proporcionais às casas decimais armazenadas: proporções em torno de `5,1×10⁻¹¹`, percentuais `5,1×10⁻⁷`, transformação inversa de centroides até `10⁻⁶` ponto, além de checagens exatas para contagens inteiras, IDs e estruturas. Maior diferença de reconstrução de centroides observada: aproximadamente `0.000000526` ponto.

## 6. Limitações metodológicas e de privacidade

**Esta validação é uma auditoria de consistência de artefatos agregados reais; não uma reexecução independente sobre microdados.** Portanto, não se verificou independentemente, redação a redação, a atribuição ao centro mais próximo, eventual critério de desempate ou a contagem gerada diretamente das cinco notas individuais. Os totais agregados batem internamente e com os indicadores de referência, mas um erro sistemático de classificação individual poderia não aparecer nessas conciliações.

**K-Means:** perfis foram treinados no IND-017 com amostra determinística de até 4.000 observações por recorte; `k=4` é uma escolha exploratória, não derivada do edital ou de um estudo de ótimo. A adequação, estabilidade, silhouette e outros diagnósticos ainda dependem do IND-019. A distinção entre P1–P4 é **local a cada modelo** e não autoriza inferências diretas de mudança temporal ou ranking entre UFs.

**Privacidade:** as 896 células populacionais estão acima do limiar primário de 30, mas isso **não** significa que o painel inteiro esteja liberado. Persistem riscos de reconstrução por cruzamento de indicadores e supressão complementar pendente em IND-007/008/012/016. O campo geral legado `quality.suppression.suppressed_cells = 0` não descreve todas as supressões do conjunto e **não deve ser interpretado como ausência de riscos**. O status do dashboard permanece `draft`.

**Abrangência auditada:** apenas o **dashboard cumulativo de 2024** foi disponibilizado nesta rodada. O módulo declara gerar sete dashboards, porém os outros seis dashboards cumulativos finais não foram individualmente examinados. As versões anteriores do IND-017 e dos indicadores precedentes foram comparadas por suas referências modulares e partes auditáveis do dashboard, não por comparação byte a byte de sete dashboards.

## 7. Parecer e próximos passos

**IND-018 APROVADO TECNICAMENTE PARA USO INTERNO**, com **36.161 verificações e nenhuma divergência**, respeitados os limites descritos. A aprovação não equivale à revisão acadêmica do significado dos perfis nem à conformidade final para publicação pública.

- Salvar este relatório na pasta `docs/` do repositório.
- Manter os artefatos como `draft` e a revisão de privacidade pendente.
- Prosseguir ao **IND-019 — Qualidade dos clusters**, para avaliar empiricamente o número e a estrutura dos grupos antes de interpretá-los como categorias estáveis.
- Não alterar o Streamlit sem autorização explícita.

## 8. Arquivos da auditoria

- `auditoria_IND018.py` — código independente e reproduzível da auditoria.
- `auditoria_IND018_resultados.json` — resultados detalhados, métricas, testes, SHA-256 dos insumos e ressalvas.
- `Validacao_Tecnica_IND_018_ENEM_2019_2025.md` — este relatório.

---
**Classificação:** uso técnico-acadêmico interno; revisão acadêmica e de privacidade pendentes.
