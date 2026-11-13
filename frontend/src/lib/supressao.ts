import { numero } from './formatar.ts';

/**
 * Critério de divulgação exploratória:
 * - contagens agregadas pequenas podem ser exibidas;
 * - métricas calculadas com menos de 5 observações continuam indisponíveis;
 * - supressões efetivas feitas na origem são respeitadas.
 */
const MIN_AMOSTRA_METRICA = 5;

export function marcado(item: unknown): boolean {
  if (!item || typeof item !== 'object') return false;
  const registro = item as Record<string, unknown>;
  return registro.suprimido === true || registro.sinalizacao_suprimida === true;
}

/** Não confundir contagem pequena com contagem ausente ou suprimida na origem. */
export function contagemPublicavel(valor: unknown, _limiar: number, item?: unknown): number | null {
  if (item && marcado(item)) return null;
  return numero(valor);
}

/** Uma média com n=1 revelaria o valor do único registro do recorte. */
export function metricaPublicavel(valor: unknown, denominador: unknown, _limiar: number, item?: unknown): number | null {
  if (item && marcado(item)) return null;
  const n = numero(denominador);
  if (n !== null && n < MIN_AMOSTRA_METRICA) return null;
  return numero(valor);
}

export function porUf<T extends { uf?: string }>(lista: T[] | undefined | null, uf: string): T | undefined {
  return lista?.find((item) => item.uf === uf);
}
