"""IMDb (arquivos públicos, uso pessoal): notas diárias e grafo semanal de ligações entre pessoas."""
import gzip
import unicodedata
from datetime import datetime, timedelta

from .. import db
from ..config import GRAFO_DIAS, GRAFO_VOTOS_MIN, IMDB_DIR
from ..rede import baixar_arquivo

BASE = "https://datasets.imdbws.com/"


def _linhas(arq):
    with gzip.open(arq, "rt", encoding="utf-8", newline="\n") as f:
        next(f)
        for linha in f:
            yield linha.rstrip("\n").split("\t")


def normalizar(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace(".", " ").split())


def notas(con, ex, registrar=True):
    arq = IMDB_DIR / "title.ratings.tsv.gz"
    baixar_arquivo(BASE + "title.ratings.tsv.gz", arq)
    meus = {r[0]: r[1] for r in con.execute("SELECT imdb_id, id FROM titulos WHERE imdb_id IS NOT NULL")}
    do_grafo = {r[0] for r in con.execute("SELECT tconst FROM g_titulos")}
    n, lote = 0, []
    for tconst, nota, votos in _linhas(arq):
        if tconst in meus:
            db.gravar_titulo(con, dict(id=meus[tconst], nota_imdb=float(nota), votos_imdb=int(votos)), registrar)
            n += 1
        if tconst in do_grafo:
            lote.append((float(nota), int(votos), tconst))
    con.executemany("UPDATE g_titulos SET nota=?, votos=? WHERE tconst=?", lote)
    con.commit()
    ex.itens = n


def grafo(con, ex, forcar=False):
    """Pessoa —(conhecida por)— título. Reconstruído a cada GRAFO_DIAS dias."""
    ultimo = db.meta(con, "grafo_em")
    if not forcar and ultimo and datetime.fromisoformat(ultimo) > datetime.now() - timedelta(days=GRAFO_DIAS):
        ex.mensagem = f"em dia (última montagem {ultimo[:10]})"
        return
    notas_arq = IMDB_DIR / "title.ratings.tsv.gz"
    if not notas_arq.exists():
        baixar_arquivo(BASE + "title.ratings.tsv.gz", notas_arq)
    votos, notas_g = {}, {}
    for t, nota, v in _linhas(notas_arq):
        if int(v) >= GRAFO_VOTOS_MIN:
            votos[t], notas_g[t] = int(v), float(nota)

    tb, nb = IMDB_DIR / "title.basics.tsv.gz", IMDB_DIR / "name.basics.tsv.gz"
    baixar_arquivo(BASE + "title.basics.tsv.gz", tb)
    titulos = {}
    for c in _linhas(tb):
        if c[0] in votos and c[1] in ("movie", "tvSeries", "tvMiniSeries"):
            titulos[c[0]] = (c[2], int(c[5]) if c[5].isdigit() else None, c[1], votos[c[0]])
    tb.unlink(missing_ok=True)

    # Ligação = estar no elenco principal (6 primeiros créditos) ou dirigir. Assim "ligado" quer dizer
    # que contracenaram, e não que um figurante passou pelo mesmo filme.
    pr = IMDB_DIR / "title.principals.tsv.gz"
    baixar_arquivo(BASE + "title.principals.tsv.gz", pr)
    arestas, peso = set(), {}
    for c in _linhas(pr):
        if c[0] not in titulos:
            continue
        if (c[3] in ("actor", "actress") and c[1].isdigit() and int(c[1]) <= 6) or c[3] == "director":
            arestas.add((c[2], c[0]))
            peso[c[2]] = peso.get(c[2], 0) + titulos[c[0]][3]
    pr.unlink(missing_ok=True)

    baixar_arquivo(BASE + "name.basics.tsv.gz", nb)
    nomes = {}
    for c in _linhas(nb):
        if c[0] in peso:
            nomes[c[0]] = c[1]
    nb.unlink(missing_ok=True)

    con.execute("DELETE FROM g_arestas")
    con.execute("DELETE FROM g_pessoas")
    con.execute("DELETE FROM g_titulos")
    con.executemany("INSERT INTO g_titulos(tconst,nome,ano,tipo,votos,nota) VALUES(?,?,?,?,?,?)",
                    [(k, *v, notas_g[k]) for k, v in titulos.items()])
    con.executemany("INSERT OR IGNORE INTO g_pessoas VALUES(?,?,?,?)",
                    [(n, nomes[n], normalizar(nomes[n]), p) for n, p in peso.items() if n in nomes])
    con.executemany("INSERT OR IGNORE INTO g_arestas VALUES(?,?)", [a for a in arestas if a[0] in nomes])
    pessoas, arestas = len(nomes), len(arestas)
    db.meta(con, "grafo_em", db.agora())
    con.commit()
    ex.itens = pessoas
    ex.mensagem = f"{pessoas} pessoas, {len(titulos)} títulos, {arestas} ligações"
