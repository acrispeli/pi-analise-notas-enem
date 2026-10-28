# Validação Técnica — IND-042: Renda familiar × competências C1–C5 da redação

**Projeto Integrador IV — UNIVESP**
**Período auditado:** ENEM 2019–2024 (2025 indisponível)
**Data da auditoria:** 23/10/2026
**Status:** **APROVAÇÃO COMPUTACIONAL PARCIAL, COM BLOQUEIO DE DIVULGAÇÃO DAS CÉLULAS PEQUENAS**
**Escopo da conclusão:** consistência dos produtos agregados; não corresponde à validação independente dos microdados.

## 1. Resumo executivo

A auditoria independente dos **arquivos de saída** do IND-042 executou **465,134 verificações**, obtendo **0 falhas de consistência**, sobre **14,430 linhas CSV** e **168 recortes anuais** (6 anos × Brasil + 27 UFs). Os dados de 2024 coincidem com o bloco `pages.socioeconomic.income_competencies` do dashboard enviado. As contagens por faixas de renda também foram confrontadas com o arquivo IND-041 presente no projeto.

**A divulgação pública integral não está aprovada.** Há **3 células publicadas com 1–29 redações**, incluindo duas representações da mesma observação única em 2021 (Brasil e São Paulo), que disponibilizam estatísticas por competência. A marcação `n_pequeno=true` não impede a divulgação nem elimina riscos de inferência a partir dos totais.

Há, ainda, **uma divergência nos microdados de 2023**, já registrada no dashboard/IND-009: uma redação de Santa Catarina apresenta a soma das cinco competências **30 pontos abaixo** da nota total. Trata-se de **uma ocorrência**, que aparece uma vez no recorte de SC e outra no agregado Brasil. Não constitui uma falha de reconciliação introduzida pelo IND-042; deve ser documentada como ressalva da fonte.

## 2. Arquivos analisados e rastreabilidade

| Arquivo | Papel na auditoria |
|---|---|
| `IND_042_renda_competencias.json` | Agregados anuais, recortes BR/UF, categorias e estatísticas C1–C5 |
| `IND_042_renda_competencias.csv` | Reconciliação campo a campo com o JSON |
| `dashboard_enem_2024.json` | Conferência do bloco IND-042 de 2024 e das médias do IND-009 |
| `IND_041_renda_nota_total.json` (arquivo disponível no projeto) | Confronto independente dos denominadores por ano, UF e renda |
| `dashboard_enem_2023.json` (arquivo disponível no projeto) | Conferência da anomalia de nota total × soma C1–C5 reportada pelo IND-009 |

**SHA-256 dos quatro arquivos principais:**

- `IND_042_renda_competencias.json`: `7a99e9990c3a0277983f747519455ba435c6760b314ea6ab78dcd522b6555431`
- `IND_042_renda_competencias.csv`: `012c47f26cba553d1b9c68723ce3ffef981449c50d5d32f5e2059a416aafe512`
- `dashboard_enem_2024.json`: `969532ead80de91605ff94e22977bb1b3abb59864ca15346417a2a755b076877`
- `IND_041_renda_nota_total.json`: `724611c391e6f9ecd6e1f2d27d9c00da90567b499810da079a05b5585186db59`

## 3. População, fontes e metodologia declarada

- **Indicador:** IND-042 — Renda familiar × competências da redação.
- **População:** `POP_SOCIO_VALID` = redações com `TP_STATUS_REDACAO=1`, nota total final dentro de `[0, 1000]` e C1–C5 válidas em `[0, 200]` conforme o método da rotina.
- **Dimensão geográfica:** `SG_UF_PROVA` (local de prova, não residência).
- **Renda:** `Q006` nos microdados 2019–2023; `Q007` em 2024.
- **Integração em 2024:** junção por `NU_INSCRICAO` de `PARTICIPANTES_2024` com `COMPETENCIAS_REDACAO_2024`, conforme metadados e código-fonte disponibilizado no projeto.
- **Estatísticas reportadas:** N, média, mediana, Q1, Q3, IQR e desvio-padrão populacional (`ddof=0`) de cada competência; mediana e quartis declarados pela regra Hyndman–Fan tipo 7.
- **2025:** indisponível por falta de chave pública comum para a vinculação individual entre renda e notas; não foi inferido ou estimado.
- **Interpretação:** estatística descritiva de renda autorreferida; não constitui inferência causal.

## 4. Abrangência da população por ano

| Ano | Redações em POP_SOCIO_VALID (Brasil) | Variável renda | Situação |
|---|---:|---|---|
| 2019 | 3,779,356 | Q006 | Disponível; BR + 27 UFs |
| 2020 | 2,674,914 | Q006 | Disponível; BR + 27 UFs |
| 2021 | 2,293,797 | Q006 | Disponível; BR + 27 UFs |
| 2022 | 2,363,615 | Q006 | Disponível; BR + 27 UFs |
| 2023 | 2,704,814 | Q006 | Disponível; BR + 27 UFs |
| 2024 | 3,002,710 | Q007 | Disponível; BR + 27 UFs |
| **Total 2019–2024** | **16,819,206** | — | Soma de participações, não pessoas únicas |
| 2025 | — | — | Indisponível (sem vínculo público entre as fontes) |

**Atenção:** os limites monetários de A–Q variam conforme o ano. As letras de categorias não autorizam a comparação direta de valores absolutos de renda de anos diferentes sem harmonização.

## 5. Testes realizados e resultados

| Dimensão auditada | Resultado | Critério aplicado |
|---|---|---|
| Estrutura do arquivo JSON | **Aprovado** | Identificador, população, anos, códigos A–Q e conjunto de BR + 27 UFs |
| Reconciliação populacional | **Aprovado** | Soma das faixas = N do recorte; tipos declarada/não informada/inválida = N; soma das 27 UFs = Brasil |
| Completude das competências | **Aprovado** | C1–C5 presentes para cada faixa; mesmo N por faixa nas cinco competências |
| Plausibilidade estatística | **Aprovado no agregado** | Médias/quantis em 0–200; Q1 ≤ mediana ≤ Q3; IQR = Q3 − Q1; desvio-padrão não negativo e plausível |
| Proporções | **Aprovado** | Percentuais recalculados dos respectivos denominadores, com tolerância de arredondamento de 0,00000051 ponto percentual |
| Brasil × UFs por faixa | **Aprovado** | Contagens e médias ponderadas por N; desvio-padrão combinado considerando variação intra/inter-UF |
| CSV × JSON | **Aprovado** | 14.430 linhas reconciliadas campo a campo, incluindo valores nulos, percentuais e `n_pequeno` |
| IND-041 × IND-042 | **Aprovado** | Contagens por recorte e categoria iguais às disponibilizadas pelo IND-041 |
| Dashboard 2024 × IND-042 | **Aprovado** | Blocos `national`, `states`, fonte Q007 e metadados iguais ao JSON do IND-042 |
| IND-009 × IND-042 (2024) | **Aprovado** | Médias das cinco competências recompostas por média ponderada de cada faixa nos 28 recortes |
| Células pequenas | **Não aprovado para publicação integral** | 3 células de 1–29 redações mantidas nos dados exportados |
| Soma C1–C5 × nota total em 2023 | **Ressalva da fonte** | 1 redação em SC (também contada no BR), diferença acumulada de −30 pontos, já registrada pelo IND-009 |
| Reprocessamento dos microdados originais | **Não realizado** | Fontes brutas individuais não fazem parte deste pacote de auditoria |

## 6. Problema de privacidade — ação obrigatória

Foram identificadas as seguintes células com quantidade positiva inferior a 30:

| Ano | UF | Categoria de renda | N | Situação de exportação |
|---|---|---|---:|---|
| 2020 | RR | `SEM_RESPOSTA` (renda não informada) | 16 | Estatísticas C1–C5 presentes em JSON e CSV |
| 2021 | BR | `SEM_RESPOSTA` (renda não informada) | 1 | Estatísticas C1–C5 presentes em JSON e CSV |
| 2021 | SP | `SEM_RESPOSTA` (renda não informada) | 1 | Estatísticas C1–C5 presentes em JSON e CSV |

**Ação necessária:** não disponibilizar os detalhes dessas células (inclusive média, mediana, quartis, desvio-padrão e N) em resultados públicos. Aplicar **supressão primária e complementar** para que a célula não seja reconstruída por subtração dos totais ou pela relação Brasil × UFs e com outros indicadores. A simples ocultação do marcador visual não é suficiente se o dado continuar no JSON acessível à aplicação.

O limiar N≥30 é a regra operacional de agregação deste projeto, mas **não garante sozinho anonimização**; a validação de privacidade contextual e o aceite acadêmico ainda são necessários. Caso o aplicativo Streamlit esteja público, revisar sua exposição antes de integrar/disponibilizar o IND-042.

## 7. Anomalia conhecida da fonte — ENEM 2023

| Recorte | Redações divergentes | Soma de C1–C5 menos nota total |
|---|---:|---:|
| Santa Catarina (SC) | 1 | −30 pontos |
| Brasil (BR) | 1 | −30 pontos |

Os dois recortes se referem à **mesma redação**, não a duas ocorrências independentes. O mesmo registro consta em `quality.ind009_validation` do dashboard de 2023, com `validas_soma_competencias_divergente = 1` e `delta_soma_competencias_menos_nota_redacao = -30.0`. O IND-042 preserva a média das competências tal como aparece na fonte, sem forçar a soma a reproduzir a nota final. Não alterar artificialmente os valores para eliminar a discrepância: registrar a exceção e verificar sua origem na base bruta em revisão futura.

## 8. Limitações e decisões pendentes

1. **Não foi reprocessada a base individual.** Assim, os percentis exatos, a seleção `TP_STATUS_REDACAO=1`, a junção real por `NU_INSCRICAO` em 2024 e o cálculo dos desvios a partir das notas individuais não são verificáveis de forma independente com os arquivos agregados fornecidos. Foram comprovadas consistência, plausibilidade e reconciliação de suas saídas.
2. **A referência IND-041 não substitui a conferência dos microdados**: os dois indicadores podem compartilhar parte do processamento original.
3. **A privacidade cruzada continua pendente** e foi identificado material que exige supressão antes da divulgação.
4. **A revisão acadêmica permanece pendente**, inclusive o esclarecimento da heterogeneidade das faixas de renda entre anos e do caráter observacional/não causal.
5. **A indisponibilidade de 2025 é metodologicamente correta** enquanto as fontes públicas não fornecerem uma chave de vínculo legítima.

## 9. Parecer técnico e encaminhamento

**Parecer:** o IND-042 está **coerente e aprovado quanto à consistência computacional dos agregados examinados (465.134 verificações, zero falhas)**. **Não está aprovado para divulgação pública irrestrita**, por conter células com N inferior a 30 e pela necessidade de revisão acadêmica/contextual. A discrepância da fonte de 2023 deve ser preservada como ressalva documentada.

**Ordem recomendada para conclusão:** (1) implementar supressão primária/complementar nas categorias de renda não informada identificadas e impedir exportação dos valores derivados; (2) regenerar os JSONs/CSV e dashboards afetados; (3) reexecutar o script de auditoria e testes de reidentificação por subtração; (4) documentar a exceção de 2023; (5) solicitar aprovação acadêmica e de divulgação.

## 10. Reprodução

Com os arquivos reunidos na mesma pasta que `auditar_IND_042.py`:

```bash
python auditar_IND_042.py
```

A rotina gera `Auditoria_IND_042_resultados_verificacoes.json` e reproduz os testes agregados. Também aceita `--raiz` e `--saida` para selecionar pastas. Em um repositório organizado, o script localiza automaticamente `outputs/json/IND_042_renda_competencias.json` e `outputs/indicadores/IND_042_renda_competencias.csv` quando elas estiverem sob a raiz indicada.

---

*Este documento é um parecer de validação técnica dos produtos disponibilizados, e não um atestado de anonimização ou de aprovação acadêmica definitiva.*
