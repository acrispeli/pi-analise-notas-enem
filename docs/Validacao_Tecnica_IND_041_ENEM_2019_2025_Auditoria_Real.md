# Validação técnica IND-041 — Renda familiar × nota total da redação

**Projeto:** Projeto Integrador IV — UNIVESP  
**Período solicitado:** ENEM 2019–2025; **dados efetivamente cruzáveis:** 2019–2024  
**Data da auditoria:** 22 de outubro de 2026  
**Estado da análise:** `draft`; saídas reais agregadas examinadas, sem recálculo independente dos microdados de origem.  
**Parecer:** **APROVADO quanto à aritmética, consistência agregada e aderência ao objetivo descritivo; COM RESSALVAS** para documentação, células raras, auditoria da junção de 2024 e publicação externa.

## 1. Objetivo e arquivos examinados

O **IND-041** busca verificar como **quantidade de redações válidas, média, mediana e dispersão (Q1, Q3, IQR e desvio-padrão)** se distribuem pelas faixas de **renda familiar declarada**, no Brasil e nas 27 unidades federativas de **aplicação da prova**. São participações em exames, não pessoas únicas, e a análise é **associativa/descritiva**, não causal.

Foram confrontados:

- `IND_041_renda_nota_total.csv` (CSV com separador `;`, UTF-8 com BOM);
- `IND_041_renda_nota_total.json` (módulo IND-041 de 2019–2025);
- `dashboard_enem_2024.json` (`pages.socioeconomic.income_total`);
- `IND_041_renda_nota_total.py` (código gerador disponibilizado);
- `IND_002_nota_media.json` e `IND_006_distribuicao_notas.json` (controles de notas e de população);
- `IND_040_perfil_socioeconomico.json` (controle da renda na população do questionário);
- `DICIONARIOS.xlsx` (faixas monetárias oficiais das questões `Q006` / `Q007`).

Foram examinadas **2.886 linhas do CSV**, correspondentes às **2.886 categorias/recortes do JSON**, distribuídas por **168 recortes efetivamente calculados** (2019–2024 × Brasil + 27 UFs). A soma das populações anuais brasileiras é de **16.819.206 participações com redação válida**. O ano **2025 está registrado como indisponível**, sem linhas de resultados de renda × nota, pois os arquivos públicos envolvidos não fornecem uma chave individual comum para essa análise.

## 2. Parecer computacional e alcance da auditoria

**84.270 verificações programáticas executadas; 0 falhas nas condições testadas.** As verificações cobriram estrutura, fechamentos, integridade de percentuais, limites das estatísticas, correspondência CSV × JSON, integração com o dashboard, controles contra IND-002/006/040, faixas dos dicionários e casos sintéticos do gerador.

| Grupo de verificações | Testes | Falhas |
|---|---:|---:|
| Estrutura do módulo e das categorias | 864 | 0 |
| Registro de indisponibilidade de 2025 | 2 | 0 |
| Abrangência geográfica e soma das UFs | 12 | 0 |
| Populações, partições e fechamento das categorias | 1.182 | 0 |
| Percentuais e denominadores | 5.940 | 0 |
| Estatísticas, quartis, IQR, amplitude e avisos de pequenos N | 25.974 | 0 |
| Confrontos compatíveis com IND-040 | 3.024 | 0 |
| Confrontos com IND-002 e IND-006 | 840 | 0 |
| Igualdade linha/campo do CSV com o JSON | 46.179 | 0 |
| Integração com dashboard de 2024 | 35 | 0 |
| Casos sintéticos das funções do gerador | 14 | 0 |
| Códigos e limites monetários do dicionário (102 faixas × 2 verificações) | 204 | 0 |
| **TOTAL** | **84.270** | **0** |

**Limite fundamental:** a auditoria **não é um novo cálculo a partir das linhas dos microdados brutos**. Comparações com outros indicadores e a integridade das saídas permitem detectar inconsistências, mas **não comprovam sozinhas a correção de cada registro, a unicidade das inscrições no complemento de 2024, nem a ausência de erro sistemático compartilhado entre geradores**. Não foi executada validação formal contra `04_resultados_analises.schema.json`, que não integra o conjunto de arquivos usado nesta auditoria.

## 3. Método verificado

- **População (`POP_SOCIO_VALID`):** `TP_STATUS_REDACAO = 1` e `NU_NOTA_REDACAO` numérica entre 0 e 1.000, inclusive; todos os cálculos de desempenho dizem respeito **somente a redações válidas**.
- **Renda:** `Q006` nos microdados de **2019–2023**; `Q007` em **2024**, obtida de `PARTICIPANTES_2024.csv` e relacionada por `NU_INSCRICAO` ao complemento `COMPETENCIAS_REDACAO_2024.csv` para obter status e nota. O uso da chave está documentado no código, mas seu funcionamento completo não foi reexecutado sobre as fontes individuais nesta auditoria.
- **Categorias:** `A` a `Q`, com **17 faixas nominais por edição**; o significado monetário muda de acordo com o ano. Foram verificados os códigos e os valores em reais correspondentes às **102 combinações ano × faixa** nos dicionários locais. A categoria `A` representa **nenhuma renda**, não uma ausência de resposta.
- **Ausência de resposta:** tratada como `SEM_RESPOSTA`, separada de `A` e incluída no denominador de redações válidas; não se imputa renda ao participante. O denominador de `percentual_renda_declarada` é apenas o conjunto que declarou uma das faixas `A`–`Q`.
- **Estatísticas:** média aritmética; quantis empíricos ponderados pelas frequências de **notas exatas** com interpolação linear; IQR = Q3 − Q1; desvio-padrão populacional (`ddof = 0`). Os testes sintéticos confirmaram as fórmulas implementadas, incluindo amostras unitárias e vazias.
- **Geografia:** `SG_UF_PROVA` é a **UF de aplicação da prova**, não necessariamente a de residência. As 27 UFs fecham com o agregado do Brasil em cada ano.
- **2025:** ausência de associação individual válida entre renda e nota foi corretamente indicada como `indisponivel`, sem preencher resultados artificiais.

## 4. Resultados nacionais auditados e aderência ao objetivo

| Ano | Redações válidas (BR) | Renda não informada | Média faixa A | Média faixa Q | Diferença Q − A |
|---|---:|---:|---:|---:|---:|
| 2019 | 3.779.356 | 0 | 528,71 | 747,85 | +219,14 |
| 2020 | 2.674.914 | 29.047 | 517,92 | 749,10 | +231,18 |
| 2021 | 2.293.797 | 1 | 562,66 | 756,80 | +194,14 |
| 2022 | 2.363.615 | 0 | 573,13 | 780,44 | +207,31 |
| 2023 | 2.704.814 | 0 | 563,58 | 780,77 | +217,19 |
| 2024 | 3.002.710 | 0 | 580,48 | 784,21 | +203,73 |
| **Total 2019–2024** | **16.819.206** | **29.048** | — | — | — |

**2024/Brasil:** a média da faixa **A** (nenhuma renda) foi **580,4840** pontos (`N = 234.465`), enquanto a da faixa **Q** (acima de **R$ 28.240,00**) foi **784,2097** pontos (`N = 49.828`): **203,7257 pontos de diferença**. A mediana subiu de **560** para **820 pontos**. A progressão nacional das médias entre as 17 faixas foi monotônica em **todos os seis anos**; a média da faixa Q superou a da A em **todos os 168 recortes de ano × geografia**.

Nas UFs, porém, a progressão faixa a faixa **não é sempre monotônica**: o número de estados com todas as 17 médias em ordem crescente foi **3, 4, 8, 7, 4 e 4** em 2019, 2020, 2021, 2022, 2023 e 2024, respectivamente. Portanto, é correto afirmar uma **associação descritiva positiva e persistente**, mas **não** que cada mudança de renda sempre aumente a nota em toda UF e ano, nem que haja causalidade.

**Indicador complementar calculado nesta auditoria, não presente no módulo original:** a razão entre variância das médias dos grupos de renda e variância total das notas em **2024/Brasil** é **η² ≈ 0,11046** (cerca de **11,05%** da variância na decomposição descritiva). Esse tamanho de efeito ajuda a contextualizar a associação: a maior parte da variação de notas está **dentro** das faixas de renda, e não entre suas médias. A estimativa usa médias e desvios-padrão já arredondados do IND-041.

## 5. Controles específicos aprovados

1. **Fechamento populacional:** para todos os 168 recortes, a soma das faixas `A`–`Q`, da renda não informada e de eventuais códigos inválidos reproduz exatamente `n_redacoes_validas`. A soma das 27 UFs reproduz o Brasil em cada edição.
2. **Percentuais:** percentuais sobre todas as redações válidas e percentuais condicionados à renda declarada coincidem com seus numeradores e denominadores, dentro da precisão de exportação (**seis casas decimais**).
3. **Tendência central/dispersão:** médias, medianas, Q1, Q3 e IQR respeitam as relações e os limites aplicáveis às notas de 0–1.000; o desvio-padrão é não negativo e compatível com a escala. O cálculo sintético de quantis foi conferido separadamente.
4. **IND-002/IND-006:** os `N` de todos os recortes são idênticos; médias ponderadas e desvios-padrão recompostos por grupos de renda coincidem com os resultados de referência dentro das tolerâncias de arredondamento empregadas (**0,0002** para médias e **0,0005** para desvio-padrão).
5. **IND-040:** os `N` com redação válida não excedem os totais do questionário; contagens por faixas comparáveis não excedem suas frequências na população socioeconômica completa. Categorias previamente agrupadas no IND-040 foram respeitadas, sem comparações indevidas com seus componentes suprimidos.
6. **CSV × JSON:** 2.886 linhas únicas por `(ano, uf, codigo_renda)`, colunas corretas e concordância campo a campo, inclusive `n_pequeno` e valores ausentes.
7. **Dashboard de 2024:** `national` e **todos os 27** blocos de `states` em `pages.socioeconomic.income_total` são iguais aos recortes de 2024 do módulo, sem divergência identificada.
8. **Faixas monetárias:** códigos e limites monetários de 2019–2024 coincidem com `DICIONARIOS.xlsx`; não se aplicaram os limites reais de 2024 aos anos anteriores.

## 6. Ressalvas e pontos que exigem acompanhamento

### 6.1. Células pequenas e interpretação

Existem **três células publicadas com `0 < N < 30`**, corretamente marcadas `n_pequeno=true`:

| Ano/UF | Categoria | N | Observação |
|---|---|---:|---|
| 2020/RR | `SEM_RESPOSTA` | 16 | Foi preservada; o erro anterior de bloqueio não ocorreu nos agregados produzidos. |
| 2021/SP | `SEM_RESPOSTA` | 1 | Estatísticas como mediana e desvio-padrão não representam tendência de grupo. |
| 2021/BR | `SEM_RESPOSTA` | 1 | É o mesmo caso de SP repetido no total nacional; não são dois indivíduos distintos. |

**A presença de poucos registros não é, por si só, evidência de falha matemática ou justificativa universal para descartá-los.** Entretanto, uma média de `N = 1` reproduz exatamente a nota da única redação daquela categoria (**520 pontos** em 2021/SP e 2021/BR). Antes de divulgação externa, recomenda-se avaliar especificamente esse recorte e a exposição conjunta de ano, UF, renda não informada e nota; para inferências pedagógicas, resultados de amostra unitária devem ser apresentados como contagens, sem interpretação de tendência.

### 6.2. Seleção condicionada à redação válida

O **IND-040** contém **4.332.944** participações no questionário socioeconômico de 2024; o IND-041 analisa **3.002.710** redações válidas (**69,30%** do total socioeconômico). A proporção com redação válida difere por faixa de renda: **59,76%** na A (234.465 de 392.340) e **84,88%** na Q (49.828 de 58.703). A diferença é consequência do recorte escolhido e **não é um erro do IND-041**, mas restringe a generalização dos achados para a população de inscritos.

### 6.3. Comparação temporal e causalidade

Renda é **autodeclarada**, categorizada, sem ajuste por inflação ou equivalência de poder de compra nesta saída. A comparação longitudinal por letra de categoria deve mencionar a mudança dos limites monetários. O indicador não controla escolaridade dos responsáveis, tipo de escola, idade, região ou outras covariáveis; portanto, as diferenças observadas **não demonstram efeito causal da renda**. Não se deve somar/médias simples das medianas anuais para obter uma mediana histórica. O módulo atual não entrega um consolidado de renda × nota para todos os anos, somente recortes anuais.

### 6.4. Junção e rastreabilidade de 2024

O código gerador estabelece uma tabela de participantes com `NU_INSCRICAO` única e cruza as redações válidas do complemento pela inscrição mascarada. **Não foi possível verificar diretamente a taxa de correspondência individual, as duplicidades da chave no complemento ou a integridade de cada par** sem as fontes originais. O fechamento com indicadores anteriores fortalece a evidência agregada, mas recomenda-se adicionar e guardar um relatório de qualidade específico da junção (`n_participantes`, `n_inscricoes_unicas_complemento`, `n_validas_com_match`, `n_validas_sem_match`, duplicidades) em futura execução controlada.

### 6.5. Metadados e contrato do dashboard

O bloco `pages.socioeconomic.income_total` foi integrado corretamente ao dashboard de 2024, **mas `meta.analysis_version` ainda termina em `ind040`**, e o dashboard não possui `quality.ind041_validation` nem `pages.methodology.ind041`. Também permanece a data geral de geração anterior à integração do IND-041. Recomenda-se atualizar esses campos **no gerador e reexecutá-lo**, preservando os indicadores anteriores. A validade contra o contrato JSON global **não foi testada** nesta auditoria por falta do respectivo esquema no conjunto examinado.

## 7. Parecer final e recomendações

**RESULTADO: APROVADO na consistência aritmética e nos controles agregados; COM RESSALVAS DE METADADOS, PEQUENAS AMOSTRAS E JUNÇÃO INDEPENDENTE.**

O **objetivo principal do IND-041 foi alcançado** para 2019–2024: comparar a distribuição e o desempenho da redação segundo renda familiar, no Brasil e nas UFs, preservando as categorias de cada edição. **Não é necessário refazer os cálculos por causa do antigo bloqueio de 2020/RR**: os 16 casos foram mantidos e a análise passou nos controles efetuados.

Para conclusão acadêmica/publicação externa, recomenda-se: (a) completar metadados e testes de contrato do dashboard; (b) documentar a auditoria da junção 2024 sobre os microdados originais; (c) qualificar a interpretação de grupos com `N = 1` e avaliar publicação externa de células unitárias; (d) explicitar que 2025 está indisponível e que a comparação de renda é descritiva, não causal. Essas recomendações **não invalidam os resultados agregados aprovados**.

---

**Rastreabilidade:** a contagem dos testes e seus resultados constam de `Auditoria_IND_041_resultados_verificacoes.json`; a execução é reproduzível, com os mesmos arquivos locais, por `auditar_ind041.py`. **Nenhum arquivo de microdados individuais foi examinado ou exportado nesta auditoria.**
