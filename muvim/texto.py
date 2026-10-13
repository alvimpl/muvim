"""Pequenos utilitários de texto."""
import re
import unicodedata


def normalizar(nome):
    """Para comparar nomes: sem acento, minúsculo, sem pontuação."""
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace(".", " ").split())


def nome_arquivo(tid):
    """Nome de arquivo seguro e estável para um id de título."""
    return re.sub(r"[^\w.-]", "_", tid)[:120]
