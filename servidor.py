"""Servidor local do Muvim: entrega a interface e a API em http://localhost:8790.
Só escuta no próprio PC (127.0.0.1)."""
import json
import mimetypes
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from muvim import db
from muvim.config import PORTA, POSTERES, RAIZ, WEB
from muvim.curadoria import achar_claude
from muvim.fontes import tmdb
from muvim.fontes.imdb import normalizar


def linhas(cur):
    return [dict(r) for r in cur.fetchall()]


def _json_campos(t):
    for k in ("generos", "onde_br"):
        if t.get(k):
            try:
                t[k] = json.loads(t[k])
            except (TypeError, json.JSONDecodeError):
                pass
    t["poster"] = f"/posteres/{t['poster']}" if t.get("poster") else None
    return t


CARTAO = ("id,tipo,titulo,titulo_pt,data_eua,data_br,temporada,servico,estudio,direcao,poster,nota_imdb,"
          "votos_imdb,hype,sinopse_pt,sinopse_en,generos,onde_br,n_temporadas,estreou")


def cartoes(con, sql, args=()):
    return [_json_campos(t) for t in linhas(con.execute(sql, args))]


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
        dest = sorted([f for f in fs if f["poster"]], key=lambda x: -(x["hype"] or 0))[:8]
        dest_s = sorted([s for s in ss if s["poster"]], key=lambda x: -(x["hype"] or 0))[:4]
        semanas.append(dict(inicio=a.isoformat(), fim=b.isoformat(), n_filmes=len(fs), n_series=len(ss),
                            itens=sorted(dest + dest_s, key=lambda x: x["data_eua"])))

    futuros = [f for f in filmes if f["data_eua"] >= hoje.isoformat()]
    hypes = sorted([f["hype"] or 0 for f in futuros])
    corte = max(15, hypes[int(len(hypes) * 0.8)] if hypes else 15)
    por_dia = defaultdict(list)
    for f in futuros:
        if (f["hype"] or 0) >= corte:
            por_dia[f["data_eua"]].append(f)
    choques = []
    for dia, fs in por_dia.items():
        if len(fs) < 2:
            continue
        fs = sorted(fs, key=lambda x: -(x["hype"] or 0))[:3]
        ids = [f["id"] for f in fs]
        comuns = [r[0] for r in con.execute(
            f"SELECT pessoa FROM elenco WHERE titulo_id IN ({','.join('?' * len(ids))}) GROUP BY pessoa HAVING count(*)>1", ids)]
        choques.append(dict(dia=dia, filmes=fs, comuns=comuns, peso=sum(f["hype"] or 0 for f in fs)))
    choques.sort(key=lambda c: -c["peso"])

    aguardado = max(futuros, key=lambda f: f["hype"] or 0, default=None)
    sem_atual = semanas[0]
    esta = cartoes(con, f"SELECT {CARTAO} FROM titulos WHERE data_eua BETWEEN ? AND ? ORDER BY data_eua, hype DESC",
                   (hoje.isoformat(), (hoje + timedelta(days=6)).isoformat()))
    n_pessoas = con.execute(
        "SELECT count(*) FROM (SELECT e.pessoa FROM elenco e JOIN titulos t ON t.id=e.titulo_id "
        "WHERE t.data_eua BETWEEN date('now') AND date('now','+120 day') GROUP BY e.pessoa HAVING count(*)>1)").fetchone()[0]
    kpis = dict(
        filmes=sum(1 for f in filmes if f["data_eua"] >= hoje.isoformat()),
        series=sum(1 for s in series if s["data_eua"] >= hoje.isoformat()),
        pessoas=n_pessoas,
        mudancas=con.execute("SELECT count(*) FROM mudancas WHERE dia>=date('now','-1 day')").fetchone()[0])
    return dict(hoje=hoje.isoformat(), semanas=semanas, choques=choques[:3], aguardado=aguardado,
                esta_semana=esta[:12], kpis=kpis, aniversarios=aniversarios(con), semana_atual=sem_atual["inicio"])


def aniversarios(con):
    out = []
    for a in linhas(con.execute("SELECT * FROM aniversarios WHERE dia=? ORDER BY ano", (date.today().isoformat(),))):
        prox = linhas(con.execute(
            "SELECT t.id, t.titulo, t.data_eua FROM elenco e JOIN titulos t ON t.id=e.titulo_id "
            "WHERE e.pessoa=? AND t.data_eua >= date('now') ORDER BY t.data_eua LIMIT 2", (a["nome"],)))
        g = con.execute("SELECT nconst, peso FROM g_pessoas WHERE nome_busca=? ORDER BY peso DESC LIMIT 1",
                        (normalizar(a["nome"]),)).fetchone()
        conhecido = [r[0] for r in con.execute(
            "SELECT t.nome FROM g_arestas a JOIN g_titulos t ON t.tconst=a.tconst WHERE a.nconst=? "
            "ORDER BY t.votos DESC LIMIT 3", (g[0],))] if g else []
        a.update(proximos=prox, conhecido=conhecido, peso=g[1] if g else 0)
        out.append(a)
    # Os mais conhecidos primeiro, depois quem tem estreia chegando
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
    t = con.execute("SELECT * FROM titulos WHERE id=?", (tid,)).fetchone()
    if not t:
        return None
    t = _json_campos(dict(t))
    t["elenco"] = linhas(con.execute("SELECT pessoa, papel FROM elenco WHERE titulo_id=? ORDER BY ordem", (tid,)))
    t["curiosidades"] = linhas(con.execute("SELECT titulo, texto, fonte, gerado_por FROM curiosidades WHERE titulo_id=? ORDER BY ordem", (tid,)))
    t["mudancas"] = linhas(con.execute("SELECT dia, campo, antes, depois FROM mudancas WHERE titulo_id=? AND campo<>'novo' ORDER BY id DESC LIMIT 20", (tid,)))
    t["na_lista"] = con.execute("SELECT 1 FROM lista WHERE titulo_id=?", (tid,)).fetchone() is not None
    # Outros lançamentos com gente deste elenco
    t["cruzamentos"] = linhas(con.execute(
        "SELECT e2.pessoa, t2.id, t2.titulo, t2.data_eua FROM elenco e1 JOIN elenco e2 ON e1.pessoa=e2.pessoa AND e2.titulo_id<>e1.titulo_id "
        "JOIN titulos t2 ON t2.id=e2.titulo_id WHERE e1.titulo_id=? AND t2.data_eua >= date('now','-30 day') ORDER BY t2.data_eua LIMIT 20", (tid,)))
    # A franquia em notas: títulos do IMDb com o mesmo nome-base
    base = re.split(r":| Part | – | - ", t["titulo"])[0].strip()
    fr = []
    if len(base) >= 3:
        fr = linhas(con.execute(
            "SELECT nome, ano, tipo, votos, nota, tconst FROM g_titulos WHERE (nome=? OR nome LIKE ? OR nome LIKE ?) "
            "AND nota IS NOT NULL ORDER BY ano LIMIT 12", (base, base + ":%", base + " %")))
    t["franquia"] = fr if len(fr) >= 2 else []
    if t["tvmaze_id"]:
        t["episodios"] = linhas(con.execute("SELECT temporada, numero, nome, data, duracao FROM episodios "
                                            "WHERE tvmaze_show=? ORDER BY temporada, numero", (t["tvmaze_id"],)))
        l = con.execute("SELECT assistido_temp, assistido_ep FROM lista WHERE titulo_id=?", (tid,)).fetchone()
        t["assistido"] = dict(l) if l else None
    return t


# ---------------------------------------------------------------- mudanças, lista, alertas
ROTULOS = {"novo": "Entrou no radar", "data_eua": "Estreia nos EUA", "data_br": "Estreia no Brasil",
           "temporada": "Temporada", "onde_br": "Onde assistir", "nota_imdb": "Nota IMDb", "titulo_pt": "Título em português"}


def mudancas(con, dias):
    rs = linhas(con.execute(
        "SELECT m.dia, m.campo, m.antes, m.depois, t.id, t.titulo, t.tipo, t.poster, t.data_eua FROM mudancas m "
        "JOIN titulos t ON t.id=m.titulo_id WHERE m.dia >= date('now', ?) ORDER BY m.dia DESC, m.campo, t.hype DESC",
        (f"-{dias} day",)))
    for r in rs:
        r["rotulo"] = ROTULOS.get(r["campo"], r["campo"])
        r["poster"] = f"/posteres/{r['poster']}" if r["poster"] else None
    return rs


def lista(con):
    return cartoes(con, f"SELECT {', '.join('t.' + c for c in CARTAO.split(','))}, l.adicionado_em, l.assistido_temp, l.assistido_ep, "
                        "t.tvmaze_id FROM lista l JOIN titulos t ON t.id=l.titulo_id ORDER BY COALESCE(t.data_br, t.data_eua)")


# ---------------------------------------------------------------- ligações entre pessoas
def resolver_pessoa(con, nome):
    return con.execute("SELECT nconst, nome FROM g_pessoas WHERE nome_busca=? ORDER BY peso DESC LIMIT 1",
                       (normalizar(nome),)).fetchone()


def _vizinhos(con, pessoas):
    """pessoa -> [(titulo, outra pessoa)], dos títulos e pessoas mais conhecidos para os menos,
    para que o caminho escolhido passe por gente que se reconhece."""
    out = defaultdict(list)
    ps = list(pessoas)
    for i in range(0, len(ps), 400):
        lote = ps[i:i + 400]
        q = ",".join("?" * len(lote))
        for n1, t, n2 in con.execute(
                f"SELECT a1.nconst, a1.tconst, a2.nconst FROM g_arestas a1 JOIN g_arestas a2 ON a2.tconst=a1.tconst "
                f"AND a2.nconst<>a1.nconst JOIN g_titulos gt ON gt.tconst=a1.tconst JOIN g_pessoas gp ON gp.nconst=a2.nconst "
                f"WHERE a1.nconst IN ({q}) ORDER BY gt.votos DESC, gp.peso DESC", lote):
            out[n1].append((t, n2))
    return out


def conexao(con, a, b, max_passos=6):
    pa, pb = resolver_pessoa(con, a), resolver_pessoa(con, b)
    if not pa or not pb:
        return dict(erro=f"Não encontrei {'“' + a + '”' if not pa else '“' + b + '”'} entre as pessoas do IMDb.")
    if pa[0] == pb[0]:
        return dict(caminho=[dict(pessoa=pa[1])])
    # Busca em largura pelos dois lados ao mesmo tempo
    pais_a, pais_b = {pa[0]: None}, {pb[0]: None}
    fr_a, fr_b = {pa[0]}, {pb[0]}
    encontro = None
    for _ in range(max_passos):
        lado_a = len(fr_a) <= len(fr_b)
        fr, pais, outros = (fr_a, pais_a, pais_b) if lado_a else (fr_b, pais_b, pais_a)
        prox, encontros = set(), []
        for p, viz in _vizinhos(con, fr).items():
            for t, q in viz:
                if q not in pais:
                    pais[q] = (p, t)
                    prox.add(q)
                if q in outros and q not in encontros:
                    encontros.append(q)
        if lado_a:
            fr_a = prox
        else:
            fr_b = prox
        if encontros:
            # Entre os pontos de encontro desta camada, o mais conhecido
            q = ",".join("?" * len(encontros))
            encontro = con.execute(f"SELECT nconst FROM g_pessoas WHERE nconst IN ({q}) ORDER BY peso DESC LIMIT 1",
                                   encontros).fetchone()[0]
            break
        if not prox:
            break
    if not encontro:
        return dict(erro="Não achei ligação em até 6 passos. O grafo só inclui títulos com 5 mil votos ou mais no IMDb.")
    ida, n = [], encontro
    while pais_a[n]:
        p, t = pais_a[n]
        ida.append((n, t))
        n = p
    ida.append((n, None))
    ida.reverse()  # de A até o encontro: [(A,None),(x,t1),...]
    volta, n = [], encontro
    while pais_b[n]:
        p, t = pais_b[n]
        volta.append((p, t))
        n = p
    seq = ida + volta  # pessoas com o título que liga à anterior
    nomes = {r[0]: r[1] for r in con.execute(
        f"SELECT nconst, nome FROM g_pessoas WHERE nconst IN ({','.join('?' * len(seq))})", [s[0] for s in seq])}
    tits = {r[0]: (r[1], r[2]) for r in con.execute(
        f"SELECT tconst, nome, ano FROM g_titulos WHERE tconst IN ({','.join('?' * len(seq))})", [s[1] for s in seq])}
    caminho = []
    for p, t in seq:
        item = dict(pessoa=nomes.get(p, p), nconst=p)
        if t:
            item["via"], item["ano"] = tits.get(t, (t, None))
        caminho.append(item)
    return dict(caminho=caminho, passos=len(caminho) - 1)


def sugerir_pessoas(con, q):
    n = normalizar(q)
    if len(n) < 2:
        return []
    return [r[0] for r in con.execute("SELECT nome FROM g_pessoas WHERE nome_busca LIKE ? ORDER BY peso DESC LIMIT 8", (n + "%",))]


def busca(con, q):
    like = f"%{q}%"
    tits = cartoes(con, f"SELECT {CARTAO} FROM titulos WHERE titulo LIKE ? OR titulo_pt LIKE ? "
                        "ORDER BY data_eua >= date('now') DESC, hype DESC LIMIT 20", (like, like))
    pes = linhas(con.execute("SELECT e.pessoa, count(*) n FROM elenco e WHERE e.pessoa LIKE ? GROUP BY e.pessoa "
                             "ORDER BY n DESC LIMIT 8", (like,)))
    for p in pes:
        p["titulos"] = cartoes(con, f"SELECT {', '.join('t.' + c for c in CARTAO.split(','))} FROM elenco e "
                                    "JOIN titulos t ON t.id=e.titulo_id WHERE e.pessoa=? ORDER BY t.data_eua DESC", (p["pessoa"],))
    return dict(titulos=tits, pessoas=pes)


# ---------------------------------------------------------------- bastidores
def bastidores(con):
    fontes = linhas(con.execute(
        "SELECT e.* FROM execucoes e JOIN (SELECT fonte, max(id) id FROM execucoes GROUP BY fonte) u ON u.id=e.id ORDER BY e.id"))
    contagens = dict(
        filmes=con.execute("SELECT count(*) FROM titulos WHERE tipo='filme'").fetchone()[0],
        series=con.execute("SELECT count(*) FROM titulos WHERE tipo='serie'").fetchone()[0],
        posteres=con.execute("SELECT count(*) FROM titulos WHERE poster IS NOT NULL").fetchone()[0],
        com_pt=con.execute("SELECT count(*) FROM titulos WHERE sinopse_pt IS NOT NULL").fetchone()[0],
        curiosidades=con.execute("SELECT count(DISTINCT titulo_id) FROM curiosidades").fetchone()[0],
        episodios=con.execute("SELECT count(*) FROM episodios").fetchone()[0],
        grafo_pessoas=con.execute("SELECT count(*) FROM g_pessoas").fetchone()[0],
        grafo_titulos=con.execute("SELECT count(*) FROM g_titulos").fetchone()[0],
        mudancas=con.execute("SELECT count(*) FROM mudancas").fetchone()[0])
    return dict(fontes=fontes, contagens=contagens, ultima_coleta=db.meta(con, "coleta_ok"),
                grafo_em=db.meta(con, "grafo_em"), tmdb=tmdb.disponivel(), claude=bool(achar_claude()),
                coletando=(RAIZ / "dados" / "coleta.trava").exists())


# ---------------------------------------------------------------- HTTP
class App(BaseHTTPRequestHandler):
    server_version = "Muvim/1.0"

    def log_message(self, *a):
        pass

    def _enviar(self, corpo, tipo="application/json; charset=utf-8", status=200, cache=None):
        if not isinstance(corpo, bytes):
            corpo = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", cache or "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, base, nome, cache=None):
        p = (base / nome).resolve()
        if base.resolve() not in p.parents or not p.is_file():
            return self._enviar({"erro": "não encontrado"}, status=404)
        tipo = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo.endswith("javascript"):
            tipo += "; charset=utf-8"
        self._enviar(p.read_bytes(), tipo, cache=cache)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        cam = unquote(u.path)
        if cam in ("/", "/index.html"):
            return self._arquivo(WEB, "index.html")
        if cam.startswith("/web/"):
            return self._arquivo(WEB, cam[5:])
        if cam.startswith("/posteres/"):
            return self._arquivo(POSTERES, cam[10:], cache="max-age=604800")
        con = db.conectar()
        try:
            rotas = {
                "/api/radar": lambda: radar(con),
                "/api/series": lambda: series(con),
                "/api/pessoas": lambda: pessoas(con),
                "/api/titulo": lambda: titulo(con, q.get("id", "")) or {"erro": "título não encontrado"},
                "/api/mudancas": lambda: mudancas(con, int(q.get("dias", 7))),
                "/api/lista": lambda: lista(con),
                "/api/alertas": lambda: linhas(con.execute(
                    "SELECT a.*, t.titulo, t.poster FROM alertas a LEFT JOIN titulos t ON t.id=a.titulo_id ORDER BY a.id DESC LIMIT 50")),
                "/api/conexao": lambda: conexao(con, q.get("a", ""), q.get("b", "")),
                "/api/sugerir-pessoas": lambda: sugerir_pessoas(con, q.get("q", "")),
                "/api/busca": lambda: busca(con, q.get("q", "")),
                "/api/bastidores": lambda: bastidores(con),
            }
            if cam not in rotas:
                return self._enviar({"erro": "rota desconhecida"}, status=404)
            self._enviar(rotas[cam]())
        except Exception as e:
            self._enviar({"erro": f"{type(e).__name__}: {e}"}, status=500)
        finally:
            con.close()

    def do_POST(self):
        # Só aceita chamadas da própria interface (o cabeçalho próprio barra outros sites)
        if self.headers.get("X-Muvim") != "1":
            return self._enviar({"erro": "proibido"}, status=403)
        n = int(self.headers.get("Content-Length") or 0)
        corpo = json.loads(self.rfile.read(n) or b"{}")
        cam = urlparse(self.path).path
        con = db.conectar()
        try:
            if cam == "/api/lista":
                tid, acao = corpo.get("id"), corpo.get("acao")
                if acao == "add":
                    con.execute("INSERT OR IGNORE INTO lista(titulo_id, adicionado_em) VALUES(?,?)", (tid, db.agora()))
                elif acao == "remove":
                    con.execute("DELETE FROM lista WHERE titulo_id=?", (tid,))
                elif acao == "assistido":
                    con.execute("UPDATE lista SET assistido_temp=?, assistido_ep=? WHERE titulo_id=?",
                                (corpo.get("temp"), corpo.get("ep"), tid))
                con.commit()
                return self._enviar({"ok": True, "na_lista": con.execute("SELECT 1 FROM lista WHERE titulo_id=?", (tid,)).fetchone() is not None})
            if cam == "/api/alertas/lidos":
                con.execute("UPDATE alertas SET lido=1")
                con.commit()
                return self._enviar({"ok": True})
            if cam == "/api/coletar":
                subprocess.Popen([sys.executable, str(RAIZ / "coletar.py"), "--forcar"], cwd=RAIZ,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return self._enviar({"ok": True})
            self._enviar({"erro": "rota desconhecida"}, status=404)
        finally:
            con.close()


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), App)
    print(f"Muvim em http://localhost:{PORTA}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
