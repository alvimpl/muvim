"""Caminhos e constantes do Muvim."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"          # banco (no GitHub, guardado no branch "dados")
BANCO = DADOS / "muvim.db"
LOGS = DADOS / "logs"
WEB = RAIZ / "web"              # fonte da interface
SITE = RAIZ / "site"            # site estático gerado por exportar.py

REPOSITORIO = "https://github.com/alvimpl/muvim"
USER_AGENT = f"Muvim/2.0 (catalogo de filmes e series; {REPOSITORIO})"

# Janela de interesse do radar
DIAS_PASSADO = 30
DIAS_FUTURO = 400

# Serviços de streaming acompanhados nas grades do TVmaze
SERVICOS = {
    "Netflix", "Disney+", "Prime Video", "HBO Max", "Max", "Apple TV", "Apple TV+",
    "Globoplay", "Paramount+", "Crunchyroll", "Star+", "Mubi", "Peacock", "Hulu",
}
IDIOMAS_SERIES = {"English", "Portuguese", "Spanish", "Korean", "Japanese", "French", "German"}

GRAFO_DIAS = 7                  # intervalo entre remontagens do grafo de ligações (QLever)

for p in (DADOS, LOGS):
    p.mkdir(parents=True, exist_ok=True)
