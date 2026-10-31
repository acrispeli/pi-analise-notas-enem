# Projeto Integrador IV — UNIVESP
## Pacote preparado para IND-055 a IND-072 · ENEM 2019–2025

**Estado desta entrega:** códigos preparados e testados com dados **sintéticos**. **NÃO houve execução em microdados reais** ou no computador do usuário. **Não instalar nem executar enquanto o Lote 2 estiver rodando.**

O ZIP contém 18 scripts numerados, um núcleo comum, instalador, executor único sem paralelismo, documentação de catálogo, contrato da ponte e testes.

### O que pode ser executado com dados já existentes

| Indicador | Fontes | Abordagem | Condição |
|---|---|---|---|
| 064 | IND-002/003 CSV | evolução média, mediana, N | pronto após arquivos válidos |
| 065 | IND-009/010 CSV | médias/medianas C1-C5 | pronto após arquivos válidos |
| 066 | IND-031/032 CSV | média de perdas, frequência | pronto após reconciliação |
| 067 | IND-020/022 CSV | diferenças AV1/AV2 e discrepância | padronização do edital deve ser explicitada |
| 069 | microdados em `data/raw/` | QA de chaves, duplicidades, left/right/matched (SQLite) | pode ser custoso; **executar antes das pontes** |
| 070 | fontes de notas e questionário em `data/raw/` | faltantes por campo/população | 2025 sem junção notas×questionário |
| 071 | CSVs agregados | **auditoria de células 1–29**, sem ocultação automática | adaptação deliberada ao catálogo |
| 072 | saídas existentes | hashes SHA256, commit, versões | não exporta números de inscrição |

### Dependências que NÃO podem ser puladas

| Indicador | Dependência obrigatória antes de calcular |
|---|---|
| 055–059 | ponte socio×nota×cluster por participante, com **chaves e modelo fixo auditados** |
| 060–061 | a mesma ponte, questionário harmonizado, avaliação fora de amostra, baseline/CV |
| 062–063 | mesma ponte e modelo IND-060 treinado na edição e fonte correspondentes |
| 068 | **modelo pooled fixo**; não cruzar nomes `C1..Ck` de modelos anuais distintos |

**IMPORTANTE:** os arquivos públicos do IND-054 fornecem perfis e centroides, NÃO as atribuições dos participantes aos clusters. Sem a ponte com um modelo fixo reconstituído, validado e aplicado aos registros reais, é metodologicamente incorreto gerar os IND-055 a 063 e IND-068. Esses scripts estão implementados, mas **bloqueiam a execução** se faltar essa etapa; não geram dados fictícios. Ver `docs/CONTRATO_PONTE.md`.

Para IND-055 a 063, **2025 é indisponível** para cruzamentos com notas: não inventar `NU_INSCRICAO` comparável entre PARTICIPANTES e RESULTADOS. IND-068 pode incluir 2025 apenas quando houver projeção socioeconômica no mesmo modelo fixo, sem uso de notas.

### Instalação segura — SOMENTE APÓS O LOTE 2

1. Aguarde `FIM. Sucessos=9, falhas=0` do Lote 2 e confira os logs/saídas.
2. Faça o checkpoint/backup dos resultados do Lote 2 conforme nosso procedimento.
3. Extraia o conteúdo deste ZIP **diretamente na raiz** `D:\pi-analise-notas-enem`. Os novos scripts vêm na pasta **de staging** `pacote_ind055_072/src/indicadores/`, não substituem nada por extração.
4. Verifique a instalação, sem escrever ou executar:

```powershell
python instalar_ind055_072.py --verificar
```

5. Após confirmar, instale somente os novos códigos:

```powershell
python instalar_ind055_072.py --instalar --confirmar-lote2-concluido
```

6. Verifique as dependências de todos os indicadores, **sem executá-los**:

```powershell
python executar_ind055_072.py --verificar
```

7. Futuramente, **somente depois da auditoria dos dados e com o Lote 2 finalizado**, poderá executar sequencialmente o subconjunto independente das pontes:

```powershell
python -u executar_ind055_072.py --executar --confirmar-lote2-concluido --apenas 69,70,64,65,66,67,71,72
```

O comando de execução primeiro gera ZIP em `backups_lote3/`, grava logs em `logs_lote3/`, para no primeiro erro e preserva dashboards existentes. Não há paralelismo. Por padrão **não sobrescreve** saídas previamente geradas; só permite `--sobrescrever` explícito.

Para tentar todos os 18 em uma só fila **após a ponte estar concluída e auditada**:

```powershell
python -u executar_ind055_072.py --executar --confirmar-lote2-concluido
```

Se a ponte ainda não existir, a pré-verificação bloqueia a execução em vez de gerar valores inválidos. O modo `--permitir-pendencias` permite pular indicadores sem pré-requisitos, mantendo um relatório de quais faltam; não use esse modo para apresentar a entrega como completa.

### Validação e limites

Os testes sintéticos cobrem: cálculo das séries 064–067; QA de chaves/missing em 069/070; diagnóstico 071; proveniência 072; uso do contrato da ponte, agregação 055–059, regressão 060–061, permutação 062, auditoria 063 e composição temporal 068.

Para `IND-060/061`: Random Forest 120 árvores, max_depth=16, min_samples_leaf=5, treino/teste 80/20 seed=2026, baseline, validação cruzada 3-fold em subamostra de treinamento. **Treino/teste não usa redação como feature.** `IND-062` implementa importância por **permutação** no holdout; SHAP é um método previsto no catálogo, mas **não é calculado nesta versão**. As saídas permanecem `draft` até revisão metodológica, especialmente após modelagem exploratória.

Para o computador com ~10 GB RAM: processar sequencialmente, usar chunks, não usar `n_jobs` acima de 1; IND-069 pode criar SQLite temporário de grande porte, exigindo espaço em disco.

**Revisão de privacidade:** o projeto decidiu exibir contagens agregadas pequenas. Isso não comprova anonimização por si só. IND-071 registra valores 1–29 e sinaliza revisão contextual, **sem apagá-los**. Essa é uma **adaptação explícita** da regra de supressão do catálogo, documentada para futura avaliação.

Nenhum script integra os JSONs no Streamlit nesta etapa: a publicação visual deve ocorrer somente após a validação das saídas e do contrato da interface.
