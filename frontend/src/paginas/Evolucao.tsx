import { COR, Grafico, type Figura } from '../grafico.tsx';
import { Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { contagemPublicavel, metricaPublicavel } from '../lib/supressao.ts';

type Ponto = {
  year: number;
  percentual_validas?: number;
  n_validas?: number;
  mean_score?: number;
  n_media?: number;
  median_score?: number;
  n_mediana?: number;
  std_score?: number;
  n_desvio?: number;
  perfect_scores?: number;
  perfect_flag?: boolean;
};

type Temporal = {
  national_by_year?: { year: number; percentual_validas?: number; redacoes_validas?: number }[];
  ind002?: { national_by_year?: { year: number; n?: number; mean_score?: number }[] };
  ind003?: { national_by_year?: { year: number; n?: number; median_score?: number }[] };
  ind004?: { national_by_year?: { year: number; n?: number; std_score?: number }[] };
  ind008?: { national_by_year?: { year: number; n?: number; perfect_scores?: number; privacy_review_required?: boolean }[] };
};

type SerieUf = {
  ufs: Record<string, {
    year: number;
    ind001?: { percentual_validas?: number; redacoes_validas?: number };
    ind002?: { n?: number; mean_score?: number };
    ind003?: { n?: number; median_score?: number };
    ind004?: { n?: number; std_score?: number };
    ind008?: { perfect_scores?: number; privacy_review_required?: boolean };
  }[]>;
};

export default function Evolucao() {
  const { ano, uf, limiar } = useFiltros();
  const brasil = uf === 'BR';
  const temporal = useDados<Temporal>(brasil ? '/data/temporal.json' : null);
  const serie = useDados<SerieUf>(brasil ? null : '/data/serie-uf.json');
  const fonte = brasil ? temporal : serie;
  if (fonte.carregando || fonte.erro || !fonte.dados) return <Estado carregando={fonte.carregando} erro={fonte.erro} />;

  const pontos = brasil ? pontosBrasil(temporal.dados) : pontosUf(serie.dados, uf);
  const destaque = ano === 'todos' ? null : Number(ano);
  if (!pontos.length) {
    return (
      <div>
        <h1>Evolução</h1>
        <p className="indisponivel">indisponível</p>
      </div>
    );
  }

  return (
    <div>
      <h1>Evolução</h1>
      <p className="nota">A série usa o valor já publicado de cada edição. O ano selecionado fica em destaque. Não há média dos anos nesta tela.</p>
      <div className="grade-2">
        <Grafico identificador="serie-validas" titulo="Qual foi a parcela de redações válidas em cada edição?" figura={linha(pontos, destaque, (ponto) => metricaPublicavel(ponto.percentual_validas, ponto.n_validas, limiar), 'Percentual', [0, 100])} />
        <Grafico identificador="serie-notas" titulo="Como evoluíram a média e a mediana?" figura={duasLinhas(pontos, destaque, limiar)} />
        <Grafico identificador="serie-desvio" titulo="Como evoluiu o desvio-padrão?" figura={linha(pontos, destaque, (ponto) => metricaPublicavel(ponto.std_score, ponto.n_desvio, limiar), 'Desvio-padrão')} />
        <Grafico identificador="serie-mil" titulo="Quantas redações chegaram a 1.000 pontos?" figura={linhaMil(pontos, destaque, limiar)} />
      </div>
    </div>
  );
}

function pontosBrasil(doc: Temporal | null): Ponto[] {
  if (!doc?.national_by_year) return [];
  const media = new Map((doc.ind002?.national_by_year ?? []).map((item) => [item.year, item]));
  const mediana = new Map((doc.ind003?.national_by_year ?? []).map((item) => [item.year, item]));
  const desvio = new Map((doc.ind004?.national_by_year ?? []).map((item) => [item.year, item]));
  const mil = new Map((doc.ind008?.national_by_year ?? []).map((item) => [item.year, item]));
  return doc.national_by_year.map((item) => ({
    year: item.year,
    percentual_validas: item.percentual_validas,
    n_validas: item.redacoes_validas,
    mean_score: media.get(item.year)?.mean_score,
    n_media: media.get(item.year)?.n,
    median_score: mediana.get(item.year)?.median_score,
    n_mediana: mediana.get(item.year)?.n,
    std_score: desvio.get(item.year)?.std_score,
    n_desvio: desvio.get(item.year)?.n,
    perfect_scores: mil.get(item.year)?.perfect_scores,
    perfect_flag: mil.get(item.year)?.privacy_review_required,
  }));
}

function pontosUf(doc: SerieUf | null, uf: string): Ponto[] {
  const lista = doc?.ufs?.[uf];
  if (!lista) return [];
  return lista.map((item) => ({
    year: item.year,
    percentual_validas: item.ind001?.percentual_validas,
    n_validas: item.ind001?.redacoes_validas,
    mean_score: item.ind002?.mean_score,
    n_media: item.ind002?.n,
    median_score: item.ind003?.median_score,
    n_mediana: item.ind003?.n,
    std_score: item.ind004?.std_score,
    n_desvio: item.ind004?.n,
    perfect_scores: item.ind008?.perfect_scores,
    perfect_flag: item.ind008?.privacy_review_required,
  }));
}

function corMarcador(anos: number[], destaque: number | null, base: string): string[] {
  return anos.map((ano) => (destaque !== null && ano === destaque ? '#c45c26' : base));
}

function linha(pontos: Ponto[], destaque: number | null, ler: (ponto: Ponto) => number | null, eixo: string, intervalo?: [number, number]): Figura | null {
  const y = pontos.map(ler);
  if (y.every((valor) => valor === null)) return null;
  return {
    data: [{
      type: 'scatter',
      mode: 'lines+markers',
      x: pontos.map((ponto) => String(ponto.year)),
      y,
      connectgaps: false,
      line: { color: COR, width: 2 },
      marker: { size: 9, color: corMarcador(pontos.map((ponto) => ponto.year), destaque, COR) },
      hovertemplate: '%{x}<br>%{y}<extra></extra>',
    }],
    altura: 340,
    layout: { yaxis: { title: { text: eixo }, range: intervalo }, xaxis: { title: { text: 'Ano' } } },
  };
}

function duasLinhas(pontos: Ponto[], destaque: number | null, limiar: number): Figura | null {
  const media = pontos.map((ponto) => metricaPublicavel(ponto.mean_score, ponto.n_media, limiar));
  const mediana = pontos.map((ponto) => metricaPublicavel(ponto.median_score, ponto.n_mediana, limiar));
  if (media.every((valor) => valor === null) && mediana.every((valor) => valor === null)) return null;
  const anos = pontos.map((ponto) => ponto.year);
  return {
    data: [
      { type: 'scatter', mode: 'lines+markers', name: 'Média', x: anos.map(String), y: media, connectgaps: false, line: { color: COR }, marker: { size: 9, color: corMarcador(anos, destaque, COR) } },
      { type: 'scatter', mode: 'lines+markers', name: 'Mediana', x: anos.map(String), y: mediana, connectgaps: false, line: { color: '#4f86c6' }, marker: { size: 9, color: corMarcador(anos, destaque, '#4f86c6') } },
    ],
    altura: 360,
    layout: { yaxis: { title: { text: 'Nota' }, range: [0, 1000] }, xaxis: { title: { text: 'Ano' } } },
  };
}

function linhaMil(pontos: Ponto[], destaque: number | null, limiar: number): Figura | null {
  const y = pontos.map((ponto) => contagemPublicavel(ponto.perfect_scores, limiar, ponto.perfect_flag ? { privacy_review_required: true } : undefined));
  if (y.every((valor) => valor === null)) return null;
  return linha(
    pontos,
    destaque,
    (ponto) => contagemPublicavel(ponto.perfect_scores, limiar, ponto.perfect_flag ? { privacy_review_required: true } : undefined),
    'Redações',
  );
}
