import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { carregar, type MetaPainel } from './lib/dados.ts';
import { nomeUf } from './lib/ufs.ts';

type Filtros = {
  ano: string;
  uf: string;
  definirAno: (ano: string) => void;
  definirUf: (uf: string) => void;
  anos: number[];
  ufs: string[];
  limiar: number;
  avisos: string[];
  statusDados: string;
  carregandoMeta: boolean;
};

const Contexto = createContext<Filtros | null>(null);

export function ProvedorFiltros({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const [metaOpcoes, setMetaOpcoes] = useState<MetaPainel | null>(null);
  const [metaAno, setMetaAno] = useState<MetaPainel | null>(null);
  const ano = params.get('ano') || 'todos';
  const uf = params.get('uf') || 'BR';

  useEffect(() => {
    let ativo = true;
    carregar<MetaPainel>('/data/2024/meta.json')
      .then((meta) => {
        if (ativo) setMetaOpcoes(meta);
      })
      .catch(() => {
        if (ativo) setMetaOpcoes(null);
      });
    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    if (ano === 'todos') {
      setMetaAno(null);
      return;
    }
    let ativo = true;
    carregar<MetaPainel>(`/data/${ano}/meta.json`)
      .then((meta) => {
        if (ativo) setMetaAno(meta);
      })
      .catch(() => {
        if (ativo) setMetaAno(null);
      });
    return () => {
      ativo = false;
    };
  }, [ano]);

  const valor = useMemo<Filtros>(() => {
    const anos = metaOpcoes?.filters.available.year ?? [2019, 2020, 2021, 2022, 2023, 2024, 2025];
    const ufs = metaOpcoes?.filters.available.uf_exam ?? ['BR'];
    // O limite da fonte permanece documentado nos metadados; a apresentação é exploratória.
    const limiar = 5;
    return {
      ano,
      uf,
      definirAno: (proximo) => {
        const copia = new URLSearchParams(params);
        copia.set('ano', proximo);
        setParams(copia);
      },
      definirUf: (proximo) => {
        const copia = new URLSearchParams(params);
        copia.set('uf', proximo);
        setParams(copia);
      },
      anos,
      ufs,
      limiar,
      avisos: metaAno?.meta.warnings ?? [],
      statusDados: metaAno?.meta.data_status ?? metaOpcoes?.meta.data_status ?? 'draft',
      carregandoMeta: metaOpcoes === null,
    };
  }, [ano, uf, params, setParams, metaOpcoes, metaAno]);

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useFiltros(): Filtros {
  const valor = useContext(Contexto);
  if (!valor) throw new Error('Filtros ausentes');
  return valor;
}

export function rotuloUf(codigo: string): string {
  if (codigo === 'BR') return 'Brasil';
  return `${nomeUf(codigo)} (${codigo})`;
}
