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
    // Fiscaliza automaticamente todos os gráficos: coordenadas numéricas
    // precisam de eixos numéricos; códigos/nomes continuam categóricos.
    const eixosNumericosInvalidos = figuras.flatMap((figura, indice) => {
      const dados = Array.isArray(figura.data) ? figura.data : [];
      return ['x', 'y'].flatMap((coordenada) => {
        let temNumeros = false;
        let temCategorias = false;
        for (const trace of dados) {
          const lista = trace?.[coordenada];
          if (!Array.isArray(lista)) continue;
          for (const valor of lista) {
            if (valor === null || valor === undefined) continue;
            if (typeof valor === 'number' && Number.isFinite(valor)) temNumeros = true;
            else temCategorias = true;
          }
        }
        if (!temNumeros || temCategorias) return [];
        const tipo = figura._fullLayout?.[coordenada + 'axis']?.type;
        return tipo === 'linear' || tipo === 'log' ? [] : [{
          grafico: indice + 1, eixo: coordenada, tipoDetectado: tipo ?? 'indefinido',
        }];
      });
    });
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
      eixosNumericosInvalidos,
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
      expect(medidas.eixosNumericosInvalidos, 'números renderizados como categorias nos eixos Plotly').toEqual([]);

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
  const menuMobile = page.locator('.menu-mobile');
  if (await menuMobile.isVisible()) await menuMobile.click();
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
      // Plotly converte autorange: 'reversed' em range decrescente
      // depois do primeiro desenho. Verificar o eixo renderizado, não a opção inicial.
      eixoReverso: Array.isArray(elemento._fullLayout?.yaxis?.range) &&
        elemento._fullLayout.yaxis.range[0] > elemento._fullLayout.yaxis.range[1],
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

test('abertura sem parâmetros apresenta todas as edições e evolução anual', async ({ page }, testInfo) => {
  await page.goto('/visao-geral', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-filtro="ano"]')).toHaveValue('todos');
  await expect(page.locator('[data-filtro="uf"]')).toHaveValue('BR');
  const grafico = page.locator('[data-visual="resumo-evolucao"] .js-plotly-plot');
  await expect(grafico).toBeVisible({ timeout: 40_000 });
  await expect(page.locator('[data-visual="resumo-evolucao"]')).toContainText('média consolidada');
  const serie = await grafico.evaluate((elemento) => {
    const ponto = elemento.data?.[0];
    return { anos: [...(ponto?.x ?? [])].map(String), valores: [...(ponto?.y ?? [])] };
  });
  expect(serie.anos).toContain('2019');
  expect(serie.anos).toContain('2025');
  expect(serie.valores.filter((v) => typeof v === 'number').length).toBeGreaterThan(1);
  const layout = await medirLayout(page);
  expect(layout.excessoHorizontalPx).toBeLessThanOrEqual(4);
  expect(layout.elementosForaDaTela).toEqual([]);
  await testInfo.attach('captura-visao-historica-' + testInfo.project.name, {
    body: await page.screenshot({ fullPage: true, animations: 'disabled' }),
    contentType: 'image/png',
  });
});

test('evolução da abertura respeita a UF selecionada', async ({ page }) => {
  await page.goto('/visao-geral?ano=todos&uf=SP');
  await expect(page.locator('[data-filtro="uf"]')).toHaveValue('SP');
  await expect(page.locator('[data-visual="resumo-evolucao"] .js-plotly-plot')).toBeVisible({ timeout: 40_000 });
  await expect(page.locator('[data-visual="resumo-evolucao"]')).toContainText('Edição do exame');
});

test('guia dos indicadores explica conceitos e cuidados, sem alterar valores', async ({ page }) => {
  await prepararPagina(page, 'visao-geral', '2024', 'BR');
  const guia = page.locator('[data-visual="histograma"] [data-indicador="IND-006"]');
  await expect(guia.locator('summary')).toBeVisible();
  await guia.locator('summary').click();
  await expect(guia).toContainText('O que está sendo medido?');
  await expect(guia).toContainText('Como interpretar?');
  await expect(guia).toContainText('Sugestão pedagógica');
  await expect(guia).toContainText('não demonstram causalidade');
  await expect(guia).toContainText('2024 · Brasil');
});

test('questionário 2024 mostra significado real de alternativa e enunciado', async ({ page }) => {
  await prepararPagina(page, 'socioeconomico', '2024', 'BR');
  await expect(page.getByTestId('enunciado-questionario')).toContainText('Até que série');
  const legenda = page.getByTestId('respostas-questionario');
  await legenda.locator('summary').click();
  await expect(legenda).toContainText('Nunca estudou.');
  await expect(legenda.locator('tbody tr').first()).toContainText('A');
  await expect(legenda.locator('tbody tr').first()).toContainText('Nunca estudou.');
});

test('questionário preserva diferença semântica da pergunta Q006 entre 2023 e 2024', async ({ page }) => {
  await prepararPagina(page, 'socioeconomico', '2023', 'BR');
  await page.locator('[data-visual="perfil"] select').selectOption('Q006');
  await expect(page.getByTestId('enunciado-questionario')).toContainText('Qual é a renda mensal');
  await page.locator('[data-filtro="ano"]').selectOption('2024');
  await expect(page.locator('[data-visual="perfil"] select')).toHaveValue('Q006');
  await expect(page.getByTestId('enunciado-questionario')).toContainText('Você possui renda?');
});

test('questionário no período completo mostra tendência POP_SOCIO sem agregar alternativas', async ({ page }, testInfo) => {
  await prepararPagina(page, 'socioeconomico', 'todos', 'BR');
  const painel = page.locator('[data-visual="serie-questionario"]');
  await expect(painel.locator('.js-plotly-plot')).toBeVisible({ timeout: 40_000 });
  await expect(painel).toContainText('POP_SOCIO');
  await expect(page.getByText('Para consultar as alternativas e seus significados')).toBeVisible();
  const serie = await painel.locator('.js-plotly-plot').evaluate((e) => ({
    anos: Array.from(e.data?.[0]?.x ?? [], String),
    valores: Array.from(e.data?.[0]?.y ?? []),
  }));
  expect(serie.anos).toEqual(['2019', '2020', '2021', '2022', '2023', '2024', '2025']);
  expect(serie.valores.filter((v) => typeof v === 'number').length).toBe(7);
  await expect(painel.locator('[data-indicador="IND-040"]')).toBeVisible();
  const layout = await medirLayout(page);
  expect(layout.excessoHorizontalPx).toBeLessThanOrEqual(4);
  expect(layout.elementosForaDaTela).toEqual([]);
  await testInfo.attach('captura-questionario-historico-' + testInfo.project.name, {
    body: await page.screenshot({ fullPage: true, animations: 'disabled' }),
    contentType: 'image/png',
  });
});

test('eixos percentuais e de notas são lineares e respeitam distâncias reais', async ({ page }) => {
  await prepararPagina(page, 'evolucao', 'todos', 'BR');
  for (const id of ['serie-validas', 'serie-notas', 'serie-desvio', 'serie-mil']) {
    const grafico = page.locator('[data-visual="' + id + '"] .js-plotly-plot');
    await expect(grafico).toBeVisible();
    const resultado = await grafico.evaluate((elemento) => {
      const eixo = elemento._fullLayout?.yaxis;
      const coordenadas = (elemento.data ?? []).flatMap((trace) =>
        Array.from(trace.y ?? []).filter((v) => typeof v === 'number' && Number.isFinite(v))
      );
      return {
        tipo: eixo?.type,
        quantidade: coordenadas.length,
        // Em eixos lineares, a diferença visual entre 60 e 70 equivale
        // à diferença entre 70 e 80. Eixos categóricos falham nessa propriedade.
        distancia60a70: eixo?.l2p ? Math.abs(eixo.l2p(70) - eixo.l2p(60)) : null,
        distancia70a80: eixo?.l2p ? Math.abs(eixo.l2p(80) - eixo.l2p(70)) : null,
      };
    });
    expect(resultado.tipo, id + ': o eixo não pode ser categoria').toBe('linear');
    expect(resultado.quantidade, id + ': série precisa conter números').toBeGreaterThan(0);
    expect(resultado.distancia60a70, id + ': escala deve ser proporcional')
      .toBeCloseTo(resultado.distancia70a80, 3);
  }
});

test('eixo horizontal de respostas continua categórico enquanto percentual é linear', async ({ page }) => {
  await prepararPagina(page, 'socioeconomico', '2024', 'BR');
  const grafico = page.locator('[data-visual="perfil-grafico"] .js-plotly-plot');
  await expect(grafico).toBeVisible();
  const tipos = await grafico.evaluate((elemento) => ({
    eixoCodigos: elemento._fullLayout?.yaxis?.type,
    eixoPercentual: elemento._fullLayout?.xaxis?.type,
  }));
  expect(tipos.eixoCodigos).toBe('category');
  expect(tipos.eixoPercentual).toBe('linear');
});
