"""Wikipedia: listas anuais de estreias, resumos, pôsteres e texto para curiosidades."""
import re
from datetime import date, timedelta

from .. import db
from ..config import DIAS_FUTURO, DIAS_PASSADO
from ..rede import json_de

API_EN = "https://en.wikipedia.org/w/api.php"
API_PT = "https://pt.wikipedia.org/w/api.php"
MESES = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _limpar(t):
    t = re.sub(r"<ref[^>]*/>", "", t)
    t = re.sub(r"<ref.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"''+", "", t)
    for _ in range(3):
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _titulo_celula(cel):
    """Devolve (pagina, rotulo) de uma célula de título, com ou sem link."""
    cel = re.sub(r"\{\{sort\|[^|]*\|(.*)\}\}", r"\1", cel.strip())
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", cel)
    if m:
        return m.group(1).strip(), _limpar(m.group(2) or m.group(1))
    rot = _limpar(cel)
    return None, rot


def ler_lista(ano):
    """Lê 'List of American films of <ano>' e devolve [{pagina,titulo,data,estudio,equipe}]."""
    try:
        w = json_de(API_EN, dict(action="parse", page=f"List of American films of {ano}", prop="wikitext",
                                 format="json", formatversion=2, redirects=1))["parse"]["wikitext"]
    except KeyError:
        return []
    inicio = w.find("== January")
    w = w[inicio if inicio >= 0 else 0:]
    mes, dia, filmes = None, None, []
    for linha in w.split("\n|-"):
        # O mês aparece como letras verticais: J<br>A<br>N...
        m = re.search(r">((?:[A-Za-z]\s*<br\s*/?>\s*)+[A-Za-z])\s*<", linha)
        if m:
            letras = re.sub(r"<br\s*/?>|\s", "", m.group(1)).upper()
            mes = MESES.get(letras[:3], mes)
        m = re.search(r"\|\s*'''(\d{1,2})'''", linha)
        if m:
            dia = int(m.group(1))
        m = re.search(r"^\|\s*((?:\{\{sort\|[^\n]*?)?''.+?)\s*\|\|\s*(.*?)\s*\|\|\s*(.*?)\s*\|\|", linha, re.M)
        if not (m and mes and dia):
            continue
        pagina, titulo = _titulo_celula(m.group(1))
        if not titulo:
            continue
        try:
            data = date(ano, mes, dia).isoformat()
        except ValueError:
            continue
        filmes.append(dict(pagina=pagina, titulo=titulo, data=data,
                           estudio=_limpar(m.group(2)), equipe=_limpar(m.group(3))))
    return filmes


def _equipe(eq):
    """Separa direção e elenco do texto 'Fulano (director); Beltrano (screenplay); Ator, Atriz'."""
    partes = [p.strip() for p in eq.split(";") if p.strip()]
    direcao, elenco = [], []
    for p in partes:
        if "(" in p:
            nomes, funcao = p.rsplit("(", 1)
            if "director" in funcao:
                direcao += [n.strip() for n in re.split(r",| and ", nomes) if n.strip()]
        else:
            elenco += [n.strip() for n in p.split(",") if n.strip()]
    return direcao, elenco


def id_filme(pagina, titulo, data):
    return "f:" + (pagina or f"{titulo} ({data[:4]})").replace(" ", "_")


def coletar_listas(con, ex, registrar=True):
    hoje = date.today()
    ini, fim = hoje - timedelta(days=DIAS_PASSADO), hoje + timedelta(days=DIAS_FUTURO)
    vistos = 0
    for ano in sorted({ini.year, hoje.year, fim.year}):
        for f in ler_lista(ano):
            if not (ini.isoformat() <= f["data"] <= fim.isoformat()):
                continue
            direcao, elenco = _equipe(f["equipe"])
            tid = id_filme(f["pagina"], f["titulo"], f["data"])
            db.gravar_titulo(con, dict(id=tid, tipo="filme", titulo=f["titulo"], data_eua=f["data"],
                                       estudio=f["estudio"].split(" / ")[0], direcao=", ".join(direcao),
                                       wiki_pagina=f["pagina"]), registrar)
            db.gravar_elenco(con, tid, [(n, None) for n in elenco[:12]])
            vistos += 1
    con.commit()
    ex.itens = vistos
    ex.mensagem = f"{vistos} filmes na janela"


def _lotes(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def coletar_detalhes(con, ex, registrar=True):
    """Resumo em inglês, pôster, item do Wikidata e título em português, 20 páginas por consulta."""
    linhas = con.execute("SELECT id, wiki_pagina FROM titulos WHERE tipo='filme' AND wiki_pagina IS NOT NULL "
                         "AND (wikidata IS NULL OR sinopse_en IS NULL OR date(atualizado_em) < date('now','-6 day') "
                         "OR data_eua >= date('now'))").fetchall()
    por_pagina = {r["wiki_pagina"]: r["id"] for r in linhas}
    feitos = 0
    for lote in _lotes(list(por_pagina), 20):
        d = json_de(API_EN, dict(action="query", prop="pageimages|extracts|langlinks|pageprops",
                                 piprop="thumbnail", pithumbsize=500, pilicense="any",
                                 exintro=1, explaintext=1, exsentences=4, exlimit=20,
                                 lllang="pt", lllimit=50, ppprop="wikibase_item", redirects=1,
                                 format="json", formatversion=2, titles="|".join(lote)))
        q = d.get("query", {})
        alias = {x["from"]: x["to"] for x in q.get("normalized", []) + q.get("redirects", [])}
        paginas = {p["title"]: p for p in q.get("pages", [])}
        for pag in lote:
            alvo = alias.get(pag, pag)
            alvo = alias.get(alvo, alvo)
            p = paginas.get(alvo)
            if not p or p.get("missing"):
                continue
            pt = (p.get("langlinks") or [{}])[0].get("title")
            thumb = (p.get("thumbnail") or {}).get("source")
            db.gravar_titulo(con, dict(
                id=por_pagina[pag], sinopse_en=p.get("extract") or None, poster_url=thumb,
                wikidata=(p.get("pageprops") or {}).get("wikibase_item"),
                titulo_pt=re.sub(r"\s*\((?:filme|film|série|\d{4})[^)]*\)$", "", pt) if pt else None), registrar)
            if pt:
                con.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", ("ptwiki:" + por_pagina[pag], pt))
            feitos += 1
        con.commit()
    ex.itens = feitos
    _sinopses_pt(con)


def _sinopses_pt(con):
    """Para filmes com artigo na Wikipedia em português, usa a introdução de lá como sinopse."""
    pend = con.execute("SELECT t.id, m.valor FROM titulos t JOIN meta m ON m.chave='ptwiki:'||t.id "
                       "WHERE t.sinopse_pt IS NULL").fetchall()
    for lote in _lotes(pend, 20):
        mapa = {r[1]: r[0] for r in lote}
        d = json_de(API_PT, dict(action="query", prop="extracts", exintro=1, explaintext=1, exsentences=4,
                                 exlimit=20, redirects=1, format="json", formatversion=2, titles="|".join(mapa)))
        q = d.get("query", {})
        alias = {x["to"]: x["from"] for x in q.get("normalized", []) + q.get("redirects", [])}
        for p in q.get("pages", []):
            orig = alias.get(p["title"], p["title"])
            orig = alias.get(orig, orig)
            if orig in mapa and p.get("extract"):
                texto = p["extract"]
                # A Wikipedia lusófona costuma trazer o título local: "(bra: Duna: Parte Três; prt: ...)"
                br = re.search(r"\(bra(?:sil)?\s*:\s*([^;)]+)", texto)
                if br:
                    con.execute("UPDATE titulos SET titulo_pt=? WHERE id=?", (br.group(1).strip(), mapa[orig]))
                texto = re.sub(r"\s*\((?:bra|prt)\s*:[^)]*\)", "", texto)
                con.execute("UPDATE titulos SET sinopse_pt=?, sinopse_pt_fonte='Wikipedia em português' "
                            "WHERE id=? AND sinopse_pt IS NULL", (texto, mapa[orig]))
        con.commit()


# ---------- curiosidades por extração (sem IA) ----------
SECOES = ("Production", "Development", "Pre-production", "Casting", "Filming", "Principal photography",
          "Post-production", "Music", "Visual effects", "Release", "Marketing", "Box office", "Design")
PISTAS = re.compile(r"\b(first|only|record|sold out|debut|replaced|originally|initially|largest|longest|"
                    r"shortest|youngest|oldest|million|billion|IMAX|shot on|returned|reprise|homage|"
                    r"cameo|inspired|based on|real|dropped out|exclusive|budget)\b", re.I)


def baixar_artigos(con, limite=25):
    """Guarda o texto completo dos filmes que estreiam nos próximos 120 dias (por ordem de interesse)."""
    pend = con.execute(
        "SELECT t.id, t.wiki_pagina FROM titulos t LEFT JOIN artigos a ON a.titulo_id=t.id "
        "LEFT JOIN lista l ON l.titulo_id=t.id "
        "WHERE t.tipo='filme' AND t.wiki_pagina IS NOT NULL AND t.data_eua BETWEEN date('now','-30 day') AND date('now','+120 day') "
        "AND (a.titulo_id IS NULL OR date(a.buscado_em) < date('now','-14 day')) "
        "ORDER BY l.titulo_id IS NULL, COALESCE(t.hype,0) DESC LIMIT ?", (limite,)).fetchall()
    for r in pend:
        d = json_de(API_EN, dict(action="query", prop="extracts", explaintext=1, redirects=1,
                                 format="json", formatversion=2, titles=r["wiki_pagina"]))
        pags = d.get("query", {}).get("pages", [])
        texto = pags[0].get("extract") if pags else None
        if texto:
            con.execute("INSERT OR REPLACE INTO artigos VALUES(?,?,?)", (r["id"], texto, db.agora()))
            con.commit()
    return len(pend)


def _secoes(texto):
    atual, out = "Introdução", {}
    for linha in texto.split("\n"):
        m = re.match(r"^=+\s*(.+?)\s*=+$", linha.strip())
        if m:
            atual = m.group(1)
            continue
        if linha.strip():
            out.setdefault(atual, []).append(linha.strip())
    return out


def extrair_curiosidades(con, ex):
    """Escolhe frases com 'cara de curiosidade' das seções de produção. Fica em inglês;
    a curadoria do Claude, quando disponível, substitui por versões em português."""
    n_art = baixar_artigos(con)
    alvos = con.execute("SELECT a.titulo_id, a.texto FROM artigos a WHERE NOT EXISTS "
                        "(SELECT 1 FROM curiosidades c WHERE c.titulo_id=a.titulo_id)").fetchall()
    feitos = 0
    for r in alvos:
        escolhidas = []
        for sec, pars in _secoes(r["texto"]).items():
            if not any(s.lower() in sec.lower() for s in SECOES):
                continue
            for frase in re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(pars)):
                if 60 <= len(frase) <= 320 and PISTAS.search(frase):
                    escolhidas.append((sec, frase))
        vistos, final = set(), []
        for sec, frase in escolhidas:
            if sec in vistos and len(escolhidas) > 6:
                continue
            vistos.add(sec)
            final.append((sec, frase))
            if len(final) == 6:
                break
        for i, (sec, frase) in enumerate(final):
            con.execute("INSERT OR REPLACE INTO curiosidades VALUES(?,?,?,?,?,?)",
                        (r["titulo_id"], i, sec, frase, f"Wikipedia · {sec}", "extracao"))
        feitos += bool(final)
    con.commit()
    ex.itens = feitos
    ex.mensagem = f"{n_art} artigos baixados, {feitos} com curiosidades"
