import { useState } from 'react';
import { COR, CORES, Grafico, type Figura } from '../grafico.tsx';
import { Aviso, Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { formatarNota, numero } from '../lib/formatar.ts';
import { contagemPublicavel, metricaPublicavel, porUf } from '../lib/supressao.ts';

type CategoriaPerfil = { codigo?: string; rotulo?: string; quantidade?: number; percentual?: number; requires_privacy_review?: boolean };
type Questao = { questao?: string; tema?: string; categorias?: CategoriaPerfil[]; tem_agregacao_para_privacidade?: boolean };
type FaixaRenda = { codigo_renda?: string; faixa_renda?: string; descricao_faixa?: string; ordem?: number; n_redacoes?: number; media?: number; n_pequeno?: boolean; competencias?: Record<string, { media?: number; n_redacoes?: number }> };
type FaixaEscola = { codigo_escolaridade?: string; descricao_categoria?: string; ordem?: number; n_redacoes?: number; media?: number; n_pequeno?: boolean; suprimido?: boolean };
type CatCompetencia = {
  codigo_escolaridade?: string;
  descricao_categoria?: string;
  ordem?: number;
  n_redacoes?: number;
  suprimido?: boolean;
  competencias?: Record<string, { media?: number; mediana?: number; n_redacoes?: number }>;
};
type EscolaCompetencias = { questions?: Record<string, { responsavel?: string; categories?: CatCompetencia[] }> };
type TipoEscola = { categories?: (FaixaEscola & { codigo_escola?: string })[]; conceito?: string; source_variable?: string };

type Socio = {
  status?: string;
  profile?: {
    versao_questionario?: string;
    brasil?: { questoes?: Questao[]; n_participacoes?: number };
    ufs?: { uf: string; questoes?: Questao[] }[];
  };
  income_total?: { national?: Renda; states?: Record<string, Renda>; source_question?: string };
  income_competencies?: { national?: Renda; states?: Record<string, Renda> };
  parent_education_total?: { national?: Escola; states?: Record<string, Escola> };
  parent_education_competencies?: { national?: EscolaCompetencias; states?: Record<string, EscolaCompetencias> };
  school_type_total?: { national?: TipoEscola; states?: Record<string, TipoEscola>; source_variable?: string };
};
type Renda = { faixas?: FaixaRenda[]; categories?: FaixaRenda[] };
type Escola = { questions?: Record<string, { responsavel?: string; categories?: FaixaEscola[] }> };

export default function Socioeconomico() {
  const { ano, uf, limiar } = useFiltros();
  const todos = ano === 'todos';
  const pedido = useDados<Socio>(todos ? null : `/data/${ano}/socioeconomic.json`);
  const [questao, setQuestao] = useState('Q001');
  const [guardiao, setGuardiao] = useState<'Q001' | 'Q002'>('Q001');

  if (todos) {
    return (
      <div>
        <h1>Socioeconômico</h1>
        <Aviso>Os questionários de 2019–2023 e de 2024–2025 não são juntados. Selecione um ano.</Aviso>
        <Grafico identificador="perfil" titulo="Como se distribuem as respostas do questionário?" figura={null} />
        <Grafico identificador="renda-nota" titulo="Qual é a nota média em cada faixa de renda?" figura={null} />
        <Grafico identificador="renda-competencia" titulo="Como a média de cada competência varia com a renda?" figura={null} />
        <Grafico identificador="escolaridade" titulo="Qual é a nota média segundo a escolaridade dos responsáveis?" figura={null} />
      </div>
    );
  }
  if (pedido.carregando || pedido.erro || !pedido.dados) return <Estado carregando={pedido.carregando} erro={pedido.erro} />;

  const doc = pedido.dados;
  const perfil = uf === 'BR' ? doc.profile?.brasil : porUf(doc.profile?.ufs, uf);
  const questoes = perfil?.questoes ?? [];
  const escolhida = questoes.find((item) => item.questao === questao) ?? questoes[0];
  const temCruzamento = Boolean(doc.income_total && doc.income_competencies && doc.parent_education_total);
  const renda = uf === 'BR' ? doc.income_total?.national : doc.income_total?.states?.[uf];
  const rendaComp = uf === 'BR' ? doc.income_competencies?.national : doc.income_competencies?.states?.[uf];
  const escola = uf === 'BR' ? doc.parent_education_total?.national : doc.parent_education_total?.states?.[uf];

  return (
    <div>
      <h1>Socioeconômico</h1>
      <p className="nota">Versão do questionário: {doc.profile?.versao_questionario ?? 'indisponível'}.</p>
      <section className="painel" data-visual="perfil">
        <h2>Como se distribuem as respostas do questionário?</h2>
        {questoes.length && escolhida ? (
          <>
            <label className="seletor">
              Pergunta
              <select value={escolhida.questao} onChange={(evento) => setQuestao(evento.target.value)}>
                {questoes.map((item) => (
                  <option key={item.questao} value={item.questao}>
                    {item.questao} — {item.tema}
                  </option>
                ))}
              </select>
            </label>
            <UmGrafico identificador="perfil-grafico" figura={graficoPerfil(escolhida, limiar)} />
            <p className="nota">
              Os rótulos são os códigos publicados no questionário.
              {escolhida.tem_agregacao_para_privacidade ? ' Há categorias reunidas por proteção de privacidade.' : ''}
            </p>
          </>
        ) : (
          <p className="indisponivel">indisponível</p>
        )}
      </section>
      {temCruzamento ? (
        <>
          <Grafico identificador="renda-nota" titulo="Qual é a nota média em cada faixa de renda?" figura={graficoRenda(renda, limiar)} nota={`Questão ${doc.income_total?.source_question ?? ''}. Os limites monetários são os desta edição. Passe o cursor para ler a faixa.`} />
          <Grafico identificador="renda-competencia" titulo="Como a média de cada competência varia com a renda?" figura={graficoRendaCompetencia(rendaComp, limiar)} />
          <section className="painel" data-visual="escolaridade">
            <h2>Qual é a nota média segundo a escolaridade dos responsáveis?</h2>
            <label className="seletor">
              Responsável
              <select value={guardiao} onChange={(evento) => setGuardiao(evento.target.value as 'Q001' | 'Q002')}>
                <option value="Q001">{escola?.questions?.Q001?.responsavel ?? 'Q001'}</option>
                <option value="Q002">{escola?.questions?.Q002?.responsavel ?? 'Q002'}</option>
              </select>
            </label>
            <UmGrafico identificador="escolaridade-grafico" figura={graficoEscola(escola?.questions?.[guardiao]?.categories, limiar)} />
          </section>
          <EscolaridadeCompetencias doc={doc} uf={uf} guardiao={guardiao} definirGuardiao={setGuardiao} limiar={limiar} />
          <TipoEscolaGrafico doc={doc} uf={uf} limiar={limiar} />
        </>
      ) : (
        <>
          <Aviso>Em 2025 a página só tem o perfil. Renda, escolaridade e tipo de escola cruzados com a nota não foram estimados.</Aviso>
          <Grafico identificador="renda-nota" titulo="Qual é a nota média em cada faixa de renda?" figura={null} />
          <Grafico identificador="renda-competencia" titulo="Como a média de cada competência varia com a renda?" figura={null} />
          <Grafico identificador="escolaridade" titulo="Qual é a nota média segundo a escolaridade dos responsáveis?" figura={null} />
        </>
      )}
    </div>
  );
}

function EscolaridadeCompetencias({
  doc,
  uf,
  guardiao,
  definirGuardiao,
  limiar,
}: {
  doc: Socio;
  uf: string;
  guardiao: 'Q001' | 'Q002';
  definirGuardiao: (valor: 'Q001' | 'Q002') => void;
  limiar: number;
}) {
  const bloco = uf === 'BR' ? doc.parent_education_competencies?.national : doc.parent_education_competencies?.states?.[uf];
  if (!bloco) return <Grafico identificador="ind044" titulo="Como a escolaridade dos responsáveis se relaciona com cada competência?" figura={null} />;
  const pergunta = bloco.questions?.[guardiao];
  return (
    <section className="painel" data-visual="ind044">
      <h2>Como a escolaridade dos responsáveis se relaciona com cada competência?</h2>
      <label className="seletor">
        Responsável
        <select value={guardiao} onChange={(evento) => definirGuardiao(evento.target.value as 'Q001' | 'Q002')}>
          <option value="Q001">{bloco.questions?.Q001?.responsavel ?? 'Q001'}</option>
          <option value="Q002">{bloco.questions?.Q002?.responsavel ?? 'Q002'}</option>
        </select>
      </label>
      <UmGrafico identificador="ind044-grafico" figura={graficoEscolaCompetencias(pergunta?.categories, limiar)} />
      <p className="nota">Média publicada de 0 a 200. Categoria suprimida não entra como zero.</p>
    </section>
  );
}

function TipoEscolaGrafico({ doc, uf, limiar }: { doc: Socio; uf: string; limiar: number }) {
  const bloco = uf === 'BR' ? doc.school_type_total?.national : doc.school_type_total?.states?.[uf];
  return (
    <Grafico
      identificador="ind045"
      titulo="Qual é a nota média segundo a trajetória escolar declarada?"
      figura={graficoEscola(bloco?.categories, limiar)}
      nota={`Variável ${doc.school_type_total?.source_variable ?? bloco?.conceito ?? 'Q023'}. As categorias de 2019–2023 e de 2024 não são juntadas.`}
    />
  );
}

function UmGrafico({ figura, identificador }: { figura: Figura | null; identificador: string }) {
  return <Grafico identificador={identificador} titulo="" figura={figura} embutido />;
}

function graficoPerfil(questao: Questao, limiar: number): Figura | null {
  const linhas = [];
  for (const categoria of questao.categorias ?? []) {
    const n = contagemPublicavel(categoria.quantidade, limiar, categoria);
    const pct = numero(categoria.percentual);
    if (n === null || pct === null) continue;
    linhas.push({ rotulo: categoria.rotulo || categoria.codigo || '', pct });
  }
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', orientation: 'h', y: linhas.map((item) => item.rotulo), x: linhas.map((item) => item.pct), marker: { color: COR }, hovertemplate: '%{y}: %{x:.1f}%<extra></extra>' }],
    altura: Math.max(280, linhas.length * 32),
    layout: { margin: { l: 220 }, xaxis: { title: { text: 'Participações (%)' } } },
  };
}

function faixasRenda(renda: Renda | undefined, limiar: number): { codigo: string; descricao: string; media: number | null; competencias?: FaixaRenda['competencias']; ordem: number }[] {
  const lista = [...(renda?.faixas ?? renda?.categories ?? [])].sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0));
  return lista.map((faixa) => ({
    codigo: faixa.faixa_renda || faixa.codigo_renda || '',
    descricao: faixa.descricao_faixa || '',
    media: metricaPublicavel(faixa.media, faixa.n_redacoes, limiar, faixa),
    competencias: faixa.competencias,
    ordem: faixa.ordem ?? 0,
  }));
}

function graficoRenda(renda: Renda | undefined, limiar: number): Figura | null {
  const linhas = faixasRenda(renda, limiar).filter((item) => item.media !== null && item.codigo);
  if (!linhas.length) return null;
  return {
    data: [{
      type: 'bar',
      x: linhas.map((item) => item.codigo),
      y: linhas.map((item) => item.media),
      customdata: linhas.map((item) => item.descricao),
      marker: { color: COR },
      hovertemplate: '%{x}<br>%{customdata}<br>%{y:.1f}<extra></extra>',
    }],
    altura: 360,
    layout: { xaxis: { title: { text: 'Faixa de renda' } }, yaxis: { title: { text: 'Nota média' }, range: [0, 1000] } },
  };
}

function graficoRendaCompetencia(renda: Renda | undefined, limiar: number): Figura | null {
  const base = faixasRenda(renda, limiar).filter((item) => item.codigo);
  if (!base.length) return null;
  const data = ['C1', 'C2', 'C3', 'C4', 'C5'].map((codigo, indice) => ({
    type: 'scatter',
    mode: 'lines+markers',
    name: codigo,
    x: base.map((item) => item.codigo),
    y: base.map((item) => {
      const celula = item.competencias?.[codigo];
      if (!celula || item.media === null) return null;
      return metricaPublicavel(celula.media, celula.n_redacoes, limiar);
    }),
    line: { color: CORES[indice % CORES.length] },
    connectgaps: false,
  }));
  if (data.every((traco) => (traco.y as (number | null)[]).every((valor) => valor === null))) return null;
  return {
    data,
    altura: 440,
    layout: {
      margin: { b: 100 },
      yaxis: { title: { text: 'Nota média da competência' }, range: [0, 200] },
      xaxis: { title: { text: 'Faixa de renda' } },
    },
  };
}

function graficoEscola(categorias: FaixaEscola[] | undefined, limiar: number): Figura | null {
  if (!categorias?.length) return null;
  const linhas = [...categorias]
    .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
    .map((item) => ({
      nome: item.descricao_categoria || item.codigo_escolaridade || '',
      media: metricaPublicavel(item.media, item.n_redacoes, limiar, item),
    }))
    .filter((item) => item.media !== null && item.nome);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.nome), y: linhas.map((item) => item.media), marker: { color: COR }, hovertemplate: '%{x}<br>%{y:.1f}<extra></extra>' }],
    altura: 360,
    layout: { margin: { b: 128 }, yaxis: { title: { text: 'Nota média' }, range: [0, 1000] }, xaxis: { tickangle: -35 } },
  };
}

function graficoEscolaCompetencias(categorias: CatCompetencia[] | undefined, limiar: number): Figura | null {
  if (!categorias?.length) return null;
  const linhas = [...categorias].sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0));
  const y = linhas.map((item) => item.descricao_categoria || item.codigo_escolaridade || '');
  const x = ['C1', 'C2', 'C3', 'C4', 'C5'];
  const z = linhas.map((item) => x.map((codigo) => {
    if (item.suprimido) return null;
    const celula = item.competencias?.[codigo];
    if (!celula) return null;
    return metricaPublicavel(celula.media, celula.n_redacoes ?? item.n_redacoes, limiar, item);
  }));
  if (z.every((linha) => linha.every((valor) => valor === null))) return null;
  const texto = z.map((linha) => linha.map((valor) => (valor === null ? '' : formatarNota(valor))));
  return {
    data: [{ type: 'heatmap', x, y, z, text: texto, texttemplate: '%{text}', colorscale: 'Blues', zmin: 0, zmax: 200, hovertemplate: '%{y} · %{x}: %{z:.1f}<extra></extra>' }],
    altura: Math.max(420, y.length * 28),
    layout: { margin: { l: 220, b: 48 } },
  };
}
