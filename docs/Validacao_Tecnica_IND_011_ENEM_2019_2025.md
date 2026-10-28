# Relatório de Validação Técnica — IND-011

**Projeto Integrador IV — UNIVESP**
**Indicador:** IND-011 — Dispersão C1–C5
**Período:** ENEM 2019–2025
**Data de auditoria:** 18/10/2026
**Resultado:** **APROVADO TECNICAMENTE PARA ANÁLISE INTERNA**, com ressalvas documentadas
**Situação de publicação:** `draft` — pendente de aprovação acadêmica e revisão geral de privacidade.

## 1. Artefatos auditados

- `IND_011_dispersao_competencias.csv` — 1.120 linhas, separador `;`.
- `IND_011_dispersao_competencias.json` — sete edições, consolidado histórico, Brasil e 27 UFs.
- `dashboard_enem_2024.json` — saída cumulativa 2024, versão `2.10.0-ind001-ind002-ind003-ind004-ind005-ind006-ind007-ind008-ind009-ind010-ind011`.
- Referências previamente entregues: resultados modulares IND-001, IND-002, IND-009 e IND-010, utilizados para reconciliação de denominadores, médias, medianas, totais e ocorrência SC/2023.
- Contrato `04_resultados_analises.schema.json` e script `IND_011_dispersao_competencias.py`, utilizado para testes controlados independentes com NumPy.

**Importante:** os microdados brutos `MICRODADOS_ENEM_*.csv` e `RESULTADOS_*.csv` não foram disponibilizados nesta auditoria. Ela verifica, de maneira independente, a consistência entre saídas agregadas, identidades estatísticas e a implementação sobre dados sintéticos — não constitui reprocessamento independente da população original.

## 2. Escopo e método

O indicador calcula, para cada `NU_NOTA_COMP1` a `NU_NOTA_COMP5`, entre as redações `POP_VALID`, com escala 0–200:

- Desvio-padrão **populacional**, `ddof=0`, divisor **N**.
- Variância populacional, correspondente ao quadrado do desvio-padrão antes do arredondamento.
- Quartis **P25 e P75** pelo método empírico **Hyndman–Fan tipo 7**, interpolação linear.
- **IQR = P75 − P25**.
- Média e mediana como controles, confrontadas aos IND-009 e IND-010.

Os dados abrangem sete edições anuais e um histórico 2019–2025, em 28 geografias (Brasil e 27 UFs), totalizando **224 grupos e 1.120 registros por competência/grupo**. A variável estadual é `SG_UF_PROVA`, local de realização da prova, não necessariamente residência. O histórico soma participações, não participantes únicos.

## 3. Resultado quantitativo da auditoria

| Indicador de controle | Resultado |
|---|---:|
| Verificações automatizadas | **47.332** |
| Falhas nas verificações | **0** |
| Categorias de verificação | **122** |
| Linhas CSV conferidas | **1.120** |
| Grupos período/geografia | **224** |
| Casos sintéticos comparados ao NumPy | **180** |
| Valores comparados ao NumPy por caso | **7** |

As verificações abrangeram:

1. Cobertura exata de anos, UFs, competências e chaves, ausência de duplicidades e tipos/identificadores de saída.
2. Comparação campo a campo de CSV versus JSON modular para **médias de controle, medianas de controle, P25, P75, IQR, desvio-padrão, variância, N, método, fonte e indicadores de qualidade**.
3. Recalculo do IQR pela diferença P75−P25, consistência matemática entre desvio-padrão e variância com tolerância de arredondamento, ordem dos quartis e verificação da escala.
4. Reconciliação de POP_VALID e POP_ALL com IND-001 e IND-002, e de médias/medianas com IND-009 e IND-010; inclusive médias reconstruídas pelas **somas exatas** do IND-009.
5. Reconstituição da variância nacional em cada ano **por combinação ponderada das 27 variâncias estaduais e das diferenças entre suas médias**. Todas as competências e todos os períodos conferiram, tolerando apenas arredondamento de quatro casas decimais.
6. Reconstituição da variância do histórico **por combinação ponderada das variâncias e médias das sete edições anuais**, separadamente para Brasil, cada UF e cada competência. Todas as reconciliações fecharam.
7. Conferências nacionais = 27 UFs para contagens, população total, exceções e diferenças de pontos; histórico = soma dos sete anos para denominadores e exceções.
8. Validação do dashboard de 2024 contra JSON Schema **v1.0.0** e comparação de `pages.competencies.dispersion`, `pages.competencies.summary`, séries anuais, consolidados estaduais e campos de qualidade com o módulo IND-011. Campos preexistentes dos indicadores 001–010 permanecem presentes e as médias e medianas do resumo conferem com IND-009 e IND-010.
9. **180 testes sintéticos**, usando distribuições discretas variadas e comparando média, mediana, P25, P75, IQR, desvio-padrão e variância da função de cálculo do script contra o NumPy (1.260 comparações).

## 4. ENEM 2024 — Brasil

**População válida:** 3.002.710 redações.

| Competência | Desvio-padrão | Variância | P25 | P75 | IQR |
|---|---:|---:|---:|---:|---:|
| C1 | 25,6699 | 658,9459 | 120 | 140 | 20 |
| C2 | 34,8871 | 1.217,1115 | 120 | 180 | 60 |
| C3 | 33,0933 | 1.095,1649 | 100 | 140 | 40 |
| C4 | 35,5244 | 1.261,9805 | 120 | 160 | 40 |
| **C5** | **58,1138** | **3.377,2185** | **80** | **160** | **80** |

A C5 apresenta a maior dispersão em 2024, tanto pelo desvio-padrão como pelo IQR. Esse achado é **descritivo** e não explica causalmente por que os participantes obtiveram notas mais heterogêneas.

## 5. Histórico nacional 2019–2025

**População histórica:** 20.064.902 participações válidas.

| Competência | Desvio-padrão histórico | IQR histórico |
|---|---:|---:|
| C1 | 25,6186 | 20 |
| C2 | 40,2010 | 60 |
| C3 | 33,8734 | 40 |
| C4 | 33,2654 | 40 |
| **C5** | **58,5899** | **80** |

O desvio-padrão histórico **não** foi obtido pela média dos desvios-padrão anuais. A auditoria reconstruiu os momentos históricos com as fórmulas de combinação de populações, sendo coerente com o cálculo informado a partir das frequências completas das cinco competências.

## 6. Exceção da fonte em SC/2023

A única divergência conhecida está preservada no IND-011 e concorda com IND-009:

| Verificação | Resultado |
|---|---|
| Ano / UF | 2023 / SC |
| Ocorrências válidas com soma C1–C5 divergente | 1 |
| Nota de redação no registro diagnosticado anteriormente | 320 |
| Soma das competências | 290 |
| Diferença (soma − nota total) | **−30 pontos** |
| Registro incluído nos cálculos | **Sim** |
| Histórico 2019–2025 carrega a divergência | **Sim** |

A medição de dispersão usa os valores reais das competências da fonte, sem trocar, excluir ou imputar notas. As outras edições mostram zero divergências. Recomenda-se manter a exceção documentada na metodologia acadêmica e verificar sua origem junto à documentação dos microdados.

## 7. Observações estatísticas

Em algumas UFs/anos, uma competência apresenta **IQR igual a zero** e desvio-padrão positivo. Esse comportamento é matematicamente válido para distribuições discretas: os 50% centrais podem ter o mesmo valor enquanto notas mais extremas produzem variabilidade no conjunto. Foram observados 12 pares estaduais anuais com IQR zero, sem indicação de falha por esse motivo.

As diferenças entre desvio-padrão ao quadrado e variância publicada refletem o arredondamento independente de ambas as medidas a quatro casas decimais. A auditoria aplicou tolerâncias explícitas e efetuou também verificações pela identidade de combinação de variâncias.

## 8. Privacidade, publicação e limitações

O IND-011 apresenta medidas agregadas para Brasil e UFs com denominadores superiores a 30. Ainda assim, a autorização para exposição pública depende de revisão global, pois indicadores anteriores apresentam células pequenas, especialmente IND-006, IND-007 e IND-008. O campo geral `quality.suppression.suppressed_cells = 0`, herdado de indicadores anteriores, **não demonstra inexistência de riscos nos demais indicadores** e deve ter sua semântica revisada antes da divulgação, inclusive para supressão complementar.

Esta verificação não prova que cada nota original foi lida corretamente, pois não houve reprocessamento dos microdados. Também não foi possível certificar os dashboards cumulativos de 2019, 2020, 2021, 2022, 2023 e 2025: **somente o dashboard de 2024 foi enviado**. O cumprimento formal do catálogo e a publicação requerem aprovação acadêmica final.

## 9. Conclusão e próximos passos

**IND-011 APROVADO TECNICAMENTE para análise interna — 47.332 verificações, zero falhas.**

Permanecem:

- Validar com dados reais o **IND-012 — Distribuição dos níveis C1–C5**, quando seu processamento terminar.
- Realizar revisão acadêmica e de privacidade antes de abrir os arquivos para divulgação pública.
- Manter os valores de `data_status = "draft"` até a liberação do projeto.
- Não alterar o Streamlit sem aprovação específica.

**Progresso:** IND-001 a IND-011 validados tecnicamente (11 de 72). O IND-012 está implementado, aguardando execução/validação dos resultados reais.
