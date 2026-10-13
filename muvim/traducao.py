"""Tradutor próprio do Muvim: inglês -> português do Brasil, rodando dentro da coleta.
Usa o modelo aberto do Argos Translate (MIT) com CTranslate2. Sem API externa, sem cadastro.
Cada texto é traduzido uma vez e guardado na tabela `traducoes` (chave: hash do original)."""
import hashlib
import io
import re
import zipfile

from . import db
from .config import MODELOS
from .rede import baixar

MODELO = "translate-en_pb-1_9"
MODELO_URL = f"https://argos-net.com/v1/{MODELO}.argosmodel"
LOTE = 48


def chave(texto):
    return hashlib.sha1(texto.strip().encode("utf-8")).hexdigest()


def _frases(t):
    return [f for f in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'“(])", t.strip()) if f]


class Tradutor:
    def __init__(self):
        import ctranslate2
        import sentencepiece
        pasta = MODELOS / MODELO
        if not (pasta / "model" / "model.bin").exists():
            MODELOS.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(baixar(MODELO_URL, tempo=600))) as z:
                z.extractall(MODELOS)
        self.tr = ctranslate2.Translator(str(pasta / "model"), device="cpu", compute_type="int8")
        self.sp = sentencepiece.SentencePieceProcessor(model_file=str(pasta / "sentencepiece.model"))

    def traduzir(self, textos):
        partes = [_frases(t) for t in textos]
        todas = [f for p in partes for f in p]
        saida = []
        for i in range(0, len(todas), LOTE):
            lote = todas[i:i + LOTE]
            res = self.tr.translate_batch([self.sp.encode(f, out_type=str) for f in lote],
                                          beam_size=4, max_decoding_length=300)
            saida += ["".join(r.hypotheses[0]).replace("▁", " ").strip() for r in res]
        it = iter(saida)
        out = []
        for original, p in zip(textos, partes):
            t = " ".join(next(it) for _ in p)
            # O modelo põe ponto final em rótulos curtos ("Australian actor" -> "Ator australiano.")
            if not original.rstrip().endswith((".", "!", "?")) and t.endswith("."):
                t = t[:-1]
            out.append(t)
        return out


def pendentes(con):
    """Textos em inglês que aparecem no site e ainda não têm tradução."""
    textos = set()
    for (t,) in con.execute("SELECT sinopse_en FROM titulos WHERE sinopse_en IS NOT NULL AND sinopse_pt IS NULL"):
        textos.add(t)
    for (t,) in con.execute("SELECT texto FROM curiosidades WHERE gerado_por='extracao'"):
        textos.add(t)
    for (t,) in con.execute("SELECT descricao FROM aniversarios WHERE dia >= date('now','-2 day') AND descricao <> ''"):
        textos.add(t)
    feitas = {r[0] for r in con.execute("SELECT chave FROM traducoes")}
    return [t for t in textos if chave(t) not in feitas]


def coletar(con, ex, limite=2000):
    try:
        tradutor = Tradutor()
    except ImportError:
        ex.mensagem = "tradutor indisponível (instale ctranslate2 e sentencepiece)"
        return
    textos = pendentes(con)[:limite]
    for i in range(0, len(textos), 40):
        lote = textos[i:i + 40]
        for orig, pt in zip(lote, tradutor.traduzir(lote)):
            con.execute("INSERT OR REPLACE INTO traducoes VALUES(?,?,?,?)", (chave(orig), orig, pt, db.agora()))
        con.commit()
    ex.itens = len(textos)
    ex.mensagem = f"{len(textos)} textos traduzidos"


def mapa(con):
    """chave -> tradução, para o exportador."""
    return {k: v for k, v in con.execute("SELECT chave, pt FROM traducoes")}
