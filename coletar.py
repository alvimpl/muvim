"""Coleta diária do Muvim. No GitHub, roda pelo Actions uma vez por dia (.github/workflows/muvim.yml).

    python coletar.py              # todas as etapas
    python coletar.py --so tvmaze  # uma etapa só (nomes abaixo)
    python coletar.py --grafo      # remonta as ligações agora, mesmo que estejam em dia
"""
import argparse
import logging
import sys
import time

from muvim import db, traducao
from muvim.config import LOGS
from muvim.fontes import extras, qlever, tvmaze, wikidata, wikipedia


def etapas(registrar, forcar_grafo):
    return [
        ("wikipedia-listas", lambda c, e: wikipedia.coletar_listas(c, e, registrar)),
        ("wikipedia-detalhes", lambda c, e: wikipedia.coletar_detalhes(c, e, registrar)),
        ("wikidata", lambda c, e: wikidata.coletar(c, e, registrar)),
        ("tvmaze", lambda c, e: tvmaze.coletar(c, e, registrar)),
        ("aniversarios", extras.aniversarios),
        ("curiosidades", wikipedia.extrair_curiosidades),
        ("traducao", traducao.coletar),
        ("grafo", lambda c, e: qlever.grafo(c, e, forcar_grafo)),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so")
    ap.add_argument("--grafo", action="store_true")
    a = ap.parse_args()

    logging.basicConfig(filename=LOGS / f"coleta-{db.hoje()}.log", level=logging.INFO,
                        format="%(asctime)s %(message)s", encoding="utf-8")
    log = logging.getLogger("muvim")
    log.addHandler(logging.StreamHandler(sys.stdout))

    con = db.conectar()
    # Na primeira coleta tudo é novo: não enche "O que mudou" com centenas de itens.
    registrar = con.execute("SELECT count(*) FROM titulos").fetchone()[0] > 0
    lista = etapas(registrar, a.grafo)
    if a.so:
        lista = [e for e in lista if e[0] == a.so]
    elif a.grafo:
        lista = [e for e in lista if e[0] == "grafo"]
    falhas = 0
    for nome, fn in lista:
        t = time.time()
        with db.Execucao(con, nome) as ex:
            fn(con, ex)
        r = con.execute("SELECT status, itens, mensagem FROM execucoes WHERE id=?", (ex.id,)).fetchone()
        falhas += r["status"] == "erro"
        log.info(f"{nome:<20} {r['status']:<5} {r['itens'] or 0:>6} itens  {time.time() - t:6.1f}s  {r['mensagem'] or ''}")
    if not (a.so or a.grafo):
        db.meta(con, "coleta_ok", db.agora())
        con.commit()
    # Uma fonte com erro não impede a publicação; só falha se todas falharam
    sys.exit(1 if lista and falhas == len(lista) else 0)


if __name__ == "__main__":
    main()
