import { COR, CORES, Grafico, type Figura } from '../grafico.tsx';
import { Aviso, Cartao, Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { formatarIndice, formatarInteiro, formatarNota, formatarPercentual, numero } from '../lib/formatar.ts';
import { contagemPublicavel, metricaPublicavel, porUf } from '../lib/supressao.ts';

type Hist = { faixa?: string; n_redacoes?: number; percentual?: number };
type CompDif = { competencia?: string; media?: number; n_pares_validos?: number };
type Kappa = { kappa_ponderado_quadratico?: number; situacao?: string; n_pares_validos?: number };
type Cluster = { cluster_id?: string; rotulo?: string; n_amostra?: number; centro_por_competencia?: { competencia?: string; diferenca_media_pontos?: number }[] };

export default function Avaliadores() {
  const { ano, uf, limiar } = useFiltros();
  const todos = ano === 'todos';
  const anual = useDados<Record<string, unknown>>(todos ? null : `/data/${ano}/evaluators.json`);
  const temporal = useDados<Record<string, unknown>>(todos ? '/data/temporal.json' : null);
  const fonte = todos ? temporal : anual;
  if (fonte.carregando || fonte.erro || !fonte.dados) return <Estado carregando={fonte.carregando} erro={fonte.erro} />;

  const doc = fonte.dados;
  const dif = fatia(doc, todos, uf, 'total_difference', 'ind020');
  const comp = fatia(doc, todos, uf, 'by_competency', 'ind021');
  const oficial = fatia(doc, todos, uf, 'official_discrepancy', 'ind022');
  const status = fatia(doc, todos, uf, 'status_disagreement', 'ind023');
  const av3 = fatia(doc, todos, uf, 'third_reviewer', 'ind024');
  const banca = fatia(doc, todos, uf, 'panel_details', 'ind025');
  const kappa = fatia(doc, todos, uf, 'weighted_kappa', 'ind026');
  const icc = fatia(doc, todos, uf, 'icc', 'ind027');
  const perfis = fatia(doc, todos, uf, 'divergence_clusters', 'ind028');
  const atipicos = fatia(doc, todos, uf, 'anomalies', 'ind029');
  const motivo = todos ? 'indicadores_ainda_nao_implementados' : String((anual.dados?.reason as string) ?? '');
  const parcial = todos ? '' : String(anual.dados?.status ?? '');

  const hist = histograma(dif?.histograma as Hist[] | undefined, limiar);
  const barras = diferencaCompetencia(comp?.competencias as CompDif[] | undefined, limiar);
  const kappas = barrasKappa(kappa?.competencias as Record<string, Kappa> | undefined, limiar);
  const divergencia = perfisDivergencia(perfis);
  const nIcc = numero(icc?.n_pares_validos);
  const iccValor = icc?.situacao_icc === 'ok' && (nIcc === null || nIcc >= limiar) ? numero(icc?.icc_concordancia_absoluta) : null;

  return (
    <div>
      <h1>Avaliadores</h1>
      <Aviso>
        {parcial === 'partial' ? `${motivo}. ` : ''}
        O restante do catálogo de avaliadores está pendente. A regra de discrepância é a de 2024, aplicada a todos os anos.
      </Aviso>
      <div className="cartoes">
        <Cartao rotulo="Diferença média total" valor={textoNota(metricaPublicavel(dif?.media, dif?.n_avaliacoes_pareadas, limiar))} />
        <Cartao
          rotulo="Discrepância oficial"
          valor={textoPercentual(metricaPublicavel(oficial?.percentual_discrepancia_confirmada_pop_evaluator, oficial?.n_pop_evaluator, limiar))}
        />
        <Cartao rotulo="ICC" valor={iccValor === null ? 'indisponível' : formatarIndice(iccValor)} />
        <Cartao rotulo="Terceiro avaliador" valor={textoPercentual(metricaPublicavel(av3?.percentual_com_av3, av3?.n_pop_all, limiar))} />
        <Cartao rotulo="Banca" valor={textoPercentual(metricaPublicavel(banca?.percentual_com_av4, banca?.n_pop_all, limiar))} />
        <Cartao
          rotulo="Situação divergente"
          valor={textoPercentual(metricaPublicavel(status?.percentual_divergencia_pop_evaluator, status?.n_pop_evaluator, limiar))}
          detalhe="A matriz de situação fica indisponível."
        />
      </div>
      <div className="grade-2">
        <Grafico identificador="diferenca-total" titulo="Como se distribui a diferença entre os dois corretores?" figura={hist.figura} nota={hist.omitidos ? 'Faixas com contagem suprimida ficam indisponíveis.' : 'A população é a das duas notas de corretor, não a das redações válidas.'} />
        <Grafico identificador="diferenca-competencia" titulo="Em qual competência a diferença média é maior?" figura={barras} />
      </div>
      <Grafico identificador="kappa" titulo="Qual é o kappa de cada competência?" figura={kappas} />
      {divergencia ? (
        <Grafico identificador="perfis-divergencia" titulo="Como os perfis de divergência se separam?" figura={divergencia} nota={notaAmostra(perfis?.n_amostra_ml_evaluator)} />
      ) : (
        <Grafico identificador="perfis-divergencia" titulo="Como os perfis de divergência se separam?" figura={null} nota="Este recorte não tem perfis publicados." />
      )}
      <section className="painel" data-visual="atipicos">
        <h2>Quantas avaliações da amostra foram sinalizadas como atípicas?</h2>
        {atipicos?.sinalizacao_suprimida ? (
          <p className="indisponivel">indisponível</p>
        ) : (
          <div className="cartoes">
            <Cartao rotulo="Sinalizadas na amostra" valor={textoContagem(contagemPublicavel(atipicos?.n_sinalizados_auto, limiar, atipicos))} />
            <Cartao rotulo="Percentual da amostra" valor={textoPercentual(numero(atipicos?.percentual_sinalizados_auto))} />
          </div>
        )}
        <p className="nota">
          Amostra de {numero(atipicos?.n_amostra_ml_evaluator) === null ? 'tamanho indisponível' : formatarInteiro(numero(atipicos?.n_amostra_ml_evaluator) ?? 0)}. Atípico é um padrão menos frequente na amostra, não um erro nem uma pessoa.
        </p>
      </section>
    </div>
  );
}

function fatia(doc: Record<string, unknown>, todos: boolean, uf: string, anual: string, historico: string): Record<string, unknown> | undefined {
  if (todos) {
    const bloco = doc[historico] as { period_total?: Record<string, unknown>; period_by_uf?: { uf: string }[] } | undefined;
    if (!bloco) return undefined;
    return uf === 'BR' ? bloco.period_total : (porUf(bloco.period_by_uf as { uf: string }[], uf) as Record<string, unknown> | undefined);
  }
  const bloco = doc[anual] as { brasil?: Record<string, unknown>; by_uf?: { uf: string }[] } | undefined;
  if (!bloco) return undefined;
  return uf === 'BR' ? bloco.brasil : (porUf(bloco.by_uf as { uf: string }[], uf) as Record<string, unknown> | undefined);
}

function textoNota(valor: number | null): string {
  return valor === null ? 'indisponível' : formatarNota(valor);
}
function textoPercentual(valor: number | null): string {
  return valor === null ? 'indisponível' : formatarPercentual(valor);
}
function textoContagem(valor: number | null): string {
  return valor === null ? 'indisponível' : formatarInteiro(valor);
}

function notaAmostra(valor: unknown): string {
  const n = numero(valor);
  const tamanho = n === null ? 'tamanho indisponível' : `${formatarInteiro(n)} avaliações`;
  return `Amostra de ${tamanho}. Os percentuais da amostra não são os da população.`;
}

function histograma(itens: Hist[] | undefined, limiar: number): { figura: Figura | null; omitidos: boolean } {
  if (!itens?.length) return { figura: null, omitidos: false };
  const linhas = [];
  let omitidos = false;
  for (const item of itens) {
    const n = contagemPublicavel(item.n_redacoes, limiar);
    if (n === null) {
      omitidos = true;
      continue;
    }
    const pct = numero(item.percentual);
    if (pct === null) continue;
    linhas.push({ faixa: item.faixa ?? '', pct });
  }
  if (!linhas.length) return { figura: null, omitidos };
  return {
    figura: {
      data: [{ type: 'bar', x: linhas.map((item) => item.faixa), y: linhas.map((item) => item.pct), marker: { color: COR }, hovertemplate: '%{x}<br>%{y:.2f}%<extra></extra>' }],
      altura: 380,
      layout: {
        margin: { b: 120 },
        xaxis: { tickangle: -35, title: { text: 'Diferença absoluta na nota total' } },
        yaxis: { title: { text: 'Avaliações (%)' } },
      },
    },
    omitidos,
  };
}

function diferencaCompetencia(itens: CompDif[] | undefined, limiar: number): Figura | null {
  if (!itens?.length) return null;
  const linhas = itens
    .map((item) => ({ nome: item.competencia ?? '', valor: metricaPublicavel(item.media, item.n_pares_validos, limiar) }))
    .filter((item) => item.valor !== null && item.nome);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.nome), y: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{x}: %{y:.1f} pontos<extra></extra>' }],
    altura: 320,
    layout: { yaxis: { title: { text: 'Diferença média (pontos)' }, range: [0, 80] } },
  };
}

function barrasKappa(mapa: Record<string, Kappa> | undefined, limiar: number): Figura | null {
  if (!mapa) return null;
  const linhas = ['C1', 'C2', 'C3', 'C4', 'C5']
    .map((codigo) => {
      const item = mapa[codigo];
      if (!item || (item.situacao && item.situacao !== 'ok')) return null;
      const valor = metricaPublicavel(item.kappa_ponderado_quadratico, item.n_pares_validos, limiar);
      return valor === null ? null : { codigo, valor };
    })
    .filter((item): item is { codigo: string; valor: number } => item !== null);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.codigo), y: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{x}: %{y:.3f}<extra></extra>' }],
    altura: 320,
    layout: { yaxis: { title: { text: 'Kappa quadrático' }, range: [0, 1] } },
  };
}

function perfisDivergencia(recorte: Record<string, unknown> | undefined): Figura | null {
  const clusters = recorte?.clusters as Cluster[] | undefined;
  if (!clusters?.length) return null;
  if (recorte?.situacao && recorte.situacao !== 'ok') return null;
  const data = clusters.map((cluster, indice) => {
    const pontos = cluster.centro_por_competencia ?? [];
    if (!pontos.length || pontos.some((ponto) => numero(ponto.diferenca_media_pontos) === null)) return null;
    const n = numero(cluster.n_amostra);
    return {
      type: 'scatter',
      mode: 'lines+markers',
      name: `${cluster.cluster_id ?? 'Perfil'}${n === null ? '' : ` · amostra ${formatarInteiro(n)}`}`,
      x: pontos.map((ponto) => ponto.competencia ?? ''),
      y: pontos.map((ponto) => ponto.diferenca_media_pontos),
      line: { color: CORES[indice % CORES.length] },
    };
  });
  if (data.some((item) => item === null)) return null;
  return {
    data: data as object[],
    altura: 440,
    layout: { margin: { b: 110 }, yaxis: { title: { text: 'Diferença média no centro (pontos)' } } },
  };
}
