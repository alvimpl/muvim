"""Grafo de ligações e notas da crítica a partir do Wikidata (domínio público, CC0),
consultado pelo QLever, espelho público e rápido do Wikidata (Universidade de Freiburg).
O SPARQL oficial do Wikidata recusa consultas deste tamanho; o QLever responde em segundos."""
import csv
import io
import re
import urllib.parse
from datetime import datetime, timedelta

from .. import db
from ..config import GRAFO_DIAS
from ..rede import baixar
from ..texto import normalizar

API = "https://qlever.dev/api/wikidata"
ROTTEN, METACRITIC = "Q105584", "Q150248"
FILME, SERIE = "Q11424", "Q5398426"
POP_TITULO, POP_PESSOA = 12, 8  # mínimo de Wikipedias com artigo para entrar no grafo

PREFIXOS = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
TITULOS = f"""VALUES ?tipo {{ wd:{FILME} wd:{SERIE} }}
?f wdt:P31 ?tipo ; wikibase:sitelinks ?pop . FILTER(xsd:integer(?pop) >= {POP_TITULO})"""

def _rotulo(var, saida):
    """Nome em inglês ou, na falta, o rótulo 'mul' (multilíngue): o Wikidata vem movendo o nome
    de muitas pessoas para 'mul', e sem ele Meryl Streep e Zendaya sumiam do grafo."""
    return (f"OPTIONAL {{ {var} rdfs:label {saida}_en FILTER(LANG({saida}_en)=\"en\") }} "
            f"OPTIONAL {{ {var} rdfs:label {saida}_mul FILTER(LANG({saida}_mul)=\"mul\") }} "
            f"BIND(COALESCE({saida}_en, {saida}_mul) AS {saida}) FILTER(BOUND({saida}))")


CONSULTAS = {
    "titulos": f"SELECT ?f ?tipo ?pop ?nome WHERE {{ {TITULOS} {_rotulo('?f', '?nome')} }}",
    "titulos_pt": f"SELECT ?f ?nome WHERE {{ {TITULOS} ?f rdfs:label ?nome FILTER(LANG(?nome)=\"pt-br\" || LANG(?nome)=\"pt\") }}",
    "anos": f"SELECT ?f (MIN(YEAR(?d)) AS ?ano) WHERE {{ {TITULOS} ?f wdt:P577 ?d }} GROUP BY ?f",
    "criticas": f"SELECT ?f ?nota ?por WHERE {{ {TITULOS} ?f p:P444 ?s . ?s ps:P444 ?nota ; pq:P447 ?por . "
                f"VALUES ?por {{ wd:{ROTTEN} wd:{METACRITIC} }} }}",
    "series": f"SELECT ?f ?serie ?nome WHERE {{ {TITULOS} ?f wdt:P179 ?serie . {_rotulo('?serie', '?nome')} }}",
    "arestas": f"SELECT ?f ?p WHERE {{ {TITULOS} VALUES ?rel {{ wdt:P161 wdt:P57 }} ?f ?rel ?p . "
               f"?p wikibase:sitelinks ?np . FILTER(xsd:integer(?np) >= {POP_PESSOA}) }}",
    "pessoas": f"SELECT DISTINCT ?p ?nome ?np WHERE {{ {TITULOS} VALUES ?rel {{ wdt:P161 wdt:P57 }} ?f ?rel ?p . "
               f"?p wikibase:sitelinks ?np . FILTER(xsd:integer(?np) >= {POP_PESSOA}) "
               f"{_rotulo('?p', '?nome')} }}",
}


def consultar(sparql):
    """Devolve as linhas (sem cabeçalho) de uma consulta, em TSV."""
    url = API + "?" + urllib.parse.urlencode({"query": PREFIXOS + sparql})
    texto = baixar(url, {"Accept": "text/tab-separated-values"}, tempo=300).decode("utf-8")
    linhas = list(csv.reader(io.StringIO(texto), delimiter="\t", quoting=csv.QUOTE_NONE))
    return [[_valor(c) for c in l] for l in linhas[1:] if l]


def _valor(c):
    if c.startswith("<http://www.wikidata.org/entity/"):
        return c[32:-1]
    m = re.match(r'^"(.*)"(?:@[\w-]+|\^\^<[^>]+>)?$', c, re.S)
    if m:
        return m.group(1).replace('\\"', '"').replace("\\\\", "\\")
    return c


def _pct(nota):
    """'92%' -> 92; '79/100' -> 79; '8.4/10' -> 84. Outros formatos são ignorados."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(%|/\s*(\d+))\s*$", nota)
    if not m:
        return None
    v, base = float(m.group(1)), float(m.group(3) or 100)
    return round(v * 100 / base) if base else None


def grafo(con, ex, forcar=False):
    ultimo = db.meta(con, "grafo_em")
    if not forcar and ultimo and datetime.fromisoformat(ultimo) > datetime.now() - timedelta(days=GRAFO_DIAS):
        ex.mensagem = f"em dia (última montagem {ultimo[:10]})"
        return
    r = {k: consultar(q) for k, q in CONSULTAS.items()}
    tit = {}
    for f, tipo, pop, nome in r["titulos"]:
        tit[f] = dict(nome=nome, tipo="filme" if tipo == FILME else "serie", pop=int(pop))
    for f, nome in r["titulos_pt"]:
        if f in tit and nome != tit[f]["nome"]:
            tit[f]["nome_pt"] = nome
    for f, ano in r["anos"]:
        if f in tit and ano.lstrip("-").isdigit():
            tit[f]["ano"] = int(ano)
    for f, nota, por in r["criticas"]:
        if f in tit:
            chave = "rt" if por == ROTTEN else "mc"
            v = _pct(nota)
            if v is not None:
                tit[f][chave] = max(v, tit[f].get(chave, 0))
    for f, serie, nome in r["series"]:
        if f in tit:
            tit[f]["serie"], tit[f]["serie_nome"] = serie, nome
    pessoas = {p: (nome, int(np)) for p, nome, np in r["pessoas"]}
    arestas = {(p, f) for f, p in r["arestas"] if f in tit and p in pessoas}
    if len(tit) < 1000 or len(arestas) < 10000:
        raise RuntimeError(f"resposta incompleta do QLever ({len(tit)} títulos, {len(arestas)} ligações); grafo anterior mantido")

    con.execute("DELETE FROM g_arestas")
    con.execute("DELETE FROM g_pessoas")
    con.execute("DELETE FROM g_titulos")
    con.executemany("INSERT INTO g_titulos VALUES(?,?,?,?,?,?,?,?,?,?)",
                    [(q, t["nome"], t.get("nome_pt"), t.get("ano"), t["tipo"], t["pop"], t.get("rt"), t.get("mc"),
                      t.get("serie"), t.get("serie_nome")) for q, t in tit.items()])
    con.executemany("INSERT INTO g_pessoas VALUES(?,?,?,?)",
                    [(p, n, normalizar(n), pop) for p, (n, pop) in pessoas.items()])
    con.executemany("INSERT INTO g_arestas VALUES(?,?)", sorted(arestas))
    db.meta(con, "grafo_em", db.agora())
    con.commit()
    ex.itens = len(arestas)
    ex.mensagem = f"{len(pessoas)} pessoas, {len(tit)} títulos, {len(arestas)} ligações"
