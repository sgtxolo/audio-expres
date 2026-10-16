// Servidor local con soporte de Range (para probar el audio). Uso: node tools/servir.js [puerto]
const http = require('http'), fs = require('fs'), path = require('path');
const raiz = path.join(__dirname, '..');
const tipos = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.mp3': 'audio/mpeg', '.png': 'image/png', '.css': 'text/css'};
http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(raiz, p);
  if (!f.startsWith(raiz) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('no'); }
  const st = fs.statSync(f), t = tipos[path.extname(f)] || 'application/octet-stream';
  const r = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
  if (r) {
    const a = r[1] ? +r[1] : 0, b = r[2] ? Math.min(+r[2], st.size - 1) : st.size - 1;
    res.writeHead(206, {'Content-Type': t, 'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${a}-${b}/${st.size}`, 'Content-Length': b - a + 1});
    fs.createReadStream(f, {start: a, end: b}).pipe(res);
  } else {
    res.writeHead(200, {'Content-Type': t, 'Accept-Ranges': 'bytes', 'Content-Length': st.size});
    fs.createReadStream(f).pipe(res);
  }
}).listen(+process.argv[2] || 8766, '127.0.0.1', () => console.log('http://127.0.0.1:' + (process.argv[2] || 8766)));
