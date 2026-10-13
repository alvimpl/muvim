"""TMDB (opcional): estreia no Brasil, título e sinopse em português, onde assistir no Brasil.
Só roda se existir a chave em D:/Segredos/Muvim/tmdb.txt. O valor nunca é impresso."""
from .. import db
from ..config import TMDB_CHAVE
from ..rede import json_de

API = "https://api.themoviedb.org/3"


def _chave():
    if not TMDB_CHAVE.exists():
        return None
    v = TMDB_CHAVE.read_text(encoding="utf-8").strip().splitlines()
    return v[0].strip() if v else None


def disponivel():
    return _chave() is not None


def _get(caminho, chave, **params):
    # Chave curta (v3) vai como parâmetro; token longo (v4) vai no cabeçalho.
    if len(chave) > 40:
        return json_de(API + caminho, params, {"Authorization": "Bearer " + chave})
    return json_de(API + caminho, {**params, "api_key": chave})


def _data_br(release_dates):
    for pais in release_dates.get("results", []):
        if pais.get("iso_3166_1") == "BR":
            datas = sorted(rd["release_date"][:10] for rd in pais.get("release_dates", [])
                           if rd.get("type") in (2, 3) and rd.get("release_date"))
            if not datas:
                datas = sorted(rd["release_date"][:10] for rd in pais.get("release_dates", []) if rd.get("release_date"))
            return datas[0] if datas else None
    return None


def _onde(provs):
    br = provs.get("results", {}).get("BR", {})
    nomes = [p["provider_name"] for p in br.get("flatrate", [])]
    return sorted(set(nomes)) or None


def coletar(con, ex, registrar=True):
    chave = _chave()
    if not chave:
        ex.mensagem = "sem chave"
        return
    linhas = con.execute("SELECT id, tipo, imdb_id, tmdb_id, sinopse_pt_fonte FROM titulos "
                         "WHERE (imdb_id IS NOT NULL OR tmdb_id IS NOT NULL) "
                         "AND (data_eua IS NULL OR data_eua >= date('now','-120 day'))").fetchall()
    n = 0
    for r in linhas:
        tmdb_id = r["tmdb_id"]
        if not tmdb_id:
            achado = _get(f"/find/{r['imdb_id']}", chave, external_source="imdb_id")
            lista = achado.get("movie_results" if r["tipo"] == "filme" else "tv_results") or []
            if not lista:
                continue
            tmdb_id = lista[0]["id"]
        if r["tipo"] == "filme":
            d = _get(f"/movie/{tmdb_id}", chave, language="pt-BR", append_to_response="release_dates,watch/providers")
            rec = dict(id=r["id"], tmdb_id=tmdb_id, titulo_pt=d.get("title"), data_br=_data_br(d.get("release_dates", {})),
                       onde_br=_onde(d.get("watch/providers", {})))
        else:
            d = _get(f"/tv/{tmdb_id}", chave, language="pt-BR", append_to_response="watch/providers")
            rec = dict(id=r["id"], tmdb_id=tmdb_id, titulo_pt=d.get("name"), onde_br=_onde(d.get("watch/providers", {})))
        db.gravar_titulo(con, rec, registrar)
        if d.get("overview") and r["sinopse_pt_fonte"] in (None, "Claude"):
            con.execute("UPDATE titulos SET sinopse_pt=?, sinopse_pt_fonte='TMDB' WHERE id=?", (d["overview"], r["id"]))
        n += 1
        if n % 25 == 0:
            con.commit()
    con.commit()
    ex.itens = n
