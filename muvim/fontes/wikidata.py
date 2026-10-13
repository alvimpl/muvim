"""Wikidata: código do IMDb e popularidade (quantas Wikipedias têm artigo sobre o filme).
Usa a API de entidades, mais leve que o SPARQL, que recusou consultas pesadas por excesso de uso."""
from .. import db
from ..rede import json_de

API = "https://www.wikidata.org/w/api.php"


def coletar(con, ex, registrar=True):
    linhas = con.execute("SELECT id, wikidata FROM titulos WHERE wikidata IS NOT NULL "
                         "AND (imdb_id IS NULL OR hype IS NULL OR data_eua >= date('now','-30 day'))").fetchall()
    por_q = {}
    for r in linhas:
        por_q.setdefault(r["wikidata"], []).append(r["id"])
    qs, feitos = list(por_q), 0
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
            for tid in por_q.get(q, []):
                db.gravar_titulo(con, dict(id=tid, imdb_id=imdb, hype=hype), registrar)
                feitos += 1
        con.commit()
    ex.itens = feitos
