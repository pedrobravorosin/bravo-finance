"""Lê uma fatura num processo separado e com limites.

O servidor chama este arquivo para cada PDF. Assim, um PDF malformado ou feito
de propósito para travar o leitor não derruba nem compromete o servidor: o
processo tem tempo e memória limitados e não tem acesso à internet.

Entrada (stdin, JSON): {"pdf": "<caminho>", "senha": "<senha ou null>"}
Saída (stdout, JSON): {"meta": ..., "transacoes": ...} ou {"erro": ..., "senha": bool}
A senha chega pelo stdin, nunca pela linha de comando (que outros programas podem ver).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blindagem  # noqa: E402

blindagem.ativar()


def limitar():
    try:
        import resource
    except ImportError:  # Windows: o servidor controla o tempo
        return
    for nome, valor in (("RLIMIT_CPU", 90), ("RLIMIT_AS", 3 * 1024 ** 3), ("RLIMIT_NOFILE", 64)):
        lim = getattr(resource, nome, None)
        if lim is None:
            continue
        try:
            resource.setrlimit(lim, (valor, valor))
        except (ValueError, OSError):
            pass  # alguns sistemas (ex.: macOS com RLIMIT_AS) não aceitam


def main():
    pedido = json.loads(sys.stdin.buffer.read(10_000).decode("utf-8"))
    limitar()
    from leitor import SenhaNecessaria, parse_pdf
    try:
        meta, txs = parse_pdf(pedido["pdf"], pedido.get("senha") or None)
        saida = {"meta": meta, "transacoes": txs}
    except SenhaNecessaria as e:
        saida = {"erro": f"Fatura protegida por senha ({e}).", "senha": True}
    except Exception as e:  # noqa: BLE001
        saida = {"erro": f"Não consegui ler a fatura: {e}"[:400], "senha": False}
    sys.stdout.buffer.write(json.dumps(saida, ensure_ascii=False).encode("utf-8"))  # UTF-8 em qualquer sistema


if __name__ == "__main__":
    main()
