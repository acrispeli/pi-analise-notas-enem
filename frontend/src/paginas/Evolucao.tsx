import { COR, CORES, Grafico, type Figura } from '../grafico.tsx';
import { Aviso, Estado } from '../layout.tsx';
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

type ExtraLinha = { ano?: number; competencia?: string; cluster_referencia?: string; status?: string; media?: number; n_validas?: number; frequencia_desconto?: number; n_near?: number; percentual_discrepancia_confirmada?: number; n_pareadas?: number; percentual_amostra?: number; n_amostra?: number; alerta?: string };
type ExtraEvolucao = { competencias?: { results?: ExtraLinha[] }; quase?: { results?: ExtraLinha[] }; divergencia?: { results?: ExtraLinha[] }; perfis?: { results?: ExtraLinha[] } };

export default function Evolucao() {
  const { ano, uf, limiar } = useFiltros();
  const brasil = uf === 'BR';
  const temporal = useDados<Temporal>(brasil ? '/data/temporal.json' : null);
  const serie = useDados<SerieUf>(brasil ? null : '/data/serie-uf.json');
  const extra = useDados<ExtraEvolucao>('/data/extra/evolucao.json');
  const fonte = brasil ? temporal : serie;
  if (fonte.carregando || fonte.erro || !fonte.dados) return <Estado carregando={fonte.carregando} erro={fonte.erro} />;

  const pontos = brasil ? pontosBrasil(temporal.dados) : pontosUf(serie.dados, uf);
  const destaque = ano === 'todos' ? null : Number(ano);
  if (!pontos.length) {
    return (
      <div>
        <h1>Evolução</h1>
        <p className="indisponivel">não disponível</p>
      </div>
    );
  }

  return (
    <div>
      <h1>Evolução</h1>
      <p className="nota">Cada ponto é o valor daquele ano. O ano escolhido fica em destaque.</p>
      <div className="grade-2">
        <Grafico identificador="serie-validas" titulo="Qual foi a parcela de redações válidas em cada edição?" figura={linha(pontos, destaque, (ponto) => metricaPublicavel(ponto.percentual_validas, ponto.n_validas, limiar), 'Percentual', [0, 100])} />
        <Grafico identificador="serie-notas" titulo="Como evoluíram a média e a mediana?" figura={duasLinhas(pontos, destaque, limiar)} />
        <Grafico identificador="serie-desvio" titulo="Como evoluiu o desvio-padrão?" figura={linha(pontos, destaque, (ponto) => metricaPublicavel(ponto.std_score, ponto.n_desvio, limiar), 'Desvio-padrão')} />
        <Grafico identificador="serie-mil" titulo="Quantas redações chegaram a 1.000 pontos?" figura={linhaMil(pontos, destaque, limiar)} />
      </div>
      {brasil ? (
        <SeriesNacionais extra={extra.dados} destaque={destaque} limiar={limiar} carregando={extra.carregando} erro={extra.erro} />
      ) : (
        <Aviso>Estas séries são do Brasil. No estado, ficam as quatro séries de cima.</Aviso>
      )}
    </div>
  );
}

function SeriesNacionais({ extra, destaque, limiar, carregando, erro }: { extra: ExtraEvolucao | null; destaque: number | null; limiar: number; carregando: boolean; erro: boolean }) {
  if (carregando) return <Estado carregando erro={false} />;
  if (erro || !extra) {
    return <Grafico identificador="serie-competencias" titulo="Como evoluiu a média de cada competência?" figura={null} />;
  }
  const alerta = extra.divergencia?.results?.find((item) => item.alerta)?.alerta;
  return (
    <>
      <Grafico identificador="serie-competencias" titulo="Como evoluiu a média de cada competência?" figura={seriePorGrupo(extra.competencias?.results, 'competencia', 'media', 'n_validas', limiar, destaque, [0, 200])} nota="Brasil. O ano escolhido fica em destaque." />
      <Grafico identificador="serie-quase" titulo="Com que frequência cada competência recebe desconto nas notas próximas de 1.000?" figura={seriePorGrupo(extra.quase?.results, 'competencia', 'frequencia_desconto', 'n_near', limiar, destaque, [0, 100], true)} nota="Percentual de redações com desconto naquela competência." />
      <Grafico identificador="serie-divergencia" titulo="Como evoluiu a parcela de redações com discrepância?" figura={serieUnica(extra.divergencia?.results, 'percentual_discrepancia_confirmada', 'n_pareadas', limiar, destaque, [0, 100])} nota={alerta ? 'A regra é a do edital de 2024, usada em todos os anos.' : undefined} />
      <Grafico identificador="serie-perfis" titulo="Como mudou a participação de cada perfil?" figura={seriePorGrupo(extra.perfis?.results, 'cluster_referencia', 'percentual_amostra', 'n_amostra', limiar, destaque, [0, 100])} nota="Amostra. Estes perfis são os mesmos ao longo dos anos e não são os grupos da página Perfis." />
    </>
  );
}

function serieUnica(linhas: ExtraLinha[] | undefined, campo: keyof ExtraLinha, denominador: keyof ExtraLinha, limiar: number, destaque: number | null, intervalo?: [number, number]): Figura | null {
  const pontos = (linhas ?? []).filter((item) => item.ano && item.status !== 'nao_aplicavel');
  if (!pontos.length) return null;
  const anos = pontos.map((item) => item.ano as number);
  const y = pontos.map((item) => metricaPublicavel(item[campo], item[denominador], limiar, item));
  if (y.every((valor) => valor === null)) return null;
  return {
    data: [{ type: 'scatter', mode: 'lines+markers', x: anos.map(String), y, connectgaps: false, line: { color: COR, width: 2 }, marker: { size: 9, color: corMarcador(anos, destaque, COR) }, hovertemplate: '%{x}<br>%{y:.1f}<extra></extra>' }],
    altura: 340,
    layout: { yaxis: { title: { text: 'Percentual' }, range: intervalo }, xaxis: { title: { text: 'Ano' } } },
  };
}

function seriePorGrupo(linhas: ExtraLinha[] | undefined, grupo: keyof ExtraLinha, campo: keyof ExtraLinha, denominador: keyof ExtraLinha, limiar: number, destaque: number | null, intervalo?: [number, number], taxa?: boolean): Figura | null {
  const pontos = (linhas ?? []).filter((item) => item.ano && item[grupo] && item.status !== 'nao_aplicavel');
  const nomes = [...new Set(pontos.map((item) => String(item[grupo])))];
  if (!nomes.length) return null;
  const anos = [...new Set(pontos.map((item) => item.ano as number))].sort((a, b) => a - b);
  const data = nomes.map((nome, indice) => {
    const cor = CORES[(indice + 4) % CORES.length];
    const y = anos.map((anoLinha) => {
      const item = pontos.find((linha) => linha.ano === anoLinha && String(linha[grupo]) === nome);
      if (!item) return null;
      const valor = metricaPublicavel(item[campo], item[denominador], limiar, item);
      return taxa && valor !== null ? valor * 100 : valor;
    });
    return { type: 'scatter', mode: 'lines+markers', name: nome, x: anos.map(String), y, connectgaps: false, line: { color: cor, width: 2 }, marker: { size: 8, color: corMarcador(anos, destaque, cor) }, hovertemplate: '%{fullData.name}<br>%{x}: %{y:.1f}<extra></extra>' };
  });
  if (data.every((serieLinha) => (serieLinha.y as (number | null)[]).every((valor) => valor === null))) return null;
  return {
    data,
    altura: 380,
    layout: { yaxis: { title: { text: taxa || intervalo?.[1] === 100 ? 'Percentual' : 'Nota média' }, range: intervalo }, xaxis: { title: { text: 'Ano' } }, margin: { b: 96 } },
  };
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
