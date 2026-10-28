# Relatório de validação técnica — IND-002

**Projeto:** Projeto Integrador IV — UNIVESP
**Indicador:** IND-002 — Nota média da redação
**Período:** ENEM 2019–2025
**Estado:** Validado tecnicamente sobre os arquivos agregados; **aguarda aprovação acadêmica** para publicação.

## Escopo dos arquivos conferidos

- `IND_002_nota_media.csv` (224 linhas: sete anos e um consolidado, com Brasil e 27 UFs por período).
- `IND_002_nota_media.json` (médias, somas e contagens nacionais e estaduais para sete anos).
- `dashboard_enem_2024.json` (integração dos indicadores 001 e 002).
- Referências de comparação fornecidas anteriormente: `IND_001_redacoes_validas.csv` e `IND_001_redacoes_validas.json`.
- Contrato testado: `04_resultados_analises.schema.json`, versão 1.0.0 (aplicado ao **dashboard de 2024**, único dashboard do IND-002 anexado nesta etapa).

## Procedimentos e achados

**942 verificações automáticas aprovadas, nenhuma divergência encontrada.** Os testes incluem:

1. Conferência de 224 combinações únicas período × UF no CSV, incluindo Brasil (BR) e as 27 UFs.
2. Igualdade da contagem de redações válidas entre IND-002 e IND-001, nacional e estadualmente.
3. Soma dos quantitativos estaduais igual à contagem brasileira, em cada ano.
4. Soma das notas estaduais igual à soma das notas nacional em cada ano (tolerância para ponto flutuante).
5. Recalculo das médias como `soma_notas/n_validas`, confrontadas com quatro casas decimais informadas.
6. Média nacional histórica reconstruída pela ponderação de cada edição pela quantidade de redações válidas (não média simples das sete médias).
7. Histórico das UFs reconstruído a partir dos sete anos e reconciliado com o JSON consolidado e CSV.
8. Correspondência do dashboard de 2024 com os resultados do indicador, inclusive 27 UFs, notas e população.
9. Validação do `dashboard_enem_2024.json` pelo JSON Schema v1.0.0 e conferência de ausência de identificadores individuais no payload.

## Totais conferidos

| Ano | Redações válidas | Média nacional (0–1000) |
|---|---:|---:|
| 2019 | 3.779.356 | 592,9016 |
| 2020 | 2.674.914 | 590,3961 |
| 2021 | 2.293.797 | 636,1228 |
| 2022 | 2.363.615 | 652,4511 |
| 2023 | 2.704.814 | 644,7115 |
| 2024 | 3.002.710 | 658,9658 |
| 2025 | 3.245.696 | 618,7151 |
| **2019–2025** | **20.064.902** | **625,5697** |

A média histórica utiliza a soma de **12.551.994.140 pontos** dividida pelas **20.064.902 redações válidas**. A série descreve participações por edição, não pessoas únicas ao longo do período.

## Fontes e definições

- 2019–2023: `MICRODADOS_ENEM_AAAA.csv`.
- 2024–2025: `RESULTADOS_AAAA.csv`.
- População: `TP_STATUS_REDACAO == 1` com `NU_NOTA_REDACAO` preenchida, numérica e no intervalo de 0 a 1000.
- Unidade geográfica: `SG_UF_PROVA` — **UF de aplicação da prova**, não necessariamente UF de residência.
- A estatística histórica pondera os resultados pela quantidade de redações válidas de cada ano, sem interpretação causal de variações entre edições.

## Pendências para encerramento formal

- Revisão acadêmica final dos critérios e resultados; manter `data_status = draft` até a aprovação.
- O processamento não foi reexecutado sobre os CSVs brutos nesta conferência; as validações utilizaram resultados exportados do script no computador do pesquisador.
- Foi disponibilizado para teste **somente o dashboard de 2024**: validar os JSONs progressivos de outros seis anos quando disponíveis, sem inferir a partir do teste atual.
- O JSON Schema v1.0.0 verifica a estrutura declarada; regras estatísticas de negócio exigem testes independentes, como os realizados neste relatório.

## Orientação de integração

Para o frontend, os caminhos de 2024 estão em `pages.overview.kpis.mean_score` (média Brasil), `pages.overview.ind002.by_uf` (média por UF) e `pages.temporal.ind002` (histórico do indicador). Preservar os arquivos do IND-001 como resultados de referência. Os dashboards progressivos combinados ainda estão sujeitos a aprovação de publicação.
