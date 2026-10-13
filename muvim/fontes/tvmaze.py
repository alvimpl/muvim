"""TVmaze: estreias de temporada em streaming e TV, ficha das séries e lista de episódios."""
import re
from datetime import date, timedelta

from .. import db
from ..config import IDIOMAS_SERIES, SERVICOS
from ..rede import json_de

API = "https://api.tvmaze.com"
DIAS = 35


def _sem_html(t):
    return re.sub(r"<[^>]+>", "", t or "").strip() or None


def _grade():
    """Episódios dos próximos dias: streaming global, streaming brasileiro e TV brasileira."""
    eps = []
    for i in range(DIAS):
        d = (date.today() + timedelta(days=i)).isoformat()
        for url in (f"{API}/schedule/web?date={d}&country=", f"{API}/schedule/web?date={d}&country=BR",
                    f"{API}/schedule?country=BR&date={d}"):
            for e in json_de(url):
                show = e.get("_embedded", {}).get("show") or e.get("show") or {}
                canal = (show.get("webChannel") or show.get("network") or {})
                eps.append((e, show, canal.get("name"), (canal.get("country") or {}).get("code")))
    return eps


def coletar(con, ex, registrar=True):
    estreias = {}
    for e, show, canal, pais in _grade():
        if e.get("number") != 1 or not show.get("id"):
            continue
        relevante = (canal in SERVICOS and show.get("language") in IDIOMAS_SERIES) or pais == "BR"
        if relevante and (show.get("type") not in ("News", "Sports", "Talk Show")):
            k = show["id"]
            if k not in estreias or e["airdate"] < estreias[k][0]:
                estreias[k] = (e["airdate"], e["season"], canal)
    # Séries que já estão no banco e estrearam há pouco continuam sendo atualizadas
    # (episódios novos saem toda semana e alimentam a maratona)
    recentes = [r[0] for r in con.execute(
        "SELECT tvmaze_id FROM titulos WHERE tvmaze_id IS NOT NULL AND data_eua >= date('now','-75 day')")]
    ids = list(estreias) + [i for i in recentes if i not in estreias]
    for sid in ids:
        s = json_de(f"{API}/shows/{sid}", {"embed[]": "cast"})
        s2 = json_de(f"{API}/shows/{sid}/episodes")
        img = s.get("image") or {}
        data, temp, canal = estreias.get(sid, (None, None, None))
        if data is None:  # já no banco: próxima temporada futura, se houver
            fut = [ep for ep in s2 if ep.get("number") == 1 and (ep.get("airdate") or "") >= date.today().isoformat()]
            if fut:
                data, temp = fut[0]["airdate"], fut[0]["season"]
        canal = canal or (s.get("webChannel") or s.get("network") or {}).get("name")
        tid = f"s:{sid}"
        db.gravar_titulo(con, dict(
            id=tid, tipo="serie", titulo=s["name"], data_eua=data, temporada=temp, servico=canal,
            generos=s.get("genres") or [], sinopse_en=_sem_html(s.get("summary")),
            poster_url=img.get("medium") or img.get("original"), imdb_id=(s.get("externals") or {}).get("imdb"),
            nota_tvmaze=(s.get("rating") or {}).get("average"),
            tvmaze_id=sid, hype=s.get("weight"), estreou=s.get("premiered"),
            n_temporadas=max([ep.get("season") or 0 for ep in s2] or [0])), registrar)
        elenco = [(c["person"]["name"], c["character"]["name"]) for c in s.get("_embedded", {}).get("cast", [])[:12]]
        db.gravar_elenco(con, tid, elenco)
        con.execute("DELETE FROM episodios WHERE tvmaze_show=?", (sid,))
        con.executemany("INSERT OR REPLACE INTO episodios VALUES(?,?,?,?,?,?)",
                        [(sid, ep.get("season"), ep.get("number"), ep.get("name"), ep.get("airdate"),
                          ep.get("runtime") or s.get("averageRuntime")) for ep in s2 if ep.get("number") is not None])
        con.commit()
    ex.itens = len(ids)
    ex.mensagem = f"{len(estreias)} estreias de temporada em {DIAS} dias"
