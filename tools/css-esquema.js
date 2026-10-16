// Extrae de esquemas.html los estilos de colores, subrayados y cuadros, y los guarda en estilos-esquema.css
// con el prefijo #texto, para que el reproductor se vea igual que el esquema. Uso: node tools/css-esquema.js
const fs = require('fs'), path = require('path');
const src = process.argv[2] || path.join(process.env.USERPROFILE, 'Desktop', 'HTML OFICIAL', 'esquemas.html');
const html = fs.readFileSync(src, 'utf8');
const css = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n').replace(/\/\*[\s\S]*?\*\//g, '');

const QUIERO = /(^|[\s,>+~])(mark\.|u\.m-|span\.m-|\.m-|\.vis|\.vt-|\.ex-sello|\.ex-plg|\.vista-of)/;
const NO = /data-theme|\.hl|guia-hit|\[data-q\]|:hover|\.ex-sello-r|cursor/;

function bloques(s) {                     // separa bloques de primer nivel: "sel{...}" o "@media(...){...}"
  const out = []; let i = 0;
  while (i < s.length) {
    const a = s.indexOf('{', i); if (a < 0) break;
    let d = 1, j = a + 1;
    while (j < s.length && d) { if (s[j] === '{') d++; else if (s[j] === '}') d--; j++; }
    out.push([s.slice(i, a).trim(), s.slice(a + 1, j - 1)]);
    i = j;
  }
  return out;
}
function regla(sel, cuerpo) {
  const sels = sel.split(',').map(x => x.trim()).filter(x => x && QUIERO.test(x) && !NO.test(x));
  if (!sels.length) return '';
  return sels.map(x => '#texto ' + x).join(',') + '{' + cuerpo.trim() + '}\n';
}
let out = '';
for (const [sel, cuerpo] of bloques(css)) {
  if (sel.startsWith('@media')) {
    if (!/max-width:\s*(640|600|700)px/.test(sel)) continue;
    let inn = '';
    for (const [s2, c2] of bloques(cuerpo)) inn += regla(s2, c2);
    if (inn) out += sel + '{' + inn + '}\n';
  } else if (!sel.startsWith('@')) {
    out += regla(sel, cuerpo);
  }
}
fs.writeFileSync(path.join(__dirname, '..', 'estilos-esquema.css'), out);
console.log(out.split('\n').length, 'reglas,', out.length, 'bytes');
