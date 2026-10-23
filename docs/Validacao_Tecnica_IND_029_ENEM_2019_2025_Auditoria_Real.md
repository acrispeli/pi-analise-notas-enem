# Validação técnica IND-029 — Avaliações atípicas (Isolation Forest)

**Projeto:** Projeto Integrador IV — UNIVESP  
**Período analisado:** ENEM 2019 a 2025 e histórico 2019–2025  
**Data da auditoria:** 22 de outubro de 2026  
**Estado da análise:** `draft`; resultados reais agregados, com revisão acadêmica e de privacidade ainda pendentes.

## 1. Objetivo e arquivos examinados

A auditoria conferiu `IND_029_*.csv`, `IND_029_*.json` e o bloco correspondente no arquivo `dashboard_enem_2024.json` enviado. Foram examinados **224 registros de CSV**, distribuídos por **224 recortes** (2019–2025 e histórico × Brasil e 27 UFs). O dashboard de 2024 passou no contrato `04_resultados_analises.schema.json` disponível no projeto.

## 2. Parecer computacional

- **13.730 verificações programáticas executadas**, com **0 falhas** nas condições efetivamente testadas.
- Os testes incluíram consistência de campos entre CSV e JSON, somatórios, percentuais, abrangência territorial e histórica, e equivalência integral dos blocos de Brasil e UFs com o dashboard enviado para 2024.
- Este parecer **não é um recálculo independente a partir dos microdados**. Os microdados originais não foram disponibilizados nesta auditoria. Verificações sobre a mesma agregação detectam inconsistências internas, mas não comprovam, por si, a validade do cálculo original.

## 3. Método e resultados

O IND-029 ajustou um **Isolation Forest** sobre a amostra determinística da população de avaliadores com pares completos. Os seis atributos são a diferença **assinada** entre notas totais (AV1−AV2) e as cinco diferenças **absolutas** C1–C5. Configuração: `n_estimators=100`, `random_state=42`, `contamination="auto"` e escore de anomalia `-score_samples`; sinaliza escores **superiores a 0,5**. A amostra reproduz os cinco momentos médios de divergência de C1–C5 do IND-028.

| Ano | Amostra BR | Sinalizados (limiar auto) | Percentual amostral |
|---|---:|---:|---:|
| 2019 | 4.000 | 1.134 | 28,350% |
| 2020 | 4.000 | 1.144 | 28,600% |
| 2021 | 4.000 | 979 | 24,475% |
| 2022 | 4.000 | 972 | 24,300% |
| 2023 | 4.000 | 1.197 | 29,925% |
| 2024 | 4.000 | 1.092 | 27,300% |
| 2025 | 4.000 | 1.074 | 26,850% |
| 2019–2025 | 4.000 | 1.097 | 27,425% |

Em **2024, Brasil**, foram sinalizadas **1.092 das 4.000 observações amostrais** (**27,3%**). Em análise de sensibilidade do **mesmo modelo**, os limiares 0,45 e 0,55 sinalizaram 1.856 (46,4%) e 583 (14,575%), respectivamente. Essa variação **não representa comparação entre modelos treinados independentemente**.

## 4. Controles específicos aprovados

1. 224 recortes e **224 linhas CSV**, com equivalência quantitativa integral CSV/JSON para os campos principais.
2. Tamanho amostral e denominador `POP_EVALUATOR` iguais aos do IND-028 em todos os recortes; médias de `abs_delta_C1` a `abs_delta_C5` coincidem com o IND-028.
3. Todas as quantidades de sinalizados variam entre zero e o tamanho da amostra, com percentuais reconstituídos corretamente.
4. As cinco faixas por quintil recompõem a amostra; os quantis são ordenados e os limiares de sensibilidade produzem contagens monotônicas.
5. Brasil = soma das UFs e consolidado histórico = soma anual **somente para os denominadores populacionais**. O número de sinalizados não deve ser somado dessa maneira porque cada recorte foi modelado isoladamente.

## 5. Limitações e publicação

**Parecer: APROVADO na consistência computacional dos agregados; NÃO liberado automaticamente para publicação.** A classificação de anomalia é descritiva e depende do limiar, da amostra e do ajuste. **Não indica fraude, erro do avaliador, má-fé, nem frequência populacional de incorreção.** Não foi possível reexecutar o Isolation Forest com os registros originais; as comparações de médias entre IND-028/029 **não provam a identidade linha a linha da amostra**. Recomenda-se testar estabilidade com novas sementes, sensibilidade de hiperparâmetros e revisar privacidade antes da divulgação.
