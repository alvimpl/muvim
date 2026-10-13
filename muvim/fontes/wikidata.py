"""Wikidata: código do IMDb, popularidade (quantas Wikipedias têm artigo sobre o filme) e,
quando cadastrada, a data de estreia no Brasil.
Usa a API de entidades, mais leve que o SPARQL, que recusou consultas pesadas por excesso de uso."""
from .. import db
from ..rede import json_de

API = "https://www.wikidata.org/w/api.php"
BRASIL = "Q155"


def _data_br(claims):
    """Menor data de publicação (P577) com qualificador 'local de publicação' (P291) = Brasil."""
    datas = []
    for c in claims.get("P577", []):
        paises = [q.get("datavalue", {}).get("value", {}).get("id") for q in c.get("qualifiers", {}).get("P291", [])]
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        # Só datas com precisão de dia (11); ano ou mês sozinhos não servem para o radar
        if BRASIL in paises and v.get("precision") == 11:
            datas.append(v["time"][1:11])
    return min(datas) if datas else None


def coletar(con, ex, registrar=True):
    linhas = con.execute("SELECT id, wikidata FROM titulos WHERE wikidata IS NOT NULL "
                         "AND (imdb_id IS NULL OR hype IS NULL OR data_eua >= date('now','-30 day'))").fetchall()
    por_q = {}
    for r in linhas:
        por_q.setdefault(r["wikidata"], []).append(r["id"])
    qs, feitos, com_br = list(por_q), 0, 0
    for i in range(0, len(qs), 50):
        lote = qs[i:i + 50]
        d = json_de(API, dict(action="wbgetentities", ids="|".join(lote), props="claims|sitelinks", format="json"))
        for q, ent in d.get("entities", {}).items():
            claims = ent.get("claims", {})
            imdb = None
            for c in claims.get("P345", []):
                v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(v, str) and v.startswith("tt"):
                    imdb = v
                    break
            hype = sum(1 for k in ent.get("sitelinks", {}) if k.endswith("wiki") and k != "commonswiki")
            data_br = _data_br(claims)
            com_br += bool(data_br)
            for tid in por_q.get(q, []):
                db.gravar_titulo(con, dict(id=tid, imdb_id=imdb, hype=hype, data_br=data_br), registrar)
                feitos += 1
        con.commit()
    ex.itens = feitos
    ex.mensagem = f"{com_br} com data de estreia no Brasil"
