const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const umaCasa = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const tresCasas = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });

export function formatarInteiro(valor: number): string {
  return inteiro.format(valor);
}

export function formatarNota(valor: number): string {
  return umaCasa.format(valor);
}

export function formatarPercentual(valor: number): string {
  return `${umaCasa.format(valor)}%`;
}

export function formatarIndice(valor: number): string {
  return tresCasas.format(valor);
}

export function numero(valor: unknown): number | null {
  if (typeof valor === 'number' && Number.isFinite(valor)) return valor;
  return null;
}
