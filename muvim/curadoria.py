"""Curadoria pelo Claude Code (opcional): sinopse em português e curiosidades a partir do artigo.
Usa o `claude` da linha de comando em modo não interativo. Se não estiver instalado ou logado,
a etapa é pulada e ficam as curiosidades extraídas automaticamente."""
import glob
import json
import os
import re
import shutil
import subprocess

from . import db
from .config import CURADORIA_POR_EXECUCAO

PROMPT = """Você recebe o texto de um artigo da Wikipedia sobre o filme "{titulo}".
Responda SOMENTE com um JSON válido, sem comentários, neste formato:
{{"sinopse_pt": "2 a 3 frases em português do Brasil, sem spoilers",
  "curiosidades": [{{"titulo": "título curto e chamativo", "texto": "1 a 2 frases", "secao": "seção do artigo de onde veio"}}]}}
Regras: de 4 a 6 curiosidades; use apenas fatos que estão no texto; prefira bastidores surpreendentes,
números, recordes, trocas de elenco e escolhas técnicas; escreva em português do Brasil, de forma direta.

ARTIGO:
{texto}"""


def achar_claude():
    if os.environ.get("MUVIM_CLAUDE"):
        return os.environ["MUVIM_CLAUDE"]
    if shutil.which("claude"):
        return shutil.which("claude")
    # Claude Code que vem com o app desktop (a pasta muda a cada versão)
    candidatos = glob.glob(os.path.expandvars(r"%APPDATA%\Claude\claude-code\*\*\claude.exe"))
    return max(candidatos, key=os.path.getmtime) if candidatos else None


def _perguntar(exe, prompt):
    r = subprocess.run([exe, "-p", "--output-format", "text"], input=prompt, capture_output=True,
                       text=True, encoding="utf-8", timeout=300,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (r.stdout or "") + (r.stderr or "")


def _json(saida):
    i, j = saida.find("{"), saida.rfind("}")
    if i < 0 or j < 0:
        return None
    try:
        return json.loads(saida[i:j + 1])
    except json.JSONDecodeError:
        return None


def coletar(con, ex):
    exe = achar_claude()
    if not exe:
        ex.mensagem = "Claude Code não encontrado"
        return
    alvos = con.execute(
        "SELECT t.id, t.titulo, a.texto, t.sinopse_pt FROM artigos a JOIN titulos t ON t.id=a.titulo_id "
        "LEFT JOIN lista l ON l.titulo_id=t.id "
        "WHERE NOT EXISTS (SELECT 1 FROM curiosidades c WHERE c.titulo_id=t.id AND c.gerado_por='claude') "
        "ORDER BY l.titulo_id IS NULL, COALESCE(t.hype,0) DESC LIMIT ?", (CURADORIA_POR_EXECUCAO,)).fetchall()
    feitos = 0
    for r in alvos:
        saida = _perguntar(exe, PROMPT.format(titulo=r["titulo"], texto=r["texto"][:14000]))
        if re.search(r"not logged in|please run /login", saida, re.I):
            ex.mensagem = "Claude Code sem login: rode `claude` uma vez no terminal e faça /login"
            break
        dados = _json(saida)
        if not dados or not dados.get("curiosidades"):
            continue
        con.execute("DELETE FROM curiosidades WHERE titulo_id=?", (r["id"],))
        for i, c in enumerate(dados["curiosidades"][:6]):
            con.execute("INSERT INTO curiosidades VALUES(?,?,?,?,?,?)",
                        (r["id"], i, c.get("titulo"), c.get("texto"), f"Wikipedia · {c.get('secao', '')}".strip(" ·"), "claude"))
        if dados.get("sinopse_pt") and not r["sinopse_pt"]:
            con.execute("UPDATE titulos SET sinopse_pt=?, sinopse_pt_fonte='Claude' WHERE id=?", (dados["sinopse_pt"], r["id"]))
        con.commit()
        feitos += 1
    traduzidas = 0 if ex.mensagem else _traduzir_sinopses(con, exe)
    ex.itens = feitos
    if not ex.mensagem:
        ex.mensagem = f"{feitos} títulos com curadoria, {traduzidas} sinopses traduzidas"


def _traduzir_sinopses(con, exe, limite=40):
    """Traduz numa chamada só as sinopses em inglês dos títulos mais próximos que ainda não têm português."""
    pend = con.execute("SELECT id, sinopse_en FROM titulos WHERE sinopse_pt IS NULL AND sinopse_en IS NOT NULL "
                       "AND data_eua >= date('now','-7 day') ORDER BY data_eua LIMIT ?", (limite,)).fetchall()
    if not pend:
        return 0
    entrada = json.dumps({r["id"]: r["sinopse_en"][:900] for r in pend}, ensure_ascii=False)
    saida = _perguntar(exe, "Traduza para português do Brasil cada valor deste JSON, de forma natural e concisa. "
                            "Mantenha as mesmas chaves. Responda SOMENTE com o JSON.\n\n" + entrada)
    dados = _json(saida) or {}
    n = 0
    for tid, texto in dados.items():
        if isinstance(texto, str) and texto.strip():
            n += con.execute("UPDATE titulos SET sinopse_pt=?, sinopse_pt_fonte='Claude' WHERE id=? AND sinopse_pt IS NULL",
                             (texto.strip(), tid)).rowcount
    con.commit()
    return n
