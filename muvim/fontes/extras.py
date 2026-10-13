"""Aniversariantes do dia (Wikimedia) e pôsteres locais."""
import io
import re
from datetime import date

from .. import db
from ..config import POSTERES
from ..rede import baixar, json_de

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


def _nome_arquivo(tid):
    return re.sub(r"[^\w.-]", "_", tid)[:120] + ".jpg"


def posteres(con, ex, limite=250):
    """Baixa e reduz os pôsteres que ainda não estão no disco. Títulos próximos primeiro."""
    try:
        from PIL import Image
    except ImportError:
        Image = None
    pend = con.execute("SELECT id, poster_url FROM titulos WHERE poster_url IS NOT NULL AND poster IS NULL "
                       "ORDER BY abs(julianday(COALESCE(data_eua,'2100-01-01')) - julianday('now')) LIMIT ?",
                       (limite,)).fetchall()
    n = 0
    for r in pend:
        try:
            dados = baixar(r["poster_url"], tempo=60)
        except Exception:
            continue
        nome = _nome_arquivo(r["id"])
        if Image:
            im = Image.open(io.BytesIO(dados)).convert("RGB")
            if im.width > 400:
                im = im.resize((400, round(im.height * 400 / im.width)), Image.LANCZOS)
            im.save(POSTERES / nome, "JPEG", quality=82, optimize=True)
        else:
            (POSTERES / nome).write_bytes(dados)
        con.execute("UPDATE titulos SET poster=? WHERE id=?", (nome, r["id"]))
        con.commit()
        n += 1
    ex.itens = n
    ex.mensagem = f"{n} novos, {len(pend) - n} com falha"
