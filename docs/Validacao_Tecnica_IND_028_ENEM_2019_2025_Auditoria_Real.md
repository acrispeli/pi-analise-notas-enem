# Validação técnica IND-028 — Perfis de divergência (K-Means)

**Projeto:** Projeto Integrador IV — UNIVESP  
**Período analisado:** ENEM 2019 a 2025 e histórico 2019–2025  
**Data da auditoria:** 22 de outubro de 2026  
**Estado da análise:** `draft`; resultados reais agregados, com revisão acadêmica e de privacidade ainda pendentes.

## 1. Objetivo e arquivos examinados

A auditoria conferiu `IND_028_*.csv`, `IND_028_*.json` e o bloco correspondente no arquivo `dashboard_enem_2024.json` enviado. Foram examinados **896 registros de CSV**, distribuídos por **224 recortes** (2019–2025 e histórico × Brasil e 27 UFs). O dashboard de 2024 passou no contrato `04_resultados_analises.schema.json` disponível no projeto.

## 2. Parecer computacional

- **27.170 verificações programáticas executadas**, com **0 falhas** nas condições efetivamente testadas.
- Os testes incluíram consistência de campos entre CSV e JSON, somatórios, percentuais, abrangência territorial e histórica, e equivalência integral dos blocos de Brasil e UFs com o dashboard enviado para 2024.
- Este parecer **não é um recálculo independente a partir dos microdados**. Os microdados originais não foram disponibilizados nesta auditoria. Verificações sobre a mesma agregação detectam inconsistências internas, mas não comprovam, por si, a validade do cálculo original.

## 3. Método e resultados

O IND-028 ajustou K-Means sobre as **diferenças absolutas AV1−AV2 de C1 a C5**. A população-alvo de referência é `POP_EVALUATOR` com os cinco pares completos, mas os centroides, tamanhos e percentuais publicados são referentes à **amostra determinística `AMOSTRA_ML_EVALUATOR`**. Foram usadas amostras de até 4.000 registros para Brasil e 2.000 por UF, padronização com desvio-padrão `ddof=0`, `n_init=20` e `k_alvo=4`. Os perfis P1–P4 são locais a cada recorte.

| Ano | Amostra BR | Clusters (P1/P2/P3/P4) — % da amostra |
|---|---:|---|
| 2019 | 4.000 | 30,175% / 23,475% / 34,100% / 12,250% |
| 2020 | 4.000 | 28,800% / 22,525% / 34,700% / 13,975% |
| 2021 | 4.000 | 34,875% / 21,700% / 31,500% / 11,925% |
| 2022 | 4.000 | 32,350% / 28,850% / 26,950% / 11,850% |
| 2023 | 4.000 | 28,800% / 26,750% / 31,475% / 12,975% |
| 2024 | 4.000 | 42,575% / 33,575% / 18,450% / 5,400% |
| 2025 | 4.000 | 35,750% / 26,075% / 24,450% / 13,725% |
| 2019–2025 | 4.000 | 40,150% / 33,125% / 17,100% / 9,625% |

Em **2024, Brasil**, a amostra contém 4.000 das 3.167.955 participações elegíveis. Os tamanhos por perfil são **1.703, 1.343, 738 e 216**, respectivamente. Os centroides possuem somas de diferenças de **61,632; 125,272; 179,079 e 348,889 pontos**; a soma das diferenças das competências **não equivale necessariamente** à diferença absoluta da nota total, porque desvios de sinais opostos podem se compensar.

## 4. Controles específicos aprovados

1. Exatamente 224 recortes e **896 registros CSV** (quatro perfis por recorte).
2. Cada perfil tem pelo menos 30 registros amostrais; cada conjunto de perfis soma o tamanho total da amostra.
3. Percentuais fecham em 100%, médias ponderadas dos centroides reproduzem as médias amostrais e inércia média = inércia total / amostra.
4. Denominadores geográficos fecham Brasil = soma das UFs e, no consolidado, histórico = soma anual para a população elegível (não para os modelos ajustados).
5. Em cada recorte, as médias amostrais das diferenças C1–C5 são reproduzidas pelo IND-029, reforçando a consistência entre ambas as amostras agregadas.

## 5. Limitações e publicação

**Parecer: APROVADO na consistência computacional dos agregados; NÃO liberado automaticamente para publicação.** Os perfis foram treinados separadamente por UF, edição e histórico; não há identidade garantida entre P1 de diferentes períodos. A escolha de quatro perfis é exploratória, sem teste independente de estabilidade/qualidade ou generalização. Os percentuais da amostra não são percentuais da população. Não é possível inferir qual corretor estaria certo ou errado. A análise de privacidade deve considerar o dashboard completo, não só este bloco.
