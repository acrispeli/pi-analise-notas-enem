import { useEffect, useState } from 'react';
import { carregar } from './lib/dados.ts';

export function useDados<T>(url: string | null): {
  dados: T | null;
  erro: boolean;
  carregando: boolean;
} {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState(false);
  const [carregando, setCarregando] = useState(url !== null);

  useEffect(() => {
    if (!url) {
      setDados(null);
      setErro(false);
      setCarregando(false);
      return;
    }
    let ativo = true;
    setCarregando(true);
    setErro(false);
    carregar<T>(url)
      .then((json) => {
        if (!ativo) return;
        setDados(json);
        setCarregando(false);
      })
      .catch(() => {
        if (!ativo) return;
        setDados(null);
        setErro(true);
        setCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [url]);

  return { dados, erro, carregando };
}
