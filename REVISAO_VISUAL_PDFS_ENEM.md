# Revisão visual dos sete PDFs — Redação no ENEM

Análise de referência feita em 19/10/2026, sobre os **PDFs da execução anterior** enviados pela equipe (não representam captura da atualização aqui entregue).

| PDF | Observação nas páginas | Correção/decisão |
|---|---|---|
| `Panorama.pdf` (4 páginas) | Cartões com contagens truncadas `20.0...`; gráficos cortados à direita na impressão | Grade de métricas em 2×2, CSS responsivo e impressão A4 horizontal |
| `Panorama2.pdf` (5 páginas) | Contagem de registros aparece truncada; eixo de faixas de notas não cabe na página impressa | Rótulos métricos com quebra de linha, largura responsiva e rotação de rótulos de classes |
| `Panorama3.pdf` (6 páginas) | Barras de competências C4/C5 parcialmente fora da área visível na impressão | Ajustes responsivos de margens, Plotly e CSS de impressão |
| `Panorama4.pdf` (6 páginas) | Mapas de calor mostram parte das cinco colunas; mapa hexagonal IND-016 está presente | Mantidos os cinco eixos; impressão em paisagem; preservado o mapa agregado |
| `Panorama5.pdf` (4 páginas) | Gráficos de clusters deixam C4/C5 e P4 fora da impressão; conteúdo conceitualmente bem explicado | Atualização de impressão/legendas; modelos e interpretação inalterados |
| `Panorama6.pdf` (1 página) | Avaliação entre corretores só possui texto de reserva | Nova página com IND-020/021/022 e série anual |
| `Panorama7.pdf` (16 páginas) | Evolução temporal extensa, eixos cortados ao final dos anos | Cinco abas temáticas, preservando as séries existentes e incluindo os avaliadores |

## Limites

O PDF salva uma fotografia da **versão anterior no navegador** e possui limitações de impressão, especialmente para gráficos Plotly responsivos e componentes interativos. As alterações de CSS foram verificadas sintaticamente e os gráficos foram produzidos em testes simulados com os dados reais de 2024; **não houve inspeção final do HTML no navegador Windows ou nova rodada de PDFs gerados pelo Streamlit** neste ambiente. A equipe deve testar o layout após substituir os arquivos.

Não houve recálculo de indicadores ou modificação de microdados. Para o IND-022, a fórmula aplicada aos anos de 2019–2025 é a versão de 2024, com advertência de comparabilidade normativa.
