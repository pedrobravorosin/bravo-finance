"""Testes do leitor com faturas fictícias. Rode: python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "app"))
sys.path.insert(0, str(AQUI))

import leitor  # noqa: E402
from gerar_exemplos import ESPERADO, PASTA, main as gerar  # noqa: E402


class TestLeitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all((PASTA / n).exists() for n in ESPERADO):
            gerar()

    def test_exemplos(self):
        for nome, esp in ESPERADO.items():
            with self.subTest(nome):
                meta, txs = leitor.parse_pdf(PASTA / nome, esp["senha"])
                self.assertEqual(meta["banco"], esp["banco"])
                self.assertEqual(meta["id"], esp["id"])
                self.assertAlmostEqual(meta["total"], esp["total"], places=2)
                self.assertAlmostEqual(meta["soma_lancamentos"], esp["total"], places=2)
                self.assertEqual(sum(1 for t in txs if t["tipo"] != "pagamento"), esp["n_gastos"])

    def test_senha(self):
        with self.assertRaises(leitor.SenhaNecessaria):
            leitor.parse_pdf(PASTA / "estilo-duas-colunas.pdf")
        with self.assertRaises(leitor.SenhaNecessaria):
            leitor.parse_pdf(PASTA / "estilo-duas-colunas.pdf", "errada")

    def test_detalhes(self):
        _, txs = leitor.parse_pdf(PASTA / "estilo-duas-colunas.pdf", "12345")
        cartoes = {t["cartao"] for t in txs}
        self.assertEqual(cartoes, {"1111", "2222"})
        hotel = next(t for t in txs if t["descricao"].startswith("HOTEL"))
        self.assertEqual(hotel["parcela"], "02/03")
        self.assertEqual(hotel["data"], "2026-10-20")
        _, txs = leitor.parse_pdf(PASTA / "estilo-nubank.pdf")
        self.assertFalse(any(t["data"] and t["data"].startswith("2026-12") for t in txs), "não pode contar próximas faturas")


if __name__ == "__main__":
    unittest.main()
