# Protocolo de divulgação dos perfis materiais V2 (IND-055–059 e IND-068)

**Decisões editoriais:** apresentação pública autorizada pelo responsável em 13/11/2026 e retirada da supressão automática de contagens inferiores a 30 na mesma data.  
**Escopo:** gráficos e tabelas agregados dos seis indicadores M1–M3 no Streamlit público.  
**Limites:** não configura certificação acadêmica externa, auditoria integral de privacidade nem autorização de divulgação de microdados identificáveis.

## Indicadores e origem

Os IND-055–059 e IND-068 permanecem entre os 68 indicadores do projeto. O modelo de referência é `V2_MCA10_KMeans3_e31f55489e16f296`; ele não é equivalente ao agrupamento original do IND-054.

Os três perfis M1–M3 descrevem **amostras**, não classes sociais oficiais, distribuição censitária ou diagnósticos individuais. Para 2025, o IND-068 tem composição dos perfis, mas os indicadores 055–059 não possuem ligação de notas validada; ausências permanecem ausências.

## Regra de divulgação atual

- A função `preparar_doc_publico_v2` exige `publicacao_autorizada: true` e a versão V2 correta. Não altera os JSONs estatísticos e não fabrica dados.
- **Não ocorre supressão automática pelo número de registros da célula** nos seis indicadores V2. Resultados de grupos pequenos são apresentados quando a métrica está definida.
- Para o IND-057 foram encontrados **6 de 18 registros aplicáveis** com alguma contagem inferior a 30; para o IND-058, **34 de 90**. Esses 40 registros deixam de ser omitidos por tamanho. O limite de 30 passa a funcionar como **aviso sobre estabilidade estatística**, não como restrição de visibilidade.
- Quando não há denominador suficiente para calcular uma métrica, o valor segue como **ausente** (`null`) e não é apresentado como zero. Exemplo: grupos do IND-058 com `n_near_cluster = 0`.
- O Streamlit mostra um aviso quando algum grupo tem contagem pequena. Isso é relevante para a interpretação dos percentuais e médias.
- As duas rotas de visualização, `painel_paginas_contrato_68.py` e `painel_catalogo_68.py`, usam o mesmo preparo dos dados.
- A autorização editorial é registrada nos JSONs e no histórico Git; não pressupõe validação científica independente.

## Avaliação de risco e apresentação

A retirada da regra de supressão atende à decisão do responsável pelo projeto. Expor contagens pequenas aumenta a granularidade da informação pública e pode tornar mais frágeis as estimativas e a privacidade contextual. Os arquivos inspecionados apresentam dados agregados por edição e perfil, sem campos diretos de identificação nas linhas examinadas. Isso **não comprova ausência de risco de inferência**. Evite acrescentar campos pessoais ou disponibilizar microdados em downloads públicos.

## Verificação antes de divulgar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_publicacao_segura_v2.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe .\auditar_streamlit_entrega.py
```

Visualmente, conferir os seis indicadores em “Todos os anos”, 2024, 2025 e com uma UF selecionada, preservando a informação de ausência de cruzamentos não calculados.

**Controle de versão:** alterações limitadas à branch `fix/qualidade-visual-streamlit` até a decisão sobre integração com `main`.
