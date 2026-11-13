import { Grafico, barra, type Figura } from '../grafico.tsx';
import { Cartao, Estado, Aviso } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { formatarInteiro, formatarNota, formatarPercentual, numero } from '../lib/formatar.ts';
import { contagemPublicavel, metricaPublicavel, porUf } from '../lib/supressao.ts';
import { nomeUf } from '../lib/ufs.ts';

type Percentis = { p25?: number; p50?: number; p75?: number; p90?: number; p95?: number };
type Bin = { faixa?: string; quantidade?: number; requires_privacy_review?: boolean; requer_revisao_privacidade?: boolean };
type Categoria = { rotulo?: string; quantidade?: number; requer_revisao_privacidade?: boolean; requires_privacy_review?: boolean };
type UfNota = { uf: string; n?: number; mean_score?: number };

type Overview = {
  kpis: {
    valid_essays?: number;
    mean_score?: number;
    median_score?: number;
    std_score?: number;
    percentiles?: Percentis;
    perfect_scores?: { count?: number; n_valid?: number };
  };
  ind001: { national_percentage?: number; by_uf: { uf: string; redacoes_validas?: number; percentual_validas?: number }[] };
  ind002: { n?: number; mean_score?: number; by_uf: UfNota[] };
  ind003: { n?: number; median_score?: number; by_uf: { uf: string; n?: number; median_score?: number }[] };
  ind004: { n?: number; std_score?: number; by_uf: { uf: string; n?: number; std_score?: number }[] };
  ind005: { n?: number; percentiles?: Percentis; by_uf: { uf: string; n?: number; percentiles?: Percentis }[] };
  ind008: { n?: number; perfect_scores?: number; by_uf: { uf: string; n?: number; perfect_scores?: number; privacy_review_required?: boolean }[] };
  score_distribution: { n?: number; bins?: Bin[]; by_uf: { uf: string; n?: number; bins?: Bin[] }[] };
  essay_status: { n?: number; population?: string; categories?: Categoria[]; by_uf: { uf: string; n?: number; categories?: Categoria[] }[] };
};

type BlocoPeriodo<T> = { period_total?: T; period_by_uf?: (T & { uf: string })[] };
type PontoHistorico = { year: number; mean_score?: number; n?: number };
type SerieUF = { ufs?: Record<string, { year: number; ind002?: { mean_score?: number; n?: number } }[]> };
type Temporal = {
  period_total?: { redacoes_validas?: number; percentual_validas?: number };
  period_by_uf?: { uf: string; redacoes_validas?: number; percentual_validas?: number }[];
  ind002: BlocoPeriodo<{ n?: number; mean_score?: number }> & { national_by_year?: PontoHistorico[] };
  ind003: BlocoPeriodo<{ n?: number; median_score?: number }>;
  ind004: BlocoPeriodo<{ n?: number; std_score?: number }>;
  ind005: BlocoPeriodo<{ n?: number; percentiles?: Percentis }>;
  ind006: BlocoPeriodo<{ n?: number; bins?: Bin[] }>;
  ind007: BlocoPeriodo<{ n?: number; categories?: Categoria[] }>;
  ind008: BlocoPeriodo<{ n?: number; perfect_scores?: number; privacy_review_required?: boolean }>;
};

function textoContagem(valor: number | null): string {
  return valor === null ? 'não disponível' : formatarInteiro(valor);
}

function textoNota(valor: number | null): string {
  return valor === null ? 'não disponível' : formatarNota(valor);
}

function histograma(bins: Bin[] | undefined, limiar: number): { figura: Figura | null; omitidos: boolean } {
  if (!bins?.length) return { figura: null, omitidos: false };
  const linhas = bins.map((bin) => ({
    faixa: bin.faixa ?? '',
    quantidade: contagemPublicavel(bin.quantidade, limiar, bin),
  }));
  const omitidos = linhas.some((linha) => linha.quantidade === null);
  if (linhas.every((linha) => linha.quantidade === null)) return { figura: null, omitidos: true };
  const figura = barra(
    linhas.map((linha) => linha.faixa),
    linhas.map((linha) => linha.quantidade),
  );
  figura.altura = 420;
  figura.layout = {
    margin: { b: 108 },
    xaxis: { title: { text: 'Faixa da nota' }, tickangle: -35 },
    yaxis: { title: { text: 'Redações' } },
  };
  return { figura, omitidos };
}

function situacao(categorias: Categoria[] | undefined, limiar: number): { figura: Figura | null; omitidos: number } {
  if (!categorias?.length) return { figura: null, omitidos: 0 };
  const seguras = [];
  let omitidos = 0;
  for (const categoria of categorias) {
    const quantidade = contagemPublicavel(categoria.quantidade, limiar, categoria);
    if (quantidade === null) {
      omitidos += 1;
      continue;
    }
    seguras.push({ rotulo: categoria.rotulo ?? 'Sem rótulo', quantidade });
  }
  if (!seguras.length) return { figura: null, omitidos };
  const figura = barra(
    seguras.map((item) => item.rotulo),
    seguras.map((item) => item.quantidade),
    true,
  );
  figura.altura = Math.max(280, seguras.length * 36);
  figura.layout = { margin: { l: 180 }, xaxis: { title: { text: 'Participações' } }, yaxis: { automargin: true } };
  return { figura, omitidos };
}

const ORDEM_PERCENTIL = [
  ['p25', '25% das notas'],
  ['p50', 'Metade das notas'],
  ['p75', '75% das notas'],
  ['p90', '90% das notas'],
  ['p95', '95% das notas'],
] as const;

export default function VisaoGeral() {
  const { ano, uf, limiar } = useFiltros();
  const todos = ano === 'todos';
  const anual = useDados<Overview>(todos ? null : `/data/${ano}/overview.json`);
  const temporal = useDados<Temporal>(todos ? '/data/temporal.json' : null);
  const serieUf = useDados<SerieUF>(todos && uf !== 'BR' ? '/data/serie-uf.json' : null);
  const fonte = todos ? temporal : anual;
  if (fonte.carregando || fonte.erro || !fonte.dados) {
    return <Estado carregando={fonte.carregando} erro={fonte.erro} />;
  }

  const brasil = uf === 'BR';
  let validas: number | null = null;
  let percentual: number | null = null;
  let media: number | null = null;
  let mediana: number | null = null;
  let desvio: number | null = null;
  let notasMil: number | null = null;
  let percentis: Percentis | undefined;
  let bins: Bin[] | undefined;
  let categorias: Categoria[] | undefined;
  let populacaoStatus = '';
  let ranking: UfNota[] = [];

  if (!todos && anual.dados) {
    const doc = anual.dados;
    if (brasil) {
      validas = numero(doc.kpis.valid_essays);
      percentual = numero(doc.ind001.national_percentage);
      media = metricaPublicavel(doc.kpis.mean_score, doc.ind002.n, limiar);
      mediana = metricaPublicavel(doc.kpis.median_score, doc.ind003.n, limiar);
      desvio = metricaPublicavel(doc.kpis.std_score, doc.ind004.n, limiar);
      notasMil = contagemPublicavel(doc.kpis.perfect_scores?.count, limiar);
      percentis = doc.kpis.percentiles;
      bins = doc.score_distribution.bins;
      categorias = doc.essay_status.categories;
      ranking = doc.ind002.by_uf;
    } else {
      const a = porUf(doc.ind001.by_uf, uf);
      const b = porUf(doc.ind002.by_uf, uf);
      const c = porUf(doc.ind003.by_uf, uf);
      const d = porUf(doc.ind004.by_uf, uf);
      const e = porUf(doc.ind005.by_uf, uf);
      const f = porUf(doc.ind008.by_uf, uf);
      const g = porUf(doc.score_distribution.by_uf, uf);
      const h = porUf(doc.essay_status.by_uf, uf);
      validas = numero(a?.redacoes_validas);
      percentual = numero(a?.percentual_validas);
      media = metricaPublicavel(b?.mean_score, b?.n, limiar);
      mediana = metricaPublicavel(c?.median_score, c?.n, limiar);
      desvio = metricaPublicavel(d?.std_score, d?.n, limiar);
      notasMil = contagemPublicavel(f?.perfect_scores, limiar, f);
      percentis = e?.percentiles;
      bins = g?.bins;
      categorias = h?.categories;
    }
    populacaoStatus = doc.essay_status.population ?? '';
  }

  if (todos && temporal.dados) {
    const doc = temporal.dados;
    const base = brasil ? doc.period_total : porUf(doc.period_by_uf, uf);
    const i2 = brasil ? doc.ind002.period_total : porUf(doc.ind002.period_by_uf, uf);
    const i3 = brasil ? doc.ind003.period_total : porUf(doc.ind003.period_by_uf, uf);
    const i4 = brasil ? doc.ind004.period_total : porUf(doc.ind004.period_by_uf, uf);
    const i5 = brasil ? doc.ind005.period_total : porUf(doc.ind005.period_by_uf, uf);
    const i6 = brasil ? doc.ind006.period_total : porUf(doc.ind006.period_by_uf, uf);
    const i7 = brasil ? doc.ind007.period_total : porUf(doc.ind007.period_by_uf, uf);
    const i8 = brasil ? doc.ind008.period_total : porUf(doc.ind008.period_by_uf, uf);
    validas = numero(base?.redacoes_validas);
    percentual = numero(base?.percentual_validas);
    media = metricaPublicavel(i2?.mean_score, i2?.n, limiar);
    mediana = metricaPublicavel(i3?.median_score, i3?.n, limiar);
    desvio = metricaPublicavel(i4?.std_score, i4?.n, limiar);
    notasMil = contagemPublicavel(i8?.perfect_scores, limiar, i8);
    percentis = i5?.percentiles;
    bins = i6?.bins;
    categorias = i7?.categories;
    if (brasil) ranking = doc.ind002.period_by_uf ?? [];
  }

  const hist = histograma(bins, limiar);
  const sit = situacao(categorias, limiar);
  const rankingFigura = brasil ? rankingMedias(ranking, limiar) : null;
  const pontosHistoricos: PontoHistorico[] = !todos ? [] : brasil
    ? (temporal.dados?.ind002.national_by_year ?? [])
    : (serieUf.dados?.ufs?.[uf] ?? []).map((item) => ({
        year: item.year, mean_score: item.ind002?.mean_score, n: item.ind002?.n,
      }));
  const historico = evolucaoInicial(pontosHistoricos, limiar);

  return (
    <div>
      <h1>Visão geral</h1>
      {ano === '2020' ? (
        <Aviso>Em 2020, a parcela de redações válidas é menor do que nas outras edições.</Aviso>
      ) : null}
      {todos ? (
        <p className="nota">Soma de 2019 a 2025. A série de cada ano está em Evolução.</p>
      ) : null}
      <div className="cartoes">
        <Cartao rotulo="Redações válidas" valor={textoContagem(validas)} detalhe={percentual === null ? undefined : formatarPercentual(percentual)} />
        <Cartao rotulo="Média" valor={textoNota(media)} />
        <Cartao rotulo="Mediana" valor={textoNota(mediana)} />
        <Cartao rotulo="Desvio-padrão" valor={textoNota(desvio)} />
        <Cartao rotulo="Notas 1000" valor={textoContagem(notasMil)} />
      </div>
      {todos ? (
        <Grafico
          identificador="resumo-evolucao"
          titulo="Como a nota média evoluiu de 2019 a 2025?"
          figura={historico.figura}
          nota={historico.leitura + ' Cada ponto representa uma edição, e não os mesmos estudantes ao longo do tempo. A média consolidada acima é ponderada pelas redações válidas, não a média simples dos anos.'}
        />
      ) : null}
      <Grafico
        identificador="histograma"
        titulo="Em quais faixas se concentram as notas?"
        figura={hist.figura}
        nota={hist.omitidos ? 'Algumas faixas não possuem contagem disponível e permanecem sem barra, sem serem transformadas em zero.' : undefined}
      />
      <div className="grade-2">
        <Grafico
          identificador="situacao"
          titulo="Como se distribuem as situações da redação?"
          figura={sit.figura}
          nota={
            [
              populacaoStatus === 'POP_ALL' ? 'Inclui todas as participações, não só as redações válidas.' : '',
              sit.omitidos ? 'Situações sem contagem disponível não aparecem e não entram como zero.' : '',
            ]
              .filter(Boolean)
              .join(' ') || undefined
          }
        />
        <section className="painel" data-visual="percentis">
          <h2>Até que nota chega cada fatia das redações?</h2>
          <table>
            <thead>
              <tr>
                <th>Fatia</th>
                <th>Nota</th>
              </tr>
            </thead>
            <tbody>
              {ORDEM_PERCENTIL.map(([chave, rotulo]) => {
                const valor = numero(percentis?.[chave]);
                return (
                  <tr key={chave}>
                    <td>{rotulo}</td>
                    <td>{valor === null ? 'não disponível' : formatarNota(valor)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </div>
      {brasil ? (
        <Grafico
          identificador="ranking-uf"
          titulo="Qual UF da prova tem a maior média?"
          figura={rankingFigura}
          nota="Comparação dos estados. Some quando um estado está selecionado."
        />
      ) : null}
    </div>
  );
}


function evolucaoInicial(pontos: PontoHistorico[], limiar: number): { figura: Figura | null; leitura: string } {
  const serie = [...pontos].sort((a, b) => a.year - b.year).map((ponto) => ({
    ano: ponto.year,
    nota: metricaPublicavel(ponto.mean_score, ponto.n, limiar),
  }));
  const validos = serie.filter((item): item is { ano: number; nota: number } => item.nota !== null);
  if (!validos.length) {
    return { figura: null, leitura: 'Não há valores publicáveis para a série do recorte selecionado.' };
  }
  const primeiro = validos[0];
  const ultimo = validos[validos.length - 1];
  const diferenca = ultimo.nota - primeiro.nota;
  const leitura = validos.length > 1
    ? 'Entre ' + primeiro.ano + ' e ' + ultimo.ano + ', a média registrada passou de ' +
      formatarNota(primeiro.nota) + ' para ' + formatarNota(ultimo.nota) +
      ' pontos (diferença de ' + (diferenca >= 0 ? '+' : '−') + formatarNota(Math.abs(diferenca)) + ' pontos).'
    : 'Há somente um ano com nota média publicável neste recorte.';
  return {
    figura: {
      data: [{
        type: 'scatter', mode: 'lines+markers',
        name: 'Média anual', x: serie.map((item) => String(item.ano)),
        y: serie.map((item) => item.nota),
        connectgaps: false,
        line: { color: '#176590', width: 3 }, marker: { color: '#176590', size: 9 },
        hovertemplate: 'ENEM %{x}<br>Nota média: %{y:.1f} pontos<extra></extra>',
      }],
      altura: 350,
      layout: { yaxis: { title: { text: 'Nota média (0–1.000 pontos)' }, range: [0, 1000] }, xaxis: { title: { text: 'Edição do exame' } } },
    },
    leitura,
  };
}

function rankingMedias(lista: UfNota[], limiar: number): Figura | null {
  const linhas = lista
    .map((item) => ({ uf: item.uf, media: metricaPublicavel(item.mean_score, item.n, limiar) }))
    .filter((item): item is { uf: string; media: number } => item.media !== null)
    .sort((a, b) => b.media - a.media);
  if (!linhas.length) return null;
  const figura = barra(
    linhas.map((item) => nomeUf(item.uf)),
    linhas.map((item) => item.media),
    true,
  );
  figura.altura = Math.max(420, linhas.length * 22);
  figura.layout = {
    margin: { l: 170, t: 12, b: 55 },
    xaxis: { title: { text: 'Nota média (0–1000)' }, range: [0, 1000] },
    yaxis: { automargin: true, autorange: 'reversed' },
  };
  return figura;
}
