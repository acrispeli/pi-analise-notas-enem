# Validação técnica — IND-005: Percentis da nota da redação

**Projeto:** Projeto Integrador IV — UNIVESP  
**Período:** ENEM 2019–2025  
**Data da revisão:** 17/10/2026  
**Status técnico:** aprovado na auditoria dos arquivos agregados e em testes sintéticos do algoritmo  
**Status acadêmico:** `draft` — sujeito à revisão e aprovação acadêmica

## 1. Arquivos examinados

- `IND_005_percentis_redacao.csv` (224 registros; delimitador `;`)
- `IND_005_percentis_redacao.json` (módulo de sete edições e consolidado histórico)
- `dashboard_enem_2024.json` (integração cumulativa dos indicadores IND-001 a IND-005)
- `IND_005_percentis_redacao.py` (implementação do cálculo, para ensaios unitários)
- `04_resultados_analises.schema.json` (contrato formal de saída disponível no ambiente de validação)

## 2. Definição metodológica

População: redações com `TP_STATUS_REDACAO = 1`, `NU_NOTA_REDACAO` numérica de 0 a 1000 (inclusive). UF: `SG_UF_PROVA` (local de aplicação, não residência). São calculados P25, P50, P75, P90 e P95 pelo quantil empírico com interpolação linear de Hyndman–Fan tipo 7, também padrão do NumPy (`method="linear"`). A amplitude interquartil, IQR, é P75 − P25.

O consolidado histórico deve resultar da distribuição conjunta das notas dos sete anos; não é calculado pela média dos percentis anuais. A soma histórica conta participações, não indivíduos únicos.

## 3. Resultados nacionais

| Ano | Redações válidas | P25 | P50 | P75 | P90 | P95 | IQR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019 | 3.779.356 | 500 | 580 | 680 | 820 | 880 | 180 |
| 2020 | 2.674.914 | 480 | 580 | 700 | 860 | 920 | 220 |
| 2021 | 2.293.797 | 540 | 620 | 740 | 860 | 900 | 200 |
| 2022 | 2.363.615 | 540 | 640 | 780 | 880 | 920 | 240 |
| 2023 | 2.704.814 | 520 | 620 | 780 | 900 | 920 | 260 |
| 2024 | 3.002.710 | 540 | 640 | 800 | 880 | 920 | 260 |
| 2025 | 3.245.696 | 500 | 600 | 720 | 840 | 900 | 220 |
| **2019–2025** | **20.064.902** | **520** | **600** | **740** | **860** | **920** | **220** |

## 4. Verificações efetuadas

**3.957 verificações programáticas aprovadas e nenhuma inconsistência.** Entre elas:

1. Quantidade de registros CSV (224), unicidade e cobertura de oito períodos × Brasil e 27 UFs; confirmação dos nomes dos arquivos-fonte.
2. Correspondência de quantidades, cinco percentis e IQR entre CSV, JSON modular e JSON de dashboard 2024, quando presentes.
3. Consistência das quantidades: soma das 27 UFs em cada ano e no histórico; soma anual para o Brasil; consolidação por UF ao longo dos sete anos.
4. Percentis em ordem não decrescente e no intervalo [0, 1000]; verificação de IQR = P75 − P25; ausência de grupos positivos inferiores a 30 registros nos agregados.
5. Correspondência com indicadores anteriores mantidos no dashboard de 2024; o P50 corresponde à mediana do IND-003 nas sete edições, no histórico do Brasil e nas 27 UFs históricas.
6. Preservação dos objetos IND-001 a IND-004 no dashboard cumulativo.
7. Validação formal **do arquivo fornecido `dashboard_enem_2024.json`** usando `jsonschema` e `04_resultados_analises.schema.json` v1.0.0.
8. Comparação do algoritmo `quantis_frequencias` com NumPy em **100 distribuições sintéticas aleatórias**, cinco percentis por distribuição, sem divergências.

## 5. Interpretação e limitações

Em 2024, P25=540, mediana=640, P75=800, P90=880 e P95=920. A metade central da distribuição está compreendida entre o primeiro e o terceiro quartil, com IQR de 260 pontos. No período 2019–2025, P25=520, P50=600, P75=740, P90=860 e P95=920, com IQR de 220 pontos.

**Escopo da validação:** a auditoria examinou os três arquivos agregados enviados pelo usuário e testou o algoritmo de quantis com dados sintéticos. Não houve reprocessamento independente dos microdados originais do ENEM neste ambiente nem validação dos demais seis dashboards anuais não enviados. Consequentemente, a consistência dos arquivos fornecidos não equivale a certificação independente dos valores percentílicos reais. A declaração de status acadêmico permanece `draft`.

## 6. Encaminhamento

O IND-005 pode ser marcado **validado tecnicamente nos arquivos examinados**, manter `draft` acadêmico e ser versionado no repositório. Para acrescentar visualização específica de percentis/boxplot ao Streamlit, será necessário implementar o respectivo painel, já que a versão anterior cobre até IND-004.
