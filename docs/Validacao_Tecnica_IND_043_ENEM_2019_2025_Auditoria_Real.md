# Validação Técnica — IND-043: Escolaridade dos responsáveis × nota total da redação

**Projeto:** Projeto Integrador IV — UNIVESP
**Indicador:** IND-043
**Escopo temporal solicitado:** ENEM 2019–2025
**Período efetivamente disponível:** 2019–2024 (2025 indisponível)
**Data da auditoria:** 23/10/2026
**Parecer:** **APROVADO PARCIALMENTE — consistência agregada aprovada, publicação de células pequenas bloqueada até correção de privacidade.**

## 1. Sumário executivo

Os dados agregados de `IND_043_escolaridade_responsaveis_nota.json`, as 2.748 linhas de `IND_043_escolaridade_responsaveis_nota.csv` e o bloco `pages.socioeconomic.parent_education_total` do `dashboard_enem_2024.json` foram submetidos a **92.697 verificações programáticas**, todas concluídas sem falhas de consistência (**0 falhas**). O escopo compreendeu 168 recortes ano × geografia (Brasil e 27 UFs), 336 distribuições por questão e 2.748 células de categorias.

Foi confirmada a coerência de contagens, denominadores, fechamento das categorias, soma das 27 UFs, percentuais, indicadores de grupos pequenos, conformidade CSV ↔ JSON, consistência das médias e desvios-padrão agregados e correspondência do dashboard de 2024.

**Pendência impeditiva de divulgação irrestrita:** **6 células divulgadas com 1 a 29 redações**, ligadas a **2 situações subjacentes** (não são seis grupos independentes). Elas contêm médias e demais estatísticas potencialmente identificáveis e precisam de **supressão primária e complementar** antes de integrar o painel público. Para 2021, a contagem de **uma redação** é repetida no Brasil e em SP, em Q001 e Q002; a divulgação dos parâmetros da nota dessa célula não é aceitável sem revisão de privacidade.

O parecer **não** equivale à validação independente dos microdados originais: CSV e JSON são saídas do mesmo processamento, e a junção de 2024 não foi reexecutada nesta auditoria.

## 2. Entradas auditadas

| Arquivo | Finalidade | Situação |
|---|---|---|
| `IND_043_escolaridade_responsaveis_nota.json` | Consolidado completo IND-043 2019–2025 | Analisado |
| `IND_043_escolaridade_responsaveis_nota.csv` | Exportação tabular, separador `;`, BOM UTF-8 | Analisado, 2.748 linhas |
| `dashboard_enem_2024.json` | Aplicação 2024, `pages.socioeconomic.parent_education_total`, KPIs gerais | Analisado |
| Microdados individuais do INEP 2019–2024 | Recalcular diretamente estatísticas, categorias e junção de 2024 | **Não disponíveis para esta auditoria** |

A auditoria considerou como definição declarada de população **`POP_SOCIO_VALID`**, definida pelo próprio indicador como `TP_STATUS_REDACAO=1` e `NU_NOTA_REDACAO` numérica dentro do intervalo `[0,1000]`; a localização geográfica é a **UF de realização da prova** (`SG_UF_PROVA`), não a residência. A variável **Q001** representa a escolaridade do pai/homem responsável, e **Q002** a da mãe/mulher responsável; os dois conjuntos são *marginais independentes*, sem cruzamento entre si. As categorias **A–G** representam níveis escolares e **H** significa “Não sei”, não sendo um nível ordinal. Os resultados são descritivos, não causais.

## 3. Abrangência e volumes

| Ano | Redações válidas BR (`POP_SOCIO_VALID`) | Células de categorias | Células com 1–29 redações |
|---|---:|---:|---:|
| 2019 | 3.779.356 | 448 | 0 |
| 2020 | 2.674.914 | 504 | 2 |
| 2021 | 2.293.797 | 452 | 4 |
| 2022 | 2.363.615 | 448 | 0 |
| 2023 | 2.704.814 | 448 | 0 |
| 2024 | 3.002.710 | 448 | 0 |
| **Total 2019–2024** | **16.819.206 participações** | **2.748** | **6** |
| 2025 | Indisponível | 0 | Não aplicável |

Os totais históricos representam **participações por edição**, não pessoas únicas. Não existe, no arquivo examinado, uma distribuição específica de 2025 porque o próprio indicador informa falta de chave pública compartilhada entre fontes para conectar escolaridade e nota individual.

2020 possui oito categorias A–H mais `SEM_RESPOSTA` em todos os recortes por pergunta. Em 2021, `SEM_RESPOSTA` aparece apenas nos recortes Brasil e SP, para ambas as perguntas; nos outros anos há apenas A–H nos arquivos fornecidos. A presença ou ausência de categorias sem contagem foi respeitada na reconciliação.

## 4. Testes executados e resultados

| Frente | Procedimento | Resultado |
|---|---|---|
| Estrutura | Identificador IND-043, população, anos disponíveis e ausência coerente de 2025 | Conforme |
| Completude geográfica | BR + 27 UFs para cada ano 2019–2024 | Conforme |
| Denominadores | Mesmos N declarados por recorte em Q001 e Q002, alinhados a `n_pop_socio_valid` | Conforme |
| Fechamento de categorias | Soma `n_redacoes` = total da pergunta; conhecidos A–G, H, brancos e inválidos reconciliados | Conforme |
| Brasil × UFs | Soma das UFs = BR, inclusive por código de escolaridade e por questão | Conforme |
| Percentuais | Recomputados a partir de `100 × N_categoria / N_validas`, com tolerância de arredondamento | Conforme |
| Estatísticas | Média entre 0 e 1000; quartis em ordem, IQR = Q3−Q1, DP não negativo; teste de coerência estatística | Conforme |
| Médias e DP | Médias ponderadas e desvios-padrão combinados de UFs reproduzem BR; média total de Q001 e Q002 coincide por recorte | Conforme |
| CSV × JSON | Mesmas 2.748 chaves únicas e mesmos 18 campos por célula, sem linhas órfãs ou divergências | Conforme |
| Proteção mínima | Campo `n_pequeno` identifica corretamente `0 < N < 30` | **6 células identificadas; não suprimidas** |
| Dashboard 2024 | Indicador, população, bloco BR e 27 UFs idênticos ao JSON; total, média e DP reconstruídos compatíveis com KPIs | Conforme |
| Metadados do dashboard | Presença explícita de `quality.ind043_validation` e aviso específico sobre IND-043 em `meta.warnings` | **Pendente de complementação** |

**Resultado global programático:** **92.697 aprovadas / 92.697 executadas / 0 inconsistências detectadas**. Esse número representa as regras automáticas documentadas no script reproduzível, e **não** testes independentes sobre os registros individuais.

### 4.1 Coerência com o dashboard 2024

- O JSON do IND-043 e `dashboard_enem_2024.json` possuem o mesmo bloco completo da edição 2024, inclusive as 27 UFs.
- A população nacional reconciliada é **3.002.710 redações válidas**, em consonância com os KPIs gerais do dashboard.
- A média geral reconstruída pelos grupos de Q001 é aproximadamente **658,9658 pontos**; em Q002 também é aproximadamente **658,9658 pontos**. O KPI correspondente é **658,9658**.
- O desvio-padrão populacional reconstruído a partir dos grupos de Q001 e Q002 é aproximadamente **163,4915 pontos**, compatível com o KPI **163,4915**.
- O diagnóstico da fonte informa, para a junção de 2024, **3.002.710 redações válidas vinculadas**, **zero válidas sem correspondência** e **unicidade das chaves**. Esses campos foram verificados apenas como **metadados declarados**; a junção `NU_INSCRICAO` não foi reexecutada.
- Embora o módulo do indicador conste no dashboard, **não foi localizado** `quality.ind043_validation` nem aviso nominal do IND-043 em `meta.warnings` no arquivo recebido. Recomenda-se inserir ambos para rastreabilidade, especialmente antes de qualquer liberação pública.

### 4.2 Natureza das estatísticas verificadas

As médias e desvios-padrão agregados foram reconciliados matematicamente entre UFs e Brasil. Para mediana, Q1 e Q3, foram testados intervalos válidos, ordem dos quantis e consistência de IQR. **Não é possível reconstruir ou certificar os quantis exatos tipo Hyndman–Fan 7, a partir de médias e quartis agregados**, sem os histogramas exatos de notas ou os microdados originais. A mesma limitação vale para verificar autonomamente a filtragem `TP_STATUS_REDACAO=1` e a escolha da chave de junção.

## 5. Achado crítico de privacidade: seis células pequenas

| Ano | Geografia | Questão | Categoria | N |
|---|---|---|---|---:|
| 2020 | RR | Q001 (pai/homem responsável) | `SEM_RESPOSTA` | 16 |
| 2020 | RR | Q002 (mãe/mulher responsável) | `SEM_RESPOSTA` | 16 |
| 2021 | BR | Q001 | `SEM_RESPOSTA` | 1 |
| 2021 | BR | Q002 | `SEM_RESPOSTA` | 1 |
| 2021 | SP | Q001 | `SEM_RESPOSTA` | 1 |
| 2021 | SP | Q002 | `SEM_RESPOSTA` | 1 |

Não são seis grupos diferentes: Q001 e Q002 referem-se à mesma população, e em 2021 a mesma ocorrência aparece tanto no total BR quanto em SP. A **repetição em níveis geográficos diferentes amplia o risco de dedução**, inclusive por operações de subtração e por exposição das medidas de tendência central de grupos de um único participante.

O código do indicador **sinaliza**, mas **não suprime automaticamente**, os casos `0 < N < 30`. Por isso, o campo booleano `n_pequeno=True` está consistente, mas é **insuficiente como política de divulgação**. Recomendações obrigatórias:

1. **Suprimir as estatísticas e, quando necessário, a própria contagem** de todas as células positivas com N inferior a 30, em CSV/JSON/exportações e no Streamlit público; evitar deixar os números acessíveis por download do JSON.
2. Aplicar **supressão complementar** nos níveis BR ↔ UF e nas marginais Q001 ↔ Q002, para impedir a reconstituição dos valores por diferença de totais, médias ponderadas ou cruzamento com outras páginas/indicadores.
3. Definir convenção de saída para células suprimidas (`null`, `suprimido_por_privacidade` etc.), compatível com o consumidor no Streamlit; não transformar o N real em zero, o que distorceria totais.
4. Reexecutar geração, validação, teste do dashboard e revisão humana de privacidade antes de divulgar a nova versão.

O relatório deliberadamente **não reproduz as notas e médias dos grupos pequenos**, que já estão expostas nos arquivos originais auditados.

## 6. Ressalvas metodológicas e acadêmicas

- Escolaridade autorreferida não equivale a escolaridade comprovada.
- A categoria H (“Não sei”) não pode integrar escalas ordinais A–G sem recodificação e justificativa.
- Q001 e Q002 são recortes separados da mesma população: **não se devem somar suas contagens** como se fossem participantes distintos.
- UF refere-se à aplicação da prova, e não necessariamente à residência.
- Diferenças na nota conforme escolaridade dos responsáveis indicam **associações descritivas**, não efeito causal da escolaridade.
- Para 2024, a junção por `NU_INSCRICAO` consta na metodologia e no diagnóstico, mas precisa de conferência independente sobre os arquivos de origem se for exigida validação completa.
- As edições não devem ser apresentadas como indivíduos únicos numa soma histórica.
- Falta revisão de privacidade contextual cruzada com outros indicadores, além da supressão por limiar simples.

## 7. Parecer e ações para homologação

**Parecer: APROVADO PARCIALMENTE, COM PENDÊNCIA OBRIGATÓRIA DE PRIVACIDADE.**

**Aprovado neste momento:** consistência interna, conciliação geográfica, integridade da exportação CSV, aderência ao JSON agregado, compatibilidade integral do dashboard 2024 e compatibilidade aritmética dos KPIs.

**Ainda não homologado para divulgação pública:** células positivas com N inferior a 30, proteção contra reidentificação por totais nacionais/estaduais e revisão acadêmica da metodologia. Para aprovação plena, exige-se regeneração e nova auditoria após a supressão, e, quando viável, reprocessamento amostral/independente diretamente das fontes do INEP.

**Ordem sugerida:**

1. Corrigir `src/indicadores/IND_043_escolaridade_responsaveis_nota.py` para gerar saídas públicas suprimidas e manter, quando necessário, uma versão analítica interna separada.
2. Regenerar `outputs/json/IND_043_escolaridade_responsaveis_nota.json` e `outputs/indicadores/IND_043_escolaridade_responsaveis_nota.csv` sem divulgar as estatísticas sensíveis.
3. Regerar os dashboards correspondentes, inserir `quality.ind043_validation`, e atualizar os avisos do indicador.
4. Executar novamente a auditoria **com regras adequadas para dados suprimidos** e inspecionar manualmente as operações de subtração entre Brasil e UFs.
5. Testar a interface e o acesso direto aos arquivos no GitHub/Streamlit antes de liberar IND-043 publicamente.

## 8. Reprodutibilidade

Foi criado o script `auditar_IND_043.py`, que usa somente a biblioteca padrão do Python e produz `Auditoria_IND_043_resultados_verificacoes.json`. Executar na pasta com os três arquivos:

```powershell
python auditar_IND_043.py --json IND_043_escolaridade_responsaveis_nota.json --csv IND_043_escolaridade_responsaveis_nota.csv --dashboard dashboard_enem_2024.json --saida Auditoria_IND_043_resultados_verificacoes.json
```

**Nota:** o script fornecido audita o **formato atual não suprimido**. Após alterar os dados públicos para omitir células pequenas, será necessário adaptar as verificações de estatísticas nulas/suprimidas e, sobretudo, acrescentar testes específicos de supressão complementar; **não é correto exigir igualdade entre CSV/JSON públicos e os agregados internos com dados sensíveis**.

---

*Documento elaborado a partir da auditoria computacional dos arquivos agregados efetivamente fornecidos. Não constitui revisão independente dos microdados do INEP nem autorização automática de publicação.*
