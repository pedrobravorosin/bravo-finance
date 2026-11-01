"""Gera o ícone do Bravo Finance (PNG, ICO e ICNS) em app/icone/.

Uso: python ferramentas/gerar_icone.py   (precisa de Pillow e da fonte Inter ExtraBold)
Os arquivos gerados ficam no repositório; só rode de novo para mudar o desenho.
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

S = 2048  # desenha grande e reduz, para bordas suaves
DEST = Path(__file__).resolve().parent.parent / "app" / "icone"
FONTE = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"


def gradiente(w, h, c1, c2):
    """Degradê diagonal (canto superior esquerdo → inferior direito)."""
    g = Image.new("RGB", (w, h))
    px = g.load()
    for y in range(h):
        for x in range(w):
            t = (x + y) / (w + h - 2)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))
    return g


def desenhar():
    m = int(S * 0.098)  # margem padrão dos ícones do macOS (824 de 1024)
    lado = S - 2 * m
    raio = int(lado * 0.225)
    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((m, m, m + lado, m + lado), raio, fill=255)

    fundo = gradiente(256, 256, (14, 23, 48), (12, 92, 84)).resize((S, S), Image.BICUBIC)
    # brilho suave no alto
    brilho = Image.new("L", (S, S), 0)
    ImageDraw.Draw(brilho).ellipse((-S * 0.2, -S * 0.9, S * 1.2, S * 0.35), fill=34)
    brilho = brilho.filter(ImageFilter.GaussianBlur(S * 0.12))
    fundo = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), fundo, brilho)

    icone = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # sombra
    sombra = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sombra).rounded_rectangle((m, m + S * 0.012, m + lado, m + lado + S * 0.012), raio, fill=110)
    sombra = sombra.filter(ImageFilter.GaussianBlur(S * 0.018))
    icone.paste((0, 0, 0, 255), (0, 0), sombra)
    icone.paste(fundo, (0, 0), mascara)

    # "B" em branco
    fonte = ImageFont.truetype(FONTE, int(lado * 0.66))
    letra = Image.new("L", (S, S), 0)
    ImageDraw.Draw(letra).text((m + lado * 0.47, m + lado * 0.49), "B", font=fonte, fill=255, anchor="mm")
    icone.paste((255, 255, 255, 255), (0, 0), letra)

    # linha de tendência dourada que sobe e sai da letra
    ouro = (244, 196, 92, 255)
    pts = [(m + lado * 0.17, m + lado * 0.76), (m + lado * 0.40, m + lado * 0.56),
           (m + lado * 0.55, m + lado * 0.66), (m + lado * 0.80, m + lado * 0.36)]
    w = int(lado * 0.055)
    contorno = Image.new("L", (S, S), 0)
    ImageDraw.Draw(contorno).line(pts, fill=255, width=w + int(lado * 0.026), joint="curve")
    contorno = ImageChops.multiply(contorno, mascara)
    # recorta a letra em volta da linha para ela "passar por cima"
    icone.paste(fundo, (0, 0), ImageChops.multiply(contorno, letra))
    d = ImageDraw.Draw(icone)
    d.line(pts, fill=ouro, width=w, joint="curve")
    for p in (pts[0],):
        d.ellipse((p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2), fill=ouro)
    # ponta da seta
    tx, ty = pts[-1]
    a = lado * 0.11
    d.polygon([(tx + a * 0.35, ty - a * 0.55), (tx - a * 0.62, ty - a * 0.38), (tx + a * 0.18, ty + a * 0.48)], fill=ouro)
    return icone.resize((1024, 1024), Image.LANCZOS)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    img = desenhar()
    img.save(DEST / "bravo-finance.png")
    img.resize((256, 256), Image.LANCZOS).save(DEST / "bravo-finance-256.png")
    img.resize((64, 64), Image.LANCZOS).save(DEST / "favicon.png")
    img.save(DEST / "bravo-finance.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(DEST / "bravo-finance.icns")
    print("Ícones em", DEST)


if __name__ == "__main__":
    main()
