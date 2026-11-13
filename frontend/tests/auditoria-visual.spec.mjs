import { test, expect } from '@playwright/test';

const secoes = [
  { rota: 'visao-geral', titulo: 'Visão geral' },
  { rota: 'competencias', titulo: 'Competências' },
  { rota: 'avaliadores', titulo: 'Corretores' },
  { rota: 'alto-desempenho', titulo: 'Notas altas' },
  { rota: 'socioeconomico', titulo: 'Questionário' },
  { rota: 'evolucao', titulo: 'Evolução' },
  { rota: 'metodologia', titulo: 'Método' },
  { rota: 'padroes-ml', titulo: 'Perfis' },
];

async function prepararPagina(page, rota, ano = '2024', uf = 'BR') {
  const errosJavaScript = [];
  const falhasDados = [];
  page.on('pageerror', (erro) => errosJavaScript.push(erro.message));
  page.on('response', (resposta) => {
    if (resposta.status() >= 400 && resposta.url().includes('/data/')) {
      falhasDados.push(resposta.status() + ' ' + resposta.url());
    }
  });
  await page.goto('/' + rota + '?ano=' + ano + '&uf=' + uf, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => Boolean(document.querySelector('main h1') || document.querySelector('.estado.erro')),
    null,
    { timeout: 40_000 },
  );
  // Aguarda JSONs e a renderização inicial do Plotly; sem pressupor
  // que todas as seções possuam gráficos disponíveis em todos os anos.
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(800);
  return { errosJavaScript, falhasDados };
}

async function medirLayout(page) {
  return page.evaluate(() => {
    const largura = window.innerWidth;
    const documento = document.documentElement;
    const visivel = (elemento) => {
      const estilo = getComputedStyle(elemento);
      const r = elemento.getBoundingClientRect();
      return estilo.display !== 'none' && estilo.visibility !== 'hidden' && r.width > 1 && r.height > 1;
    };
    const arredondar = (valor) => Math.round(valor * 10) / 10;
    const larguraTotal = Math.max(documento.scrollWidth, document.body?.scrollWidth ?? 0);
    const foraDaTela = Array.from(document.querySelectorAll(
      'main, .topo, .contexto, .painel, .cartao, .grafico-canvas, .js-plotly-plot, .filtros, .seletor',
    ))
      .filter((elemento) => visivel(elemento))
      .map((elemento) => ({
        tag: elemento.tagName.toLowerCase(),
        classe: String(elemento.className || '').slice(0, 90),
        esquerda: arredondar(elemento.getBoundingClientRect().left),
        direita: arredondar(elemento.getBoundingClientRect().right),
      }))
      .filter((item) => item.esquerda < -5 || item.direita > largura + 5)
      .slice(0, 25);
    const textosCortados = Array.from(document.querySelectorAll(
      'main h1, .painel h2, .cartao strong, .menu-link, .topo-titulo, .metodo summary',
    ))
      .filter((elemento) => visivel(elemento) && elemento.scrollWidth > elemento.clientWidth + 6)
      .map((elemento) => ({
        tag: elemento.tagName.toLowerCase(),
        texto: elemento.textContent?.trim().slice(0, 80),
        excedente: elemento.scrollWidth - elemento.clientWidth,
      }))
      .slice(0, 25);
    const ids = [...document.querySelectorAll('[id]')].map((elemento) => elemento.id);
    const idsDuplicados = [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
    const controlesSemNome = [...document.querySelectorAll('button, select')]
      .filter((elemento) => visivel(elemento))
      .filter((elemento) => {
        if (elemento.getAttribute('aria-label')?.trim()) return false;
        if (elemento.getAttribute('aria-labelledby')) return false;
        if (elemento.tagName === 'BUTTON') return !elemento.textContent?.trim();
        return elemento.labels?.length === 0;
      })
      .map((elemento) => elemento.outerHTML.slice(0, 120))
      .slice(0, 10);
    const figuras = [...document.querySelectorAll('main .js-plotly-plot')].filter(visivel);
    const alturas = figuras.map((e) => arredondar(e.getBoundingClientRect().height));
    return {
      larguraViewport: largura,
      alturaViewport: window.innerHeight,
      alturaPagina: documento.scrollHeight,
      larguraDocumento: larguraTotal,
      excessoHorizontalPx: Math.max(0, larguraTotal - largura),
      elementosForaDaTela: foraDaTela,
      textosPossivelmenteCortados: textosCortados,
      idsDuplicados,
      controlesSemNome,
      titulosH1: document.querySelectorAll('main h1').length,
      graficosPlotly: figuras.length,
      elementosVisuais: document.querySelectorAll('main [data-visual]').length,
      graficosIndisponiveis: document.querySelectorAll('main [data-visual] .indisponivel').length,
      alturaMinimaGrafico: alturas.length ? Math.min(...alturas) : null,
      alturaMaximaGrafico: alturas.length ? Math.max(...alturas) : null,
    };
  });
}

test.describe('Medição visual automatizada de 8 seções × 3 tamanhos de tela', () => {
  for (const { rota, titulo } of secoes) {
    test(rota + ' — medidas, captura e erros de interface', async ({ page }, testInfo) => {
      const { errosJavaScript, falhasDados } = await prepararPagina(page, rota);
      const medidas = await medirLayout(page);
      const captura = testInfo.outputPath(rota + '-' + testInfo.project.name + '.png');

      await page.screenshot({
        path: captura,
        fullPage: true,
        animations: 'disabled',
        caret: 'hide',
        scale: 'css',
      });
      await testInfo.attach('captura-' + rota + '-' + testInfo.project.name, {
        path: captura, contentType: 'image/png',
      });
      await testInfo.attach('metricas-' + rota, {
        body: Buffer.from(JSON.stringify({
          rota, viewport: testInfo.project.name, ...medidas,
          errosJavaScript, falhasDados,
        }, null, 2)),
        contentType: 'application/json',
      });
      if (medidas.textosPossivelmenteCortados.length) {
        testInfo.annotations.push({
          type: 'aviso-visual',
          description: medidas.textosPossivelmenteCortados.length + ' textos possivelmente cortados',
        });
      }
      if (medidas.graficosIndisponiveis) {
        testInfo.annotations.push({
          type: 'cobertura-dos-dados',
          description: medidas.graficosIndisponiveis + ' gráficos sem valores neste recorte',
        });
      }

      await expect(page.locator('main h1')).toHaveText(titulo);
      expect(medidas.excessoHorizontalPx, 'rolagem horizontal global').toBeLessThanOrEqual(4);
      expect(medidas.elementosForaDaTela, 'elementos fora da área útil').toEqual([]);
      expect(medidas.idsDuplicados, 'IDs HTML duplicados').toEqual([]);
      expect(medidas.controlesSemNome, 'controles sem nome acessível').toEqual([]);
      expect(falhasDados, 'erros HTTP ao buscar dados JSON').toEqual([]);
      expect(errosJavaScript, 'erros JavaScript não tratados').toEqual([]);

      // Comparação pixel a pixel opcional, habilitada somente após aprovar e
      // versionar uma linha de base feita no mesmo ambiente de renderização.
      if (process.env.AUDIT_COMPARAR_BASELINE === '1') {
        await expect(page).toHaveScreenshot(rota + '-' + testInfo.project.name + '.png', {
          fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.02,
        });
      }
    });
  }
});

test('filtros permanecem no endereço ao navegar e atualizar', async ({ page }) => {
  await prepararPagina(page, 'visao-geral');
  await page.locator('[data-filtro="ano"]').selectOption('2020');
  await page.locator('[data-filtro="uf"]').selectOption('SP');
  await expect(page).toHaveURL(/ano=2020/);
  await expect(page).toHaveURL(/uf=SP/);
  await page.getByRole('link', { name: 'Competências' }).click();
  await expect(page).toHaveURL(/competencias\?/);
  await page.reload();
  await expect(page.locator('[data-filtro="ano"]')).toHaveValue('2020');
  await expect(page.locator('[data-filtro="uf"]')).toHaveValue('SP');
  await expect(page.locator('main h1')).toHaveText('Competências');
});

test('menu móvel recolhe, abre e permite navegar', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'desktop-1440', 'Menu móvel não aparece no desktop.');
  await prepararPagina(page, 'visao-geral');
  const botao = page.locator('.menu-mobile');
  await expect(botao).toBeVisible();
  await expect(botao).toHaveAttribute('aria-expanded', 'false');
  await botao.click();
  await expect(botao).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByRole('navigation', { name: 'Seções do painel' })).toBeVisible();
  await page.getByRole('link', { name: 'Questionário' }).click();
  await expect(page.locator('main h1')).toHaveText('Questionário');
  await expect(botao).toHaveAttribute('aria-expanded', 'false');
});

test('gráfico ampliado é acessível e fecha com Escape', async ({ page }) => {
  await prepararPagina(page, 'visao-geral');
  const ampliar = page.getByRole('button', { name: /^Ampliar gráfico:/ }).first();
  await expect(ampliar).toBeVisible();
  await ampliar.click();
  const modal = page.getByRole('dialog');
  await expect(modal).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
});

test('ranking de notas por UF mantém maior valor no topo', async ({ page }) => {
  await prepararPagina(page, 'visao-geral', '2024', 'BR');
  const ranking = page.locator('[data-visual="ranking-uf"] .js-plotly-plot');
  await expect(ranking).toBeVisible();
  const resultados = await ranking.evaluate((elemento) => {
    const trace = elemento.data?.[0];
    const notas = Array.from(trace?.x || []).map(Number);
    return {
      orientacao: trace?.orientation,
      ordemDecrescente: notas.every((nota, i) => i === 0 || notas[i - 1] >= nota),
      eixoReverso: elemento._fullLayout?.yaxis?.autorange === 'reversed',
      quantidade: notas.length,
    };
  });
  expect(resultados.orientacao).toBe('h');
  expect(resultados.quantidade).toBeGreaterThan(20);
  expect(resultados.ordemDecrescente).toBe(true);
  expect(resultados.eixoReverso).toBe(true);
});

test('página Método oferece pesquisa por indicador', async ({ page }) => {
  await prepararPagina(page, 'metodologia');
  const busca = page.getByRole('searchbox', { name: /Buscar por indicador/ });
  await expect(busca).toBeVisible();
  await busca.fill('IND-020');
  await expect(page.locator('.metodo')).toHaveCount(1);
  await expect(page.locator('.metodo summary')).toContainText('IND-020');
  await expect(page.locator('.metodo')).toHaveAttribute('open', '');
});