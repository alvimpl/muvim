"""Abre o Muvim no navegador. Se o servidor não estiver respondendo, sobe ele antes.
Extensão .pyw: roda sem janela de console (é o alvo do atalho da área de trabalho)."""
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from muvim.config import PORTA

URL = f"http://localhost:{PORTA}"
RAIZ = Path(__file__).resolve().parent
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def no_ar():
    try:
        with urllib.request.urlopen(URL + "/web/muvim.png", timeout=2):
            return True
    except Exception:
        return False


if not no_ar():
    # Primeiro pela tarefa agendada (mantém o servidor igual ao do dia a dia); senão, direto
    r = subprocess.run(["schtasks", "/Run", "/TN", "Muvim - Servidor"], capture_output=True, creationflags=SEM_JANELA)
    if r.returncode != 0:
        subprocess.Popen([sys.executable, str(RAIZ / "servidor.py")], cwd=RAIZ,
                         creationflags=SEM_JANELA | subprocess.DETACHED_PROCESS)
    for _ in range(40):
        time.sleep(0.25)
        if no_ar():
            break

webbrowser.open(URL)
