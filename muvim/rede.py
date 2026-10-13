"""Acesso à internet com educação: identificação, pausa por site e nova tentativa em 429/5xx."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import USER_AGENT

_ultimo = {}
PAUSA = {"wikipedia.org": 0.6, "wikidata.org": 1.5, "wikimedia.org": 1.0, "tvmaze.com": 0.55, "themoviedb.org": 0.1}


def _esperar(url):
    host = urllib.parse.urlparse(url).hostname or ""
    pausa = next((v for k, v in PAUSA.items() if host.endswith(k)), 0.2)
    falta = _ultimo.get(host, 0) + pausa - time.time()
    if falta > 0:
        time.sleep(falta)
    _ultimo[host] = time.time()


def baixar(url, cabecalhos=None, tentativas=5, tempo=90):
    """Devolve os bytes da resposta. Espera e tenta de novo em 429 e erros 5xx."""
    h = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    h.update(cabecalhos or {})
    for i in range(tentativas):
        _esperar(url)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=tempo) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                espera = int(e.headers.get("Retry-After") or 0) or 5 * (i + 1)
                time.sleep(min(espera, 60))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i == tentativas - 1:
                raise
            time.sleep(3 * (i + 1))
    # Sem a query: ela pode conter chave de API, e esta mensagem vai para o banco e para a tela.
    raise RuntimeError(f"desisti depois de {tentativas} tentativas: {url.split('?')[0]}")


def json_de(url, params=None, cabecalhos=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    return json.loads(baixar(url, cabecalhos))


def baixar_arquivo(url, destino: Path, tempo=600):
    """Baixa para disco em blocos (arquivos grandes do IMDb)."""
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=tempo) as r, open(tmp, "wb") as f:
        while bloco := r.read(1 << 20):
            f.write(bloco)
    tmp.replace(destino)
