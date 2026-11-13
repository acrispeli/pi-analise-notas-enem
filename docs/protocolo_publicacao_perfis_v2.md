# Protocolo de divulgação dos perfis materiais V2 (IND-055–059 e IND-068)

**Decisão:** autorização de apresentação pelo responsável pelo Projeto Integrador IV em 13/11/2026.  
**Escopo:** somente gráficos e tabelas agregados na interface pública Streamlit, com supressão de células pequenas.  
**Não é:** revisão acadêmica formal concluída, auditoria exaustiva de risco de reidentificação, publicação irrestrita dos JSONs ou autorização de divulgação de microdados.

## Indicadores

Os seis indicadores permanecem no catálogo final de 68: IND-055, IND-056, IND-057, IND-058, IND-059 e IND-068. O modelo fixo de referência é `V2_MCA10_KMeans3_e31f55489e16f296`. Não comparar os grupos materiais M1–M3 com o IND-054 (agrupamento original).

O modelo descreve **amostras**, não classes sociais oficiais nem estimativas censitárias. Para 2025, o IND-068 apresenta perfis da amostra, mas os indicadores de desempenho 055–059 não possuem vínculo individual validado com as notas e não devem preencher resultados ausentes.

## Restrições preservadas na publicação

- Os dados originais permanecem nos JSONs para rastreabilidade. A interface pública constrói uma cópia filtrada **antes** de gerar gráficos, tabelas ou resumos pedagógicos.
- A função `preparar_doc_publico_v2` exige `publicacao_autorizada: true` e o modelo V2 correto; caso contrário, o resultado não é exibido.
- São omitidos registros com **qualquer contagem `n` ou `n_*` abaixo de 30**, inclusive contagens iguais a zero. Na análise condicional dos IND-057/058, o critério considera explicitamente tanto denominadores quanto numeradores.
- Na verificação dos JSONs de 13/11/2026, o IND-057 possui **6 de 18 registros aplicáveis** com contagens pequenas; o IND-058 possui **34 de 90**. Nos campos de contagem examinados dos IND-055/056/059/068, não foram encontradas células abaixo de 30.
- **Não se substitui dado ausente por zero** e não se recalculam médias, medianas ou percentuais a partir das linhas omitidas.
- A proteção é aplicada tanto em `painel_paginas_contrato_68.py` quanto em `painel_catalogo_68.py`. Os gráficos podem apresentar lacunas ou não ter todos os perfis/competências em determinado recorte.
- O aviso na interface distingue a autorização editorial **com ressalvas** da **revisão acadêmica formal ainda pendente**.

## Verificações e pendências

A inspeção do conteúdo dos seis JSONs e a aplicação de uma regra de supressão simples **não garantem anonimização completa**, não avaliam todas as possibilidades de inferência por comparação entre tabelas e não substituem revisão de especialistas. Devem ser evitadas rotas públicas de download dos arquivos completos sem sanitização.

Antes de colocar o link público em circulação, executar:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_publicacao_segura_v2.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe .\auditar_streamlit_entrega.py
```

Também é necessário inspecionar na interface os IND-055, 056, 057, 058, 059 e 068 em **Todos os anos**, em **2024**, em **2025** e em uma **UF**. O link público não deve expor os CSVs/JSONs originais com contagens suprimidas pela interface.

**Controle de versão:** alterações apenas na branch `fix/qualidade-visual-streamlit`, sem alterar `main`.
