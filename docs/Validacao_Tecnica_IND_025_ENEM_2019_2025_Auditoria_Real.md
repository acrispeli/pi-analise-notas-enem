# Validação técnica — IND-025 | Frequência de banca avaliadora (AV4) | ENEM 2019–2025

**Projeto:** Projeto Integrador IV — UNIVESP
**Data desta auditoria:** 22/10/2026
**Fontes examinadas:** CSV e JSON gerados pelo processamento local; saídas de referência de indicadores anteriores; código e testes sintéticos da implementação.
**Status:** **Aprovado na auditoria computacional dos resultados agregados**, com **3.537 verificações aprovadas e 0 falhas**. Permanece `draft`; divulgação pública não aprovada.
**Escopo:** sete edições (2019–2025), Brasil e 27 UFs por edição, mais consolidado histórico; 224 linhas do CSV.

## 1. Objetivo e definição metodológica

O indicador estima a frequência observável de participação do **banca de três avaliadores** no processo de correção, a partir da presença de pelo menos um dos campos `NU_NOTA_AV4` ou `TP_STATUS_REDACAO_AV4`. Trata-se de **proxy de convocação**, não de conferência de atos administrativos do Inep. No caso de AV4, a designação corresponde à **banca de três avaliadores**, e não a um quarto avaliador individual.

**População/denominador:** `POP_ALL`, isto é, todos os registros da edição/UF. **Numerador:** união (OU inclusivo) entre nota e status preenchidos, sem contar o mesmo registro duas vezes; nota `0` é preenchimento válido. O percentual é:

`100 × n_com_av4 / n_pop_all`.

Para o período de 2019–2024, a fonte complementar de correção é ligada à UF da prova usando `NU_INSCRICAO` + `NU_ANO`; em 2025, a UF consta em `RESULTADOS_2025.csv`. O histórico soma participações nas sete edições, sem deduplicar pessoas entre anos. Não confundir `POP_ALL` com `POP_EVALUATOR` dos indicadores de divergência.

## 2. Resultados nacionais observados

| Ano/período | POP_ALL | Com AV4 | Sem AV4 | Taxa AV4 (%) |
|---|---:|---:|---:|---:|
| 2019 | 5.095.171 | 138.338 | 4.956.833 | 2,7151 |
| 2020 | 5.783.109 | 113.882 | 5.669.227 | 1,9692 |
| 2021 | 3.389.832 | 55.938 | 3.333.894 | 1,6502 |
| 2022 | 3.476.105 | 64.676 | 3.411.429 | 1,8606 |
| 2023 | 3.933.955 | 185.447 | 3.748.508 | 4,7140 |
| 2024 | 4.332.944 | 171.463 | 4.161.481 | 3,9572 |
| 2025 | 4.810.772 | 185.926 | 4.624.846 | 3,8648 |
| 2019–2025 | 30.821.888 | 915.670 | 29.906.218 | 2,9708 |

A taxa histórica é **ponderada pelo total de registros** das edições, e não uma média aritmética das sete taxas anuais. As diferenças temporais são descritivas e não demonstram, isoladamente, alteração de regra ou de qualidade da correção.

## 3. Procedimentos e resultados da auditoria

A validação reprocessou aritmeticamente as informações **agregadas** fornecidas: conferência de `CSV × JSON`, chaves únicas, sete anos + histórico, 27 UFs, limites do numerador, decomposição `com + sem = POP_ALL`, recomputação de todos os percentuais com tolerância máxima de `0,00000051` ponto percentual para seis casas decimais, soma das UFs contra Brasil, soma anual contra o histórico, metadados e controle de grupos pequenos. Também houve comparação, **para cada um dos 224 recortes**, do denominador `POP_ALL` com o `total_registros` do **IND-007**.

| Verificação | Resultado |
|---|---|
| Linhas CSV / recortes esperados | 224 / 224 |
| População conferida com IND-007 | 224 de 224 |
| Soma `com + sem = total` | 224 de 224 |
| Percentuais recalculados dentro da tolerância | 224 de 224 |
| Brasil = soma das 27 UFs | 8 períodos completos |
| Histórico = soma dos anos por UF | 28 recortes territoriais |
| Numerador e complemento em 0 ou pelo menos 30 | Nenhuma violação detectada |
| CSV e JSON correspondentes | Sem divergências |
| Verificações automáticas deste indicador | **3.537** |
| Falhas automáticas | **0** |

Os arquivos também apresentam `n_candidatos_sem_juncao = 0` e `n_candidatos_sem_uf = 0` na telemetria de origem para todas as sete edições. Esses dados são **declarações da execução local**, corroboradas pela reconciliação dos totais, mas a junção registro a registro não foi refeita nesta auditoria.

## 4. Verificação cruzada com o indicador complementar

Os **224 denominadores** coincidem exatamente entre IND-024 e IND-025. Em todos os 224 recortes, a contagem observada de registros com AV4 não excede a de AV3. Foram aprovadas **448 verificações cruzadas** (denominador e ordenação das contagens). Essa desigualdade é uma verificação de plausibilidade dos agregados, **não** uma prova de inclusão registro a registro ou de relação causal entre etapas.

**Atenção:** AV4 não é um quarto corretor individual; o preenchimento dos campos identifica a evidência de banca. Não é possível concluir, só com esses totais, quais registros com banca também tiveram AV3.

## 5. Testes do programa e proteção de dados

Foi executada novamente a suíte sintética do indicador nesta sessão, com **resultado aprovado**. Ela cobre nota zero como valor presente, presença isolada de nota/status, união sem dupla contagem, validação de entradas, somas, histórico, bloqueio de sobrescrita sem autorização, integração simulada com sete dashboards e interrupção em caso de células positivas de 1 a 29. A auditoria real examinou numeradores e complementos publicados e não encontrou células positivas inferiores a 30.

Não foram exportados números de inscrição nem registros individuais nos CSV/JSON fornecidos. O limiar de 30 é uma salvaguarda inicial, **não substitui a avaliação de supressão complementar e do risco de cruzamentos entre indicadores**.

## 6. Limitações e pendências para divulgação

1. A auditoria recebeu **saídas agregadas** (CSV/JSON), referências agregadas anteriores e scripts/testes. **Os microdados individuais originais de 2019–2025 não foram reprocessados de forma independente nesta sessão.** A checagem do comportamento dos algoritmos foi feita em dados sintéticos.
2. **Os sete dashboards atualizados após IND-026 não foram fornecidos para a auditoria atual.** A presença do nome de cada dashboard na lista `dashboard_files` **não comprova** a integração final nem a preservação dos indicadores anteriores em arquivos reais. Os testes de integração foram sintéticos.
3. Os resultados permanecem `draft`, sujeitos a revisão metodológica/estatística, acadêmica, comparabilidade interanual e avaliação de privacidade complementar antes de publicação.
4. Para aprovação empírica integral, executar um recálculo independente, ao menos amostral e preferencialmente completo, diretamente dos microdados e conferir os sete dashboards finais.

## 7. Rastreabilidade dos arquivos auditados

| Arquivo | SHA-256 |
|---|---|
| `IND_025_banca.csv` | `cea4506a00ea156bebaeffaa9c3ed1f3c136f511776d9a354f4be28846a01885` |
| `IND_025_banca.json` | `71eb6fa9915044a3bef7c9d2a710980cfbd5eef4f0b81afd94a56a65b362ae3c` |
| `IND_007_situacao_redacao.json` (referência) | `e6060bdf06962ac911632f3d5c0398c47dd7c84a39d38ef70e4e315545b00207` |

**Arquivos de auditoria reproduzível:** `auditar_ind024_025_026.py` e `auditoria_IND024_025_026_resultados.json` (separados deste relatório). Os contadores representam asserções automatizadas, podendo haver várias asserções sobre o mesmo recorte; não correspondem a registros individuais distintos.

## 8. Parecer técnico

**IND-025: APROVADO COMPUTACIONALMENTE PARA USO INTERNO E DISCUSSÃO ACADÊMICA**, nos limites dos CSV/JSON agregados recebidos e dos testes executados (**3.537 verificações sem falhas**). **NÃO APROVADO AINDA PARA PUBLICAÇÃO IRRESTRITA**; dependem de revisão acadêmica, verificação independente dos microdados e auditoria dos dashboards finais.
