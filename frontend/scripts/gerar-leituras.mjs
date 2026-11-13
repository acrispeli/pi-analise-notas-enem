import fs from 'node:fs';
import path from 'node:path';

// Conversão automática, no build, dos textos revisados no Streamlit.
// Não há IA generativa, microdados ou inferência numérica nesta etapa.
function desescapar(valor) {
  return valor.replace(/\\([\\'"nrt])/g, (_trecho, ch) => ({ n: '\n', r: '\r', t: '\t' }[ch] ?? ch));
}

function lerStrings(trecho) {
  const tokens = trecho.match(/'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"/g) ?? [];
  return tokens.map((token) => desescapar(token.slice(1, -1))).join('');
}

function extrairGuias(texto) {
  const inicio = texto.indexOf('GUIAS = {');
  if (inicio < 0) throw new Error('GUIAS não encontrado em leitura_acessivel_68.py');
  const fim = texto.indexOf('\n}\n', inicio);
  if (fim < 0) throw new Error('Final de GUIAS não encontrado');
  const bloco = texto.slice(inicio, fim);
  const re = /^\s*(\d+):\s*\(/gm;
  const guias = {};
  for (const candidato of bloco.matchAll(re)) {
    const id = candidato[1];
    let pos = candidato.index + candidato[0].length;
    let profundidade = 1;
    let aspas = null;
    let escape = false;
    let parte = '';
    const partes = [];
    for (; pos < bloco.length; pos++) {
      const ch = bloco[pos];
      if (aspas !== null) {
        parte += ch;
        if (escape) escape = false;
        else if (ch === '\\') escape = true;
        else if (ch === aspas) aspas = null;
        continue;
      }
      if (ch === "'" || ch === '"') { aspas = ch; parte += ch; continue; }
      if (ch === '(') { profundidade++; parte += ch; continue; }
      if (ch === ')') {
        profundidade--;
        if (profundidade === 0) { partes.push(parte); break; }
        parte += ch;
        continue;
      }
      if (ch === ',' && profundidade === 1) { partes.push(parte); parte = ''; continue; }
      parte += ch;
    }
    const [oque, como, pedagogia] = partes.map(lerStrings);
    if (partes.length !== 3 || !oque || !como || !pedagogia) {
      throw new Error('Guia incompleto: IND-' + String(id).padStart(3, '0'));
    }
    guias[id] = { oque, como, pedagogia };
  }
  if (Object.keys(guias).length !== 68) throw new Error('Esperados 68 guias pedagógicos; encontrados ' + Object.keys(guias).length);
  return guias;
}

function extrairMapa(texto, nome) {
  const inicio = texto.indexOf(nome + ' = {');
  if (inicio < 0) throw new Error('Mapa não encontrado: ' + nome);
  const fechamentoEmLinha = texto.indexOf('\n}', inicio);
  const fim = fechamentoEmLinha >= 0 ? fechamentoEmLinha : texto.lastIndexOf('}');
  if (fim < inicio) throw new Error('Mapa sem fechamento: ' + nome);
  const trecho = texto.slice(inicio, fim);
  const saida = {};
  const re = /(\d+):\s*('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")/g;
  for (const match of trecho.matchAll(re)) saida[match[1]] = desescapar(match[2].slice(1, -1));
  return saida;
}

export function gerarLeituras(raiz, destino) {
  const python = fs.readFileSync(path.join(raiz, 'leitura_acessivel_68.py'), 'utf8');
  const orientacoes = fs.readFileSync(path.join(raiz, 'orientacoes_pedagogicas_68.py'), 'utf8');
  const guias = extrairGuias(python);
  const cuidados = extrairMapa(python, 'CUIDADOS');
  const glossario = extrairMapa(python, 'GLOSSARIO_RAPIDO');
  const acoes = extrairMapa(orientacoes, 'ACOES');
  for (const [id, guia] of Object.entries(guias)) {
    if (cuidados[id]) guia.cuidado = cuidados[id];
    if (glossario[id]) guia.glossario = glossario[id];
    if (acoes[id]) guia.acao = acoes[id];
  }
  if (Object.keys(acoes).length !== 68) throw new Error('Ações pedagógicas incompletas: ' + Object.keys(acoes).length);
  fs.writeFileSync(path.join(destino, 'guias-pedagogicos.json'), JSON.stringify({
    fonte: 'leitura_acessivel_68.py e orientacoes_pedagogicas_68.py',
    natureza: 'Leituras gerais revisadas, não conclusões numéricas sobre um recorte específico',
    indicadores: guias,
  }));

  const dicionario = JSON.parse(fs.readFileSync(
    path.join(raiz, 'docs', 'dicionario_questoes_enem_2019_2025.json'), 'utf8',
  ));
  for (let ano = 2019; ano <= 2025; ano++) {
    if (!dicionario.anos?.[String(ano)]?.Q001?.respostas) {
      throw new Error('Dicionário de respostas ausente ou incompleto em ' + ano);
    }
  }
  fs.writeFileSync(path.join(destino, 'dicionario-questoes.json'), JSON.stringify(dicionario));
  return { guias: Object.keys(guias).length, anos: Object.keys(dicionario.anos).length };
}
