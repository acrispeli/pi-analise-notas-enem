# PR #7 — leitura pedagógica e apresentação histórica no React

## Escopo
Esta revisão amplia o painel público sem alterar microdados, fórmulas, indicadores, JSONs originais, arquivos de análise Python nem a metodologia de cálculo.

- O filtro inicial passa a ser **Todos os anos · Brasil**; URLs com `ano` e `uf` continuam preservadas.
- A Visão geral apresenta a média anual no período disponível, com recorte da UF selecionada. Os pontos vêm do JSON temporal ou de `serie-uf.json`, e são exibidos **sem interpolação**. Uma interpretação apresenta os valores primeiro/último disponíveis e ressalta a diferença entre série e consolidado ponderado.
- Gráficos com identificador reconhecido recebem o painel expansível **Entenda este resultado**. Os 68 textos e as ações pedagógicas vêm de `leitura_acessivel_68.py` e `orientacoes_pedagogicas_68.py`; não são inferências automáticas dos valores nem gerados por IA.
- O Questionário usa `docs/dicionario_questoes_enem_2019_2025.json` para apresentar enunciado, legenda completa, quantidades e porcentagens da edição, mantendo os códigos originais no gráfico. Respostas sem correspondência explícita não recebem rótulo inventado.
- A página Questionário também apresenta a evolução da contagem de participações POP_SOCIO quando Todos os anos está selecionado; não concatena categorias de perguntas diferentes. Para ver as alternativas, o visitante escolhe uma edição.

## Origem e sincronização das explicações
`frontend/scripts/gerar-leituras.mjs` é executado por `frontend/scripts/dividir.mjs` no prebuild. Ele gera dentro de `frontend/public/data`:
- `guias-pedagogicos.json`: 68 leituras e ações dos arquivos Python editoriais.
- `dicionario-questoes.json`: respostas originais por edição do dicionário já mantido no repositório.

Esses arquivos são **derivados** e não precisam ser alterados manualmente. O script falha deliberadamente se o número de guias ou a cobertura por ano não estiverem completos.

## Validação automática
O workflow `Auditoria visual React`, em todo PR com alterações em `frontend/**`:
1. Instala dependências e compila TypeScript/Vite via `npm run build`.
2. Executa `scripts/validar-leituras.mjs`, que exige 68 guias completos, os sete questionários e a diferença entre os enunciados de Q006 em 2023 e 2024.
3. Roda Playwright em **375, 768 e 1440 px**, incluindo as capturas das oito seções, erros HTTP/JS, rolagem, menus e gráficos e os testes da abertura histórica e legendas por edição.
4. Publica relatório HTML, capturas e resumo na execução GitHub Actions.

## Limitações
- As interpretações são **didáticas e descritivas**, sem inferência causal ou avaliação individual.
- A mudança de 2024 no significado das alternativas é preservada por edição.
- A interpretação da tendência mostra a diferença entre os primeiros e últimos pontos publicáveis, não uma explicação causal da mudança.
- O benchmark visual pode identificar transbordamentos e textos cortados; não substitui todos os critérios possíveis de acessibilidade perceptiva.
- Os indicadores sem vínculo de guia conhecido ficam sem explicação expandida, mas não recebem interpretação de outra análise.
- A geração de JSON pelo build verifica os dados estáticos; a publicação pelo Cloudflare Pages é uma verificação independente.

## Aceite automatizado
PR pronto apenas quando build, validação editorial e Playwright estiverem verdes. O merge deve ficar separado da revisão de implementação, sem modificar o site oficial antecipadamente.
