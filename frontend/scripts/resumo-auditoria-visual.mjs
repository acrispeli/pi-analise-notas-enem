import fs from 'node:fs';
import path from 'node:path';

const arquivo = path.resolve('auditoria-visual/resultados.json');
if (!fs.existsSync(arquivo)) {
  console.log('## Auditoria visual\n\nRelatório ainda não disponível: o build ou a instalação dos testes falhou antes da medição.');
  process.exit(0);
}

const relatorio = JSON.parse(fs.readFileSync(arquivo, 'utf8'));
const linhas = [];
function extrair(grupos) {
  for (const grupo of grupos ?? []) {
    for (const especificacao of grupo.specs ?? []) {
      for (const teste of especificacao.tests ?? []) {
        const resultado = teste.results?.at(-1);
        const metricas = resultado?.attachments
          ?.filter((anexo) => anexo.name?.startsWith('metricas-') && anexo.body)
          .map((anexo) => {
            try { return JSON.parse(Buffer.from(anexo.body, 'base64').toString('utf8')); }
            catch { return null; }
          })
          .find(Boolean);
        linhas.push({
          nome: especificacao.title,
          projeto: teste.projectName ?? 'desconhecido',
          status: teste.status ?? resultado?.status ?? 'desconhecido',
          metricas,
        });
      }
    }
    extrair(grupo.suites);
  }
}
extrair(relatorio.suites);

const estatisticas = relatorio.stats ?? {};
console.log('## Auditoria visual automatizada — ENEM / UNIVESP');
console.log('');
console.log('Relatório: Playwright com capturas integrais nas oito páginas e três tamanhos de tela.');
console.log('');
console.log('| Indicador | Quantidade |');
console.log('|---|---:|');
console.log('| Testes esperados | ' + (estatisticas.expected ?? '—') + ' |');
console.log('| Testes falhos | ' + (estatisticas.unexpected ?? '—') + ' |');
console.log('| Testes ignorados | ' + (estatisticas.skipped ?? '—') + ' |');
console.log('| Testes instáveis | ' + (estatisticas.flaky ?? '—') + ' |');

const medidas = linhas.filter((item) => item.metricas);
if (medidas.length) {
  console.log('');
  console.log('### Indicadores do layout');
  console.log('');
  console.log('| Tela | Cenários medidos | Maior excesso horizontal | Páginas com texto possivelmente cortado |');
  console.log('|---|---:|---:|---:|');
  for (const projeto of ['celular-375', 'tablet-768', 'desktop-1440']) {
    const conjunto = medidas.filter((item) => item.projeto === projeto);
    const excesso = Math.max(0, ...conjunto.map((item) => item.metricas.excessoHorizontalPx ?? 0));
    const texto = conjunto.filter((item) => item.metricas.textosPossivelmenteCortados?.length > 0).length;
    console.log('| ' + projeto + ' | ' + conjunto.length + ' | ' + excesso + ' px | ' + texto + ' |');
  }
  console.log('');
  console.log('Valores ausentes em gráficos são registrados como cobertura parcial, não como erro automático.');
}

const falhos = linhas.filter((item) => !['expected', 'skipped', 'passed'].includes(item.status));
if (falhos.length) {
  console.log('');
  console.log('### Testes que precisam de atenção');
  for (const teste of falhos.slice(0, 25)) {
    console.log('- ' + teste.projeto + ': ' + teste.nome + ' (' + teste.status + ')');
  }
}
console.log('');
console.log('Consulte o artefato da execução para obter screenshots PNG, relatório HTML, JSON e traces de erros.');
