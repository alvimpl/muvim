"""Alertas da 'Minha lista': mudanças, estreias chegando e episódios novos. Avisa também no Windows."""
import subprocess
from datetime import date, timedelta

from . import db

ROTULO = {"data_eua": "mudou a estreia nos EUA", "data_br": "ganhou/mudou a data no Brasil",
          "onde_br": "mudou o streaming", "temporada": "tem temporada nova",
          "nota_imdb": "mudou a nota no IMDb", "titulo_pt": "ganhou título em português"}


def _fmt(d):
    try:
        a, m, dd = d.split("-")
        return f"{dd}/{m}/{a}"
    except Exception:
        return d


def gerar(con, ex):
    hoje = date.today()
    novos = []

    def add(tid, texto):
        cur = con.execute("INSERT OR IGNORE INTO alertas(criado_em,titulo_id,texto) VALUES(?,?,?)", (db.agora(), tid, texto))
        if cur.rowcount:
            novos.append(texto)

    for m in con.execute("SELECT m.*, t.titulo FROM mudancas m JOIN lista l ON l.titulo_id=m.titulo_id "
                         "JOIN titulos t ON t.id=m.titulo_id WHERE m.dia >= date('now','-1 day') AND m.campo<>'novo'"):
        antes, depois = m["antes"], m["depois"]
        if m["campo"].startswith("data"):
            antes, depois = _fmt(antes), _fmt(depois)
        add(m["titulo_id"], f"{m['titulo']} {ROTULO.get(m['campo'], m['campo'])}: {antes} → {depois}")

    for t in con.execute("SELECT t.* FROM lista l JOIN titulos t ON t.id=l.titulo_id"):
        for campo, onde in (("data_br", "no Brasil"), ("data_eua", "nos EUA")):
            d = t[campo]
            if d and hoje.isoformat() <= d <= (hoje + timedelta(days=7)).isoformat():
                falta = (date.fromisoformat(d) - hoje).days
                quando = "hoje" if falta == 0 else "amanhã" if falta == 1 else f"em {falta} dias"
                if t["tipo"] == "serie":
                    add(t["id"], f"{t['titulo']}: temporada {t['temporada']} estreia {quando} ({_fmt(d)}, {t['servico']})")
                else:
                    add(t["id"], f"{t['titulo']} estreia {quando} {onde} ({_fmt(d)})")
                break
        if t["tvmaze_id"]:
            for ep in con.execute("SELECT * FROM episodios WHERE tvmaze_show=? AND data BETWEEN ? AND ?",
                                  (t["tvmaze_id"], hoje.isoformat(), (hoje + timedelta(days=1)).isoformat())):
                quando = "hoje" if ep["data"] == hoje.isoformat() else "amanhã"
                add(t["id"], f"{t['titulo']}: episódio T{ep['temporada']}E{ep['numero']} sai {quando}")
    con.commit()
    ex.itens = len(novos)
    if novos:
        notificar(f"{len(novos)} novidade(s) na sua lista", novos[0])


def notificar(titulo, texto):
    """Notificação do Windows via PowerShell. Se falhar, os alertas continuam visíveis no app."""
    esc = lambda s: s.replace("'", "''").replace("<", "").replace(">", "").replace("&", "e")
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;"
        "$x=[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime]::new();"
        f"$x.LoadXml('<toast><visual><binding template=\"ToastGeneric\"><text>Muvim: {esc(titulo)}</text>"
        f"<text>{esc(texto)}</text></binding></visual></toast>');"
        "$app='{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show("
        "[Windows.UI.Notifications.ToastNotification]::new($x))")
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=30,
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass
