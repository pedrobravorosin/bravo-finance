"""Gera faturas de exemplo FICTÍCIAS (nenhum dado real) para testar o leitor.

Uso: python tests/gerar_exemplos.py   (precisa de reportlab, só para os testes)
Cria tests/exemplos/*.pdf. Os valores esperados estão em ESPERADO.
"""
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "exemplos"

ESPERADO = {
    "estilo-nubank.pdf": {"banco": "Nubank", "total": 1003.20, "id": "2026-11", "n_gastos": 6, "senha": None},
    "estilo-duas-colunas.pdf": {"banco": "Itaú", "total": 2010.25, "id": "2026-11", "n_gastos": 10, "senha": "12345"},
    "estilo-ano-completo.pdf": {"banco": "Banco do Brasil", "total": 640.00, "id": "2026-10", "n_gastos": 5, "senha": None},
}


def nubank(c):
    y = 800
    def w(t, x=40, size=10):
        nonlocal y
        c.setFont("Helvetica", size); c.drawString(x, y, t); y -= 16
    w("Nu Pagamentos S.A. - Instituição de Pagamento", size=9)
    w("Olá, Fulano de Tal", size=14)
    w("Esta é a sua fatura de novembro")
    w("Data de vencimento: 10 NOV 2026")
    w("Total a pagar R$ 1.003,20")
    w("Pagamento mínimo R$ 150,48")
    w("Limite total do cartão R$ 5.000,00")
    y -= 10
    w("TRANSAÇÕES DE 03 OUT A 02 NOV")
    linhas = [("05 OUT", "Ifood *Restaurante Exemplo", "R$ 45,90"),
              ("07 OUT", "Mercado Bom Preco", "R$ 312,40"),
              ("10 OUT", "Loja Online - Parcela 2/6", "R$ 120,00"),
              ("12 OUT", "Uber *Trip", "R$ 32,10"),
              ("15 OUT", "Estorno Uber *Trip", "−R$ 12,10"),
              ("18 OUT", "Pagamento recebido", "−R$ 900,00"),
              ("20 OUT", "Posto Combustivel Exemplo", "R$ 504,90")]
    for d, desc, v in linhas:
        c.setFont("Helvetica", 10); c.drawString(40, y, d); c.drawString(100, y, desc); c.drawRightString(550, y, v); y -= 16
    y -= 10
    w("Próximas faturas")
    c.drawString(40, y, "10 DEZ"); c.drawString(100, y, "Loja Online - Parcela 3/6"); c.drawRightString(550, y, "R$ 120,00"); y -= 16


def duas_colunas(c):
    c.setFont("Helvetica-Bold", 12); c.drawString(40, 810, "Itaú Unibanco - Cartão Exemplo Platinum")
    c.setFont("Helvetica", 9)
    c.drawString(40, 790, "Total desta fatura 2.010,25")
    c.drawString(40, 776, "Vencimento: 05/11/2026")
    c.drawString(40, 762, "Pagamento mínimo 301,54")
    c.drawString(40, 748, "Juros do rotativo: 14,50% a.m.")
    esq = [("CARTÃO FINAL 1111", None, None),
           ("02/10", "PADARIA PAO QUENTE", "18,50"),
           ("03/10", "SUPERMERCADO EXEMPLO", "432,75"),
           ("05/10", "FARMACIA SAUDE", "89,90"),
           ("09/10", "LOJA DE ROUPAS 03/05", "199,00"),
           ("11/10", "ESTORNO LOJA", "-50,00"),
           ("12/10", "PAGAMENTO EFETUADO", "-1.500,00")]
    dir_ = [("CARTÃO FINAL 2222", None, None),
            ("14/10", "STREAMING VIDEO", "55,90"),
            ("16/10", "RESTAURANTE SABOR", "210,30"),
            ("18/10", "APP DE TRANSPORTE", "27,40"),
            ("20/10", "HOTEL PRAIA 02/03", "980,00"),
            ("22/10", "ANUIDADE DIFERENCIADA", "46,50")]
    for col, x0 in ((esq, 40), (dir_, 310)):
        y = 710
        for d, desc, v in col:
            if desc is None:
                c.setFont("Helvetica-Bold", 8); c.drawString(x0, y, d)
            else:
                c.setFont("Helvetica", 8); c.drawString(x0, y, d); c.drawString(x0 + 32, y, desc); c.drawRightString(x0 + 250, y, v)
            y -= 14


def ano_completo(c):
    c.setFont("Helvetica", 10)
    y = 800
    for t in ["BANCO DO BRASIL S.A. - Ourocard Exemplo", "Vencimento 15/10/2026", "Valor total da fatura: R$ 640,00", "",
              "Data       Descrição                                    Valor (R$)"]:
        c.drawString(40, y, t); y -= 16
    for d, desc, v in [("20/09/2026", "LIVRARIA CENTRAL", "150,00"), ("22/09/2026", "ACADEMIA FORMA", "99,90"),
                       ("25/09/2026", "CINEMA SHOPPING", "60,00 C"), ("28/09/2026", "POSTO DA ESQUINA", "450,10"),
                       ("30/09/2026", "IOF COMPRA EXTERIOR", "0,00"), ("01/10/2026", "SALDO ANTERIOR", "1.234,00")]:
        c.drawString(40, y, d); c.drawString(130, y, desc); c.drawRightString(550, y, v); y -= 16


def main():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    PASTA.mkdir(exist_ok=True)
    for nome, fn in (("estilo-nubank.pdf", nubank), ("estilo-duas-colunas.pdf", duas_colunas), ("estilo-ano-completo.pdf", ano_completo)):
        senha = ESPERADO[nome]["senha"]
        kw = {}
        if senha:
            from reportlab.lib import pdfencrypt
            kw["encrypt"] = pdfencrypt.StandardEncryption(senha, canPrint=1)
        c = canvas.Canvas(str(PASTA / nome), pagesize=A4, **kw)
        fn(c)
        c.showPage(); c.save()
    print("Exemplos em", PASTA)


if __name__ == "__main__":
    main()
