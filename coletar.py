"""Coleta diária do Muvim. Roda pelo Agendador de Tarefas (ao ligar o PC e uma vez por dia).

    python coletar.py              # roda se ainda não rodou hoje
    python coletar.py --forcar     # roda de novo
    python coletar.py --so tvmaze  # uma etapa só (nomes abaixo)
    python coletar.py --grafo      # remonta as ligações do IMDb agora (baixa ~1,3 GB)
"""
import argparse
import logging
import os
import sys
import time

from muvim import alertas, curadoria, db
from muvim.config import LOGS, DADOS
from muvim.fontes import extras, imdb, tmdb, tvmaze, wikidata, wikipedia

TRAVA = DADOS / "coleta.trava"


def etapas(registrar, forcar_grafo):
    return [
        ("wikipedia-listas", lambda c, e: wikipedia.coletar_listas(c, e, registrar)),
        ("wikipedia-detalhes", lambda c, e: wikipedia.coletar_detalhes(c, e, registrar)),
        ("wikidata", lambda c, e: wikidata.coletar(c, e, registrar)),
        ("tvmaze", lambda c, e: tvmaze.coletar(c, e, registrar)),
        ("tmdb", lambda c, e: tmdb.coletar(c, e, registrar)),
        ("imdb-notas", lambda c, e: imdb.notas(c, e, registrar)),
        ("aniversarios", extras.aniversarios),
        ("posteres", extras.posteres),
        ("curiosidades", wikipedia.extrair_curiosidades),
        ("curadoria-claude", curadoria.coletar),
        ("imdb-grafo", lambda c, e: imdb.grafo(c, e, forcar_grafo)),
        ("alertas", alertas.gerar),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forcar", action="store_true")
    ap.add_argument("--so")
    ap.add_argument("--grafo", action="store_true")
    a = ap.parse_args()

    logging.basicConfig(filename=LOGS / f"coleta-{db.hoje()}.log", level=logging.INFO,
                        format="%(asctime)s %(message)s", encoding="utf-8")
    log = logging.getLogger("muvim")
    log.addHandler(logging.StreamHandler(sys.stdout))

    if TRAVA.exists() and time.time() - TRAVA.stat().st_mtime < 3 * 3600:
        log.info("Outra coleta está rodando. Saindo.")
        return
    con = db.conectar()
    if not (a.forcar or a.so or a.grafo) and db.meta(con, "coleta_ok") == db.hoje():
        log.info("Coleta de hoje já feita. Use --forcar para repetir.")
        return
    TRAVA.write_text(str(os.getpid()))
    try:
        # Na primeira coleta tudo é novo: não enche "O que mudou" com centenas de itens.
        registrar = con.execute("SELECT count(*) FROM titulos").fetchone()[0] > 0
        lista = etapas(registrar, a.grafo)
        if a.so:
            lista = [e for e in lista if e[0] == a.so]
        elif a.grafo:
            lista = [e for e in lista if e[0] == "imdb-grafo"]
        for nome, fn in lista:
            t = time.time()
            with db.Execucao(con, nome) as ex:
                fn(con, ex)
            r = con.execute("SELECT status, itens, mensagem FROM execucoes WHERE id=?", (ex.id,)).fetchone()
            log.info(f"{nome:<20} {r['status']:<5} {r['itens'] or 0:>6} itens  {time.time() - t:6.1f}s  {r['mensagem'] or ''}")
        if not (a.so or a.grafo):
            db.meta(con, "coleta_ok", db.hoje())
            con.commit()
    finally:
        TRAVA.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
