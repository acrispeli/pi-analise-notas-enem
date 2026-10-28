# Validação técnica — IND-021: Diferença por competência entre AV1 e AV2

**Projeto Integrador IV — UNIVESP**
**Abrangência:** ENEM 2019–2025, Brasil, 27 UFs e histórico 2019–2025
**Status:** **APROVADO TECNICAMENTE NOS AGREGADOS**, com ressalvas metodológicas e de divulgação
**Base da conferência:** arquivos processados fornecidos pelo projeto, não uma nova execução sobre os microdados individuais

## 1. Objetivo e definição do indicador

Para cada redação elegível da `POP_EVALUATOR` com dez notas de competências presentes e válidas, define-se, separadamente para cada competência `Ci`:

`d_i = |NU_NOTA_COMPi_AV1 − NU_NOTA_COMPi_AV2|` (i = 1, 2, 3, 4, 5).

A mesma subpopulação de pares completos é empregada para as cinco competências em cada recorte. A coluna `SG_UF_PROVA` representa **UF de aplicação da prova**, não residência. O histórico soma **participações**, sem pretensão de contar pessoas únicas entre anos.

O indicador apresenta média, mediana, percentis 25/75/90, desvio-padrão populacional (`ddof=0`), mínimo, máximo e dados resumidos para boxplots com regra de Tukey (1,5 × IQR). Diferenças não equivalem a erros confirmados de correção.

## 2. Arquivos conferidos

1. `IND_021_diferenca_por_competencia.csv` — **1.120 linhas** = 7 anos + histórico (8 períodos) × 28 recortes (BR + 27 UFs) × 5 competências.
2. `IND_021_diferenca_por_competencia.json` — **224 recortes**, cada qual contendo C1 a C5, metadados e verificações de fonte.
3. `dashboard_enem_2024.json` — integração do IND-021 em `pages.evaluators.by_competency`, `pages.temporal.ind021`, `pages.methodology.ind021` e `quality.ind021_validation`.
4. `IND_020_diferenca_total_av1_av2.json` — utilizado como referência anterior para a população `POP_EVALUATOR` e para uma desigualdade matemática entre diferenças totais e por competência.
5. `IND_022_discrepancia_oficial.json` — utilizado como referência posterior das populações pareadas e da quantidade de avaliações com cinco pares completos.

**Observação de versionamento:** o JSON modular do IND-021 foi produzido na versão `2.20.0`, enquanto o dashboard disponibilizado já contém IND-022 (`2.21.0`). A diferença é esperada nesta sequência de geração; os dados do IND-021 inseridos no dashboard correspondem ao módulo fornecido.

## 3. Balanço da auditoria independente

| Bloco de verificação | Quantidade | Resultado |
|---|---:|---|
| Contrato de estrutura, campos e ordenação | 4.304 | Aprovado |
| Integridade de registros agregados e pendências de privacidade | 1.347 | Aprovado |
| Valores, contagens, cobertura e ordenações | 12.768 | Aprovado |
| Coerência de quantis, dispersão, limites e boxplots | 12.320 | Aprovado |
| Médias e variâncias combinadas, Brasil/UF/anos | 612 | Aprovado |
| Correspondência de todas as linhas CSV com JSON | 24.641 | Aprovado |
| Diagnósticos de qualidade e fontes de dados | 69 | Aprovado |
| Referências cruzadas com IND-020 e IND-022 | 898 | Aprovado |
| Integração do dashboard de 2024 | 30 | Aprovado |
| **Total** | **56.989** | **0 divergências** |

O script independente `auditoria_IND021.py`, anexado ao relatório, implementa os testes e publica o resultado estruturado em `auditoria_IND021_resultados.json`.

### 3.1. Testes aritméticos efetivamente independentes

- As 27 UFs somam exatamente o Brasil, em todos os períodos.
- As sete participações anuais somam exatamente o histórico em cada UF e no Brasil.
- As **médias ponderadas** por número de pares foram recompostas independentemente a partir das UFs e dos anos, confrontadas com as médias nacionais e históricas.
- Os **desvios-padrão populacionais agregados** foram recompostos pelos momentos de segunda ordem:

  `E[d²] = Σ n_g (DP_g² + média_g²) / Σ n_g`, e `DP = √(E[d²] − E[d]²)`.

  Foram usadas tolerâncias pequenas de arredondamento para os seis decimais publicados, sem mascarar divergências relevantes.
- Os indicadores de mínimo, máximo, média, variância, quartis, P90 e boxplots foram submetidos a limites estatísticos e relações de ordem; quartis foram confrontados com as posições dos boxplots e IQR.
- A compatibilidade com IND-020 foi checada pela desigualdade triangular: `média(|diferença total|) ≤ Σ_i média(|diferença na competência i|)`, válida aqui porque a cobertura das cinco competências é completa em todos os recortes.
- A população pareada de IND-021 foi reconciliada com IND-020 e a população de cinco pares completos com IND-022, para todos os 224 recortes.

**Não se afirma reprodução exata independente de mediana, P25, P75, P90 ou dos bigodes observados.** Esses resultados foram confrontados entre arquivos e avaliados quanto à coerência, mas para reproduzi-los matematicamente seriam necessárias as frequências originais por nota ou as observações individuais.

## 4. População e cobertura

| Ano | Avaliações com pares completos (Brasil) |
|---|---:|
| 2019 | 3.779.355 |
| 2020 | 2.674.914 |
| 2021 | 2.378.379 |
| 2022 | 2.493.442 |
| 2023 | 2.822.643 |
| 2024 | 3.167.955 |
| 2025 | 3.457.555 |
| **2019–2025** | **20.774.243** |

As cinco competências apresentam **cobertura informada de 100%** da `POP_EVALUATOR` em todos os 224 recortes. Não foram reportados casos elegíveis sem associação geográfica, competências preenchidas inválidas ou registros pareados incompletos. A menor população dentre os recortes analisados foi de **5.265 avaliações**, superior ao limiar de 30 do projeto. A ausência de células pequenas dentro do IND-021 **não equivale** a uma aprovação global de privacidade do conjunto de dashboards.

## 5. Resultados nacionais

### 5.1. Consolidado histórico

| Competência | Diferença absoluta média (pontos) | Mediana | P90 |
|---|---:|---:|---:|
| C1 | 19,21 | 0 | 40 |
| C2 | 20,85 | 0 | 80 |
| C3 | 23,09 | 0 | 40 |
| C4 | 21,60 | 0 | 40 |
| **C5** | **25,77** | **0** | **80** |

No histórico nacional, a ordenação decrescente da média é **C5 > C3 > C4 > C2 > C1**. C5 é a competência com a maior diferença média no Brasil em todos os sete anos e no histórico. Entre os 224 recortes, C5 lidera em **222**; **C3** lidera em **Amazonas/2019** e **Roraima/2019**.

### 5.2. Brasil em 2024

| Competência | Diferença absoluta média (pontos) | Mediana | P90 |
|---|---:|---:|---:|
| C1 | 19,48 | 0 | 40 |
| C2 | 23,86 | 0 | 80 |
| C3 | 23,66 | 0 | 40 |
| C4 | 23,21 | 0 | 40 |
| **C5** | **25,62** | **0** | **80** |

Em 2024, C5 apresentou a maior diferença média, seguida de C2 e C3. **Mediana zero** em todas as competências significa que a distribuição de diferenças se concentra fortemente em concordâncias exatas de nota, sem impedir a existência de diferenças expressivas em outros casos. Percentis 90 de 80 para C2 e C5 descrevem dispersões na cauda da distribuição, não taxas oficiais de discrepância.

### 5.3. Médias nacionais anuais

| Ano | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| 2019 | 18,04 | 19,44 | 23,84 | 20,86 | 25,61 |
| 2020 | 19,58 | 22,44 | 25,25 | 20,89 | 28,81 |
| 2021 | 17,88 | 14,79 | 20,26 | 18,18 | 23,30 |
| 2022 | 18,17 | 17,98 | 20,06 | 18,73 | 22,37 |
| 2023 | 20,30 | 24,62 | 25,75 | 23,76 | 27,70 |
| 2024 | 19,48 | 23,86 | 23,66 | 23,21 | 25,62 |
| 2025 | 20,71 | 21,54 | 22,04 | 24,15 | 26,32 |

As séries anuais devem ser lidas como **descrições das populações de cada edição**, não como mudanças causais na qualidade dos corretores.

## 6. Ressalvas e encaminhamento

1. **Sem nova leitura de microdados:** os testes validam a consistência do processamento entregue, mas não certificam o cálculo de cada nota individual nem a associação `NU_INSCRICAO + NU_ANO` diretamente nos CSV originais.
2. **Sem recálculo exato de percentis:** mediana, percentis e bigodes dos boxplots foram conferidos por consistência estatística e replicação fiel entre arquivos.
3. **Outros dashboards anuais:** apenas o `dashboard_enem_2024.json` encaminhado foi inspecionado; a declaração de sete dashboards no módulo não equivale à validação dos outros seis arquivos.
4. **Populações distintas:** `POP_EVALUATOR` e `POP_VALID` não devem ser equiparadas. As notas comparadas são dos primeiros dois avaliadores, não necessariamente as notas finais consolidadas após eventuais correções adicionais.
5. **Privacidade e publicação:** os arquivos inspecionados são agregados, mas continuam com `data_status="draft"`; a revisão acadêmica e a revisão de riscos de divulgação do sistema inteiro permanecem pendentes.
6. **Visualizador Streamlit:** o projeto havia definido mostrar apenas IND-001 a IND-019; a aprovação computacional do IND-021 não altera automaticamente essa decisão de interface.

## 7. Conclusão

**O IND-021 foi validado tecnicamente quanto à integridade dos agregados recebidos, suas composições estatísticas verificáveis, a relação entre os arquivos e a integração ao dashboard de 2024: 56.989 verificações, nenhuma divergência.**

Este parecer autoriza registrar o indicador como **validado computacionalmente**, mantendo a distinção entre auditoria de agregados e recálculo a partir dos microdados originais. Não constitui autorização automática de divulgação externa.
