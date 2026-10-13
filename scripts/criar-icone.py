"""Desenha o ícone do Muvim: um 'M' de letreiro de cinema, com lâmpadas em volta.
Gera web/muvim.ico (atalho e favicon) e web/muvim.png. Rodar de novo só se quiser mudar o desenho."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WEB = Path(__file__).resolve().parent.parent / "web"
FUNDO, AMBAR, BRILHO = (23, 17, 28), (255, 181, 71), (255, 222, 160)


def fonte(tam):
    for nome in ("impact.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(nome, tam)
        except OSError:
            pass
    return ImageFont.load_default()


def desenhar(lado, lampadas=True):
    esc = 4  # desenha grande e reduz, para bordas suaves
    L = lado * esc
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    raio = int(L * 0.22)
    d.rounded_rectangle((0, 0, L - 1, L - 1), radius=raio, fill=FUNDO)

    # Moldura do letreiro
    m = int(L * 0.12)
    d.rounded_rectangle((m, m, L - m, L - m), radius=int(raio * 0.55), outline=AMBAR, width=max(2, L // 64))

    if lampadas:
        # Lâmpadas acesas ao longo da moldura, com brilho
        brilho = Image.new("RGBA", (L, L), (0, 0, 0, 0))
        db = ImageDraw.Draw(brilho)
        r = L * 0.022
        lado_q = L - 2 * m
        n = 7
        pontos = []
        for i in range(n):
            t = m + lado_q * (i + 0.5) / n
            pontos += [(t, m), (t, L - m), (m, t), (L - m, t)]
        for x, y in pontos:
            db.ellipse((x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2), fill=AMBAR + (90,))
        brilho = brilho.filter(ImageFilter.GaussianBlur(L * 0.012))
        im.alpha_composite(brilho)
        d = ImageDraw.Draw(im)
        for x, y in pontos:
            d.ellipse((x - r, y - r, x + r, y + r), fill=BRILHO)

    # O "M"
    f = fonte(int(L * (0.62 if lampadas else 0.78)))
    caixa = d.textbbox((0, 0), "M", font=f)
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    x, y = (L - w) / 2 - caixa[0], (L - h) / 2 - caixa[1]
    sombra = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text((x, y), "M", font=f, fill=AMBAR + (160,))
    im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(L * 0.03)))
    ImageDraw.Draw(im).text((x, y), "M", font=f, fill=AMBAR)
    return im.resize((lado, lado), Image.LANCZOS)


if __name__ == "__main__":
    grande = desenhar(256)
    grande.save(WEB / "muvim.png")
    # Tamanhos pequenos sem lâmpadas: em 16 e 32 px elas viram ruído
    tamanhos = [desenhar(s, lampadas=s >= 48) for s in (16, 24, 32, 48, 64, 128)]
    grande.save(WEB / "muvim.ico", format="ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
                append_images=tamanhos)
    print("ok:", WEB / "muvim.ico")
