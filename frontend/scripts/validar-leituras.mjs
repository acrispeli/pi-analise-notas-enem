import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dados = path.join(raiz, 'public', 'data');
const guias = JSON.parse(fs.readFileSync(path.join(dados, 'guias-pedagogicos.json'), 'utf8'));
const dicionario = JSON.parse(fs.readFileSync(path.join(dados, 'dicionario-questoes.json'), 'utf8'));

function exigir(condicao, descricao) {
  if (!condicao) throw new Error('Falha na validação pedagógica: ' + descricao);
}
const ids = Object.keys(guias.indicadores);
exigir(ids.length === 68, 'esperados 68 indicadores com texto');
exigir(ids.includes('1') && ids.includes('72'), 'cobertura de ponta a ponta');
for (const [id, item] of Object.entries(guias.indicadores)) {
  exigir(item.oque && item.como && item.pedagogia && item.acao, 'campos incompletos em IND-' + id);
}
for (let ano = 2019; ano <= 2025; ano++) {
  const perguntas = dicionario.anos[String(ano)];
  exigir(perguntas && Object.keys(perguntas).length > 20, 'questões do ano ' + ano);
  exigir(perguntas.Q001?.respostas?.A, 'alternativa Q001/A do ano ' + ano);
  exigir(perguntas.Q006?.pergunta, 'enunciado Q006 do ano ' + ano);
}
exigir(dicionario.anos['2023'].Q006.pergunta !== dicionario.anos['2024'].Q006.pergunta,
  'Q006 precisa respeitar mudança semântica entre 2023 e 2024');

const resultado = {
  indicadores: ids.length,
  anos: Object.keys(dicionario.anos).length,
  q006_2023: dicionario.anos['2023'].Q006.pergunta,
  q006_2024: dicionario.anos['2024'].Q006.pergunta,
  validado: true,
};
console.log(JSON.stringify(resultado, null, 2));
