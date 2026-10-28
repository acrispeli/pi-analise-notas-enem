# Validação Técnica — IND-019 | Qualidade do clustering — ENEM 2019–2025

**Projeto Integrador IV — UNIVESP**
**Situação:** APROVADO TECNICAMENTE COM RESSALVAS para análise interna; **não liberado para publicação externa**.
**Testes de consistência:** 9.110 verificações; 0 divergências (baseadas em resultados agregados, sem reexecutar microdados).
**Escopo efetivamente auditado:** IND-019 CSV e JSON completos; fontes agregadas IND-014, IND-017 e IND-018; dashboard cumulativo de 2024. Outros seis dashboards não foram recebidos para verificação de conteúdo.
**Data registrada de geração dos resultados:** 2026-10-19T00:44:44+00:00

## 1. Objetivo e escopo
Examinar a validade computacional e a consistência do IND-019, que calcula três indicadores de separação dos perfis K-Means já existentes (IND-017) sobre a **AMOSTRA_ML de 4.000 participações por recorte**: **Silhouette** (maior melhor), **Davies–Bouldin** (menor melhor) e **Calinski–Harabasz** (maior melhor). A Silhouette é estimada por subamostra determinística de **800 observações por recorte**, enquanto Davies–Bouldin e Calinski–Harabasz usam as 4.000 observações. Uma comparação exploratória de **k=2 a k=8** é calculada para o Brasil em 2019–2025 e histórico. A comparação por k para UF **não** foi executada por se tratar do modo padrão `comparacao_k=brasil`.

A cobertura inclui **7 anos + histórico**, **Brasil + 27 UFs por período**, somando **224 recortes**, além de **56 experimentos alternativos nacionais**. A UF corresponde a `SG_UF_PROVA` (local da prova, não residência). O histórico conta participações, não pessoas únicas, e foi modelado separadamente.

## 2. Arquivos e rastreabilidade
| Arquivo conferido | Finalidade | SHA-256 (12 primeiros caracteres) |
|---|---|---|
| `IND_019_qualidade_clustering.csv` | Saída tabular; 224 linhas | `ce13822545ca` |
| `IND_019_qualidade_clustering.json` | Saída modular; 224 modelos e 56 alternativas | `b63e78c4f54a` |
| `dashboard_enem_2024.json` | Dashboard cumulativo; integração IND-019 | `d75aefbf200b` |
| `IND_014_variancia_explicada_pca.json` | Referência de amostra/universo PCA | `c116e672f62a` |
| `IND_017_perfis_competencias.json` | Amostra, centroides, frequência e inércia de referência | `bdd4593d2024` |
| `IND_018_tamanho_clusters.json` | Contagens da população válida | `174780234723` |

## 3. Resultado da auditoria independente
- **9.110 verificações aprovadas** e **0 divergências**.
- **224 linhas** CSV correspondentes aos **224 modelos** JSON, sem chaves duplicadas; Brasil, 27 UFs, 7 anos e histórico completos.
- Equivalência CSV↔JSON de todos os índices e denominadores; domínio numérico e finitude das métricas verificados.
- Contagem por amostra: `sum(cluster_n_amostral)=4.000` em cada recorte, com mínimo por cluster sempre ≥30; **menor cluster amostral: 226 observações**.
- Cruzamento com IND-014, IND-017 e IND-018: denominadores, k, contagem amostral e inércia consistentes, observadas as precisões diferentes de arredondamento (IND-017 usa menos decimais para inércia).
- Todos os 56 experimentos nacionais alternativos k=2..8 presentes; limites, parâmetros e argmin/argmax das métricas recalculados e consistentes.
- Dashboard 2024: seção `pages.competencies.clusters.quality`, visão por UF, histórico/linha temporal, método, metadados e preservação dos trechos publicados dos IND-017 e IND-018 verificados.
- A divergência conhecida **SC/2023** (1 participação, soma das competências menos nota da redação = −30) continua registrada, sem exclusão.

## 4. Brasil 2024: avaliação do modelo publicado, k=4
Na amostra do IND-017 (n=4.000): Silhouette **0,2824** (n=800 no cálculo do índice), Davies–Bouldin **1,2801** e Calinski–Harabasz **3.083,5665**. Esses valores descrevem **separação interna moderada e com sobreposição**, não um teste de significância nem evidência automática de número ótimo de grupos.

### 4.1 Comparação exploratória nacional — candidatos k=2..8
| k | Silhouette ↑ | Davies–Bouldin ↓ | Calinski–Harabasz ↑ |
|---:|---:|---:|---:|
| 2 | 0,4367 | 0,8730 | 4.424,6304 |
| 3 | 0,3253 | 1,1226 | 3.676,4485 |
| 4 | 0,2824 | 1,2801 | 3.083,5665 |
| 5 | 0,2363 | 1,4182 | 2.598,7468 |
| 6 | 0,2359 | 1,3816 | 2.343,4625 |
| 7 | 0,2238 | 1,3782 | 2.152,4797 |
| 8 | 0,2228 | 1,4328 | 1.975,5439 |

O **k=2** obteve simultaneamente a melhor Silhouette (**0,4367**), o menor Davies–Bouldin (**0,8730**) e o maior Calinski–Harabasz (**4.424,63**) em 2024. A solução de k=4 permanece válida como **hipótese exploratória para detalhamento pedagógico**, mas **não foi favorecida pelos três índices de separação**. Os experimentos alternativos usam `n_init=20`, `seed=42`, enquanto o IND-017 original usa `n_init=5`, `seed=17017`; no Brasil 2024 o k=4 alternativo produziu os mesmos índices da solução original.

### 4.2 Síntese anual nacional
| Ano/período | Silhouette k=4 original | Melhor Silhouette | Melhor Davies–Bouldin | Melhor Calinski–Harabasz |
|---|---:|---:|---:|---:|
| 2019 | 0,2854 | k=2 | k=2 | k=2 |
| 2020 | 0,3207 | k=2 | k=2 | k=3 |
| 2021 | 0,2830 | k=2 | k=2 | k=2 |
| 2022 | 0,2797 | k=2 | k=2 | k=2 |
| 2023 | 0,2846 | k=2 | k=2 | k=2 |
| 2024 | 0,2824 | k=2 | k=2 | k=2 |
| 2025 | 0,2592 | k=2 | k=2 | k=2 |
| 2019-2025 | 0,2758 | k=2 | k=2 | k=2 |

**Padrão observado:** Silhouette e Davies–Bouldin apontam para **k=2 nos 8 recortes nacionais**. Calinski–Harabasz aponta para k=2 em 7 recortes e para k=3 em 2020. Esses índices são descritivos e não determinam, isoladamente, a segmentação pedagógica ideal.

### 4.3 UFs — 2024
Com k=4, a Silhouette por UF variou entre **0,2458 (PR)** e **0,3050 (CE)**. Estes valores medem separação nos próprios recortes; os modelos foram estimados separadamente, e os rótulos P1...P4 não são equivalentes entre UFs. **Não se deve usar tais diferenças como um ranking de qualidade de escolas, professores ou participantes.**

## 5. Ressalvas e ajustes recomendados
**Ressalva científica principal — k=4:** a comparação interna apoia fortemente investigar **k=2**. Manter k=4 exige fundamentação pedagógica, avaliação de estabilidade (múltiplas sementes e amostras), sensibilidade à quantidade de grupos e interpretação dos cinco centroides. Não alterar IND-017/018 retroativamente sem planejamento: seria necessário reexecutar de forma coordenada os indicadores dependentes e suas validações.

**Precisão das métricas:** a Silhouette é calculada em apenas 800 redações das 4.000 selecionadas por recorte, e pode variar entre subamostras. A amostra foi reconstituída pelo pipeline, mas esta auditoria externa verificou apenas os agregados e **não reexecutou** a seleção bottom-k, o K-Means, a atribuição individual ou o cálculo independente das métricas sobre os microdados.

**Metadados legados do dashboard:** `quality.ind017_validation.model_quality_indices` e `quality.ind018_validation.model_quality_indices` ainda informam “IND-019 pendente”; entretanto, `quality.ind019_validation.status=ok` e a seção `pages.competencies.clusters.quality` já existem. Atualizar futuramente essas mensagens sem apagar o histórico da validação. Trata-se de inconsistência **documental**, não dos cálculos.

**Divulgação:** `data_status=draft`. Não foram exportados pontos individuais. Os grupos do IND-019 obedecem ao mínimo de 30 na amostra; isto **não substitui revisão acadêmica, supressão complementar e privacidade do dashboard completo**, que apresenta outras frequências potencialmente sensíveis. Os agrupamentos não são oficiais do INEP.

**Alcance geográfico:** o dashboard de 2024 foi inspecionado, mas a gravação e preservação efetivas dos dashboards dos anos 2019–2023 e 2025 não foram conferidas nesta rodada. O JSON declara que seriam gerados, o que não equivale a validação dos arquivos.

## 6. Parecer e próximos passos
**Parecer:** IND-019 tecnicamente aprovado com ressalvas para fins de análise interna do Projeto Integrador IV. A consistência dos artefatos recebidos está confirmada; a decisão científica sobre manter 4 perfis **fica em aberto** e deve ser registrada como hipótese exploratória, diante da melhor separação dos modelos de 2 grupos.

**Antes da divulgação acadêmica:** submeter à equipe as comparações k=2 vs k=4 com os centroides C1–C5, testar estabilidade da clusterização, avaliar amostragem e privacidade, e revisar a nomenclatura dos perfis. **Próxima execução técnica:** IND-020, preferencialmente depois de conservar cópias versionadas dos resultados IND-019.

## 7. Arquivos de evidência
- `auditoria_IND019.py`: rotina independente de consistência; saída somente agregada.
- `auditoria_IND019_resultados.json`: totais dos testes, eventuais divergências e avisos documentais.
- Saídas reais recebidas: CSV e JSON modular IND-019 e `dashboard_enem_2024.json`.

