"""Gera o site estático em site/: a interface (web/) mais os dados em JSON.
É o que o GitHub Pages publica. Para ver no PC:  python exportar.py && python -m http.server -d site
"""
import json
import re
import shutil
from collections import defaultdict
from datetime import date, timedelta

from muvim import db
from muvim.config import REPOSITORIO, SITE, WEB
from muvim.texto import nome_arquivo, normalizar

CARTAO = ("id,tipo,titulo,titulo_pt,data_eua,data_br,temporada,servico,estudio,direcao,poster_url,rt,mc,"
          "nota_tvmaze,hype,sinopse_pt,sinopse_en,generos,onde_br,n_temporadas,estreou")


def linhas(cur):
    return [dict(r) for r in cur.fetchall()]


def _cartao(t):
    for k in ("generos", "onde_br"):
        if t.get(k):
            try:
                t[k] = json.loads(t[k])
            except (TypeError, json.JSONDecodeError):
                pass
    t["poster"] = t.pop("poster_url", None)
    return {k: v for k, v in t.items() if v not in (None, "", [])}


def cartoes(con, sql, args=()):
    return [_cartao(t) for t in linhas(con.execute(sql, args))]


def gravar(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")


# ---------------------------------------------------------------- radar
def radar(con):
    hoje = date.today()
    seg = hoje - timedelta(days=hoje.weekday())
    fim = seg + timedelta(weeks=12)
    filmes = cartoes(con, f"SELECT {CARTAO} FROM titulos WHERE tipo='filme' AND data_eua BETWEEN ? AND ? ORDER BY data_eua",
                     (seg.isoformat(), fim.isoformat()))
    series = cartoes(con, f"SELECT {CARTAO} FROM titulos WHERE tipo='serie' AND data_eua BETWEEN ? AND ? ORDER BY data_eua",
                     (seg.isoformat(), fim.isoformat()))
    semanas = []
    for w in range(12):
        a, b = seg + timedelta(weeks=w), seg + timedelta(weeks=w, days=6)
        fs = [f for f in filmes if a.isoformat() <= f["data_eua"] <= b.isoformat()]
        ss = [s for s in series if a.isoformat() <= s["data_eua"] <= b.isoformat()]
        dest = sorted([f for f in fs if f.get("poster")], key=lambda x: -(x.get("hype") or 0))[:8]
        dest_s = sorted([s for s in ss if s.get("poster")], key=lambda x: -(x.get("hype") or 0))[:4]
        semanas.append(dict(inicio=a.isoformat(), fim=b.isoformat(), n_filmes=len(fs), n_series=len(ss),
                            itens=[_mini(x) for x in sorted(dest + dest_s, key=lambda x: x["data_eua"])]))

    futuros = [f for f in filmes if f["data_eua"] >= hoje.isoformat()]
    hypes = sorted([f.get("hype") or 0 for f in futuros])
    corte = max(15, hypes[int(len(hypes) * 0.8)] if hypes else 15)
    por_dia = defaultdict(list)
    for f in futuros:
        if (f.get("hype") or 0) >= corte:
            por_dia[f["data_eua"]].append(f)
    choques = []
    for dia, fs in por_dia.items():
        if len(fs) < 2:
            continue
        fs = sorted(fs, key=lambda x: -(x.get("hype") or 0))[:3]
        ids = [f["id"] for f in fs]
        comuns = [r[0] for r in con.execute(
            f"SELECT pessoa FROM elenco WHERE titulo_id IN ({','.join('?' * len(ids))}) GROUP BY pessoa HAVING count(*)>1", ids)]
        choques.append(dict(dia=dia, filmes=[_mini(f) for f in fs], comuns=comuns, peso=sum(f.get("hype") or 0 for f in fs)))
    choques.sort(key=lambda c: -c["peso"])

    aguardado = max(futuros, key=lambda f: f.get("hype") or 0, default=None)
    proximos = cartoes(con, f"SELECT {CARTAO} FROM titulos WHERE data_eua BETWEEN ? AND ? ORDER BY data_eua, hype DESC",
                       (hoje.isoformat(), (hoje + timedelta(days=13)).isoformat()))
    n_pessoas = con.execute(
        "SELECT count(*) FROM (SELECT e.pessoa FROM elenco e JOIN titulos t ON t.id=e.titulo_id "
        "WHERE t.data_eua BETWEEN date('now') AND date('now','+120 day') GROUP BY e.pessoa HAVING count(*)>1)").fetchone()[0]
    kpis = dict(
        filmes=len(futuros),
        series=sum(1 for s in series if s["data_eua"] >= hoje.isoformat()),
        pessoas=n_pessoas,
        mudancas=con.execute("SELECT count(*) FROM mudancas WHERE dia>=date('now','-1 day')").fetchone()[0])
    return dict(gerado=hoje.isoformat(), semanas=semanas, choques=choques[:3],
                aguardado={k: aguardado[k] for k in aguardado if k not in ("sinopse_en", "sinopse_pt")} if aguardado else None,
                proximos=[_mini(x) for x in proximos[:40]], kpis=kpis, aniversarios=aniversarios(con))


def _mini(t):
    """O mínimo para um cartão na tela (o resto fica na página do título)."""
    return {k: t[k] for k in ("id", "tipo", "titulo", "titulo_pt", "data_eua", "data_br", "temporada", "servico",
                              "estudio", "poster", "rt", "nota_tvmaze", "onde_br", "hype") if k in t}


def aniversarios(con):
    out = []
    for a in linhas(con.execute("SELECT * FROM aniversarios WHERE dia=? ORDER BY ano", (date.today().isoformat(),))):
        prox = linhas(con.execute(
            "SELECT t.id, t.titulo, t.data_eua FROM elenco e JOIN titulos t ON t.id=e.titulo_id "
            "WHERE e.pessoa=? AND t.data_eua >= date('now') ORDER BY t.data_eua LIMIT 2", (a["nome"],)))
        g = con.execute("SELECT qid, pop FROM g_pessoas WHERE nome_busca=? ORDER BY pop DESC LIMIT 1",
                        (normalizar(a["nome"]),)).fetchone()
        conhecido = [r[0] for r in con.execute(
            "SELECT COALESCE(t.nome_pt, t.nome) FROM g_arestas a JOIN g_titulos t ON t.qid=a.titulo WHERE a.pessoa=? "
            "ORDER BY t.pop DESC LIMIT 3", (g[0],))] if g else []
        a.update(proximos=prox, conhecido=conhecido, peso=g[1] if g else 0)
        out.append(a)
    out.sort(key=lambda a: (-bool(a["proximos"]), -a["peso"], -(a["ano"] or 0)))
    return out[:8]


# ---------------------------------------------------------------- séries e pessoas
def series(con):
    return cartoes(con, f"SELECT {CARTAO} FROM titulos WHERE tipo='serie' AND data_eua >= date('now','-3 day') "
                        "ORDER BY data_eua, hype DESC")


def pessoas(con):
    rs = linhas(con.execute(
        "SELECT e.pessoa, t.id, t.titulo, t.tipo, t.data_eua FROM elenco e JOIN titulos t ON t.id=e.titulo_id "
        "WHERE t.data_eua BETWEEN date('now') AND date('now','+120 day') ORDER BY t.data_eua"))
    por = defaultdict(list)
    for r in rs:
        por[r["pessoa"]].append(dict(id=r["id"], t=r["titulo"], d=r["data_eua"], tipo=r["tipo"]))
    out = [dict(nome=p, itens=i) for p, i in por.items() if len(i) > 1]
    out.sort(key=lambda p: (-len(p["itens"]), p["itens"][0]["d"]))
    return dict(inicio=date.today().isoformat(), fim=(date.today() + timedelta(days=120)).isoformat(), pessoas=out[:60])


# ---------------------------------------------------------------- título
def titulo(con, tid):
    t = _cartao(dict(con.execute("SELECT * FROM titulos WHERE id=?", (tid,)).fetchone()))
    for k in ("criado_em", "atualizado_em", "sinopse_pt_fonte_x"):
        t.pop(k, None)
    t["elenco"] = linhas(con.execute("SELECT pessoa, papel FROM elenco WHERE titulo_id=? ORDER BY ordem", (tid,)))
    t["curiosidades"] = linhas(con.execute("SELECT titulo, texto, fonte, gerado_por FROM curiosidades WHERE titulo_id=? ORDER BY ordem", (tid,)))
    t["mudancas"] = linhas(con.execute("SELECT dia, campo, antes, depois FROM mudancas WHERE titulo_id=? AND campo<>'novo' ORDER BY id DESC LIMIT 20", (tid,)))
    t["cruzamentos"] = linhas(con.execute(
        "SELECT e2.pessoa, t2.id, t2.titulo, t2.data_eua FROM elenco e1 JOIN elenco e2 ON e1.pessoa=e2.pessoa AND e2.titulo_id<>e1.titulo_id "
        "JOIN titulos t2 ON t2.id=e2.titulo_id WHERE e1.titulo_id=? AND t2.data_eua >= date('now','-30 day') ORDER BY t2.data_eua LIMIT 20", (tid,)))
    # A franquia na crítica: títulos da mesma série no Wikidata (P179), com Rotten Tomatoes
    fr = []
    if t.get("serie_qid"):
        fr = linhas(con.execute("SELECT COALESCE(nome_pt, nome) nome, ano, tipo, rt, mc, pop FROM g_titulos "
                                "WHERE serie=? AND rt IS NOT NULL ORDER BY ano LIMIT 14", (t["serie_qid"],)))
    if len(fr) < 2:
        base = re.split(r":| Part | – | - ", t["titulo"])[0].strip()
        if len(base) >= 3:
            fr = linhas(con.execute(
                "SELECT COALESCE(nome_pt, nome) nome, ano, tipo, rt, mc, pop FROM g_titulos "
                "WHERE (nome=? OR nome LIKE ?) AND rt IS NOT NULL ORDER BY ano LIMIT 14", (base, base + ":%")))
    t["franquia"] = fr if len(fr) >= 2 else []
    if t.get("tvmaze_id"):
        t["episodios"] = [[e["temporada"], e["numero"], e["nome"], e["data"], e["duracao"]] for e in linhas(con.execute(
            "SELECT temporada, numero, nome, data, duracao FROM episodios WHERE tvmaze_show=? ORDER BY temporada, numero",
            (t["tvmaze_id"],)))]
    return t


# ---------------------------------------------------------------- mudanças, índice, grafo, bastidores
ROTULOS = {"novo": "Entrou no radar", "data_eua": "Estreia nos EUA", "data_br": "Estreia no Brasil",
           "temporada": "Temporada", "onde_br": "Streaming", "rt": "Rotten Tomatoes", "titulo_pt": "Título em português"}


def mudancas(con):
    rs = linhas(con.execute(
        "SELECT m.dia, m.campo, m.antes, m.depois, t.id, t.titulo, t.tipo, t.poster_url poster FROM mudancas m "
        "JOIN titulos t ON t.id=m.titulo_id WHERE m.dia >= date('now','-30 day') ORDER BY m.dia DESC, m.campo, t.hype DESC"))
    for r in rs:
        r["rotulo"] = ROTULOS.get(r["campo"], r["campo"])
    return rs


def indice(con):
    """Todos os títulos, para busca, links e alertas da lista (que vive no navegador)."""
    elenco = defaultdict(list)
    for tid, p in con.execute("SELECT titulo_id, pessoa FROM elenco ORDER BY ordem"):
        elenco[tid].append(p)
    out = []
    for t in cartoes(con, f"SELECT {CARTAO} FROM titulos ORDER BY data_eua"):
        m = _mini(t)
        m["a"] = nome_arquivo(t["id"])
        m["e"] = elenco.get(t["id"], [])
        out.append(m)
    return out


def grafo(con):
    """Grafo compacto para as Ligações, calculadas no navegador.
    p: [nome, popularidade]; t: [nome, ano, 'f'|'s']; e: para cada pessoa, os índices dos títulos."""
    ts = linhas(con.execute("SELECT qid, COALESCE(nome_pt, nome) nome, ano, tipo, pop FROM g_titulos ORDER BY pop DESC"))
    it = {t["qid"]: i for i, t in enumerate(ts)}
    ps = linhas(con.execute("SELECT qid, nome, pop FROM g_pessoas ORDER BY pop DESC"))
    ip = {p["qid"]: i for i, p in enumerate(ps)}
    e = [[] for _ in ps]
    for pessoa, tit in con.execute("SELECT pessoa, titulo FROM g_arestas"):
        if pessoa in ip and tit in it:
            e[ip[pessoa]].append(it[tit])
    return dict(p=[[p["nome"], p["pop"]] for p in ps], t=[[t["nome"], t["ano"], t["tipo"][0]] for t in ts],
                e=[sorted(x) for x in e])


def bastidores(con):
    fontes = linhas(con.execute(
        "SELECT e.fonte, e.inicio, e.fim, e.status, e.itens, e.mensagem FROM execucoes e "
        "JOIN (SELECT fonte, max(id) id FROM execucoes GROUP BY fonte) u ON u.id=e.id ORDER BY e.id"))
    n = lambda sql: con.execute(sql).fetchone()[0]
    return dict(fontes=fontes, ultima_coleta=db.meta(con, "coleta_ok"), grafo_em=db.meta(con, "grafo_em"),
                repositorio=REPOSITORIO, contagens=dict(
                    filmes=n("SELECT count(*) FROM titulos WHERE tipo='filme'"),
                    series=n("SELECT count(*) FROM titulos WHERE tipo='serie'"),
                    com_pt=n("SELECT count(*) FROM titulos WHERE sinopse_pt IS NOT NULL"),
                    com_critica=n("SELECT count(*) FROM titulos WHERE rt IS NOT NULL OR mc IS NOT NULL"),
                    curiosidades=n("SELECT count(DISTINCT titulo_id) FROM curiosidades"),
                    episodios=n("SELECT count(*) FROM episodios"),
                    grafo_pessoas=n("SELECT count(*) FROM g_pessoas"),
                    grafo_titulos=n("SELECT count(*) FROM g_titulos"),
                    mudancas=n("SELECT count(*) FROM mudancas")))


def main():
    con = db.conectar()
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(WEB, SITE)
    d = SITE / "dados"
    gravar(d / "radar.json", radar(con))
    gravar(d / "series.json", series(con))
    gravar(d / "pessoas.json", pessoas(con))
    gravar(d / "mudancas.json", mudancas(con))
    gravar(d / "indice.json", indice(con))
    gravar(d / "bastidores.json", bastidores(con))
    gravar(d / "grafo.json", grafo(con))
    ids = [r[0] for r in con.execute("SELECT id FROM titulos")]
    for tid in ids:
        gravar(d / "t" / f"{nome_arquivo(tid)}.json", titulo(con, tid))
    (SITE / ".nojekyll").write_text("")  # o Pages não deve processar o site com Jekyll
    tam = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"site/ gerado: {len(ids)} títulos, {tam / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
