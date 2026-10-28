# Validação Técnica — IND-020 | Diferença total entre AV1 e AV2 — ENEM 2019–2025

**Projeto Integrador IV — UNIVESP**
**Parecer:** **APROVADO TECNICAMENTE COM RESSALVAS** para análise interna; publicação externa requer revisão acadêmica e de privacidade.
**Auditoria independente dos artefatos agregados:** **75.302 verificações**, **0 divergências**.
**Escopo:** CSV completo do IND-020 (2.182 linhas), JSON modular completo (7 anos e histórico, Brasil e 27 UFs), dashboard cumulativo de **2024**.
**Data da geração registrada nas saídas:** `2026-10-19T02:42:18+00:00`.
**Natureza da auditoria:** verificação computacional dos arquivos de saída; os microdados individuais NÃO foram relidos nem as diferenças AV1×AV2 calculadas novamente registro a registro.

## 1. Objeto e população

O IND-020 mede a **diferença absoluta** entre as notas totais dadas pelos dois primeiros avaliadores de cada redação:

`D = abs(NU_NOTA_AV1 - NU_NOTA_AV2)` (pontos de **0 a 1000**).

A população é **`POP_EVALUATOR`**: redações com **ambas as notas totais AV1 e AV2 presentes e válidas** entre 0 e 1000. Ela **não é equivalente** à população de redações válidas (`POP_VALID`) utilizada nos IND-001 a IND-019. O indicador não mede viés, nem identifica o avaliador correto: apenas quantifica a distância entre duas atribuições de nota.

Os resultados são calculados por sete anos (2019–2025) e histórico consolidado, para Brasil e as **27 unidades da Federação**, representando **224 recortes**. `SG_UF_PROVA` corresponde ao estado **onde a prova foi realizada**, e não necessariamente à residência. No histórico são somadas **participações**, não pessoas únicas.

## 2. Integridade dos arquivos recebidos

| Artefato | Conteúdo verificado | SHA-256 (12 dígitos) |
|---|---|---|
| `IND_020_diferenca_total_av1_av2.csv` | 2.182 linhas, separador `;`, UTF-8 com BOM | `4e2ab02529a7` |
| `IND_020_diferenca_total_av1_av2.json` | 224 recortes e seus histogramas; metadados e QA da junção | `e57e61a6ee4d` |
| `dashboard_enem_2024.json` | `pages.evaluators.total_difference`, `pages.temporal.ind020`, `pages.methodology.ind020` e validação | `490c4fa857af` |

O CSV está em formato **longo por classe do histograma**, e não em 224 linhas únicas: o mesmo recorte aparece em tantas linhas quantas forem as classes positivas de sua distribuição. São 224 grupos e **2.182 classes agregadas**.

## 3. Resultado da auditoria

**75.302 verificações aprovadas; nenhuma divergência.**

A rotina de auditoria independente conferiu:

- Presença e unicidade dos **8 períodos × 28 recortes = 224 grupos**; presença das 27 UFs em todos eles.
- Equivalência **CSV ↔ JSON** de identificadores, população, média, mediana, P25, P75, P90, desvio-padrão, mínimo, máximo, denominação, limites de classe, inclusividade, contagens e percentuais nas **2.182 linhas**.
- Recalculo dos percentuais das classes, somas dos histogramas e concordância com os denominadores; todos os bins positivos têm `n≥30`; **menor contagem positiva: 30**.
- Ordem e limites dos percentis, compatibilidade dos quantis com os intervalos de classes e plausibilidade matemática da média em relação às classes. **Quantis exatos não são reconstruíveis somente a partir dos bins agregados**; sua verificação exata exigiria as frequências por pontuação ou os microdados.
- Recalculo independente da **média ponderada e do desvio-padrão combinado (`ddof=0`)** para Brasil a partir das 27 UFs, em cada ano e no histórico.
- Recalculo das estatísticas históricas usando as sete médias e variâncias anuais, separadamente para Brasil e cada UF, além das contagens, mínimos e máximos.
- **313 reconciliações adicionais de classes** quando os limites dos histogramas dos subgrupos permitiam agregação matemática exata (demais classes podem atravessar fronteiras diferentes entre recortes).
- Diagnósticos agregados de origem: em 2019–2024, junções por `NU_INSCRICAO` e `NU_ANO` declaradas sem faltas; em 2025, notas e UF da prova na mesma base. Esta verificação é dos **diagnósticos reportados pelo próprio pipeline**, não reexecução da junção sobre os arquivos originais.
- Consistência do dashboard de 2024 com o módulo IND-020: Brasil, 27 UFs, série nacional de sete anos, histórico, metodologia, QA, versão e carimbo temporal idênticos.

## 4. Resultados nacionais

| Ano | Redações com AV1 e AV2 (`POP_EVALUATOR`) | Diferença média (pontos) | Mediana (pontos) | P90 (pontos) |
|---|---:|---:|---:|---:|
| 2019 | 3.779.355 | 79,43 | 80 | 160 |
| 2020 | 2.674.914 | 87,49 | 80 | 200 |
| 2021 | 2.378.379 | 67,21 | 40 | 160 |
| 2022 | 2.493.442 | 70,41 | 40 | 160 |
| 2023 | 2.822.643 | 93,11 | 80 | 200 |
| 2024 | 3.167.955 | 84,28 | 80 | 200 |
| 2025 | 3.457.555 | 84,89 | 80 | 200 |
| **2019–2025** | **20.774.243** | **81,49** | **80** | **160** |

A diferença absoluta média é maior em **2023 (93,11 pontos)** e menor em **2021 (67,21 pontos)**. Esses dados são descritivos; não permitem atribuir causalidade, qualificar a correção como certa/errada ou concluir sobre a atuação individual dos avaliadores.

### 4.1 O cuidado central em 2024: denominadores diferentes

- `POP_EVALUATOR` do IND-020: **3.167.955** redações pareadas.
- `POP_VALID` do IND-001: **3.002.710** redações válidas.
- Diferença aritmética dos dois totais: **165.245**.

**Não é uma inconsistência**: as definições de elegibilidade são diferentes. Tampouco se deve interpretar automaticamente essa subtração como o número de redações inválidas com avaliação, pois o cruzamento individual das duas populações não foi auditado. No Streamlit futuro, toda porcentagem do IND-020 deverá adotar explicitamente **`POP_EVALUATOR`** como denominador.

Em 2019 há **3.779.355** avaliações pareadas contra **3.779.356** redações válidas. Essa diferença, isoladamente, também não é erro; as definições diferem e o pipeline reporta 1.315.816 registros sem ambas as notas em 2019.

## 5. Cuidados de interpretação e publicação

1. **Diferença absoluta não tem direção:** sem análise adicional, não é possível afirmar qual avaliador atribuiu nota superior com maior frequência, nem identificar erro ou viés.
2. **Intervalos do histograma variam:** quando uma classe tem contagem positiva inferior a 30, o pipeline combina classes contíguas. Comparações visuais de histogramas entre anos e UFs exigem considerar os limites efetivos das classes; não comparar barras de intervalos distintos como se representassem o mesmo evento.
3. **UF de aplicação:** não chamar os resultados estaduais de desempenho dos *residentes* daquela UF.
4. **Histórico:** agregar os sete anos conta participações (não candidatos únicos). A média histórica usa todas as participações pareadas, não a média aritmética simples das médias dos anos.
5. **Estado da análise:** todos os artefatos têm `data_status="draft"`. A regra computacional de células positivas ≥30 **não substitui** o processo de revisão acadêmica e de divulgação pública.
6. **Aviso legado:** no dashboard 2024, dois campos de QA dos IND-017/018 ainda trazem a mensagem “IND-019 pendente”, apesar de `ind019_validation.status="ok"`. É uma inconsistência de **metadados anteriores**, sem impacto nos cálculos do IND-020; deve ser corrigida em revisão documental futura.

## 6. Limitações efetivas da auditoria

- **Sem microdados de origem:** não foram reprocessadas AV1/AV2 individuais, nem refeitos os JOINs reais, nem calculados exatamente os quantis a partir de frequências por valor de nota. As 75.302 verificações medem **consistência entre artefatos e identidades estatísticas dos agregados**.
- **Somente dashboard de 2024 recebido:** os seis dashboards cumulativos restantes não foram inspecionados na presente rodada, embora o módulo IND-020 contenha todas as séries agregadas.
- **Proteção de dados:** nenhuma linha individual foi exportada nos três artefatos examinados; a avaliação de risco de publicação cruzada com outros indicadores continua uma etapa distinta.
- **Não foi executado um teste externo de significância** das diferenças anuais ou estaduais; o indicador é descritivo.

## 7. Parecer e próxima etapa

**IND-020 APROVADO TECNICAMENTE COM RESSALVAS** para análise interna do Projeto Integrador IV — UNIVESP. O CSV, o módulo JSON e a integração do dashboard de 2024 não apresentam divergências verificáveis nos agregados. A aprovação **não** significa validação acadêmica/publicação pública dos painéis.

**Próximo passo recomendado:** executar ou auditar o **IND-021 — Diferença por competência entre AV1 e AV2**, usando a população pareada compatível com o IND-020, após conferir os requisitos do script. O **Streamlit público permanece limitado aos IND-001 a IND-019**, conforme decisão anterior, até a implementação e revisão dos módulos de avaliadores.

**Rastreabilidade:** `auditoria_IND020.py` reproduz esta conferência a partir dos três arquivos agregados e gera `auditoria_IND020_resultados.json` com verificações, divergências, alertas e números essenciais.
