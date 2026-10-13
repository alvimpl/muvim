"""Banco SQLite: esquema, conexão e gravação com registro de mudanças."""
import json
import sqlite3
from datetime import date, datetime

from .config import BANCO

ESQUEMA = """
CREATE TABLE IF NOT EXISTS titulos(
  id TEXT PRIMARY KEY,            -- f:<pagina da wikipedia> ou s:<id do tvmaze>
  tipo TEXT NOT NULL,             -- filme | serie
  titulo TEXT NOT NULL,
  titulo_pt TEXT,
  data_eua TEXT,                  -- filme: estreia nos EUA; série: próxima estreia de temporada
  data_br TEXT,
  temporada INTEGER,
  servico TEXT,                   -- série: canal/streaming de origem
  onde_br TEXT,                   -- JSON: streaming de origem do filme (Netflix, Apple TV...)
  estudio TEXT,
  direcao TEXT,
  generos TEXT,                   -- JSON
  sinopse_en TEXT,
  sinopse_pt TEXT,
  sinopse_pt_fonte TEXT,
  poster TEXT,                    -- nome do arquivo em dados/posteres
  poster_url TEXT,
  wiki_pagina TEXT,
  wikidata TEXT,
  imdb_id TEXT,
  tvmaze_id INTEGER,
  nota_imdb REAL,
  votos_imdb INTEGER,
  hype INTEGER,                   -- filmes: nº de Wikipedias com artigo; séries: peso do TVmaze
  estreou TEXT,                   -- série: data da estreia original
  n_temporadas INTEGER,
  criado_em TEXT,
  atualizado_em TEXT
);
CREATE INDEX IF NOT EXISTS ix_titulos_data ON titulos(data_eua);
CREATE INDEX IF NOT EXISTS ix_titulos_imdb ON titulos(imdb_id);

CREATE TABLE IF NOT EXISTS elenco(
  titulo_id TEXT, pessoa TEXT, papel TEXT, ordem INTEGER,
  PRIMARY KEY(titulo_id, pessoa)
);
CREATE INDEX IF NOT EXISTS ix_elenco_pessoa ON elenco(pessoa);

CREATE TABLE IF NOT EXISTS episodios(
  tvmaze_show INTEGER, temporada INTEGER, numero INTEGER, nome TEXT,
  data TEXT, duracao INTEGER,
  PRIMARY KEY(tvmaze_show, temporada, numero)
);

CREATE TABLE IF NOT EXISTS curiosidades(
  titulo_id TEXT, ordem INTEGER, titulo TEXT, texto TEXT, fonte TEXT, gerado_por TEXT,
  PRIMARY KEY(titulo_id, ordem)
);

CREATE TABLE IF NOT EXISTS artigos(
  titulo_id TEXT PRIMARY KEY, texto TEXT, buscado_em TEXT
);

CREATE TABLE IF NOT EXISTS mudancas(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dia TEXT, titulo_id TEXT, campo TEXT, antes TEXT, depois TEXT
);
CREATE INDEX IF NOT EXISTS ix_mudancas_dia ON mudancas(dia);

CREATE TABLE IF NOT EXISTS lista(
  titulo_id TEXT PRIMARY KEY, adicionado_em TEXT,
  assistido_temp INTEGER, assistido_ep INTEGER   -- até onde a série já foi vista
);

CREATE TABLE IF NOT EXISTS alertas(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  criado_em TEXT, titulo_id TEXT, texto TEXT, lido INTEGER DEFAULT 0,
  UNIQUE(titulo_id, texto)
);

CREATE TABLE IF NOT EXISTS aniversarios(
  dia TEXT, ano INTEGER, nome TEXT, descricao TEXT, pagina TEXT,
  PRIMARY KEY(dia, nome)
);

CREATE TABLE IF NOT EXISTS execucoes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fonte TEXT, inicio TEXT, fim TEXT, status TEXT, itens INTEGER, mensagem TEXT
);

-- Grafo de ligações entre pessoas (IMDb, títulos mais conhecidos de cada pessoa)
CREATE TABLE IF NOT EXISTS g_pessoas(nconst TEXT PRIMARY KEY, nome TEXT, nome_busca TEXT, peso INTEGER);
CREATE INDEX IF NOT EXISTS ix_gp_nome ON g_pessoas(nome_busca);
CREATE TABLE IF NOT EXISTS g_titulos(tconst TEXT PRIMARY KEY, nome TEXT, ano INTEGER, tipo TEXT, votos INTEGER, nota REAL);
CREATE TABLE IF NOT EXISTS g_arestas(nconst TEXT, tconst TEXT, PRIMARY KEY(nconst, tconst));
CREATE INDEX IF NOT EXISTS ix_ga_t ON g_arestas(tconst);

CREATE TABLE IF NOT EXISTS meta(chave TEXT PRIMARY KEY, valor TEXT);
"""

# Campos cuja mudança vira notícia em "O que mudou"
VIGIADOS = ("data_eua", "data_br", "temporada", "onde_br", "nota_imdb", "titulo_pt")
# Nestes, aparecer pela primeira vez já é notícia (ex.: o filme ganhou data no Brasil)
NOVIDADE_DO_ZERO = ("data_br", "data_eua")


_preparado = False


def conectar():
    """Abre o banco. O esquema só é conferido na primeira conexão do processo: conferir a cada
    requisição pediria trava de escrita e o site travaria enquanto a coleta grava."""
    global _preparado
    con = sqlite3.connect(BANCO, timeout=30)
    con.row_factory = sqlite3.Row
    if not _preparado:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(ESQUEMA)
        # Migrações simples: colunas que entraram depois da primeira versão do banco
        cols = {r[1] for r in con.execute("PRAGMA table_info(g_titulos)")}
        if "nota" not in cols:
            con.execute("ALTER TABLE g_titulos ADD COLUMN nota REAL")
        con.commit()
        _preparado = True
    return con


def agora():
    return datetime.now().isoformat(timespec="seconds")


def hoje():
    return date.today().isoformat()


def meta(con, chave, valor=None):
    if valor is None:
        r = con.execute("SELECT valor FROM meta WHERE chave=?", (chave,)).fetchone()
        return r[0] if r else None
    con.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (chave, str(valor)))


def _igual(campo, a, b):
    if campo == "nota_imdb" and a is not None and b is not None:
        return abs(float(a) - float(b)) < 0.1
    return (a if a not in ("", None) else None) == (b if b not in ("", None) else None)


def gravar_titulo(con, rec: dict, registrar=True):
    """Insere ou atualiza um título. Campos ausentes ou None não apagam o que já existe.
    Mudanças em campos vigiados são registradas em `mudancas`."""
    rec = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in rec.items()}
    antigo = con.execute("SELECT * FROM titulos WHERE id=?", (rec["id"],)).fetchone()
    if antigo is None:
        rec.setdefault("criado_em", agora())
        rec["atualizado_em"] = agora()
        cols = ",".join(rec)
        con.execute(f"INSERT INTO titulos({cols}) VALUES({','.join('?' * len(rec))})", list(rec.values()))
        if registrar:
            con.execute("INSERT INTO mudancas(dia,titulo_id,campo,antes,depois) VALUES(?,?,?,?,?)",
                        (hoje(), rec["id"], "novo", None, rec.get("data_eua")))
        return
    novos = {k: v for k, v in rec.items() if k != "id" and v is not None}
    if registrar:
        for campo in VIGIADOS:
            if campo not in novos or _igual(campo, antigo[campo], novos[campo]):
                continue
            if antigo[campo] is not None or campo in NOVIDADE_DO_ZERO:
                con.execute("INSERT INTO mudancas(dia,titulo_id,campo,antes,depois) VALUES(?,?,?,?,?)",
                            (hoje(), rec["id"], campo, None if antigo[campo] is None else str(antigo[campo]),
                             str(novos[campo])))
    if novos:
        novos["atualizado_em"] = agora()
        sets = ",".join(f"{k}=?" for k in novos)
        con.execute(f"UPDATE titulos SET {sets} WHERE id=?", [*novos.values(), rec["id"]])


def gravar_elenco(con, titulo_id, pessoas):
    """pessoas: lista de (nome, papel)."""
    con.execute("DELETE FROM elenco WHERE titulo_id=?", (titulo_id,))
    con.executemany("INSERT OR IGNORE INTO elenco VALUES(?,?,?,?)",
                    [(titulo_id, n.strip(), p, i) for i, (n, p) in enumerate(pessoas) if n and n.strip()])


class Execucao:
    """Registra início, fim e resultado de cada etapa da coleta."""

    def __init__(self, con, fonte):
        self.con, self.fonte, self.itens, self.mensagem = con, fonte, 0, ""

    def __enter__(self):
        self.id = self.con.execute("INSERT INTO execucoes(fonte,inicio,status) VALUES(?,?,'rodando')",
                                   (self.fonte, agora())).lastrowid
        self.con.commit()
        return self

    def __exit__(self, tipo, erro, tb):
        if erro is not None:
            self.con.rollback()
        status = "ok" if erro is None else "erro"
        msg = self.mensagem if erro is None else f"{tipo.__name__}: {erro}"[:500]
        self.con.execute("UPDATE execucoes SET fim=?,status=?,itens=?,mensagem=? WHERE id=?",
                         (agora(), status, self.itens, msg, self.id))
        self.con.commit()
        return True  # uma fonte com erro não derruba as outras
