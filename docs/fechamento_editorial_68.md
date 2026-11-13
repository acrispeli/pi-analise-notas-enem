# Fechamento editorial dos 68 indicadores — Streamlit

**Data:** 13 de novembro de 2026.  
**Decisão registrada:** o responsável pelo projeto autorizou consolidar a apresentação pública dos 68 indicadores e remover rótulos antigos de *draft* e mensagens administrativas de pendência documental do catálogo.

## O que significa o estado consolidado

O valor `consolidado_para_apresentacao` representa **uma decisão editorial do projeto** e não uma certificação científica independente. A mudança não recalcula estatísticas nem altera populações, unidades, filtros, notas ou séries. As versões anteriores permanecem disponíveis no histórico Git, caso seja necessário conferir a origem de cada resultado.

O `publicacao_autorizada: true` dos seis indicadores M1–M3 (IND-055–059/068) permanece. A supressão das células pequenas dos IND-057/058 não deve ser desativada.

## Alterações preparadas na branch

- `docs/catalogo_navegacao_68.json`: avisos de “confirmar antes de publicar” e outras tarefas administrativas foram substituídos por ressalvas metodológicas concretas. O catálogo permanece com **68 IDs e 8 páginas**.
- `finalizar_metadados_editoriais_68.py`: rotina **local** para atualizar arquivos grandes sem reformatá-los. Substitui os valores de `status` e `data_status` declarados como `draft`/`rascunho` por `consolidado_para_apresentacao`; substitui o marcador específico de `review` de revisão pendente por `aprovacao_editorial_pelo_responsavel`. Altera somente esses valores, inclusive em linhas de resultados quando aparecem, deixando `nao_aplicavel` intacto.
- `auditar_streamlit_entrega.py`: relatório não confunde mais a palavra “independentes” com “pendente”.
- A interface e os avisos metodológicos não declaram homologação acadêmica externa.

## Aplicação dos metadados grandes no computador

A mudança dos grandes arquivos de indicadores **ainda depende de executar a rotina local**. Execute na branch `fix/qualidade-visual-streamlit`, nunca na `main`:

```powershell
cd D:\pi-analise-notas-enem
git pull --ff-only origin fix/qualidade-visual-streamlit
.\.venv\Scripts\python.exe .\finalizar_metadados_editoriais_68.py
.\.venv\Scripts\python.exe .\finalizar_metadados_editoriais_68.py --aplicar
.\.venv\Scripts\python.exe .\finalizar_metadados_editoriais_68.py --verificar
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe .\auditar_streamlit_entrega.py
```

Se os testes e a auditoria terminarem sem erros, conferir as alterações locais com `git status --short` e `git diff --stat`; preparar apenas os JSONs alterados pela rotina e realizar commit/push na branch de Streamlit.

## Cuidados que permanecem

Os IND-064–067 continuam apresentando séries temporais sobre edições independentes; o IND-067 deve manter a distinção entre critérios retroativos de 2024 e decisões históricas. IND-069–071 são informações de qualidade e metodologia e continuam no catálogo, sem destaque adicional.

A divulgação pública mantém ressalvas de não causalidade, limitações de amostragem, não equivalência entre perguntas ou editais de diferentes edições, ausência de vínculo de notas em 2025 para M1–M3 e proteção de contagens pequenas. A ausência de um dado não deve ser interpretada como zero. A autorização editorial não elimina essas limitações.
