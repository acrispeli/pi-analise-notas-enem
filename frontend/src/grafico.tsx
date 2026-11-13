import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

const Plot = createPlotlyComponent(Plotly);

const CONFIG = {
  displayModeBar: false,
  responsive: true,
  displaylogo: false,
};

export type Figura = {
  data: object[];
  layout?: object;
  altura?: number;
};

const LAYOUT = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Segoe UI, system-ui, sans-serif', size: 12, color: '#1c2430' },
  margin: { t: 16, r: 24, b: 72, l: 64 },
  legend: { orientation: 'h', yanchor: 'top', y: -0.35, x: 0, xanchor: 'left' },
  xaxis: { gridcolor: '#e6ebf2', zerolinecolor: '#d5dbe3', automargin: true, title: { standoff: 16 } },
  yaxis: { gridcolor: '#e6ebf2', zerolinecolor: '#d5dbe3', automargin: true, title: { standoff: 10 } },
};

function eixo(base: object, extra: object | undefined): object {
  if (!extra) return base;
  const acrescentado = extra as { title?: object };
  const origem = base as { title?: object };
  return {
    ...base,
    ...extra,
    title: { ...origem.title, ...acrescentado.title },
  };
}

function layoutFigura(extra: object | undefined, altura: number): object {
  const sobre = (extra ?? {}) as { xaxis?: object; yaxis?: object; margin?: object };
  return {
    ...LAYOUT,
    ...sobre,
    height: altura,
    xaxis: eixo(LAYOUT.xaxis, sobre.xaxis),
    yaxis: eixo(LAYOUT.yaxis, sobre.yaxis),
    margin: { ...LAYOUT.margin, ...sobre.margin },
  };
}

export function Grafico({
  titulo,
  figura,
  nota,
  identificador,
  embutido = false,
}: {
  titulo: string;
  figura: Figura | null;
  nota?: string;
  identificador: string;
  embutido?: boolean;
}) {
  const corpo = figura ? (
    <Plot
      data={figura.data}
      layout={layoutFigura(figura.layout, figura.altura ?? 360)}
      config={CONFIG}
      useResizeHandler
      style={{ width: '100%', height: figura.altura ?? 360 }}
    />
  ) : (
    <p className="indisponivel">não disponível</p>
  );
  const notaEl = nota ? <p className="nota">{nota}</p> : null;
  if (embutido) {
    return (
      <div data-visual={identificador}>
        {corpo}
        {notaEl}
      </div>
    );
  }
  return (
    <section className="painel" data-visual={identificador}>
      {titulo ? <h2>{titulo}</h2> : null}
      {corpo}
      {notaEl}
    </section>
  );
}

export const COR = '#1f4e79';
export const CORES = ['#d6e4f0', '#b7d0e6', '#8fb4d4', '#6a98c2', '#4f86c6', '#3a6fa3', '#1f4e79', '#163a5c', '#8d6a2f', '#c4a46a', '#5c6b7a'];

export function barra(x: (string | number)[], y: (number | null)[], horizontal = false): Figura {
  return {
    data: [
      {
        type: 'bar',
        x: horizontal ? y : x,
        y: horizontal ? x : y,
        orientation: horizontal ? 'h' : 'v',
        marker: { color: COR },
        hovertemplate: horizontal ? '%{y}<br>%{x}<extra></extra>' : '%{x}<br>%{y}<extra></extra>',
      },
    ],
  };
}
