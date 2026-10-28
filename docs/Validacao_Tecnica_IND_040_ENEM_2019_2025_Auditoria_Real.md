# Validação técnica do IND-040 — Perfil socioeconômico descritivo

**Projeto:** Projeto Integrador IV — UNIVESP
**Período:** ENEM 2019–2025
**Data da auditoria:** 23 de outubro de 2026
**Material auditado:** dados agregados efetivos fornecidos em CSV/JSON e dashboards disponíveis; **sem reprocessamento de microdados individuais**.
**Parecer:** **APROVADO PARCIALMENTE** quanto às distribuições anuais e à integração verificada. **NÃO APROVADO INTEGRALMENTE** enquanto o histórico 2019–2025 permanecer inconsistente. **Correção obrigatória antes da homologação ou publicação acadêmica do histórico.**
**Estado da fonte:** `draft`; revisão acadêmica e privacidade cruzada pendentes.

## 1. Objetivo e escopo

O **IND-040 — Perfil socioeconômico descritivo** quantifica frequências e proporções das respostas às questões socioeconômicas `Q001` a `Q023`, segmentadas pelo **Brasil** e pelas **27 UFs de aplicação da prova**, em cada ano de 2019 a 2025.

A população é **`POP_SOCIO`**, definida no módulo como **todos os registros da fonte de questionário no ano**, incluindo respostas deixadas em branco. **Não se trata exclusivamente das redações válidas**. Os resultados descrevem *participações* nos arquivos examinados, não pessoas únicas identificadas ao longo de diversos anos. As categorias são códigos de respostas, não valores numéricos contínuos. Não é possível inferir causalidade entre perfil socioeconômico e desempenho apenas com este indicador.

- **2019–2023:** questionário na versão original, obtido dos arquivos anuais `MICRODADOS_ENEM_<ano>.csv`.
- **2024–2025:** questionário reformulado, com fonte `PARTICIPANTES_<ano>.csv`.
- **Relevante para séries:** renda corresponde a **`Q006` até 2023** e a **`Q007` em 2024–2025**. Não se deve comparar códigos de perguntas de anos diferentes como se fossem invariáveis, sem harmonização semântica comprovada.
- **Proteção primária:** agrupamento de respostas em `__CATEGORIAS_AGREGADAS__`, quando necessário para evitar divulgação de células positivas abaixo de **30** participantes, adotando a mesma composição de grupos para Brasil e UFs em cada ano/questão.

## 2. Fontes efetivamente verificadas

1. `IND_040_perfil_socioeconomico.json` — módulo anual e histórico, incluindo `meta.source_qa`.
2. `IND_040_perfil_socioeconomico.csv` — exportação de categorias por edição, questão e UF; separador `;` e codificação UTF-8 com BOM.
3. `dashboard_enem_2024.json` — arquivo submetido nesta solicitação; bloco `pages.socioeconomic.profile` e `quality.ind040_validation`.
4. Os dashboards `dashboard_enem_2019.json` a `dashboard_enem_2023.json` **também estavam disponíveis no contexto do projeto** e foram confrontados na auditoria. Nenhum dashboard de 2025 foi disponibilizado para confronto externo nesta execução.
5. Os controles de população dos dashboards anuais disponíveis: `quality.ind007_validation.registros_lidos` e `pages.overview.ind001.denominator`, quando presentes.

**Não examinados/reprocessados nesta auditoria:** arquivos individuais `MICRODADOS_ENEM_*` ou `PARTICIPANTES_*` e implementação completa do gerador IND-040. Assim, as declarações de origem e de comparação do `meta.source_qa` foram conferidas quanto à *consistência interna*, e não verificadas por contagem independente nas fontes brutas. A auditoria também não substitui a conferência semântica completa de todos os códigos com cada dicionário oficial por edição.

## 3. Resultado geral dos testes

A auditoria executou **507.755 verificações programáticas**, identificando **56 falhas**. **Todas** pertencem a uma única classe de problema: o acumulado histórico não corresponde à soma dos sete anos. Não foram detectadas falhas nas demais verificações programadas.

| Tipo de verificação | Quantidade executada | Falhas |
|---|---:|---:|
| agregacao | 27.048 | 0 |
| br ufs | 815 | 0 |
| categorias | 159.740 | 0 |
| comparacao pop all | 12 | 0 |
| csv chaves | 22.878 | 0 |
| csv integridade | 251.020 | 0 |
| dashboard | 78 | 0 |
| estrutura | 826 | 0 |
| fonte declarada | 42 | 0 |
| historico | 59 | 28 |
| historico csv | 113 | 28 |
| metadados | 5 | 0 |
| particoes | 45.080 | 0 |
| qualidade | 35 | 0 |
| semantica temporal | 4 | 0 |
| **TOTAL** | **507.755** | **56** |

**Interpretação correta da contagem de falhas:** são **28 totais históricos inconsistentes no JSON** (Brasil e 27 UFs) e suas **28 correspondências equivocadas no CSV**. Portanto, as **56 falhas de asserção** não significam 56 causas independentes. O valor total do histórico e os valores estaduais precisam ser corrigidos nos arquivos gerados.

A estrutura conferida contém **196 recortes de ano × geografia** (7 × 28), **4.508 distribuições ano × UF × questão** (7 × 28 × 23), **22.820 linhas de categorias** e **28 linhas de histórico não harmonizado**. O CSV tem **22.848 linhas de dados**, sem contar o cabeçalho. Cada uma das 22.820 categorias coincide campo a campo com o JSON, dentro das tolerâncias de serialização.

## 4. Falha crítica: acumulado histórico 2019–2025

| Métrica Brasil | Participações |
|---|---:|
| **Total correto pela soma dos sete anos no módulo** | **30.821.888** |
| **Total informado em `historical.brasil.n_participacoes`** | **35.666.197** |
| **Diferença indevida** | **+4.844.309** |
| **Excesso relativo ao total correto** | **15.72%** |

A soma foi recalculada exclusivamente dos sete blocos `years[].brasil.n_participacoes` do mesmo JSON. Essa comparação é uma identidade contábil: **um histórico que representa a soma das participações anuais deve reproduzir exatamente a soma anual**, desde que se preserve a definição de população e não haja outra regra expressa de contagem. O módulo não apresenta regra alternativa que justifique o excedente.

A divergência se repete em **todas as 27 UFs**. O total estadual do histórico publicado soma exatamente o total nacional publicado (**35.666.197**), mas **ambos estão superiores à soma de suas respectivas séries anuais**. O CSV repete os 28 valores históricos incorretos em suas últimas linhas; a igualdade entre CSV e JSON, portanto, **não prova a correção do histórico**.

**Exemplos de divergência por UF:**

| UF | Soma anual correta | Histórico divulgado | Diferença |
|---|---:|---:|---:|
| SP | 4.770.472 | 5.711.930 | +941.458 |
| MG | 2.966.782 | 3.742.375 | +775.593 |
| BA | 2.503.574 | 2.767.989 | +264.415 |
| RJ | 2.117.069 | 2.378.012 | +260.943 |
| MA | 1.273.126 | 1.526.518 | +253.392 |

**Correção necessária:** alterar a rotina geradora para recomputar `historical.brasil.n_participacoes` e cada `historical.ufs[*].n_participacoes` diretamente das séries de 2019 a 2025; depois **regenerar o módulo JSON e seu CSV**. Verificar novamente que o histórico total do Brasil coincide com as 27 UFs e com a soma dos anos. As distribuições de `historical.*.questoes` devem continuar vazias, conforme a política de **não harmonização**.

## 5. Distribuições anuais: fechamento aprovado

| Ano | `POP_SOCIO` nacional | Questões | Questões com agregação | Campo de renda |
|---|---:|---:|---:|---|
| 2019 | 5.095.171 | 23 | 8 | Q006 |
| 2020 | 5.783.109 | 23 | 9 | Q006 |
| 2021 | 3.389.832 | 23 | 23 | Q006 |
| 2022 | 3.476.105 | 23 | 9 | Q006 |
| 2023 | 3.933.955 | 23 | 9 | Q006 |
| 2024 | 4.332.944 | 23 | 7 | Q007 |
| 2025 | 4.810.772 | 23 | 1 | Q007 |
| **Soma anual** | **30.821.888** | — | — | — |

Para os **4.508 blocos de distribuição** examinados, confirmaram-se:

- **Contagens:** a soma das quantidades das categorias reproduz exatamente o denominador do respectivo ano/UF/questão.
- **Proporções:** `quantidade / denominador` confere com `proporcao` (tolerância **5,1 × 10⁻⁹**) e com `percentual` (tolerância **0,000051 ponto percentual**), após arredondamento. Proporções somam aproximadamente 1 e percentuais, aproximadamente 100%, admitida a precisão de exportação.
- **Geografia:** a soma das 27 UFs equivale ao Brasil em cada ano, tanto no total de `POP_SOCIO` quanto **em cada código de resposta divulgado** de todas as 23 perguntas.
- **Chaves:** não foram encontradas duplicidades na combinação `(ano, UF, questão, categoria)`.
- **CSV × JSON:** as **22.820 linhas anuais do CSV** correspondem às categorias do módulo e seus valores numéricos, códigos, rótulos, denominadores, status e indicadores de agregação.
- **Dashboard:** o conteúdo nacional e as 27 UFs dos perfis socioeconômicos de **2019–2024** corresponde exatamente aos módulos anuais do IND-040. O dashboard de 2024 também declara `ind040_validation.status = ok`, com **4.332.944 registros** e 7 questões com agregação. Isso valida o *bloco anual de 2024*, não o histórico inconsistente.
- **Controles independentes entre saídas:** as populações informadas no módulo coincidem com os totais de participantes inscritos dos indicadores IND-001 e IND-007 nos seis dashboards disponíveis (2019–2024). Não se conclui, por isso, que a fonte individual foi recontada de forma independente.

## 6. Agrupamento e riscos de privacidade

**Resultado das células divulgadas:** o teste encontrou **0 células com quantidade positiva entre 1 e 29** entre as **22.820 categorias publicadas** nos sete anos, 28 geografias e 23 questões. As categorias agrupadas seguem a mesma lista de códigos de origem em Brasil e UFs para cada ano/questão, e nenhuma categoria agregada aparece ao mesmo tempo como categoria isolada no mesmo bloco.

**Entretanto, essa é somente uma validação de supressão primária.** A divulgação conjunta com outros módulos (por exemplo IND-041, IND-042 e indicadores geográficos) ainda pode permitir inferência por diferenças de totais, logo uma **revisão de privacidade cruzada é obrigatória antes de publicação pública definitiva**. Esse cuidado é particularmente importante porque o Streamlit do projeto já foi configurado para acesso público.

**Limitação interpretativa concreta:** em **2021**, houve agregação em **todas as 23 questões**. Por exemplo, `Q006` (renda) agrega o código `N` com `__SEM_RESPOSTA_FISICA__`, e `Q001` reúne a categoria `A` com a resposta fisicamente ausente. Já em **2024**, `Q006` (possui renda própria) reúne o código `B` com ausência de resposta. Essas categorias reunidas **não são semanticamente homogêneas** e **não devem ser apresentadas como se correspondessem apenas à categoria original A, B ou N**, nem como um nível específico de renda. O código de resposta ausente é distinto na fonte e na lógica interna, mas, quando agrupado, seu quantitativo deixa de ser isoladamente observável na saída pública.

A métrica conta todos os registros disponíveis do questionário (`POP_SOCIO`), não apenas as redações com nota válida. Comparações com indicadores de desempenho devem explicitar a mudança de denominador e os critérios de ligação das fontes.

## 7. Limites da comparabilidade histórica

Os questionários têm versões **2019–2023** e **2024–2025**. A distinção é tratada corretamente pelos blocos anuais e por `historical.status = sem_distribuicao_agregada_sem_harmonizacao`. Há itens que preservam denominação semelhante entre anos, mas o código `Q006` muda de **renda mensal familiar** para **possui renda própria**, enquanto `Q007` muda de **empregado(a) doméstico(a)** para **renda mensal familiar**. Não se deve interpretar séries pela numeração sozinha.

O problema detectado no histórico **não** é a ausência de distribuições harmonizadas: manter `historical.*.questoes = []` é consistente com a metodologia declarada. **O problema é o total acumulado de participações**, que deveria fechar mesmo sem harmonizar categorias.

## 8. Matriz de situação e ações recomendadas

| Controle | Resultado | Providência |
|---|---|---|
| Integridade dos blocos anuais JSON | **Aprovado** | Manter |
| CSV anual × JSON anual | **Aprovado** | Manter |
| Denominadores e percentuais por questão/UF | **Aprovado** | Manter |
| Fechamento nacional × UFs por categoria | **Aprovado** | Manter |
| Agregação primária de células com 1–29 registros | **Aprovado no teste** | Fazer revisão cruzada |
| Integração dashboards 2019–2024 | **Aprovado** | Testar 2025 quando disponível |
| Harmonização das distribuições históricas | **Não implementada, corretamente documentada** | Não combinar códigos incompatíveis |
| **Histórico Brasil + 27 UFs** | **Reprovado** | **Corrigir e regenerar JSON/CSV** |
| Verificação contra microdados individuais | **Não executada** | Fazer auditoria de origem quando possível |
| Aprovação acadêmica e publicação externa | **Pendente** | Revisar semântica e privacidade cruzada |

**Procedimento de correção sugerido ao gerador `src/indicadores/IND_040_perfil_socioeconomico.py`:**

```python
# years representa os sete blocos anuais já apurados e validados.
historico_br = sum(ano["brasil"]["n_participacoes"] for ano in years)

historico_uf = {
    uf: sum(
        next(reg["n_participacoes"] for reg in ano["ufs"] if reg["uf"] == uf)
        for ano in years
    )
    for uf in [
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
        "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
        "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    ]
}

assert historico_br == sum(historico_uf.values())
# Aplicar esses valores no bloco historical do JSON e nas linhas
# periodo=2019-2025 do CSV. Não gerar distribuições não harmonizadas.
```

Não é aconselhável corrigir **apenas** o CSV ou apenas o JSON manualmente: a alteração deve partir do código gerador para não reaparecer em novas execuções. Após reprocessar, execute novamente `auditar_IND_040.py` e confirme **zero falhas**. Não é necessário alterar as contagens por categoria dos sete anos sem evidência adicional de erro nelas.

## 9. Evidências, rastreabilidade e limitações

O script **`auditar_IND_040.py`** implementa as verificações aritméticas de saída e registra o resultado de cada grupo em **`Auditoria_IND_040_resultados_verificacoes.json`**, além de listar as falhas individuais. Estes são os identificadores SHA-256 dos três arquivos principais submetidos, utilizados para rastrear a versão dos dados:

- `IND_040_perfil_socioeconomico.csv`: SHA-256 `9c3a71c85388fd7c540493fbfcb34c6f629c829d68604f41e33937d3f4ba6296`
- `IND_040_perfil_socioeconomico.json`: SHA-256 `685ca982ff36e6660a97875d7393082d57fb0860a74ee844ae86be0a70e14ce6`
- `dashboard_enem_2024.json`: SHA-256 `969532ead80de91605ff94e22977bb1b3abb59864ca15346417a2a755b076877`

**Os 507.755 testes são verificações automatizadas sobre os mesmos arquivos agregados, não 507.755 observações independentes.** Eles não auditam a correspondência participante a participante, a integridade dos arquivos brutos, a veracidade das respostas declaradas, a adequação semântica integral de cada dicionário nem a privacidade sob todos os cruzamentos possíveis. As comparações entre CSV, JSON e dashboards podem confirmar consistência de exportação sem afastar erros compartilhados na origem.

## 10. Parecer técnico final

**IND-040: APROVAÇÃO PARCIAL COM CORREÇÃO OBRIGATÓRIA.**

As distribuições anuais de **2019 a 2025**, para Brasil e 27 UFs, apresentam consistência matemática, fecham com seus denominadores e são coerentes entre o módulo JSON e o CSV. A supressão primária de células positivas inferiores a 30 está aplicada nas saídas verificadas. O dashboard de 2024 — assim como os cinco dashboards anteriores disponíveis — incorpora corretamente seu respectivo perfil anual.

**Todavia, a série histórica não pode ser homologada no estado atual:** o acumulado nacional e os 27 acumulados estaduais diferem das somas anuais; a divergência aparece no JSON e no CSV. A rotina histórica deve ser corrigida e reprocessada antes da validação técnica final. Além disso, permanecem necessárias a revisão acadêmica dos agrupamentos semânticos, a revisão de privacidade cruzada e, se exigida, uma auditoria direta dos microdados de origem.

---

### Apêndice A — Reconciliação de 27 UFs no histórico

| UF | Soma dos 7 anos (correta) | Histórico informado no JSON | Excesso |
|---|---:|---:|---:|
| AC | 203.061 | 270.515 | +67.454 |
| AL | 581.040 | 628.768 | +47.728 |
| AM | 752.979 | 827.008 | +74.029 |
| AP | 226.961 | 298.221 | +71.260 |
| BA | 2.503.574 | 2.767.989 | +264.415 |
| CE | 1.836.027 | 2.064.888 | +228.861 |
| DF | 576.133 | 670.943 | +94.810 |
| ES | 570.143 | 715.911 | +145.768 |
| GO | 1.126.601 | 1.189.860 | +63.259 |
| MA | 1.273.126 | 1.526.518 | +253.392 |
| MG | 2.966.782 | 3.742.375 | +775.593 |
| MS | 398.812 | 492.751 | +93.939 |
| MT | 517.404 | 616.847 | +99.443 |
| PA | 1.765.626 | 1.957.151 | +191.525 |
| PB | 912.473 | 1.030.232 | +117.759 |
| PE | 1.702.850 | 1.927.219 | +224.369 |
| PI | 749.143 | 856.184 | +107.041 |
| PR | 1.287.915 | 1.479.142 | +191.227 |
| RJ | 2.117.069 | 2.378.012 | +260.943 |
| RN | 735.542 | 835.233 | +99.691 |
| RO | 314.448 | 410.473 | +96.025 |
| RR | 82.823 | 90.692 | +7.869 |
| RS | 1.395.839 | 1.529.283 | +133.444 |
| SC | 692.256 | 774.893 | +82.637 |
| SE | 492.211 | 549.416 | +57.205 |
| SP | 4.770.472 | 5.711.930 | +941.458 |
| TO | 270.578 | 323.743 | +53.165 |
| **Brasil** | **30.821.888** | **35.666.197** | **+4.844.309** |

### Apêndice B — Categorias de agregação no Brasil, por edição

A quantidade de perguntas que contém `__CATEGORIAS_AGREGADAS__` é **8, 9, 23, 9, 9, 7 e 1**, respectivamente de 2019 a 2025 (total de **66 blocos nacionais ano × questão**). O agrupamento por ano/questão é uniforme nos 28 recortes geográficos, mas seus conjuntos de códigos **podem mudar entre edições**. Contagens de categorias agregadas não devem ser comparadas diretamente como se fossem níveis socioeconômicos equivalentes.
