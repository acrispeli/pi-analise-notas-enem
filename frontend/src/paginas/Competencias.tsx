import { CORES, COR, Grafico, type Figura } from '../grafico.tsx';
import { Cartao, Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { formatarIndice, formatarInteiro, formatarNota, numero } from '../lib/formatar.ts';
import { contagemPublicavel, metricaPublicavel, porUf } from '../lib/supressao.ts';
import { figuraHexbin, notaHex, type RecorteHex } from '../hexbin.ts';

type Comp = {
  competency?: string;
  label?: string;
  mean_score?: number;
  median_score?: number;
  n?: number;
  levels?: { score?: number; count?: number; percentage?: number; requires_privacy_review?: boolean }[];
};
type Cluster = {
  cluster_id?: string;
  rotulo?: string;
  n_amostra?: number;
  centro_pontos?: number[];
  centro_competencias?: { competencia?: string; nota_media_centro?: number }[];
};
type Tamanho = { cluster_id?: string; rotulo?: string; n_redacoes?: number; percentual?: number };
type Qualidade = { silhouette?: number; davies_bouldin?: number; calinski_harabasz?: number; k?: number; n_amostra_ml?: number };

type Modelo = {
  medias: Comp[];
  medianas: Comp[];
  niveis: Comp[];
  correlacao: number[][] | null;
  rotulos: string[];
  variancia: { componente?: string; percentual_explicado?: number }[];
  loadings: number[][] | null;
  linhasPca: string[];
  colunasPca: string[];
  hex: RecorteHex | undefined;
  clusters: Cluster[];
  tamanhos: Tamanho[];
  qualidade: Qualidade | null;
  amostra: number | null;
};

const VAZIO: Modelo = {
  medias: [],
  medianas: [],
  niveis: [],
  correlacao: null,
  rotulos: ['C1', 'C2', 'C3', 'C4', 'C5'],
  variancia: [],
  loadings: null,
  linhasPca: [],
  colunasPca: [],
  hex: undefined,
  clusters: [],
  tamanhos: [],
  qualidade: null,
  amostra: null,
};

function lista(valor: unknown): Comp[] {
  if (Array.isArray(valor)) return valor as Comp[];
  if (valor && typeof valor === 'object') {
    const registro = valor as { summary?: Comp[]; national_summary?: Comp[] };
    return registro.summary ?? registro.national_summary ?? [];
  }
  return [];
}

function matriz(valor: unknown): number[][] | null {
  if (!Array.isArray(valor) || !valor.length || !Array.isArray(valor[0])) return null;
  return valor as number[][];
}

export default function Competencias() {
  const { ano, uf, limiar } = useFiltros();
  const todos = ano === 'todos';
  const anual = useDados<Record<string, unknown>>(todos ? null : `/data/${ano}/competencies.json`);
  const temporal = useDados<Record<string, unknown>>(todos ? '/data/temporal.json' : null);
  const fonte = todos ? temporal : anual;
  if (fonte.carregando || fonte.erro || !fonte.dados) return <Estado carregando={fonte.carregando} erro={fonte.erro} />;

  const modelo = todos ? doPeriodo(temporal.dados ?? {}, uf) : doAno(anual.dados ?? {}, uf);
  const medias = barrasCompetencia(modelo.medias, 'mean_score', limiar, 'Nota média');
  const niveis = barrasNiveis(modelo.niveis, limiar);
  const calor = heatmap(modelo.correlacao, modelo.rotulos, modelo.rotulos, 'Blues', -1, 1);
  const variancia = barrasVariancia(modelo.variancia);
  const cargas = heatmap(modelo.loadings, modelo.colunasPca, modelo.linhasPca, 'RdBu', -1, 1, 0);
  const mapa = figuraHexbin(modelo.hex, limiar);
  const perfis = graficoPerfis(modelo.clusters, modelo.tamanhos, limiar);

  return (
    <div>
      <h1>Competências</h1>
      <p className="nota">C1 escrita formal · C2 tema · C3 argumentação · C4 coesão · C5 proposta de intervenção</p>
      {todos ? <p className="nota">Período inteiro. Anos diferentes não são misturados no mapa.</p> : null}
      <p className="nota">Os perfis vêm de uma amostra de 4.000 redações. O tamanho na legenda é o de todas as redações válidas.</p>
      <div className="grade-2">
        <section className="painel" data-visual="medias">
          <h2>Qual é a média de cada competência?</h2>
          <Grafico identificador="medias" titulo="" figura={medias} embutido />
          <table>
            <thead>
              <tr>
                <th>Competência</th>
                <th>Mediana</th>
              </tr>
            </thead>
            <tbody>
              {modelo.rotulos.map((codigo) => {
                const item = modelo.medianas.find((comp) => comp.competency === codigo);
                const valor = metricaPublicavel(item?.median_score, item?.n, limiar);
                return (
                  <tr key={codigo}>
                    <td>{codigo}</td>
                    <td>{valor === null ? 'não disponível' : formatarNota(valor)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
        <Grafico identificador="niveis" titulo="Como se distribuem os níveis de cada competência?" figura={niveis} nota={niveis ? undefined : 'Não há dados completos para construir a distribuição de níveis deste recorte.'} />
      </div>
      <div className="grade-2">
        <Grafico identificador="correlacao" titulo="Quais competências variam juntas?" figura={calor} />
        <Grafico identificador="variancia" titulo="Quanto cada eixo do mapa explica?" figura={variancia} />
      </div>
      <Grafico identificador="loadings" titulo="Qual competência pesa mais em cada eixo?" figura={cargas} nota="O sentido do eixo pode inverter de um recorte para outro. O peso continua o mesmo." />
      <Grafico identificador="hexbin" titulo="Onde as redações se concentram no mapa?" figura={mapa} nota={notaHex(modelo.hex)} />
      <Grafico identificador="perfis" titulo="Como os perfis diferem nas cinco competências?" figura={perfis} nota="P1, P2 e os demais são nomes deste recorte. Não se repetem de um ano para outro." />
      <div className="cartoes" data-visual="qualidade">
        <Cartao rotulo="Separação dos grupos" valor={textoIndice(modelo.qualidade?.silhouette)} detalhe="De 0 a 1. Mais alto, grupos mais distintos." />
        <Cartao rotulo="Grupos" valor={modelo.qualidade?.k == null ? 'não disponível' : String(modelo.qualidade.k)} />
        <Cartao rotulo="Redações na amostra" valor={modelo.amostra == null ? 'não disponível' : formatarInteiro(modelo.amostra)} />
      </div>
    </div>
  );
}

function textoIndice(valor: number | undefined): string {
  const n = numero(valor);
  return n === null ? 'não disponível' : formatarIndice(n);
}

function doAno(doc: Record<string, unknown>, uf: string): Modelo {
  const brasil = uf === 'BR';
  const ind009 = doc.ind009 as { by_uf?: { uf: string; summary?: Comp[]; n?: number }[] };
  const ind010 = doc.ind010 as { national_summary?: Comp[]; by_uf?: { uf: string; summary?: Comp[]; n?: number }[] };
  const niveis = doc.level_distribution as { national_summary?: Comp[]; by_uf?: { uf: string; summary?: Comp[] }[] };
  const correlacao = doc.correlation as { spearman?: number[][]; labels?: string[]; by_uf?: { uf: string; spearman?: number[][]; n?: number }[] };
  const pca = doc.pca as {
    explained_variance?: { componente?: string; percentual_explicado?: number }[];
    loadings?: number[][];
    loading_rows?: string[];
    loading_columns?: string[];
    by_uf?: { uf: string; explained_variance?: { componente?: string; percentual_explicado?: number }[]; loadings?: number[][] }[];
    scatter?: { brasil?: RecorteHex; by_uf?: (RecorteHex & { uf: string })[] };
  };
  const clusters = doc.clusters as {
    brasil?: { clusters?: Cluster[]; n_amostra_ml?: number };
    by_uf?: { uf: string; clusters?: Cluster[]; n_amostra_ml?: number }[];
    sizes?: { brasil?: { clusters?: Tamanho[] }; by_uf?: { uf: string; clusters?: Tamanho[] }[] };
    quality?: { brasil?: Qualidade; by_uf?: (Qualidade & { uf: string })[] };
  };
  const resumo = brasil ? lista(doc.summary) : lista(porUf(ind009?.by_uf, uf));
  const medianas = brasil ? lista(ind010?.national_summary) : lista(porUf(ind010?.by_uf, uf));
  const faixas = brasil ? lista(niveis?.national_summary) : lista(porUf(niveis?.by_uf, uf));
  const matrizCor = brasil ? correlacao?.spearman : porUf(correlacao?.by_uf, uf)?.spearman;
  const blocoPca = brasil ? pca : porUf(pca?.by_uf, uf);
  const hex = brasil ? pca?.scatter?.brasil : porUf(pca?.scatter?.by_uf, uf);
  const grupo = brasil ? clusters?.brasil : porUf(clusters?.by_uf, uf);
  const tamanho = brasil ? clusters?.sizes?.brasil : porUf(clusters?.sizes?.by_uf, uf);
  const qualidade = brasil ? clusters?.quality?.brasil : porUf(clusters?.quality?.by_uf, uf);
  return {
    ...VAZIO,
    medias: resumo,
    medianas: medianas.length ? medianas : resumo,
    niveis: faixas,
    correlacao: matriz(matrizCor),
    rotulos: correlacao?.labels ?? VAZIO.rotulos,
    variancia: blocoPca?.explained_variance ?? [],
    loadings: matriz(blocoPca?.loadings),
    linhasPca: pca?.loading_rows ?? ['PC1', 'PC2', 'PC3', 'PC4', 'PC5'],
    colunasPca: pca?.loading_columns ?? ['C1', 'C2', 'C3', 'C4', 'C5'],
    hex,
    clusters: grupo?.clusters ?? [],
    tamanhos: tamanho?.clusters ?? [],
    qualidade: qualidade ?? null,
    amostra: numero(grupo?.n_amostra_ml),
  };
}

function doPeriodo(doc: Record<string, unknown>, uf: string): Modelo {
  const brasil = uf === 'BR';
  const pegar = <T,>(chave: string): T | undefined => {
    const bloco = doc[chave] as { period_total?: T; period_by_uf?: ({ uf: string } & T)[] } | undefined;
    if (!bloco) return undefined;
    if (brasil) return bloco.period_total;
    return bloco.period_by_uf?.find((item) => item.uf === uf);
  };
  const i9 = pegar<{ summary?: Comp[] }>('ind009');
  const i10 = pegar<{ summary?: Comp[] }>('ind010');
  const i12 = pegar<{ summary?: Comp[] }>('ind012');
  const i13 = pegar<{ spearman?: number[][] }>('ind013');
  const i14 = pegar<{ explained_variance?: { componente?: string; percentual_explicado?: number }[] }>('ind014');
  const i15 = pegar<{ loadings?: number[][] }>('ind015');
  const i16 = pegar<RecorteHex>('ind016');
  const i17 = pegar<{ clusters?: Cluster[]; n_amostra_ml?: number }>('ind017');
  const i18 = pegar<{ clusters?: Tamanho[] }>('ind018');
  const i19 = pegar<Qualidade>('ind019');
  return {
    ...VAZIO,
    medias: i9?.summary ?? [],
    medianas: i10?.summary ?? [],
    niveis: i12?.summary ?? [],
    correlacao: matriz(i13?.spearman),
    variancia: i14?.explained_variance ?? [],
    loadings: matriz(i15?.loadings),
    linhasPca: ['PC1', 'PC2', 'PC3', 'PC4', 'PC5'],
    colunasPca: ['C1', 'C2', 'C3', 'C4', 'C5'],
    hex: i16,
    clusters: i17?.clusters ?? [],
    tamanhos: i18?.clusters ?? [],
    qualidade: i19 ?? null,
    amostra: numero(i17?.n_amostra_ml),
  };
}

function barrasCompetencia(itens: Comp[], campo: 'mean_score', limiar: number, eixo: string): Figura | null {
  const linhas = itens
    .map((item) => ({ nome: item.competency ?? '', valor: metricaPublicavel(item[campo], item.n, limiar, item) }))
    .filter((item) => item.nome);
  if (!linhas.length || linhas.some((item) => item.valor === null)) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.nome), y: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{x}: %{y:.1f}<extra></extra>' }],
    altura: 320,
    layout: { yaxis: { title: { text: eixo }, range: [0, 200] }, margin: { t: 8 } },
  };
}

function barrasNiveis(itens: Comp[], limiar: number): Figura | null {
  if (!itens.length) return null;
  for (const item of itens) {
    const niveis = item.levels ?? [];
    if (!niveis.length) return null;
    for (const nivel of niveis) {
      if (contagemPublicavel(nivel.count, limiar, nivel) === null && numero(nivel.count) !== 0) return null;
    }
    const soma = niveis.reduce((total, nivel) => total + (numero(nivel.percentage) ?? 0), 0);
    if (Math.abs(soma - 100) > 0.05) return null;
  }
  const notas = [...new Set(itens.flatMap((item) => (item.levels ?? []).map((nivel) => nivel.score ?? 0)))].sort((a, b) => a - b);
  const data = notas.map((nota, indice) => {
    const valores = itens.map((item) => {
      const nivel = item.levels?.find((faixa) => faixa.score === nota);
      return nivel ? numero(nivel.percentage) : 0;
    });
    if (valores.some((valor) => valor === null)) return null;
    return {
      type: 'bar',
      name: String(nota),
      x: itens.map((item) => item.competency ?? ''),
      y: valores,
      marker: { color: CORES[indice % CORES.length] },
    };
  });
  if (data.some((traco) => traco === null)) return null;
  return {
    data: data as object[],
    altura: 420,
    layout: {
      barmode: 'stack',
      margin: { r: 88, b: 56 },
      legend: { orientation: 'v', y: 1, yanchor: 'top', x: 1.02, xanchor: 'left' },
      yaxis: { title: { text: 'Percentual' }, range: [0, 100] },
    },
  };
}

function heatmap(z: number[][] | null, x: string[], y: string[], escala: string, zmin: number, zmax: number, zmid?: number): Figura | null {
  if (!z?.length) return null;
  const texto = z.map((linha) => linha.map((valor) => (numero(valor) === null ? '' : formatarIndice(valor))));
  return {
    data: [{ type: 'heatmap', z, x, y, zmin, zmax, zmid, colorscale: escala, text: texto, texttemplate: '%{text}', hovertemplate: '%{y} × %{x}: %{z}<extra></extra>' }],
    altura: 420,
    layout: { margin: { l: 64, b: 48 } },
  };
}

function barrasVariancia(itens: { componente?: string; percentual_explicado?: number }[]): Figura | null {
  const linhas = itens.filter((item) => numero(item.percentual_explicado) !== null);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.componente ?? ''), y: linhas.map((item) => item.percentual_explicado), marker: { color: COR }, hovertemplate: '%{x}: %{y:.1f}%<extra></extra>' }],
    altura: 320,
    layout: { yaxis: { title: { text: 'Variância explicada (%)' } } },
  };
}

function graficoPerfis(clusters: Cluster[], tamanhos: Tamanho[], limiar: number): Figura | null {
  if (!clusters.length) return null;
  const data = clusters.map((cluster, indice) => {
    const pontos = cluster.centro_competencias?.length
      ? cluster.centro_competencias.map((item) => ({ x: item.competencia ?? '', y: numero(item.nota_media_centro) }))
      : (cluster.centro_pontos ?? []).map((valor, i) => ({ x: `C${i + 1}`, y: numero(valor) }));
    if (pontos.some((ponto) => ponto.y === null)) return null;
    const tamanho = tamanhos.find((item) => item.cluster_id === cluster.cluster_id);
    const n = contagemPublicavel(tamanho?.n_redacoes, limiar);
    const pct = numero(tamanho?.percentual);
    const nome = n === null ? cluster.rotulo ?? cluster.cluster_id ?? 'Perfil' : `${cluster.rotulo ?? cluster.cluster_id} · ${formatarInteiro(n)}${pct === null ? '' : ` (${formatarNota(pct)}%)`}`;
    return {
      type: 'scatter',
      mode: 'lines+markers',
      name: nome,
      x: pontos.map((ponto) => ponto.x),
      y: pontos.map((ponto) => ponto.y),
      line: { color: CORES[indice % CORES.length] },
    };
  });
  if (data.some((item) => item === null)) return null;
  return {
    data: data as object[],
    altura: 460,
    layout: { margin: { b: 120 }, yaxis: { title: { text: 'Nota do centro (0–200)' }, range: [0, 200] } },
  };
}

