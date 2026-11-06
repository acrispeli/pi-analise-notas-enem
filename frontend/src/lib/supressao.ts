import { numero } from './formatar.ts';

export function marcado(item: unknown): boolean {
  if (!item || typeof item !== 'object') return false;
  const registro = item as Record<string, unknown>;
  return (
    registro.n_pequeno === true ||
    registro.suprimido === true ||
    registro.requires_privacy_review === true ||
    registro.requer_revisao_privacidade === true ||
    registro.sinalizacao_suprimida === true
  );
}

/** Contagem positiva abaixo do limiar fica suprimida. Zero publicado continua zero. */
export function contagemPublicavel(valor: unknown, limiar: number, item?: unknown): number | null {
  if (item && marcado(item)) return null;
  const n = numero(valor);
  if (n === null) return null;
  if (n > 0 && n < limiar) return null;
  return n;
}

export function metricaPublicavel(valor: unknown, denominador: unknown, limiar: number, item?: unknown): number | null {
  if (item && marcado(item)) return null;
  const n = numero(denominador);
  if (n !== null && n > 0 && n < limiar) return null;
  return numero(valor);
}

export function porUf<T extends { uf?: string }>(lista: T[] | undefined | null, uf: string): T | undefined {
  return lista?.find((item) => item.uf === uf);
}
