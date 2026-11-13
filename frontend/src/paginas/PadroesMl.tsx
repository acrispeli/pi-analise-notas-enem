import { useState } from 'react';
import { COR, CORES, Grafico, type Figura } from '../grafico.tsx';
import { Aviso, Cartao, Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { formatarIndice, formatarInteiro, formatarNota, formatarPercentual, numero } from '../lib/formatar.ts';
import { metricaPublicavel } from '../lib/supressao.ts';

type Eixo = { eixo?: number; inercia_pct?: number; contribuicoes_variaveis_pct?: Record<string, number> };
type ModeloMca = {
  n_amostra?: number;
  inercia_acumulada_primeiros_eixos_pct?: number;
  dimensoes?: Eixo[];
};
type Perfil = { variavel?: string; categoria?: string; diferenca_aprox_pp?: number };
type Grupo = { cluster?: string; n_amostra?: number; participacao_aprox_pct?: number; perfil_exploratorio?: Perfil[] };
type ModeloCluster = {
  n_amostra?: number;
  k_selecionado?: number;
  metricas_k_escolhido?: { silhouette?: number; davies_bouldin?: number; calinski_harabasz?: number };
  clusters?: Grupo[];
};
type Ml = {
  status?: string;
  reason?: string;
  socio_mca?: { indicator_id?: string; data_status?: string; nota?: string; modelo_ano?: ModeloMca };
  socio_clusters?: { indicator_id?: string; data_status?: string; nota?: string; modelo_ano?: ModeloCluster };
};
type Linha = Record<string, unknown> & { ano?: number; status?: string; motivo?: string; cluster?: string };
type Pacote = { indicator_id?: string; status?: string; review?: string; results?: Linha[] };
type Perfis = { nota?: Pacote; competencias?: Pacote; alto?: Pacote; perdas?: Pacote; divergencia?: Pacote };

export default function PadroesMl() {
  const { ano, uf, limiar } = useFiltros();
  const pedido = useDados<Ml>(ano === 'todos' ? null : `/data/${ano}/ml.json`);
  const extra = useDados<Perfis>('/data/extra/perfis.json');
  const [grupo, setGrupo] = useState('C1');

  if (ano === 'todos') {
    return (
      <div data-visual="ml">
        <h1>Perfis</h1>
        <Aviso>Estes gráficos são de um ano e do Brasil. Escolha o ano. A mudança dos perfis ao longo do tempo está em Evolução.</Aviso>
      </div>
    );
  }
  if (pedido.carregando || pedido.erro || !pedido.dados) return <Estado carregando={pedido.carregando} erro={pedido.erro} />;
  if (uf !== 'BR') {
    return (
      <div data-visual="ml">
        <h1>Perfis</h1>
        <Aviso>Estes perfis são do Brasil. Não há recorte por estado.</Aviso>
      </div>
    );
  }

  const ml = pedido.dados;
  const mca = ml.socio_mca?.modelo_ano;
  const clusters = ml.socio_clusters?.modelo_ano;
  const grupos = clusters?.clusters ?? [];
  const ativo = grupos.find((item) => item.cluster === grupo) ?? grupos[0];
  const anoNumero = Number(ano);

  // Ausência dos modelos não deve gerar uma sequência de cartões e gráficos vazios.
  // Os indicadores IND-055–059 podem continuar disponíveis no pacote complementar.
  if (!mca && !clusters) {
    return (
      <div data-visual="ml">
        <h1>Perfis</h1>
        <Aviso>Os modelos exploratórios do questionário (IND-053 e IND-054) não estão disponíveis para {ano}. Os resultados complementares, quando existentes, aparecem abaixo.</Aviso>
        <PerfisAmostra extra={extra.dados} ano={anoNumero} limiar={limiar} carregando={extra.carregando} erro={extra.erro} />
      </div>
    );
  }

  return (
    <div data-visual="ml">
      <h1>Perfis</h1>
      <p className="nota">Amostra de {mca?.n_amostra ? formatarInteiro(mca.n_amostra) : 'tamanho não disponível'} redações deste ano. Os grupos daqui não são os mesmos da série em Evolução.</p>
      <div className="cartoes">
        <Cartao rotulo="Eixos do questionário" valor={mca?.dimensoes?.length ? String(mca.dimensoes.length) : 'não disponível'} detalhe={mca?.inercia_acumulada_primeiros_eixos_pct ? `${formatarPercentual(mca.inercia_acumulada_primeiros_eixos_pct)} da variação` : undefined} />
        <Cartao rotulo="Grupos deste ano" valor={clusters?.k_selecionado ? String(clusters.k_selecionado) : 'não disponível'} detalhe="Nomes locais. Não são os três perfis da série histórica." />
        <Cartao rotulo="Separação dos grupos" valor={clusters?.metricas_k_escolhido?.silhouette ? formatarIndice(clusters.metricas_k_escolhido.silhouette) : 'não disponível'} detalhe="De 0 a 1. Mais alto, grupos mais distintos." />
      </div>
      <Grafico identificador="ind053-eixos" titulo="Quanto cada eixo resume o questionário?" figura={barrasEixos(mca?.dimensoes)} nota="Parte da variação das respostas que cada eixo concentra." />
      <Grafico identificador="ind053-variaveis" titulo="Quais perguntas mais pesam no primeiro eixo?" figura={barrasContribuicao(mca?.dimensoes?.[0])} />
      <Grafico identificador="ind054-tamanho" titulo="Qual é o tamanho de cada grupo?" figura={barrasGrupos(grupos)} nota="O percentual é aproximado." />
      {ativo ? (
        <section className="painel" data-visual="ind054-perfil">
          <h2>O que distingue o grupo escolhido na amostra?</h2>
          <label className="seletor">
            Grupo
            <select value={ativo.cluster} onChange={(evento) => setGrupo(evento.target.value)}>
              {grupos.map((item) => (
                <option key={item.cluster} value={item.cluster}>{item.cluster}</option>
              ))}
            </select>
          </label>
          <Grafico identificador="ind054-perfil-grafico" titulo="" figura={barrasPerfil(ativo.perfil_exploratorio)} embutido />
          <p className="nota">Diferença, em pontos percentuais, entre o grupo e a amostra inteira.</p>
        </section>
      ) : null}
      <PerfisAmostra extra={extra.dados} ano={anoNumero} limiar={limiar} carregando={extra.carregando} erro={extra.erro} />
    </div>
  );
}

function PerfisAmostra({ extra, ano, limiar, carregando, erro }: { extra: Perfis | null; ano: number; limiar: number; carregando: boolean; erro: boolean }) {
  if (carregando) return <Estado carregando erro={false} />;
  if (erro || !extra) return <Grafico identificador="ind055" titulo="Qual é a nota média de cada perfil de referência?" figura={null} />;
  const nota = linhasDoAno(extra.nota?.results, ano);
  const bloqueio = nota.find((item) => item.status === 'nao_aplicavel');
  if (bloqueio) {
    return <Aviso>Em 2025 não há ligação entre a nota e o questionário. Os perfis não são cruzados com a nota.</Aviso>;
  }
  const competencias = linhasDoAno(extra.competencias?.results, ano);
  const alto = linhasDoAno(extra.alto?.results, ano);
  const perdas = linhasDoAno(extra.perdas?.results, ano);
  const divergencia = linhasDoAno(extra.divergencia?.results, ano);
  const aviso = 'Amostra. A diferença entre perfis descreve os grupos e não é causa da nota.';
  return (
    <>
      <Grafico identificador="ind055" titulo="Qual é a nota média de cada perfil?" figura={barrasCampo(nota, 'media', limiar, 'n')} nota={aviso} />
      <Grafico identificador="ind056" titulo="Como a média de cada competência varia entre os perfis?" figura={mapaPerfil(competencias, 'media', limiar, 'n')} nota={aviso} />
      <Grafico identificador="ind057" titulo="Qual parte de cada perfil está entre as notas mais altas?" figura={barrasCampo(alto, 'percentual_high', limiar, 'n_notas_validas', [0, 100])} nota={aviso} />
      <Grafico identificador="ind058" titulo="Quantos pontos faltam, em média, em cada competência?" figura={mapaPerfil(perdas, 'perda_media', limiar, 'n_near_cluster')} nota={aviso} />
      <Grafico identificador="ind059" titulo="Qual é a diferença média entre os corretores em cada perfil?" figura={barrasCampo(divergencia, 'media_diferenca_absoluta', limiar, 'n_pareadas')} nota={aviso} />
    </>
  );
}

function linhasDoAno(lista: Linha[] | undefined, ano: number): Linha[] {
  return (lista ?? []).filter((item) => item.ano === ano);
}

function barrasEixos(eixos: Eixo[] | undefined): Figura | null {
  if (!eixos?.length) return null;
  return {
    data: [{ type: 'bar', x: eixos.map((item) => `Eixo ${item.eixo}`), y: eixos.map((item) => numero(item.inercia_pct)), marker: { color: COR }, hovertemplate: '%{x}<br>%{y:.1f}%<extra></extra>' }],
    altura: 320,
    layout: { yaxis: { title: { text: 'Parte da variação (%)' } }, xaxis: { title: { text: 'Eixo' } } },
  };
}

function barrasContribuicao(eixo: Eixo | undefined): Figura | null {
  const pares = Object.entries(eixo?.contribuicoes_variaveis_pct ?? {})
    .map(([nome, valor]) => ({ nome, valor: numero(valor) }))
    .filter((item): item is { nome: string; valor: number } => item.valor !== null)
    .sort((a, b) => b.valor - a.valor);
  if (!pares.length) return null;
  return {
    data: [{ type: 'bar', orientation: 'h', y: pares.map((item) => item.nome).reverse(), x: pares.map((item) => item.valor).reverse(), marker: { color: COR }, hovertemplate: '%{y}<br>%{x:.1f}%<extra></extra>' }],
    altura: Math.max(360, pares.length * 22),
    layout: { margin: { l: 72 }, xaxis: { title: { text: 'Peso da pergunta (%)' } } },
  };
}

function barrasGrupos(grupos: Grupo[]): Figura | null {
  if (!grupos.length) return null;
  return {
    data: [{
      type: 'bar',
      x: grupos.map((item) => item.cluster),
      y: grupos.map((item) => numero(item.n_amostra)),
      text: grupos.map((item) => (item.participacao_aprox_pct ? `${formatarInteiro(item.participacao_aprox_pct)}%` : '')),
      textposition: 'outside',
      marker: { color: CORES[6] },
      hovertemplate: '%{x}<br>%{y}<extra></extra>',
    }],
    altura: 340,
    layout: { yaxis: { title: { text: 'Participações' } }, margin: { t: 28 } },
  };
}

function barrasPerfil(perfil: Perfil[] | undefined): Figura | null {
  const linhas = (perfil ?? [])
    .map((item) => ({ nome: `${item.variavel ?? ''} ${item.categoria ?? ''}`.trim(), valor: numero(item.diferenca_aprox_pp) }))
    .filter((item) => item.nome && item.valor !== null);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', orientation: 'h', y: linhas.map((item) => item.nome), x: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{y}<br>%{x:.0f} p.p.<extra></extra>' }],
    altura: Math.max(280, linhas.length * 36),
    layout: { margin: { l: 88 }, xaxis: { title: { text: 'Diferença aproximada (p.p.)' } } },
  };
}

function barrasCampo(linhas: Linha[], campo: string, limiar: number, denominador: string, intervalo?: [number, number]): Figura | null {
  const pontos = linhas
    .filter((item) => item.cluster)
    .map((item) => ({ nome: String(item.cluster), valor: metricaPublicavel(item[campo], item[denominador], limiar, item) }));
  if (!pontos.length || pontos.every((item) => item.valor === null)) return null;
  return {
    data: [{ type: 'bar', x: pontos.map((item) => item.nome), y: pontos.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{x}<br>%{y:.1f}<extra></extra>' }],
    altura: 320,
    layout: { yaxis: { title: { text: 'Nota ou percentual' }, range: intervalo }, xaxis: { title: { text: 'Perfil' } } },
  };
}

function mapaPerfil(linhas: Linha[], campo: string, limiar: number, denominador: string): Figura | null {
  const grupos = [...new Set(linhas.map((item) => item.cluster).filter(Boolean))] as string[];
  const competencias = ['C1', 'C2', 'C3', 'C4', 'C5'];
  if (!grupos.length) return null;
  const z = grupos.map((grupo) => competencias.map((competencia) => {
    const item = linhas.find((linha) => linha.cluster === grupo && linha.competencia === competencia);
    if (!item) return null;
    return metricaPublicavel(item[campo], item[denominador], limiar, item);
  }));
  if (z.every((linha) => linha.every((valor) => valor === null))) return null;
  const texto = z.map((linha) => linha.map((valor) => (valor === null ? '' : formatarNota(valor))));
  return {
    data: [{ type: 'heatmap', x: competencias, y: grupos, z, text: texto, texttemplate: '%{text}', colorscale: 'Blues', hovertemplate: '%{y} · %{x}: %{z:.1f}<extra></extra>' }],
    altura: Math.max(320, grupos.length * 48),
    layout: { margin: { l: 72, b: 48 } },
  };
}
