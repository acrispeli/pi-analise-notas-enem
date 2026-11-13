import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const origem = path.join(raiz, 'outputs', 'json');
const destino = path.join(raiz, 'frontend', 'public', 'data');
const anos = [2019, 2020, 2021, 2022, 2023, 2024, 2025];
const paginas = [
  'overview',
  'competencies',
  'evaluators',
  'high_performance',
  'socioeconomic',
  'ml',
  'methodology',
];

function estavel(valor) {
  if (Array.isArray(valor)) return valor.map(estavel);
  if (valor && typeof valor === 'object') {
    const saida = {};
    for (const chave of Object.keys(valor).sort()) saida[chave] = estavel(valor[chave]);
    return saida;
  }
  return valor;
}

function hash(valor) {
  return crypto.createHash('sha256').update(JSON.stringify(estavel(valor))).digest('hex');
}

function lerDashboard(ano) {
  const arquivo = path.join(origem, `dashboard_enem_${ano}.json`);
  return JSON.parse(fs.readFileSync(arquivo, 'utf8'));
}

function copiar(obj, chaves) {
  const saida = {};
  for (const chave of chaves) {
    if (obj && Object.prototype.hasOwnProperty.call(obj, chave)) saida[chave] = obj[chave];
  }
  return saida;
}

const dashboards = new Map();
for (const ano of anos) dashboards.set(ano, lerDashboard(ano));

const hashesTemporal = new Map();
for (const [ano, doc] of dashboards) hashesTemporal.set(ano, hash(doc.pages.temporal));
const unicos = new Set(hashesTemporal.values());
if (unicos.size !== 1) {
  console.error('pages.temporal difere entre os anos:', [...hashesTemporal.entries()]);
  process.exit(1);
}

fs.rmSync(destino, { recursive: true, force: true });
fs.mkdirSync(destino, { recursive: true });

const serie = {};
for (const ano of anos) {
  const doc = dashboards.get(ano);
  const dir = path.join(destino, String(ano));
  fs.mkdirSync(dir, { recursive: true });
  for (const pagina of paginas) {
    if (!(pagina in doc.pages)) {
      console.error(`${ano} sem pages.${pagina}`);
      process.exit(1);
    }
    fs.writeFileSync(path.join(dir, `${pagina}.json`), JSON.stringify(doc.pages[pagina]));
  }
  fs.writeFileSync(
    path.join(dir, 'meta.json'),
    JSON.stringify({ meta: doc.meta, filters: doc.filters, quality: doc.quality }),
  );

  const visao = doc.pages.overview;
  const por001 = new Map(visao.ind001.by_uf.map((item) => [item.uf, item]));
  const por002 = new Map(visao.ind002.by_uf.map((item) => [item.uf, item]));
  const por003 = new Map(visao.ind003.by_uf.map((item) => [item.uf, item]));
  const por004 = new Map(visao.ind004.by_uf.map((item) => [item.uf, item]));
  const por005 = new Map(visao.ind005.by_uf.map((item) => [item.uf, item]));
  const por008 = new Map(visao.ind008.by_uf.map((item) => [item.uf, item]));
  for (const uf of por001.keys()) {
    if (!serie[uf]) serie[uf] = [];
    serie[uf].push({
      year: ano,
      ind001: copiar(por001.get(uf), ['redacoes_validas', 'total_registros', 'percentual_validas']),
      ind002: copiar(por002.get(uf), ['n', 'mean_score']),
      ind003: copiar(por003.get(uf), ['n', 'median_score']),
      ind004: copiar(por004.get(uf), ['n', 'std_score']),
      ind005: copiar(por005.get(uf), ['n', 'percentiles']),
      ind008: copiar(por008.get(uf), ['n', 'perfect_scores', 'percentage', 'privacy_review_required']),
    });
  }
}

fs.writeFileSync(
  path.join(destino, 'temporal.json'),
  JSON.stringify(dashboards.get(2024).pages.temporal),
);
fs.writeFileSync(
  path.join(destino, 'serie-uf.json'),
  JSON.stringify({
    descricao:
      'Cópia dos recortes por UF já publicados em cada dashboard anual. Não há média nem recálculo.',
    ufs: serie,
  }),
);

const extraDir = path.join(destino, 'extra');
fs.mkdirSync(extraDir, { recursive: true });

function indicadorPublicado(nome) {
  const arquivo = path.join(origem, nome);
  if (!fs.existsSync(arquivo)) {
    console.error('indicador ausente:', nome);
    process.exit(1);
  }
  const doc = JSON.parse(fs.readFileSync(arquivo, 'utf8'));
  return {
    indicator_id: doc.indicator_id,
    status: doc.status,
    review: doc.review,
    results: doc.results,
  };
}

fs.writeFileSync(
  path.join(extraDir, 'evolucao.json'),
  JSON.stringify({
    competencias: indicadorPublicado('IND_065_evolucao_competencias.json'),
    quase: indicadorPublicado('IND_066_evolucao_quase_1000.json'),
    divergencia: indicadorPublicado('IND_067_evolucao_divergencias.json'),
    perfis: indicadorPublicado('IND_068_evolucao_perfis_socioeconomicos.json'),
  }),
);
fs.writeFileSync(
  path.join(extraDir, 'perfis.json'),
  JSON.stringify({
    nota: indicadorPublicado('IND_055_perfil_socio_nota.json'),
    competencias: indicadorPublicado('IND_056_perfil_socio_competencias.json'),
    alto: indicadorPublicado('IND_057_perfil_socio_alto_desempenho.json'),
    perdas: indicadorPublicado('IND_058_perfil_socio_perdas.json'),
    divergencia: indicadorPublicado('IND_059_perfil_socio_divergencia.json'),
  }),
);

const doc2024 = dashboards.get(2024);
const doc2025 = dashboards.get(2025);
const chaves2025 = Object.keys(doc2025.pages.socioeconomic);
const limiares = [...dashboards.values()].map((doc) => doc.quality.suppression.min_group_n);
const relatorio = {
  temporal_igual: true,
  temporal_hash: [...unicos][0],
  anos,
  paginas_por_ano: paginas.concat(['meta.json']),
  serie_uf: Object.keys(serie).length,
  anos_por_uf_ac: serie.AC?.length ?? 0,
  socio_2025: chaves2025,
  ml_2024: doc2024.pages.ml.status,
  avaliadores_2024: doc2024.pages.evaluators.status,
  alto_desempenho_2024: doc2024.pages.high_performance.status,
  limiar_minimo: limiares,
  filtros: doc2024.filters.available.year,
  ufs: doc2024.filters.available.uf_exam.length,
};

const esperado =
  relatorio.serie_uf === 27 &&
  relatorio.anos_por_uf_ac === 7 &&
  chaves2025.includes('profile') &&
  !chaves2025.includes('income_total') &&
  doc2024.pages.ml.reason === 'indicadores_ainda_nao_implementados' &&
  limiares.every((n) => n === 30) &&
  doc2024.filters.available.uf_exam.length === 28;

if (!esperado) {
  console.error(JSON.stringify(relatorio, null, 2));
  process.exit(1);
}

console.log(JSON.stringify(relatorio, null, 2));
