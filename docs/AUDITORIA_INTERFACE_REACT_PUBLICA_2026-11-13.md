# Auditoria da interface React pública — ENEM / UNIVESP

**Data:** 13/11/2026. **Base do código:** main após PR #5 (merge 2cceba0).  
**Site:** https://enem-redacao-univesp-pi4.pages.dev/

## Método e limites

Leitura do código React/Vite, CSS, das oito páginas e dos componentes Plotly na versão atual do GitHub, além da estrutura de geração dos arquivos JSON. O usuário confirmou a publicação e a aprovação do build anterior. A tentativa de acesso automático ao domínio nesta sessão falhou; **não houve teste de navegação visual interativa do site no ar**. A nova branch ainda requer compilação, revisão visual e prévia no Cloudflare. Dados e regras originais não foram recalculados.

## Achados e correções propostas

| Severidade | Área | Evidência no código original | Correção |
|---|---|---|---|
| Alta | Ranking por UF | Dados decrescentes em barras horizontais, sem eixo Y invertido; maior valor na posição inferior | Inverter eixo categórico vertical, preservando a escala de 0 a 1.000 |
| Alta | Histograma | Uma única faixa ausente fazia o gráfico inteiro desaparecer | Manter faixas válidas e representar dados ausentes por ausência de barra |
| Alta | Questionário | Renda identificada por códigos e escolaridade com descrições longas inclinadas | Barras horizontais, rótulos abreviados e detalhes completos ao passar o cursor |
| Alta | Dispositivos móveis | Menu de oito itens sem recolhimento e layout com espaço limitado | Menu retrátil, painéis de coluna única, filtros responsivos |
| Média | Gráficos | Ferramentas de exploração ocultas; leitura difícil de gráficos densos | Ampliar gráfico, zoom e exportação de imagem |
| Média | Método | Muitos indicadores em sequência extensa | Campo de busca e painéis expansíveis |
| Média | Perfis/2024 | Modelos indisponíveis geravam vários gráficos vazios | Mensagem específica, mantendo indicadores complementares |
| Média | Identidade visual | Hierarquia discreta dos cartões, filtros e notas | Reformulação visual consistente, maior contraste e foco de teclado |
| Média | Compartilhamento | Falta de botão para compartilhar recorte | Cópia do link contendo os filtros de ano e UF |
| Baixa | Rotas | Endereços inválidos sem mensagem adequada | Página não encontrada com retorno |
| Baixa | Compartilhamento social | Metadados HTML mínimos | Título e descrição do projeto |

## Revisão das oito seções

- **Visão geral:** ranking e histograma corrigidos; comparar magnitudes com o JSON original.
- **Competências:** médias, níveis, correlações, PCA e perfis mantêm medidas originais; testar legenda e mapa em celular.
- **Corretores:** testar histogramas, Kappa, ICC e recortes parciais; sem mudança estatística.
- **Notas altas:** testar gráficos densos e grupos suprimidos na fonte; sem alterar fórmula.
- **Questionário:** verificar descrições e ordem das faixas de renda e escolaridade.
- **Evolução:** validar 2019–2025, lacunas e filtros; não transformar ausência em zero.
- **Método:** pesquisa de indicador, detalhes expansíveis e terminologia original mantida.
- **Perfis:** mensagem clara quando IND-053/054 estão indisponíveis; resultados complementares mantidos.

## Pendências fora deste PR

1. **Desempenho:** pacote Plotly completo gera aproximadamente 4,65 MB de JavaScript; estudar bundle parcial com suporte aos tipos de gráfico existentes.
2. **Acessibilidade:** oferecer equivalentes tabulares a gráficos densos e executar testes com leitor de tela e teclado.
3. **Correção quantitativa:** criar testes automatizados que comparem escalas e valores dos gráficos com os JSONs.
4. **Privacidade:** aceitar rascunhos e pequenas contagens não equivale a afirmar que os JSONs públicos passaram por auditoria de reidentificação.
5. **Validação acadêmica:** status draft e partial podem ser apresentados com ressalvas, sem significar validação final.
6. **Produção:** capturar telas e conferir o site publicado após merge.

## Testes de aceitação obrigatórios

1. Executar npm run build na branch deste PR e verificar TypeScript e Vite sem erros.
2. Em 2024/Brasil/Visão geral, conferir maior média no **topo** do ranking; na fonte de referência anterior MG tinha cerca de 686,0 e AM cerca de 593,2. Comparar com o JSON efetivamente publicado.
3. Em histograma com lacuna, preservar as demais barras e não inventar zero.
4. Em Questionário, comparar as faixas de renda e escolaridade com a fonte e testar no Brasil e em duas UFs.
5. Em Perfis/2024, eliminar sequência de gráficos vazios quando os modelos são indisponíveis; exibir resultados complementares se existentes.
6. Em Competências/2024, PC1 deve ser a maior barra da variância explicada, e os eixos devem exibir unidades coerentes.
7. Em Evolução, a taxa de redações válidas deve apresentar queda em 2020; nunca tendência artificialmente crescente.
8. Testar páginas em telas de **375 px, 768 px e 1440 px**; abrir e fechar gráficos ampliados com botão e Escape.
9. Acessar /competencias?ano=2024&uf=BR diretamente, atualizar e confirmar a persistência dos filtros.
10. Em Método, pesquisar IND-020, ler conteúdo expandido e limpar filtro.
11. Confirmar que o Cloudflare continua publicando os 60 JSONs, sem erros.
12. Comparar uma prévia do PR com o site atual antes de aprovar o merge.

**Decisão:** não realizar merge automático nesta etapa. A versão anterior continua publicada até validação da revisão.
