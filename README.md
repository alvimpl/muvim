# Muvim

Catálogo pessoal de filmes e séries: o que vem aí, o que mudou, quem está em quê.
Roda só no seu PC, em http://localhost:8790. Os dados ficam em `dados/`.

## Como usar

```bash
python servidor.py          # abre o site em http://localhost:8790
python coletar.py           # coleta (se ainda não rodou hoje)
python coletar.py --forcar  # coleta de novo
python coletar.py --so tvmaze
python coletar.py --grafo   # remonta as ligações do IMDb agora (baixa ~1,3 GB)
```

Para rodar sozinho ao ligar o PC, registre as tarefas do Windows (não precisa de administrador):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\instalar-agendamento.ps1
```

`scripts\desinstalar-agendamento.ps1` remove as tarefas.

## Fontes

| Fonte | O que traz | Conta |
|---|---|---|
| Wikipedia (listas anuais de filmes americanos) | Estreias de cinema, direção, elenco, sinopse, pôster, texto para curiosidades | Não |
| Wikipedia em português | Sinopse e título brasileiro (“bra: …”) | Não |
| Wikidata (API de entidades) | Código do IMDb e popularidade (nº de Wikipedias com artigo) | Não |
| TVmaze | Estreias de temporada em streaming e na TV brasileira, elenco, episódios | Não |
| IMDb datasets | Notas e votos (diário); ligações entre pessoas (semanal) | Não. Uso pessoal, não comercial |
| Wikimedia “neste dia” | Aniversariantes de cinema | Não |
| TMDB | Data de estreia no Brasil, título e sinopse em português, onde assistir no Brasil | Sim, gratuita |
| Claude Code | Curiosidades e sinopses em português | Usa o seu login do Claude Code |

### Ligar o TMDB

Crie a conta em themoviedb.org, gere a chave da API e salve **só o valor**, numa linha, em
`D:\Segredos\Muvim\tmdb.txt`. A próxima coleta usa sozinha.

### Ligar a curadoria pelo Claude

O coletor procura o `claude` no PATH ou o que vem com o app desktop. Se a etapa disser “sem login”,
rode `claude` uma vez num terminal e faça `/login`. São no máximo 15 títulos e uma tradução em lote por dia.
Sem isso, as curiosidades são trechos do artigo em inglês, escolhidos automaticamente.

## Como funciona

- `coletar.py` roda as etapas em ordem. Cada uma registra resultado em `execucoes` (tela Bastidores).
  Uma etapa com erro não derruba as outras.
- Toda gravação compara com o valor anterior. Datas, temporada, onde assistir, nota e título em
  português que mudam viram linhas em `mudancas` (tela O que mudou) e, se o título está na sua lista,
  um alerta (sino e notificação do Windows).
- As requisições têm pausa por site e nova tentativa em erro 429. Wikimedia e Wikidata limitam quem pede rápido demais.
- O servidor só escuta em 127.0.0.1. As rotas que gravam exigem o cabeçalho `X-Muvim`, o que impede outro site de mexer na sua lista.

## Estrutura

```
coletar.py            orquestra a coleta
servidor.py           site e API
muvim/db.py           esquema SQLite e registro de mudanças
muvim/rede.py         acesso à internet com pausa e novas tentativas
muvim/fontes/         uma fonte por arquivo
muvim/curadoria.py    Claude Code
muvim/alertas.py      alertas da lista e notificação do Windows
web/                  interface
dados/                banco, pôsteres e logs (fora do git)
```
