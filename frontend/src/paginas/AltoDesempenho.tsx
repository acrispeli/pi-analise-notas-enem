import { useState } from 'react';
import { COR, Grafico, type Figura } from '../grafico.tsx';
import { Aviso, Cartao, Estado } from '../layout.tsx';
import { useFiltros } from '../filtros.tsx';
import { useDados } from '../useDados.ts';
import { formatarIndice, formatarInteiro, formatarNota, formatarPercentual, numero } from '../lib/formatar.ts';
import { contagemPublicavel, metricaPublicavel, porUf } from '../lib/supressao.ts';

type Faixa = { faixa?: string; quantidade?: number; percentual?: number; n_redacoes?: number };
type Perda = { competencia?: string; media_perda?: number; n_redacoes?: number };
type Comp = Record<string, unknown>;
type Recorte = Record<string, unknown>;

export default function AltoDesempenho() {
  const { ano, uf, limiar } = useFiltros();
  const todos = ano === 'todos';
  const anual = useDados<Record<string, unknown>>(todos ? null : `/data/${ano}/high_performance.json`);
  const temporal = useDados<Record<string, unknown>>(todos ? '/data/temporal.json' : null);
  const fonte = todos ? temporal : anual;
  const [tipoCombinacao, setTipoCombinacao] = useState('par');
  const [familia, setFamilia] = useState<'ocorrencia' | 'magnitude'>('ocorrencia');
  if (fonte.carregando || fonte.erro || !fonte.dados) return <Estado carregando={fonte.carregando} erro={fonte.erro} />;

  const faixas = fatia(fonte.dados, todos, uf, 'score_bands', 'ind030');
  const perda = fatia(fonte.dados, todos, uf, 'loss_by_competency', 'ind031');
  const nHigh = contagemPublicavel(faixas?.n_high, limiar);
  const pctHigh = nHigh === null ? null : numero(faixas?.percentual_high_sobre_validas);
  const nNear = contagemPublicavel(perda?.n_near, limiar);
  const desconto = todos ? undefined : fatia(fonte.dados, false, uf, 'discount_frequency', '');
  const participacao = todos ? undefined : fatia(fonte.dados, false, uf, 'loss_share', '');
  const unica = todos ? undefined : fatia(fonte.dados, false, uf, 'single_blocker', '');
  const combinacoes = todos ? undefined : fatia(fonte.dados, false, uf, 'co_loss_patterns', '');
  const regras = todos ? undefined : fatia(fonte.dados, false, uf, 'association_rules', '');
  const testes = todos ? undefined : fatia(fonte.dados, false, uf, 'tests', '');
  const mapa = todos ? undefined : fatia(fonte.dados, false, uf, 'score_competency_heatmap', '');
  const concordancia = todos ? [] : listaConcordancia(fonte.dados.reviewer_agreement, uf);

  return (
    <div>
      <h1>Notas altas</h1>
      <p className="nota">C1 escrita formal · C2 tema · C3 argumentação · C4 coesão · C5 proposta de intervenção</p>
      {todos ? <Aviso>Os gráficos de desconto são de um ano só. Escolha o ano. Os dois números e os dois gráficos de cima valem para o período inteiro.</Aviso> : null}
      <div className="cartoes">
        <Cartao rotulo="Redações de 900 a 1000" valor={nHigh === null ? 'não disponível' : formatarInteiro(nHigh)} detalhe={pctHigh === null ? undefined : formatarPercentual(pctHigh)} />
        <Cartao rotulo="Redações de 900 a 980" valor={nNear === null ? 'não disponível' : formatarInteiro(nNear)} />
      </div>
      <div className="grade-2">
        <Grafico identificador="faixas-900" titulo="Como se distribuem as notas de 900 a 1000?" figura={graficoFaixas(faixas?.faixas as Faixa[] | undefined, limiar)} />
        <Grafico identificador="perda" titulo="Quantos pontos faltam, em média, em cada competência?" figura={graficoPerda(perda?.resumo_competencias as Perda[] | undefined, limiar)} nota="A perda é calculada nas redações de 900 a 980, sem a nota 1000." />
      </div>
      {todos ? null : (
        <>
          <Grafico identificador="ind032" titulo="Em qual competência o desconto é mais frequente?" figura={barrasCompetencia(desconto?.resumo_competencias as Comp[] | undefined, 'percentual_desconto', 'n_redacoes', limiar, 'Redações com desconto (%)')} nota="Nas redações de 900 a 980. Grupo pequeno demais não entra como zero." />
          <Grafico identificador="ind033" titulo="Qual competência concentra a perda de pontos?" figura={barrasCompetencia(participacao?.resumo_competencias as Comp[] | undefined, 'percentual_participacao', 'n_redacoes', limiar, 'Participação na perda (%)')} />
          <div className="cartoes">
            <Cartao rotulo="Uma única competência abaixo de 200" valor={textoContagem(unica?.n_casos_com_uma_unica_competencia, limiar, unica)} detalhe={textoPercentual(unica?.percentual_casos_unicos_na_pop_near, unica?.n_near, limiar)} />
          </div>
          <Grafico identificador="ind034" titulo="Qual competência, sozinha, impede a nota 1000?" figura={barrasCompetencia(unica?.resumo_competencias as Comp[] | undefined, 'percentual_entre_casos_unicos', 'n_competencia_unica', limiar, 'Entre os casos de competência única (%)')} />
          <section className="painel" data-visual="ind035">
            <h2>Quais competências perdem pontos juntas?</h2>
            <label className="seletor">
              Tipo de combinação
              <select value={tipoCombinacao} onChange={(evento) => setTipoCombinacao(evento.target.value)}>
                <option value="par">Pares</option>
                <option value="trio">Trios</option>
              </select>
            </label>
            <Grafico identificador="ind035-grafico" titulo="" embutido figura={graficoCombinacoes(combinacoes?.combinacoes as Comp[] | undefined, tipoCombinacao, limiar)} nota="Uma redação com três descontos também entra nos pares." />
          </section>
          <Grafico identificador="ind036" titulo="Quais descontos aparecem juntos acima do acaso?" figura={graficoRegras(regras, limiar)} nota="Quanto maior a barra, mais a combinação supera o que seria esperado ao acaso." />
          <Testes testes={testes} familia={familia} onFamilia={setFamilia} />
          <Grafico identificador="ind038" titulo="Os dois corretores concordam sobre o desconto?" figura={graficoConcordancia(concordancia, limiar)} nota="Os dois marcaram a competência abaixo de 200, nas redações de 900 a 980." />
          <Grafico identificador="ind039" titulo="Em qual faixa de 900 a 1000 cada competência ainda perde pontos?" figura={graficoMapa(mapa, limiar)} nota="A nota 1000 entra na última faixa. Grupo pequeno demais não aparece como zero." />
        </>
      )}
    </div>
  );
}

function Testes({ testes, familia, onFamilia }: { testes: Recorte | undefined; familia: 'ocorrencia' | 'magnitude'; onFamilia: (valor: 'ocorrencia' | 'magnitude') => void }) {
  const bloco = testes?.tests as Record<string, unknown> | undefined;
  const ocorrencia = bloco?.ocorrencia as Comp | undefined;
  const magnitude = bloco?.magnitude as Comp | undefined;
  const linhas = (familia === 'ocorrencia' ? bloco?.pos_testes_ocorrencia : bloco?.pos_testes_magnitude) as Comp[] | undefined;
  return (
    <section className="painel" data-visual="ind037">
      <h2>As competências descontadas diferem entre si?</h2>
      <div className="cartoes">
        <Cartao rotulo="O desconto muda de competência?" valor={textoEstatistica(ocorrencia?.estatistica)} detalhe={textoP(ocorrencia?.p_valor)} />
        <Cartao rotulo="O tamanho da perda muda?" valor={textoEstatistica(magnitude?.estatistica)} detalhe={textoP(magnitude?.p_valor)} />
      </div>
      <label className="seletor">
        Comparação
        <select value={familia} onChange={(evento) => onFamilia(evento.target.value as 'ocorrencia' | 'magnitude')}>
          <option value="ocorrencia">Quem recebe desconto</option>
          <option value="magnitude">Quantos pontos faltam</option>
        </select>
      </label>
      <TabelaTestes linhas={linhas} />
      <p className="nota">Um valor de p igual a zero, na prática, está abaixo do que o cálculo consegue registrar.</p>
    </section>
  );
}

function TabelaTestes({ linhas }: { linhas: Comp[] | undefined }) {
  if (!linhas?.length) return <p className="indisponivel">não disponível</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>Par</th>
          <th>Margem de acaso</th>
          <th>Diferença real a 5%?</th>
        </tr>
      </thead>
      <tbody>
        {linhas.map((linha) => {
          const par = `${linha.competencia_a ?? ''} × ${linha.competencia_b ?? ''}`;
          const oculto = linha.contagens_suprimidas === true || linha.suprimido === true;
          return (
            <tr key={par}>
              <td>{par}</td>
              <td>{oculto ? 'não disponível' : textoP(linha.p_ajustado_holm)}</td>
              <td>{oculto ? 'não disponível' : linha.significativo_5pct === true ? 'sim' : linha.significativo_5pct === false ? 'não' : 'não disponível'}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function fatia(doc: Record<string, unknown>, todos: boolean, uf: string, anual: string, historico: string): Recorte | undefined {
  if (todos) {
    const bloco = doc[historico] as { period_total?: Recorte; period_by_uf?: { uf: string }[] } | undefined;
    if (!bloco) return undefined;
    return uf === 'BR' ? bloco.period_total : (porUf(bloco.period_by_uf as { uf: string }[], uf) as Recorte | undefined);
  }
  const bloco = doc[anual] as { brasil?: Recorte; by_uf?: { uf: string }[] } | undefined;
  if (!bloco) return undefined;
  return uf === 'BR' ? bloco.brasil : (porUf(bloco.by_uf as { uf: string }[], uf) as Recorte | undefined);
}

function listaConcordancia(valor: unknown, uf: string): Comp[] {
  if (!Array.isArray(valor)) return [];
  return valor.filter((item) => item && typeof item === 'object' && (item as Comp).uf === uf) as Comp[];
}

function textoContagem(valor: unknown, limiar: number, item?: unknown): string {
  const n = contagemPublicavel(valor, limiar, item);
  return n === null ? 'não disponível' : formatarInteiro(n);
}

function textoPercentual(valor: unknown, denominador: unknown, limiar: number): string | undefined {
  const n = metricaPublicavel(valor, denominador, limiar);
  return n === null ? undefined : formatarPercentual(n);
}

function textoEstatistica(valor: unknown): string {
  const n = numero(valor);
  if (n === null) return 'não disponível';
  return n >= 100 ? formatarInteiro(n) : formatarNota(n);
}

function textoP(valor: unknown): string {
  const n = numero(valor);
  if (n === null) return 'não disponível';
  if (n === 0) return 'abaixo do que o cálculo registra';
  if (n < 0.001) return n.toExponential(2).replace('.', ',');
  return formatarIndice(n);
}

function barrasCompetencia(itens: Comp[] | undefined, campo: string, denominador: string, limiar: number, eixo: string): Figura | null {
  if (!itens?.length) return null;
  const linhas = itens
    .map((item) => ({
      nome: String(item.competencia ?? ''),
      valor: metricaPublicavel(item[campo], item[denominador], limiar, item),
    }))
    .filter((item) => item.nome && item.valor !== null);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.nome), y: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{x}: %{y:.2f}<extra></extra>' }],
    altura: 340,
    layout: { yaxis: { title: { text: eixo } } },
  };
}

function graficoFaixas(faixas: Faixa[] | undefined, limiar: number): Figura | null {
  if (!faixas?.length) return null;
  const linhas = [];
  for (const faixa of faixas) {
    const n = contagemPublicavel(faixa.quantidade, limiar, faixa);
    const pct = numero(faixa.percentual);
    if (n === null || pct === null) return null;
    linhas.push({ faixa: faixa.faixa ?? '', pct });
  }
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.faixa), y: linhas.map((item) => item.pct), marker: { color: COR }, hovertemplate: '%{x}<br>%{y:.2f}%<extra></extra>' }],
    altura: 340,
    layout: { margin: { b: 96 }, yaxis: { title: { text: 'Participação na faixa alta (%)' } }, xaxis: { tickangle: -35 } },
  };
}

function graficoPerda(itens: Perda[] | undefined, limiar: number): Figura | null {
  if (!itens?.length) return null;
  const linhas = itens
    .map((item) => ({ nome: item.competencia ?? '', valor: metricaPublicavel(item.media_perda, item.n_redacoes, limiar) }))
    .filter((item) => item.valor !== null && item.nome);
  if (linhas.length !== itens.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.nome), y: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{x}: %{y:.1f} pontos<extra></extra>' }],
    altura: 340,
    layout: { yaxis: { title: { text: 'Perda média (pontos)' } } },
  };
}

function graficoCombinacoes(itens: Comp[] | undefined, tipo: string, limiar: number): Figura | null {
  const linhas = (itens ?? [])
    .filter((item) => item.tipo === tipo)
    .map((item) => ({
      nome: String(item.combinacao ?? ''),
      valor: metricaPublicavel(item.percentual_pop_near, item.n_redacoes_com_desconto_conjunto, limiar, item),
    }))
    .filter((item) => item.nome && item.valor !== null);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', orientation: 'h', y: linhas.map((item) => item.nome), x: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{y}: %{x:.2f}%<extra></extra>' }],
    altura: Math.max(320, linhas.length * 28),
    layout: { margin: { l: 120 }, xaxis: { title: { text: 'Redações da faixa 900–980 (%)' } } },
  };
}

function graficoRegras(recorte: Recorte | undefined, limiar: number): Figura | null {
  if (!recorte || recorte.suprimido === true) return null;
  const regras = recorte.rules as Comp[] | undefined;
  const linhas = (regras ?? [])
    .map((regra) => {
      const antes = Array.isArray(regra.antecedente) ? regra.antecedente.join('+') : '';
      const depois = Array.isArray(regra.consequente) ? regra.consequente.join('+') : '';
      return {
        nome: `${antes} → ${depois}`,
        valor: metricaPublicavel(regra.lift, regra.n_ambos, limiar, regra),
      };
    })
    .filter((item) => item.nome !== ' → ' && item.valor !== null);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', orientation: 'h', y: linhas.map((item) => item.nome), x: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{y}<br>lift %{x:.3f}<extra></extra>' }],
    altura: Math.max(320, linhas.length * 36),
    layout: { margin: { l: 140 }, xaxis: { title: { text: 'Lift' } } },
  };
}

function graficoConcordancia(itens: Comp[], limiar: number): Figura | null {
  const linhas = itens
    .map((item) => ({
      nome: String(item.competencia ?? ''),
      valor: metricaPublicavel(item.concordancia_percentual, item.n_near_evaluator, limiar, item),
    }))
    .filter((item) => item.nome && item.valor !== null);
  if (!linhas.length) return null;
  return {
    data: [{ type: 'bar', x: linhas.map((item) => item.nome), y: linhas.map((item) => item.valor), marker: { color: COR }, hovertemplate: '%{x}: %{y:.2f}%<extra></extra>' }],
    altura: 320,
    layout: { yaxis: { title: { text: 'Concordância (%)' }, range: [0, 100] } },
  };
}

function graficoMapa(recorte: Recorte | undefined, limiar: number): Figura | null {
  const faixas = recorte?.faixas as Comp[] | undefined;
  if (!faixas?.length) return null;
  const y = faixas.map((faixa) => String(faixa.faixa ?? ''));
  const x = ['C1', 'C2', 'C3', 'C4', 'C5'];
  const z = faixas.map((faixa) => {
    const comps = Array.isArray(faixa.competencias) ? faixa.competencias as Comp[] : [];
    return x.map((codigo) => {
      const celula = comps.find((item) => item.competencia === codigo);
      if (!celula) return null;
      return metricaPublicavel(celula.percentual_com_desconto, celula.n_com_desconto, limiar, celula);
    });
  });
  if (z.every((linha) => linha.every((valor) => valor === null))) return null;
  const texto = z.map((linha) => linha.map((valor) => (valor === null ? '' : formatarNota(valor))));
  return {
    data: [{ type: 'heatmap', x, y, z, text: texto, texttemplate: '%{text}', colorscale: 'Blues', hovertemplate: '%{y} · %{x}: %{z:.2f}%<extra></extra>', zmin: 0, zmax: 100 }],
    altura: 420,
    layout: { margin: { l: 90, b: 48 } },
  };
}
