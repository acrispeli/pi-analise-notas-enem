# Validação técnica — IND-022: Discrepância oficial (critério ENEM 2024)

**Projeto Integrador IV — UNIVESP | ENEM 2019–2025**

## Parecer

**APROVADO NA AUDITORIA DE AGREGADOS, COM RESSALVAS DE PUBLICAÇÃO E REPRODUTIBILIDADE.**

- **17.260 verificações aprovadas; zero divergências** nos três arquivos recebidos e no módulo IND-020 previamente disponível.
- A conferência recobre **224 recortes** (2019–2025 e histórico; Brasil + 27 UFs), CSV, JSON, percentuais, partições, motivos sobrepostos, histórico e dashboard de 2024.
- **Conferência independente adicional:** as 224 contagens do motivo `|AV1 − AV2| > 100` foram reconstruídas exatamente dos histogramas de IND-020, incluindo cortes das faixas.
- Todos os 224 recortes conferidos apresentam 3 categorias exaustivas: discrepância confirmada, não confirmada e indeterminada. Nos dados recebidos, os indeterminados são zero.
- Não foi constatada contagem positiva 1–29 nos campos liberados do IND-022 nem na interseção tripla inferível dos motivos, nos recortes auditados. Isso **não equivale** a auditoria completa de reidentificação/supressão complementar.

## Resultados — Brasil

| Ano | Avaliações pareadas (POP_EVALUATOR) | Discrepâncias confirmadas | Taxa |
|---|---:|---:|---:|
| 2019 | 3.779.355 | 1.140.875 | 30,19% |
| 2020 | 2.674.914 | 868.161 | 32,46% |
| 2021 | 2.378.379 | 540.029 | 22,71% |
| 2022 | 2.493.442 | 589.942 | 23,66% |
| 2023 | 2.822.643 | 988.100 | 35,01% |
| 2024 | 3.167.955 | 1.039.556 | 32,81% |
| 2025 | 3.457.555 | 1.144.795 | 33,11% |
| **Histórico 2019–2025** | **20.774.243** | **6.311.458** | **30,38%** |

O histórico soma **participações em redações**, não pessoas únicas. A taxa histórica é a razão entre totais históricos, não a média simples de taxas anuais.

### Motivos de discrepância — Brasil 2024

| Medida | Quantidade |
|---|---:|
| POP_EVALUATOR | 3.167.955 |
| Pelo menos um motivo de discrepância | 1.039.556 |
| Diferença total > 100 | 1.019.191 |
| Alguma competência com diferença > 80 | 152.972 |
| Situação da redação divergente | 49.778 |
| Dois ou três motivos simultâneos | 147.146 |
| Casos indeterminados | 0 |

**Observação:** os motivos não são mutuamente exclusivos. Sua soma excede o total de discrepâncias confirmadas sem representar erro.

## Critério e escopo normativo

O **item 14.5.3 do Edital ENEM 2024** foi conferido no arquivo do projeto: considera discrepância entre dois corretores quando as notas totais diferirem **mais de 100 pontos**, quando ao menos uma competência diferir **mais de 80 pontos**, ou quando houver **divergência de situação**.

Os limites são **estritos**: valores exatamente 100 ou exatamente 80, isoladamente, não acionam a regra. O cálculo aplica **a norma de 2024 como critério padronizado** aos anos 2019–2025; não comprova igualdade dos editais das demais edições. O resultado não é um indicador oficial publicado pelo INEP.

O denominador é `POP_EVALUATOR`, definido pelo IND-020: redações com os dois totais AV1/AV2 válidos. Esta população **não é equivalente à POP_VALID**, usada para as notas finais em indicadores anteriores.

## Escopo da auditoria executada

1. **Estrutura e cardinalidade:** 7 anos e 1 consolidado, Brasil + 27 UFs; 224 recortes e 224 linhas CSV.
2. **Aritmética da partição:** discrepância confirmada + não confirmada + indeterminada = população em todos os recortes.
3. **Motivos não exclusivos:** o total de discrepâncias fica entre o maior motivo isolado e a soma dos motivos; reconciliação de contagens de múltiplos critérios, inclusive limite da interseção tripla inferível.
4. **Porcentagens e limites:** recálculo de taxas com arredondamento de seis decimais, incluindo os limites inferior e superior e os casos classificáveis.
5. **Regional e temporal:** soma das 27 UFs reconstrói Brasil; soma dos 7 anos reconstrói o consolidado histórico para todas as 12 contagens inteiras.
6. **CSV × JSON:** correspondência de todas as linhas e campos quantitativos/qualitativos; ausência de inscrições pessoais no cabeçalho CSV.
7. **IND-020:** população pareada confere nos 224 recortes com módulo IND-020, e critério de nota total **>100** confere exatamente com a soma dos histogramas do IND-020 nos 224 recortes.
8. **IND-021:** população e cobertura das cinco competências conferidas com as projeções anuais nacionais, históricas por UF e de 2024 do dashboard; **o módulo IND-021 completo não foi recebido nesta rodada**.
9. **Dashboard 2024:** `pages.evaluators.official_discrepancy`, `pages.temporal.ind022`, `pages.methodology.ind022`, metadados, projeção por UF e campos de qualidade foram conciliados.
10. **Qualidade da fonte (declarações do gerador):** nenhuma junção de redação elegível sem correspondência, nenhuma UF elegível ausente e nenhuma nota de competência/status preenchida inválida foi indicada; **sem verificação independente nos microdados**.

## Ressalvas e recomendações

- **Sem recomputação em microdados:** conferimos resultados divulgados e regras aritméticas, não as 20.774.243 avaliações individualmente. O resultado de discrepância por competência e status depende de confiar na computação original, embora tenha passado nas relações lógicas entre os agregados.
- **Dependência do IND-021:** antes de contabilizar a validação sequencial completa, auditar separadamente o CSV e JSON do IND-021. O dashboard oferece apenas as projeções pertinentes.
- **Editais históricos:** conferir documentação normativa das edições 2019–2023 e 2025 antes de denominar a série como “taxa oficial de discrepância”. Nome mais rigoroso em gráficos: **“Discrepâncias pelo critério ENEM 2024 (aplicado à série histórica)”**.
- **Privacidade:** dados somente agregados; não detectamos contagens positivas pequenas nos campos observados ou em interseções triplas inferíveis, mas revisão de publicação e riscos por combinação permanecem pendentes.
- **Streamlit:** os IND-020, IND-021 e IND-022 ainda não foram adicionados à interface, conforme o escopo anterior IND-001–019. O dashboard JSON contém os dados para inclusão futura.
- **Versionamento:** os três arquivos estão marcados `draft`; preservar o status até aprovação acadêmica.

## Arquivos e reprodutibilidade

- `IND_022_discrepancia_oficial.csv` — 224 linhas agregadas.
- `IND_022_discrepancia_oficial.json` — anos, histórico, metadados e QA.
- `dashboard_enem_2024.json` — integração com 2024 e projeções temporais.
- `IND_020_diferenca_total_av1_av2.json` — referência anterior usada na reconciliação.
- `auditoria_IND022.py` — verificação aritmética e entre módulos reproduzível.
- `auditoria_IND022_resultados.json` — resumo detalhado com evidências e limitações.

**Resultado da auditoria: 17.260 verificações; 0 divergências.**
