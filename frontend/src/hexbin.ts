import type { Figura } from './grafico.tsx';
import { formatarInteiro, numero } from './lib/formatar.ts';

type Ponto = { pc1?: number; pc2?: number; count?: number; hex_q?: number; hex_r?: number };
export type RecorteHex = {
  raio_hex?: number;
  points?: Ponto[];
  sem_pontos_individuais?: boolean;
  n_hexagonos_exibidos?: number;
  n_hexagonos_suprimidos?: number;
  fracao_coberta?: number;
  status_privacidade?: string;
};

function cor(nivel: number): string {
  const t = Math.min(1, Math.max(0, nivel));
  const r = Math.round(222 - t * 188);
  const g = Math.round(235 - t * 154);
  const b = Math.round(247 - t * 91);
  return `rgb(${r},${g},${b})`;
}

export function figuraHexbin(recorte: RecorteHex | undefined, limiar: number): Figura | null {
  if (!recorte || recorte.sem_pontos_individuais !== true) return null;
  const raio = numero(recorte.raio_hex);
  const pontos = recorte.points;
  if (!raio || raio <= 0 || !pontos?.length) return null;
  if (pontos.length !== recorte.n_hexagonos_exibidos) return null;
  const validos = [];
  for (const ponto of pontos) {
    const count = numero(ponto.count);
    const pc1 = numero(ponto.pc1);
    const pc2 = numero(ponto.pc2);
    if (count === null || count < limiar || pc1 === null || pc2 === null) return null;
    if (!Number.isInteger(ponto.hex_q) || !Number.isInteger(ponto.hex_r)) return null;
    validos.push({ count, pc1, pc2 });
  }
  const logs = validos.map((ponto) => Math.log10(ponto.count));
  const menor = Math.min(...logs);
  const maior = Math.max(...logs);
  const intervalo = Math.max(maior - menor, 1e-12);
  const data = validos.map((ponto, indice) => {
    const xs = [];
    const ys = [];
    for (let i = 0; i < 7; i += 1) {
      const angulo = Math.PI / 2 + (i * Math.PI) / 3;
      xs.push(ponto.pc1 + raio * Math.cos(angulo));
      ys.push(ponto.pc2 + raio * Math.sin(angulo));
    }
    return {
      type: 'scatter',
      mode: 'lines',
      x: xs,
      y: ys,
      fill: 'toself',
      fillcolor: cor((logs[indice] - menor) / intervalo),
      line: { color: 'rgba(255,255,255,0.85)', width: 0.6 },
      hovertemplate: `${formatarInteiro(ponto.count)} redações<br>PC1: ${ponto.pc1.toFixed(2)}<br>PC2: ${ponto.pc2.toFixed(2)}<extra></extra>`,
      showlegend: false,
    };
  });
  return {
    data,
    altura: 520,
    layout: {
      xaxis: { title: { text: 'PC1' }, scaleanchor: undefined, constrain: 'domain' },
      yaxis: { title: { text: 'PC2' }, scaleanchor: 'x', scaleratio: 1 },
      margin: { l: 56, r: 16, t: 8, b: 64 },
    },
  };
}

export function notaHex(recorte: RecorteHex | undefined): string {
  if (!recorte) return '';
  const partes = [
    'Cada área junta várias redações. Não há ponto de uma pessoa.',
    'Anos e estados diferentes não entram no mesmo mapa.',
  ];
  if (typeof recorte.n_hexagonos_suprimidos === 'number' && recorte.n_hexagonos_suprimidos > 0) {
    partes.push(`${formatarInteiro(recorte.n_hexagonos_suprimidos)} áreas com poucas redações ficam de fora.`);
  }
  return partes.join(' ');
}
