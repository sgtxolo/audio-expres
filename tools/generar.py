"""Genera el audio (MP3, voz neuronal de Edge) y el índice de un tema Exprés.

Uso:
  python generar.py <tema> --dry          # solo cuenta, muestra muestras y censos
  python generar.py <tema> [--voz es-ES-ElviraNeural] [--limite N]

Entrada : work/expres-T<tema>.html   (lo crea volcar-expres.js)
Salida  : audio/T<tema>-pNN.mp3  y  datos/T<tema>.json  (+ actualiza datos/indice.json)
"""
import argparse, asyncio, hashlib, json, os, re, sys, collections, unicodedata
import lxml.html
import edge_tts

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KBPS = 48000                      # audio-24khz-48kbitrate-mono-mp3 (CBR)
OBJETIVO_PARTE = 20 * 60          # segundos aproximados por parte
PAUSA_P = 14                      # tramas de silencio (24 ms) entre párrafos  ≈ 0,34 s
PAUSA_H = 30                      # tras títulos ≈ 0,7 s
BLOQUES = {"div", "p", "li", "ul", "ol", "table", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
ORD_M = ["", "primero", "segundo", "tercero", "cuarto", "quinto", "sexto", "séptimo", "octavo",
         "noveno", "décimo", "undécimo", "duodécimo"]
ORD_F = [o[:-1] + "a" if o else "" for o in ORD_M]
ROMANOS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9,
           "X": 10, "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17,
           "XVIII": 18, "XIX": 19, "XX": 20}
FRACC = {"1/2": "la mitad", "1/3": "un tercio", "2/3": "dos tercios", "1/4": "un cuarto",
         "3/4": "tres cuartos", "1/5": "un quinto", "3/5": "tres quintos", "2/5": "dos quintos",
         "1/6": "un sexto", "1/10": "una décima parte"}
SIGLAS = {"BOE": "Boletín Oficial del Estado", "LO": "Ley Orgánica", "RD": "Real Decreto",
          "RDL": "Real Decreto-ley", "RDLeg": "Real Decreto Legislativo",
          "CE": "Constitución Española", "TUE": "Tratado de la Unión Europea",
          "TFUE": "Tratado de Funcionamiento de la Unión Europea"}


SIGLAS_MAYUS = {"ONU", "UE", "SDN", "PDF", "TJUE", "OTAN", "PIDCP", "DUDH", "PIDESC", "TEDH", "CEDH"}
COMUNES = {"DE", "LA", "EL", "LOS", "LAS", "EN", "NO", "SE", "LO", "CON", "POR", "UN", "UNA", "DEL", "AL",
           "SI", "SU", "SUS", "MÁS", "LEY", "ART", "SEC", "OJO", "SÍ", "TÍTULO", "CAPÍTULO"}


def limpia_espacios(t):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", t).replace("\xa0", " ")).strip()


def ordinal(romano, fem):
    n = ROMANOS.get(romano.upper())
    if not n:
        return romano
    return (ORD_F if fem else ORD_M)[n] if n < len(ORD_M) else str(n)


def narrar(t):
    """Texto tal como aparece -> texto para que la voz lo lea bien."""
    t = limpia_espacios(t)
    t = re.sub(r"[⚠🎯✔→•▶◀✱★☆✓✗✘▪■□●○]", " ", t)
    t = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", " ", t)       # emojis
    t = re.sub(r"\s*·\s*R\d+\b", "", t)                                   # «· R13»
    t = re.sub(r"\s*·\s*", ", ", t)
    # fechas dd/mm/aaaa
    def fecha(m):
        d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
        return f"{d} de {MESES[mes-1]} de {a}" if 1 <= mes <= 12 else m.group(0)
    t = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", fecha, t)
    # fracciones
    t = re.sub(r"(?<![\d/])(\d{1,2}/\d{1,2})(?![\d/])", lambda m: FRACC.get(m.group(1), m.group(1).replace("/", " entre ")), t)
    # número/año de normas: 50/1997
    t = re.sub(r"\b(\d{1,4})/(\d{2,4})\b", r"\1 barra \2", t)
    # romanos con sustantivo
    def rom(m):
        fem = m.group(1).lower() in ("sección", "parte", "subsección", "disposición")
        return f"{m.group(1)} {ordinal(m.group(2), fem)}"
    t = re.sub(r"\b(Título|Capítulo|Sección|Subsección|Libro|Parte|Disposición|TÍTULO|CAPÍTULO|SECCIÓN|LIBRO|PARTE)\s+([IVXL]+)\b", rom, t)
    t = re.sub(r"\bartículos?\b", lambda m: m.group(0), t)
    t = re.sub(r"\barts\.\s*", "artículos ", t, flags=re.I)
    t = re.sub(r"\bart\.\s*", "artículo ", t, flags=re.I)
    t = re.sub(r"\bapdos?\.\s*", "apartado ", t, flags=re.I)
    t = re.sub(r"\bnúm\.\s*|\bnº\s*|\bn\.º\s*", "número ", t, flags=re.I)
    t = re.sub(r"\bletra\s+([a-z])\)", r"letra \1", t)
    t = re.sub(r"(\d)\.([a-z])\)", r"\1, letra \2,", t)                  # 2.c)
    t = re.sub(r"(?<![\w])([ivxl]{2,5})\)\s*", lambda m: f"punto {ROMANOS.get(m.group(1).upper(), m.group(1))}, " if m.group(1).upper() in ROMANOS else m.group(0), t)
    t = re.sub(r"(?<![\w])([a-zñ])\)\s*", r"letra \1, ", t)               # a) b) c)
    t = re.sub(r"%", " por ciento", t)
    t = re.sub(r"€", " euros", t)
    t = t.replace("&", " y ").replace("§", "apartado ").replace("…", ".")
    # siglas conocidas
    t = re.sub(r"\b(" + "|".join(SIGLAS) + r")\b", lambda m: SIGLAS[m.group(1)], t)
    letras = [c for c in t if c.isalpha()]
    todo_mayus = len(letras) > 3 and sum(c.isupper() for c in letras) / len(letras) > 0.6
    def mayus(m):
        w = m.group(0)
        if w in ROMANOS and not todo_mayus:
            return w
        if w in SIGLAS_MAYUS:
            return ".".join(w) + "."
        if todo_mayus or len(w) >= 5 or w in COMUNES:
            return w.lower()
        return ".".join(w) + "."
    t = re.sub(r"\b[A-ZÁÉÍÓÚÑÜ]{2,}\b", mayus, t)
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    t = re.sub(r"([.;:,])\1+", r"\1", t)
    t = re.sub(r"[,;:]+\.", ".", t)
    return limpia_espacios(t)


# ---------------------------------------------------------------- parseo
def texto(e):
    return limpia_espacios(e.text_content())


def hijos_bloque(e):
    return any(isinstance(c.tag, str) and c.tag in BLOQUES for c in e)


def unidades(e):
    """Lista de textos (uno por 'línea' visible) de un elemento."""
    out, buf = [], []

    def vuelca():
        s = limpia_espacios("".join(buf)); buf.clear()
        if len(s) > 1:
            out.append(s)

    if e.text:
        buf.append(e.text)
    for c in e:
        if not isinstance(c.tag, str):
            if c.tail: buf.append(c.tail)
            continue
        if c.tag in BLOQUES:
            vuelca()
            if "vis-sub" in (c.get("class") or "") and not hijos_bloque(c):
                partes = [texto(s) for s in c if isinstance(s.tag, str)]
                s = "; ".join(p for p in partes if p) if partes else texto(c)
                if s: out.append(s)
            elif c.tag == "tr":
                celdas = [texto(x) for x in c if isinstance(x.tag, str)]
                s = ", ".join(x for x in celdas if x)
                if s: out.append(s)
            elif hijos_bloque(c):
                out.extend(unidades(c))
            else:
                s = texto(c)
                if len(s) > 1: out.append(s)
        else:
            buf.append(c.text_content())
        if c.tail:
            buf.append(c.tail)
    vuelca()
    return out


def parsear(html):
    raiz = lxml.html.fragment_fromstring(html, create_parent="div")
    elems = []        # {'tipo','h','sello','us':[...]}
    for c in raiz:
        if not isinstance(c.tag, str):
            continue
        cl = c.get("class") or ""
        if "bloque-titulo" in cl:
            elems.append({"tipo": "titulo", "h": texto(c), "sello": "", "us": []})
        elif "ex-ficha" in cl:
            cab = next((x for x in c if "ex-fh" in (x.get("class") or "")), None)
            sellos = []
            if cab is not None:
                for s in list(cab.iter("span")):
                    if "ex-sello" in (s.get("class") or ""):
                        sellos.append(texto(s))
                        s.drop_tree()
                h = texto(cab)
            else:
                h = ""
            sello = " ".join(sellos)
            cuerpo = next((x for x in c if "ex-fb" in (x.get("class") or "")), None)
            us = unidades(cuerpo) if cuerpo is not None else []
            # visuales dentro de la ficha
            elems.append({"tipo": "ficha", "h": h, "sello": sello, "us": us})
        elif "vis" in cl.split():
            t = next((x for x in c if "vis-t" in (x.get("class") or "")), None)
            titulo = texto(t) if t is not None else ""
            if t is not None:
                c.remove(t)
            elems.append({"tipo": "vis", "h": titulo, "sello": "", "us": unidades(c)})
        else:
            us = unidades(c)
            if us:
                elems.append({"tipo": "otros", "h": "", "sello": "", "us": us})
    return elems


def cue_de(sello):
    toks = sello.split()
    if "EXOF" in toks or "EXAMEN" in toks:
        return "Pregunta oficial"
    if "EX" in toks or "✱" in toks or "*" in toks:
        return "Importante"
    return ""


def limpia_display(t):
    t = re.sub(r"(?:(?<=\s)|^)R\d{1,2}\b\s*", "", t)                     # fichas R1…R39
    t = re.sub(r"\s*\b\d+ preguntas?( más de este artículo)?\b", "", t)  # «2 preguntas»
    t = re.sub(r"\b(EXOF|EXAMEN)\b\s*", "", t)
    t = re.sub(r"\bEX\b\s*", "", t)
    t = re.sub(r"[✱]", "", t)
    t = re.sub(r"[\s·]+$", "", t)
    return limpia_espacios(t)


def a_items(e):
    """Elemento -> lista de (clase, texto_mostrado, texto_narrado)."""
    items = []
    if e["tipo"] == "titulo":
        h = limpia_display(e["h"])
        items.append(("t", h, narrar(h) + "."))
    elif e["tipo"] == "ficha":
        cue = cue_de(e["sello"])
        h = limpia_display(e["h"])
        narr = (cue + ". " if cue else "") + narrar(h) + "."
        items.append(("h", h, narr))
        for u in e["us"]:
            u = limpia_display(u)
            if re.fullmatch(r"[\d\s]*pregunta.*|", u, re.I):
                continue
            items.append(("p", u, narrar(u)))
    elif e["tipo"] == "vis":
        h = limpia_display(e["h"])
        items.append(("h", "Cuadro: " + h, "Cuadro. " + narrar(h) + "."))
        for u in e["us"]:
            u = limpia_display(u)
            items.append(("v", u, narrar(u)))
    else:
        for u in e["us"]:
            u = limpia_display(u)
            items.append(("p", u, narrar(u)))
    return [(k, d, n) for k, d, n in items if len(n) > 1]


# ---------------------------------------------------------------- audio
def quita_cabecera_info(b):
    """edge-tts empieza cada MP3 con una trama 'Info/Xing' vacía: fuera, para poder concatenar."""
    if len(b) > 144 and (b"Info" in b[:144] or b"Xing" in b[:144]):
        return b[144:]
    return b


SILENCIO = bytes([0xFF, 0xF3, 0x64, 0xC4]) + bytes(140)


async def sintetiza(texto_n, voz, cache, sem):
    h = hashlib.sha1((voz + "|" + texto_n).encode("utf-8")).hexdigest()
    ruta = os.path.join(cache, h + ".mp3")
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return f.read()
    async with sem:
        for intento in range(6):
            try:
                datos = bytearray()
                async for ch in edge_tts.Communicate(texto_n, voz).stream():
                    if ch["type"] == "audio":
                        datos += ch["data"]
                if not datos:
                    raise RuntimeError("audio vacío")
                b = quita_cabecera_info(bytes(datos))
                with open(ruta, "wb") as f:
                    f.write(b)
                return b
            except Exception as ex:
                if intento == 5:
                    raise
                await asyncio.sleep(1.5 * (intento + 1))


async def principal(a):
    ruta_html = os.path.join(RAIZ, "work", f"expres-T{a.tema}.html")
    html = open(ruta_html, encoding="utf-8").read()
    elems = parsear(html)
    todos = [(i, it) for i, e in enumerate(elems) for it in a_items(e)]
    if a.limite:
        todos = todos[: a.limite]
    nchars = sum(len(it[2]) for _, it in todos)
    print(f"Tema {a.tema}: {len(elems)} bloques, {len(todos)} fragmentos, {nchars} caracteres "
          f"(~{nchars/15/60:.0f} min de audio)")

    if a.dry:
        censo = collections.Counter(e["sello"] for e in elems if e["tipo"] == "ficha")
        print("Sellos:", dict(censo))
        print("Tipos:", dict(collections.Counter(e["tipo"] for e in elems)))
        mayus = collections.Counter(w for _, it in todos for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ]{2,}\b", it[1]))
        print("MAYÚSCULAS frecuentes:", mayus.most_common(40))
        for _, it in todos[: a.muestra]:
            print(f"[{it[0]}] {it[2][:230]}")
        return

    cache = os.path.join(RAIZ, "work", "cache"); os.makedirs(cache, exist_ok=True)
    sem = asyncio.Semaphore(8)
    t0 = asyncio.get_event_loop().time()
    hechos = [0]

    async def uno(it):
        r = await sintetiza(it[2], a.voz, cache, sem)
        hechos[0] += 1
        if hechos[0] % 100 == 0:
            print(f"  {hechos[0]}/{len(todos)} ({asyncio.get_event_loop().time()-t0:.0f}s)", flush=True)
        return r

    audios = await asyncio.gather(*[uno(it) for _, it in todos])

    # ---- montar partes y línea de tiempo
    os.makedirs(os.path.join(RAIZ, "audio"), exist_ok=True)
    os.makedirs(os.path.join(RAIZ, "datos"), exist_ok=True)
    partes, items_p, buf, t = [], [], bytearray(), 0.0
    arts = []
    ultimo_el = None

    def cierra():
        nonlocal buf, items_p, t
        if not items_p:
            return
        n = len(partes) + 1
        nombre = f"T{a.tema}-p{n:02d}.mp3"
        with open(os.path.join(RAIZ, "audio", nombre), "wb") as f:
            f.write(buf)
        partes.append({"f": nombre, "dur": round(len(buf) * 8 / KBPS, 2), "mb": round(len(buf) / 1e6, 2), "it": items_p})
        buf, items_p, t = bytearray(), [], 0.0

    for (idx, (k, disp, narr)), audio in zip(todos, audios):
        cambio = idx != ultimo_el
        # cortar parte solo al empezar un bloque nuevo
        if cambio and t >= OBJETIVO_PARTE:
            cierra()
        if cambio:
            ultimo_el = idx
        if k in ("t", "h") and elems[idx]["tipo"] in ("titulo", "ficha"):
            arts.append({"h": disp, "p": len(partes), "t": round(t, 2), "k": k, "s": elems[idx]["sello"]})
        items_p.append({"t": round(t, 2), "k": k, "x": disp})
        buf += audio
        pausa = PAUSA_H if k in ("t", "h") else PAUSA_P
        buf += SILENCIO * pausa
        t += (len(audio) + len(SILENCIO) * pausa) * 8 / KBPS
    cierra()
    # tiempos de 'arts' referidos a partes: ya llevan índice de parte
    titulo = re.sub(r"<[^>]+>", "", elems[0]["h"]) if elems else f"Tema {a.tema}"
    datos = {"tema": int(a.tema), "titulo": titulo, "voz": a.voz, "partes": partes, "arts": arts}
    with open(os.path.join(RAIZ, "datos", f"T{a.tema}.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
    # índice general
    ruta_i = os.path.join(RAIZ, "datos", "indice.json")
    ind = json.load(open(ruta_i, encoding="utf-8")) if os.path.exists(ruta_i) else {"temas": []}
    ind["temas"] = [x for x in ind["temas"] if x["tema"] != int(a.tema)]
    ind["temas"].append({"tema": int(a.tema), "titulo": titulo,
                         "dur": round(sum(p["dur"] for p in partes)),
                         "mb": round(sum(p["mb"] for p in partes), 1), "partes": len(partes)})
    ind["temas"].sort(key=lambda x: x["tema"])
    with open(ruta_i, "w", encoding="utf-8") as f:
        json.dump(ind, f, ensure_ascii=False, separators=(",", ":"))
    tot = sum(p["dur"] for p in partes)
    print(f"Listo: {len(partes)} partes, {tot/60:.0f} min, {sum(p['mb'] for p in partes):.0f} MB, {len(arts)} entradas de índice")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tema")
    ap.add_argument("--voz", default="es-ES-ElviraNeural")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--muestra", type=int, default=25)
    asyncio.run(principal(ap.parse_args()))
