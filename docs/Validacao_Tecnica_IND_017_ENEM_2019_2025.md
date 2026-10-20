# Validação Técnica — IND-017: Perfis de competências (K-Means)

> **Status da auditoria:** APROVADO para análise interna, condicionado às ressalvas metodológicas e de privacidade. **Não autorizado para publicação.**

## 1. Identificação

- **Projeto:** Projeto Integrador IV — UNIVESP; indicadores de redação do ENEM 2019–2025.
- **Indicador:** IND-017 — Perfis de competências.
- **Método declarado:** `StandardScaler` do IND-014 (média e desvio-padrão populacional `ddof=0`) + `sklearn.cluster.KMeans`; cinco competências C1–C5.
- **Unidades de análise:** Brasil e 27 UFs segundo `SG_UF_PROVA` (UF de aplicação da prova); sete anos e ajuste histórico próprio.
- **População fonte:** redações válidas (`POP_VALID`); **população do treinamento:** amostra determinística sem reposição (`AMOSTRA_ML`) de até 4.000 por modelo.
- **Configuração:** k-alvo 4, semente 17017, `n_init=5`, `max_iter=500`, `tol=0.0`, redução potencial de k se cluster amostral ficar com menos de 30 registros.
- **Resultados recebidos:** `IND_017_perfis_competencias.csv`, `IND_017_perfis_competencias.json`, `dashboard_enem_2024.json`.
- **Referências disponíveis para reconciliação:** `IND_014_variancia_explicada_pca.json`, `IND_016_mapa_pc1_pc2.json`, `04_resultados_analises.schema.json`.
- **Versão declarada:** `2.16.1`; `meta.data_status = draft`.

## 2. Resultado executivo

- **66.539 verificações aprovadas, nenhuma divergência** após tolerâncias apropriadas ao arredondamento das saídas.
- **224 modelos** (7 anos + histórico) × (Brasil + 27 UFs).
- **896 registros de perfis** no CSV, em 224 modelos × 4 clusters.
- **Todos os modelos usaram k=4**; nenhum precisou reduzir o número de clusters.
- **Menor cluster amostral entre todos os modelos:** 226 redações; nenhum abaixo do limiar de 30.
- **Nenhum recorte declarou refinamento adicional de iterações** (`iteracoes_refinamento = 0`); a auditoria NÃO reconstruiu as iterações em razão da ausência da amostra individual.
- **Coincidência CSV, módulo JSON e dashboard 2024** para centroides, contagens, percentuais e referências metodológicas.

## 3. Resultados nacionais reais — ENEM 2024

**População válida de referência:** 3.002.710 redações. **Amostra K-Means nacional:** 4.000 redações (0,1332% da população; valor aproximado).

| Perfil local | N amostral | % amostral | Centro C1 | Centro C2 | Centro C3 | Centro C4 | Centro C5 | Soma dos centros |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P1 | 663 | 16,575% | 94,600 | 110,106 | 78,914 | 91,825 | 42,112 | 417,557 |
| P2 | 1.301 | 32,525% | 116,249 | 130,869 | 112,191 | 118,770 | 92,513 | 570,592 |
| P3 | 1.062 | 26,55% | 129,906 | 168,682 | 129,096 | 141,224 | 139,134 | 708,041 |
| P4 | 974 | 24,35% | 156,427 | 188,275 | 165,031 | 181,520 | 180,205 | 871,458 |

**Inércia amostral (SSE em z-score):** 5.965,341; **inércia por observação amostral:** 1,491.
Os rótulos P1–P4 estão ordenados pela soma dos centros **dentro do próprio modelo**; representam perfis descritivos, não faixas ou conceitos oficiais do ENEM.

**Não interpretar 16,575%, 32,525%, 26,550% e 24,350% como percentuais de todas as redações de 2024.** Essas proporções são exclusivas das 4.000 observações de treinamento. A classificação populacional é objeto do IND-018.

## 4. Consolidado Brasil, 2019–2025

**População consolidada:** 20.064.902 participações com redações válidas, não pessoas distintas. **Amostra histórica do treinamento:** 4.000 observações.

| Perfil histórico local | N amostral | % amostral | Soma dos centros (pontos) |
|---|---:|---:|---:|
| P1 | 334 | 8,35% | 328,024 |
| P2 | 1.259 | 31,475% | 496,378 |
| P3 | 1.510 | 37,75% | 646,424 |
| P4 | 897 | 22,425% | 852,798 |

**Nota:** o histórico foi ajustado com modelo próprio (não é média de centroides anuais). Da mesma forma, cada UF tem seu próprio treinamento e sua própria padronização; os rótulos P1–P4 **não identificam obrigatoriamente o mesmo perfil** entre anos, UFs e histórico.

## 5. Rastreabilidade das verificações

| Eixo de validação | Verificações | Resultado |
|---|---:|---|
| Metadados, estrutura e parâmetros globais | 22 | Aprovado |
| Controle da divergência pontual SC/2023 | 700 | Aprovado |
| Validação do JSON Schema do dashboard 2024 | 1 | Aprovado |
| Cobertura temporal, geográfica e população | 75 | Aprovado |
| Reconstrução dos centroides e escalas com IND-014/016 | 8.736 | Aprovado |
| Limites das amostras, k, rótulos e denominadores | 3.136 | Aprovado |
| Parâmetros, iterações e inércia declarados | 2.016 | Aprovado |
| Coerência matemática dos centroides e grupos | 29.344 | Aprovado |
| Conciliação de todas as linhas CSV com o JSON | 22.400 | Aprovado |
| Conciliação do painel 2024 com o módulo | 31 | Aprovado |
| Conciliação das seções anuais e históricas no painel 2024 | 38 | Aprovado |
| Presença e controles básicos dos IND-001 a IND-016 | 34 | Aprovado |
| Ausência de colunas de identificação individual no CSV | 6 | Aprovado |
| **Total** | **66.539** | **0 divergências** |

**Critérios de tolerância:** comparação exata de IDs, quantidades inteiras e estruturas; tolerâncias proporcionais às casas decimais exportadas para z-score, centroides e inércia. Na transformação inversa z-score → pontos, maior diferença: aproximadamente **0,000000526 ponto**, coerente com pontos arredondados a seis casas e z-scores a nove casas. A tolerância conservadora nessa contraprova foi 0,0000006 ponto.

### Preservação da exceção SC/2023

As fontes do IND-017 preservaram a mesma ocorrência singular de 2023/SC, com diferença `soma(C1..C5) - NU_NOTA_REDACAO = -30`, sem imputar ou excluir o registro; a informação coincide com as saídas do IND-014/016.

## 6. Escopo e limitações (indispensáveis)

Esta foi uma **auditoria independente de consistência das saídas reais agregadas**, e não uma reexecução independente do treinamento. Os microdados do ENEM nem os 4.000 pontos de cada amostra estão disponíveis nesta auditoria. Assim, **não foram verificados independentemente**: a seleção bottom-k da amostra, os rótulos das observações, a obtenção dos centroides diretamente dos pontos, os passos efetivos de convergência, a inércia recalculada dos pontos e a estabilidade dos agrupamentos sob outras sementes ou valores de k.

**A escolha de k=4 é hipótese exploratória**; requer avaliação de qualidade (IND-019, especialmente silhouette e outros critérios pertinentes), estabilidade e interpretação acadêmica. Uma inércia não-negativa e centros matematicamente consistentes **não comprovam a qualidade substantiva** do agrupamento.

Foi enviado somente `dashboard_enem_2024.json` nesta rodada; os outros seis dashboards cumulativos não foram auditados. Há checagens pontuais de preservação de IND-001 a IND-016 no painel recebido, mas não uma comparação byte a byte com todas as versões anteriores.

**Privacidade:** nenhum identificador individual é exportado no CSV de perfis; todos os clusters amostrais observados têm pelo menos 226 redações. Isso não resolve riscos de divulgação indireta ou a supressão complementar de outros indicadores (incluindo IND-007/008/012/016). Os resultados permanecem `draft` e exigem revisão acadêmica e de privacidade antes de divulgação pública.

## 7. Conclusão e próximos passos

**Resultado:** IND-017 **aprovado tecnicamente para uso interno como artefato agregado**, sob as limitações acima. **Não confundir** essa consistência de saídas com uma validação estatística completa do K-Means ou com autorização de publicação.

**Encaminhamento:** executar o IND-018 apenas após a conclusão bem-sucedida do IND-017, para classificar a população completa com os centroides já treinados. Depois auditar os resultados reais do IND-018 e avançar ao IND-019 para examinar a qualidade dos clusters. O Streamlit não foi alterado.

## 8. Arquivos e rastreabilidade

- Script independente da auditoria: `auditoria_IND017.py`.
- Resultado detalhado: `auditoria_IND017_resultados.json`.
- Resumos criptográficos SHA-256 dos seis insumos utilizados constam do resultado detalhado.
- Arquivos auditados: CSV e JSON modular do IND-017, dashboard cumulativo 2024, JSON modular IND-014 e IND-016 e JSON Schema v1.0.0.

---
**Classificação:** validação técnica interna, pendente revisão acadêmica e privacidade.
