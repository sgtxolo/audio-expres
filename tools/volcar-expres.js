// Vuelca el HTML Exprés de cada tema de esquemas.html a work/expres-T{n}.html
// Uso: node tools/volcar-expres.js [ruta-esquemas.html]
const fs = require('fs');
const path = require('path');
const src = process.argv[2] || path.join(process.env.USERPROFILE, 'Desktop', 'HTML OFICIAL', 'esquemas.html');
const s = fs.readFileSync(src, 'utf8');
const m = s.match(/<script id="expres-datos">([\s\S]*?)<\/script>/);
if (!m) { console.error('No encuentro expres-datos'); process.exit(1); }
const w = {};
new Function('window', m[1])(w);
const out = path.join(__dirname, '..', 'work');
fs.mkdirSync(out, { recursive: true });
for (const k of Object.keys(w.EXPRES_T)) {
  fs.writeFileSync(path.join(out, `expres-T${k}.html`), w.EXPRES_T[k].html, 'utf8');
  console.log('Tema', k, w.EXPRES_T[k].html.length, 'bytes');
}
