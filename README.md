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

Atalho na área de trabalho, com o ícone do letreiro (`scripts\criar-icone.py` redesenha o ícone):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\criar-atalho.ps1
```

O atalho roda `abrir.pyw`: se o servidor estiver parado, ele sobe antes de abrir o site.

## Fontes

| Fonte | O que traz | Conta |
|---|---|---|
| Wikipedia (listas anuais de filmes americanos) | Estreias de cinema, direção, elenco, sinopse, pôster, texto para curiosidades | Não |
| Wikipedia em português | Sinopse e título brasileiro (“bra: …”) | Não |
| Wikidata (API de entidades) | Código do IMDb, popularidade (nº de Wikipedias com artigo), estreia no Brasil quando cadastrada | Não |
| TVmaze | Estreias de temporada em streaming e na TV brasileira, elenco, episódios | Não |
| IMDb datasets | Notas e votos (diário); ligações entre pessoas (semanal) | Não. Uso pessoal, não comercial |
| Wikimedia “neste dia” | Aniversariantes de cinema | Não |
| Claude Code | Curiosidades e sinopses em português | Opcional. Usa o Claude Code já logado neste PC |

Nenhuma fonte pede cadastro. A data de estreia no Brasil vem do Wikidata quando alguém a cadastrou lá,
o que ainda é raro; quando falta, vale a data dos EUA, sempre marcada como tal. Filmes lançados direto
em Netflix, Apple TV, Disney+, Prime Video, HBO Max ou Paramount+ são reconhecidos pelo distribuidor.

### Curadoria pelo Claude (opcional)

O coletor procura o `claude` no PATH ou o que vem com o app desktop. Se a etapa disser “sem login”,
o Claude Code deste PC não está logado; o resto funciona igual. São no máximo 15 títulos e uma
tradução em lote por dia. Sem ela, as curiosidades são trechos do artigo em inglês, escolhidos
automaticamente.

## Como funciona

- `coletar.py` roda as etapas em ordem. Cada uma registra resultado em `execucoes` (tela Bastidores).
  Uma etapa com erro não derruba as outras.
- Toda gravação compara com o valor anterior. Datas, temporada, streaming, nota e título em
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
