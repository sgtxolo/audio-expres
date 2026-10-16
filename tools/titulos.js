// Pone en datos/indice.json y datos/T*.json el título real de cada tema (sacado de esquemas.html)
const fs = require('fs'), path = require('path');
const raiz = path.join(__dirname, '..');
const src = process.argv[2] || path.join(process.env.USERPROFILE, 'Desktop', 'HTML OFICIAL', 'esquemas.html');
const s = fs.readFileSync(src, 'utf8');
const tit = {};
const re = /(?:\bt(\d+)|esquemas\[(\d+)\])\.titulo\s*=\s*"[^"—]*—\s*([^":]*?)(?::|")/g;
for (const m of s.matchAll(re)) tit[m[1] ? +m[1] : +m[2] + 1] = m[3].trim();
const ruta = path.join(raiz, 'datos', 'indice.json');
const ind = JSON.parse(fs.readFileSync(ruta, 'utf8'));
for (const t of ind.temas) {
  if (!tit[t.tema]) continue;
  t.titulo = tit[t.tema];
  const rt = path.join(raiz, 'datos', `T${t.tema}.json`);
  const d = JSON.parse(fs.readFileSync(rt, 'utf8')); d.titulo = t.titulo;
  fs.writeFileSync(rt, JSON.stringify(d));
}
fs.writeFileSync(ruta, JSON.stringify(ind));
console.log(ind.temas.map(t => t.tema + ': ' + t.titulo).join('\n'));
