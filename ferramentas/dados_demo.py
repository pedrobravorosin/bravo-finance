"""Cria uma pasta de dados FICTÍCIOS (14 meses, 2 bancos) para ver o painel e tirar capturas.

Uso: python ferramentas/dados_demo.py /tmp/bravo-demo
     BRAVO_DADOS=/tmp/bravo-demo python app/abrir.py
Nada aqui vem de fatura real.
"""
import json
import random
import sys
from pathlib import Path

LOJAS = [  # (descrição, faixa de valor, vezes por mês)
    ("RESTAURANTE SABOR DA CASA", (60, 220), 3), ("PADARIA PAO DOURADO", (12, 45), 6), ("SUSHI EXEMPLO", (90, 260), 1),
    ("BAR DO EXEMPLO", (50, 180), 2), ("IFOOD *LANCHES", (35, 95), 5), ("SUPERMERCADO EXEMPLO", (180, 650), 3),
    ("HORTIFRUTI FICTICIO", (40, 120), 2), ("UBER *TRIP", (14, 48), 8), ("POSTO EXEMPLO", (150, 280), 2),
    ("NETFLIX.COM", (55.9, 55.9), 1), ("SPOTIFY", (21.9, 21.9), 1), ("SMARTFIT", (129.9, 129.9), 1),
    ("DROGARIA EXEMPLO", (25, 140), 1), ("AMAZON MARKETPLACE", (40, 380), 2), ("RENNER LOJA", (90, 320), 1),
    ("ENEL ENERGIA", (160, 260), 1), ("VIVO FIBRA", (119.9, 119.9), 1),
]
PARCELADOS = [("LOJA DE MOVEIS EXEMPLO", 2400, 10, 2), ("NOTEBOOK EXEMPLO", 4800, 12, 6), ("PASSAGEM LATAM", 1800, 6, 10)]


def main(destino):
    rnd = random.Random(42)
    fat = Path(destino) / "faturas"
    fat.mkdir(parents=True, exist_ok=True)
    meses = [(2025 + (m - 1) // 12, (m - 1) % 12 + 1) for m in range(10, 24)]  # out/25 a nov/26
    for i, (ano, mes) in enumerate(meses):
        for banco, cartao, peso in (("Nubank", "1234", 1.0), ("Itaú", "5678", 0.45)):
            txs = []
            sazonal = 1.25 if mes in (12, 1) else 1.0
            for desc, (a, b), n in LOJAS:
                for _ in range(max(0, round(n * peso * rnd.uniform(0.6, 1.3)))):
                    d = rnd.randint(1, 28)
                    txs.append({"data": f"{ano}-{mes:02d}-{d:02d}", "descricao": desc, "parcela": None,
                                "valor": round(rnd.uniform(a, b) * sazonal, 2), "usd": None, "cartao": cartao, "tipo": "compra"})
            futuras = 0.0
            if banco == "Nubank":
                for desc, total, n, inicio in PARCELADOS:
                    k = i - inicio + 1
                    if 1 <= k <= n:
                        txs.append({"data": f"{ano}-{mes:02d}-05", "descricao": desc, "parcela": f"{k:02d}/{n:02d}",
                                    "valor": round(total / n, 2), "usd": None, "cartao": cartao, "tipo": "compra"})
                        futuras += round(total / n, 2) * (n - k)
            if mes == 3 and banco == "Itaú":
                txs.append({"data": f"{ano}-03-10", "descricao": "ANUIDADE DIFERENCIADA", "parcela": None, "valor": 46.5,
                            "usd": None, "cartao": cartao, "tipo": "tarifa"})
            total = round(sum(t["valor"] for t in txs), 2)
            mid = f"{ano}-{mes:02d}"
            meta = {"id": mid, "total": total, "vencimento": f"{ano}-{mes:02d}-10", "minimo": round(total * 0.15, 2),
                    "limite": 15000.0 if banco == "Nubank" else 8000.0, "parcelas_futuras": round(futuras, 2), "banco": banco,
                    "soma_lancamentos": total, "n_lancamentos": len(txs), "leitor": "demo"}
            slug = "nubank" if banco == "Nubank" else "itau"
            (fat / f"{mid}__{slug}.json").write_text(json.dumps({"meta": meta, "transacoes": txs}, ensure_ascii=False), encoding="utf-8")
    print("Dados fictícios em", destino)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/bravo-demo")
