# Muvim

Catálogo de filmes e séries: o que vem aí, o que mudou, quem está em quê.
Site estático publicado no GitHub Pages e atualizado uma vez por dia pelo GitHub Actions.
**Nenhuma fonte pede cadastro.**

**Site:** https://alvimpl.github.io/muvim

## O que tem

- **Radar:** estreias das próximas 12 semanas, choques de estreia no mesmo dia, aniversariantes do dia.
- **Séries:** estreias de temporada nos streamings e na TV brasileira.
- **Pessoas:** quem tem várias estreias chegando.
- **O que mudou:** cada coleta compara com a anterior (datas, streaming, crítica, títulos em português).
- **Ligações:** o caminho mais curto entre duas pessoas, pelo elenco e direção de filmes e séries.
  Calculado no navegador, sobre um grafo de ~40 mil pessoas.
- **Página de cada título:** sinopse, ficha, curiosidades com fonte, a franquia na crítica,
  o elenco em outros lançamentos, planejador de maratona para séries.
- **Minha lista e alertas:** ficam guardados no navegador (cada aparelho tem a sua).

## Fontes

| Fonte | O que traz |
|---|---|
| Wikipedia (listas anuais de filmes americanos) | Estreias de cinema, direção, elenco, sinopse, pôster, curiosidades |
| Wikipedia em português | Sinopse e título brasileiro (“bra: …”) |
| Wikidata (API de entidades) | Rotten Tomatoes, Metacritic, franquia, popularidade, estreia no Brasil quando cadastrada |
| Wikidata pelo [QLever](https://qlever.dev) | Grafo de ligações e a crítica de ~22 mil títulos |
| TVmaze | Estreias de temporada, elenco, episódios, nota do público |
| Wikimedia “neste dia” | Aniversariantes de cinema |

### Tradução

Sinopses, curiosidades e descrições que só existem em inglês são traduzidas por um tradutor
próprio que roda na coleta: o modelo aberto inglês→português do Brasil do
[Argos Translate](https://github.com/argosopentech/argos-translate) (MIT), executado com CTranslate2.
Não usa API externa nem cadastro. Cada texto é traduzido uma vez e guardado no banco.
No site, o seletor **PT / EN** alterna entre a tradução e o original.

Pôsteres são exibidos direto da Wikipedia e do TVmaze; o Muvim não os copia.
A data de estreia no Brasil depende de alguém tê-la cadastrado no Wikidata, o que ainda é raro;
quando falta, vale a data dos EUA, sempre identificada como tal.

## Como funciona

```
GitHub Actions (todo dia, 9h de Brasília)
  ├─ recupera o banco do dia anterior (branch "dados")
  ├─ coletar.py   → atualiza o SQLite e registra mudanças
  ├─ exportar.py  → gera site/ (interface + JSON)
  ├─ guarda o banco de volta no branch "dados"
  └─ publica site/ no GitHub Pages
```

- Uma fonte com erro não impede a publicação: o log de cada coleta, na aba Actions, mostra o resultado de cada etapa.
- As requisições têm pausa por site e nova tentativa em erro 429.
- Para rodar a coleta na hora: aba **Actions** → *Coleta e publicação* → **Run workflow**.

## Rodar no PC (opcional, para testar mudanças)

```bash
python coletar.py
python exportar.py
python -m http.server -d site 8790
```

Usa a biblioteca padrão do Python (3.12 ou mais novo), mais `pip install -r requirements.txt` para o tradutor.

## Estrutura

```
coletar.py            orquestra a coleta
exportar.py           gera o site estático
muvim/db.py           esquema SQLite e registro de mudanças
muvim/rede.py         acesso à internet com pausa e novas tentativas
muvim/fontes/         uma fonte por arquivo
web/                  interface (HTML, CSS, JS)
scripts/criar-icone.py  redesenha o ícone
.github/workflows/    coleta diária e publicação
```
