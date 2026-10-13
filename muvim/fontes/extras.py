"""Aniversariantes do dia (Wikimedia)."""
import re
from datetime import date

from .. import db
from ..rede import json_de

PROFISSOES = re.compile(r"actor|actress|director|filmmaker|screenwriter|animator|cinematographer", re.I)


def aniversarios(con, ex):
    d = date.today()
    feed = json_de(f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/births/{d.month:02}/{d.day:02}")
    n = 0
    for b in feed.get("births", []):
        txt = b.get("text", "")
        if not PROFISSOES.search(txt):
            continue
        nome, _, desc = txt.partition(",")
        pag = ((b.get("pages") or [{}])[0].get("titles") or {}).get("canonical")
        con.execute("INSERT OR REPLACE INTO aniversarios VALUES(?,?,?,?,?)",
                    (d.isoformat(), b.get("year"), nome.strip(), desc.strip(), pag))
        n += 1
    con.commit()
    ex.itens = n
