# Validação técnica IND-030 — Distribuição de alto desempenho (faixas 900–1000)

**Projeto:** Projeto Integrador IV — UNIVESP
**Período analisado:** ENEM 2019 a 2025 e histórico 2019–2025
**Data da auditoria:** 22 de outubro de 2026
**Estado da análise:** `draft`; resultados reais agregados, com revisão acadêmica e de privacidade ainda pendentes.

## 1. Objetivo e arquivos examinados

A auditoria conferiu `IND_030_*.csv`, `IND_030_*.json` e o bloco correspondente no arquivo `dashboard_enem_2024.json` enviado. Foram examinados **1.077 registros de CSV**, distribuídos por **224 recortes** (2019–2025 e histórico × Brasil e 27 UFs). O dashboard de 2024 passou no contrato `04_resultados_analises.schema.json` disponível no projeto.

## 2. Parecer computacional

- **16.727 verificações programáticas executadas**, com **0 falhas** nas condições efetivamente testadas.
- Os testes incluíram consistência de campos entre CSV e JSON, somatórios, percentuais, abrangência territorial e histórica, e equivalência integral dos blocos de Brasil e UFs com o dashboard enviado para 2024.
- Este parecer **não é um recálculo independente a partir dos microdados**. Os microdados originais não foram disponibilizados nesta auditoria. Verificações sobre a mesma agregação detectam inconsistências internas, mas não comprovam, por si, a validade do cálculo original.

## 3. Método e resultados

População `POP_HIGH`: redações válidas (`POP_VALID`) com pontuação total de **900 a 1000**, inclusive. Os percentuais por faixa têm como denominador o **número de redações em `POP_HIGH`**, não o total de participantes. Faixas base de 20 pontos; os casos com notas 1000 estão agrupados na última faixa. Se uma faixa tiver contagens positivas inferiores a 30, ela pode ser mesclada com a faixa adjacente.

| Ano | Redações POP_HIGH (BR) | % das redações válidas |
|---|---:|---:|
| 2019 | 172.601 | 4,5669% |
| 2020 | 183.371 | 6,8552% |
| 2021 | 163.769 | 7,1396% |
| 2022 | 197.115 | 8,3396% |
| 2023 | 288.662 | 10,6722% |
| 2024 | 291.123 | 9,6953% |
| 2025 | 173.543 | 5,3469% |
| 2019–2025 | 1.470.184 | 7,3271% |

Em **2024, Brasil**, há **291.123 redações `POP_HIGH`** entre **3.002.710 redações válidas** (**9,6953%**). A distribuição por faixa é: 900–<920 (**91.087**), 920–<940 (**96.625**), 940–<960 (**69.184**), 960–<980 (**31.907**) e 980–1000 (**2.320**). As contagens fecham em 291.123.

## 4. Controles específicos aprovados

1. **1.077 linhas CSV** referenciam os 224 recortes; a quantidade de linhas varia devido à junção de faixas.
2. Os limites das faixas são contíguos e cobrem 900–1000 sem sobreposição; a última faixa inclui 1000.
3. Quantidades por faixa fecham `n_high` e os percentuais são recalculados com `n_high`; não há faixa divulgada com 1–29 redações.
4. Para cada ano, Brasil = soma das 27 UFs; histórico = soma dos totais anuais e das respectivas UFs.
5. Em 2024, `n_validas=3.002.710` confere com IND-001, e `n_high=291.123` confere com a faixa 900–1000 do IND-006 no dashboard enviado.

## 5. Risco de divulgação cruzada e parecer

**Achado relevante:** a diferença `IND-030.n_high − IND-031.n_near` representa o total de redações com nota 1000. Em **112 recortes** (entre Brasil, UFs, anos e histórico), o resultado é positivo e menor que 30. Em 2024, AL: `5.644 − 5.643 = 1`. Assim, a mera mesclagem de faixas em cada indicador separadamente **não garante supressão complementar** quando ambos são publicados. O IND-008 já apresenta contagens pequenas de notas 1000 em alguns recortes; isso reforça a necessidade de revisão coordenada.

**Parecer: APROVADO na aritmética; PUBLICAÇÃO PÚBLICA BLOQUEADA por revisão de privacidade cruzada pendente.** Rever conjuntamente IND-008, IND-030, IND-031 e todas as saídas expostas (CSV, JSON, app, GitHub). A disponibilização do arquivo bruto no repositório público torna irrelevante ocultar apenas os campos no Streamlit.
