"""Caminhos e constantes do Muvim."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
BANCO = DADOS / "muvim.db"
POSTERES = DADOS / "posteres"
IMDB_DIR = DADOS / "imdb"
LOGS = DADOS / "logs"
WEB = RAIZ / "web"

# A chave do TMDB fica fora do projeto, no cofre. Só o valor, numa linha.
TMDB_CHAVE = Path("D:/Segredos/Muvim/tmdb.txt")

PORTA = 8790
USER_AGENT = "Muvim/1.0 (catalogo pessoal de filmes e series; https://github.com/alvimpl/muvim)"

# Janela de interesse do radar
DIAS_PASSADO = 30
DIAS_FUTURO = 400

# Serviços de streaming acompanhados nas grades do TVmaze
SERVICOS = {
    "Netflix", "Disney+", "Prime Video", "HBO Max", "Max", "Apple TV", "Apple TV+",
    "Globoplay", "Paramount+", "Crunchyroll", "Star+", "Mubi", "Peacock", "Hulu",
}
IDIOMAS_SERIES = {"English", "Portuguese", "Spanish", "Korean", "Japanese", "French", "German"}

# Limites para não incomodar as fontes
CURADORIA_POR_EXECUCAO = 15   # títulos enviados ao Claude por dia
GRAFO_DIAS = 30               # intervalo entre remontagens das ligações do IMDb (baixa ~1,3 GB)
GRAFO_VOTOS_MIN = 5000        # só títulos com pelo menos tantos votos entram no grafo

for p in (DADOS, POSTERES, IMDB_DIR, LOGS):
    p.mkdir(parents=True, exist_ok=True)
