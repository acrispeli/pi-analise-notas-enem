const cache = new Map<string, unknown>();
const pendentes = new Map<string, Promise<unknown>>();

export function carregar<T>(url: string): Promise<T> {
  if (cache.has(url)) return Promise.resolve(cache.get(url) as T);
  const existente = pendentes.get(url);
  if (existente) return existente as Promise<T>;
  const pedido = fetch(url)
    .then(async (resposta) => {
      if (!resposta.ok) throw new Error(url);
      const json = (await resposta.json()) as T;
      cache.set(url, json);
      pendentes.delete(url);
      return json;
    })
    .catch((erro: unknown) => {
      pendentes.delete(url);
      throw erro;
    });
  pendentes.set(url, pedido);
  return pedido;
}

export type MetaPainel = {
  meta: {
    data_status?: string;
    warnings?: string[];
    year?: number;
  };
  filters: {
    available: {
      year: number[];
      uf_exam: string[];
      population: { code: string; label: string }[];
    };
  };
  quality: {
    suppression: {
      min_group_n: number;
    };
  };
};
