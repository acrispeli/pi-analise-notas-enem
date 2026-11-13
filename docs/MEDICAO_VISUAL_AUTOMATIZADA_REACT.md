# Medição visual automatizada — frontend React

## Objetivo

Validar de forma **reproduzível**, em navegador Chromium, a interface React pública do Projeto Integrador IV — UNIVESP, sem depender apenas de observação manual.

O fluxo foi incluído no **PR #6** e **não altera cálculos nem JSONs originais**.

## Dimensões e cobertura

| Perfil | Resolução | Seções | Capturas por execução |
|---|---|---|---|
| Celular | 375 × 812 | 8 | 8 |
| Tablet | 768 × 1024 | 8 | 8 |
| Desktop | 1440 × 900 | 8 | 8 |
| **Total** | 3 perfis | **24 cenários** | **24 PNGs** |

Seções: Visão geral, Competências, Corretores, Notas altas, Questionário, Evolução, Método e Perfis.

Também são verificados os filtros de ano/UF, a persistência dos parâmetros da URL, abertura e fechamento do menu móvel, ampliação de gráfico com tecla Escape, posição do ranking por UF e pesquisa na página Método.

## Indicadores medidos automaticamente

- Excesso horizontal global da página em pixels (limite de tolerância: **4 px**).
- Elementos principais que ultrapassem a largura visível da janela (tolerância: **5 px**).
- Elementos HTML com identificadores duplicados.
- Botões/seletores sem nome acessível.
- Erros JavaScript não tratados.
- Requisições de dados JSON com resposta HTTP de erro.
- Quantidade de gráficos Plotly efetivamente renderizados.
- Quantidade de resultados declarados indisponíveis (informação descritiva; não é falha automática).
- Texto potencialmente truncado em títulos, cartões e navegação (aviso para inspeção).
- Altura da página e dimensões dos gráficos.

**Critério de aprovação:** os testes de falhas de carregamento, navegação, elementos fora da viewport, controle e ranking devem passar. Avisos de corte de texto requerem avaliação do screenshot. A presença de indicador draft ou partial não é falha.

## Relatórios

Cada execução gera:
- **Capturas PNG** completas das 24 telas.
- **Relatório HTML Playwright**, com detalhes de cada teste, erros e anexos visuais.
- **JSON Playwright** com métricas das verificações.
- **Resumo na aba GitHub Actions** por tamanho de tela.
- **Trace Playwright** das falhas para reprodução.

Os artefatos ficam em frontend/auditoria-visual/ e são ignorados pelo Git. Em GitHub Actions, ficam disponíveis na página da execução, na seção **Artifacts**; a retenção configurada é de 14 dias.

## Executar no computador Windows

Abra PowerShell com o projeto já na branch de revisão:

    cd D:\pi-analise-notas-enem\frontend
    npm ci
    npm install --no-save @playwright/test@1.65.0
    npx playwright install chromium
    npm run build
    npm run audit:visual

O comando npm install --no-save instala somente a dependência de auditoria local e não precisa ser enviado ao GitHub. Pode ser repetido após executar npm ci.

Para abrir o relatório HTML gerado:

    npx playwright show-report auditoria-visual/relatorio-html

Também é possível auditar o site publicado ou a URL de prévia do PR usando o PowerShell:

    $env:AUDIT_BASE_URL = "https://enem-redacao-univesp-pi4.pages.dev"
    npm run audit:visual
    Remove-Item Env:AUDIT_BASE_URL

**Atenção:** sem a variável AUDIT_BASE_URL, o Playwright sobe uma prévia do build local na porta 4173. Com a variável definida, ele mede **somente** o site remoto e não inicia o Vite.

## Executar no GitHub

- O workflow está em .github/workflows/auditoria-visual.yml.
- É executado em Pull Requests destinados à main quando frontend ou o próprio workflow são modificados.
- Pode ser executado manualmente pela aba Actions (workflow_dispatch), depois que o arquivo do workflow estiver disponível para seleção no GitHub.
- O job executa npm ci, instala Playwright e Chromium, roda npm run build e os testes.
- Ao terminar, baixe o artefato auditoria-visual-react-N para analisar capturas e relatórios.

## Comparação pixel a pixel com linha de base

O Playwright suporta comparação automática entre um screenshot e uma imagem de referência (toHaveScreenshot). A comparação **não está ativa por padrão**, para evitar reprovações por mudanças visuais intencionais e por diferenças entre máquinas.

Depois de revisar e aprovar visualmente os screenshots **no mesmo ambiente de teste**, gere as referências:

    npx playwright test --config playwright.visual.config.mjs --update-snapshots

Versione as referências em frontend/tests/auditoria-visual.spec.mjs-snapshots (ou no caminho gerado pelo Playwright). Só depois habilite:

    $env:AUDIT_COMPARAR_BASELINE = "1"
    npm run audit:visual
    Remove-Item Env:AUDIT_COMPARAR_BASELINE

A tolerância configurada é maxDiffPixelRatio = 0.02 (2% de pixels diferentes). Isso **não é uma medida de qualidade dos dados**; é uma detecção de alteração visual não esperada. Atualize referências somente quando a alteração for validada pela equipe.

## Limitações

1. Capturas e medidas DOM não substituem inspeção de acessibilidade com tecnologias assistivas ou verificação de correspondência de todos os valores com os dados.
2. A auditoria executa cenários de 2024/Brasil em todos os 24 testes visuais; há interações adicionais com 2020 e SP. Uma futura suíte de dados deverá cobrir a matriz de 2019 a 2025 × 27 UFs, sem realizar milhares de screenshots.
3. Alguns indicadores e gráficos estão legitimamente indisponíveis ou parciais em determinados recortes; a ausência não é transformada em zero.
4. Para comparar versões em produção e prévia, execute a mesma suíte com AUDIT_BASE_URL apontando para cada endereço e compare os respectivos relatórios.
5. O site externo publicado e a versão do PR não foram visualmente medidos por esta conversa até que o primeiro relatório do Playwright seja concluído.

**Não realizar merge do PR #6 apenas porque o código dos testes foi adicionado.** Conferir a primeira execução do workflow e os screenshots antes da publicação.

## Diagnóstico da implantação Cloudflare Pages (13/11/2026)

O commit `d9c881b` passou no build do Vite e publicou 73 ativos estáticos, mas a implantação de prévia terminou com a mensagem do serviço: `Failed to publish your Function. Got error: Unknown internal error occurred.` A opção `Retry deployment` no painel também retornou um erro interno, sem iniciar uma implantação completa.

Trata-se de uma falha **posterior ao build**; por isso, não é evidência de erro de TypeScript, Vite, JSON ou Playwright. O projeto não possui pasta `frontend/functions/` e o log informa `No functions dir at /functions found`. Um novo commit de documentação nesta branch pode solicitar outra implantação pelo GitHub integrado ao Cloudflare Pages, mantendo a `main` intacta.

Se persistir, conferir o status da verificação Cloudflare Pages e contatar o suporte informando o projeto `enem-redacao-univesp-pi4`, o identificador da implantação `7515b8da-0c1b-4040-a656-644d62f7107e` e a mensagem final de erro. Não criar Pages Functions nem alterar o build para contornar uma falha interna ainda não diagnosticada.
