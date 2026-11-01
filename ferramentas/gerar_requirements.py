"""Gera app/requirements.txt com versões fixas e hashes (sha256) de todos os wheels do PyPI.

As versões abaixo funcionam do Python 3.9 ao 3.14 em Windows, macOS e Linux.
Para atualizar, mude FIXAS, rode este script e rode os testes.
"""
import json
import urllib.request
from pathlib import Path

FIXAS = [
    ("pdfplumber", "0.11.8"),
    ("pdfminer.six", "20251107"),
    ("pypdfium2", "4.30.0"),
    ("pillow", "11.3.0"),
    ("charset-normalizer", "3.4.3"),
    ("cryptography", "45.0.7"),
    ("cffi", "2.0.0"),
    ("pycparser", "2.23"),
]

linhas = ["# Gerado por ferramentas/gerar_requirements.py. Não edite à mão.",
          "# Instale com: pip install --require-hashes --only-binary=:all: -r requirements.txt"]
for nome, versao in FIXAS:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{nome}/{versao}/json") as r:
        d = json.load(r)
    hashes = sorted({u["digests"]["sha256"] for u in d["urls"] if u["packagetype"] == "bdist_wheel"})
    linhas.append(f"{nome}=={versao} \\")
    linhas += [f"    --hash=sha256:{h} \\" for h in hashes[:-1]] + [f"    --hash=sha256:{hashes[-1]}"]
destino = Path(__file__).resolve().parent.parent / "app" / "requirements.txt"
destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
print("Gerado", destino)
