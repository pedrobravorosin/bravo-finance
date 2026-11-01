"""Leitura local de faturas de cartão de crédito em PDF.

Tudo roda na própria máquina com pdfplumber. Nenhum dado é enviado para fora.

Há dois leitores:
- parse_santander: layout específico do Santander (1 ou 2 colunas).
- parse_generico: funciona com a maioria dos bancos brasileiros. Procura linhas
  que começam com uma data e terminam com um valor em reais, e lê total,
  vencimento, mínimo e limite pelo texto. Como cada banco organiza a página de
  um jeito, ele tenta algumas leituras (página inteira ou em colunas, primeiro
  ou último valor da linha) e fica com a que mais se aproxima do total da fatura.

Para ensinar um banco novo com layout muito diferente, crie uma função
parse_<banco>(pdf, texto) que devolva (meta, transacoes) ou None e coloque em
LEITORES, antes do genérico.
"""
import re
import unicodedata
from datetime import date, timedelta

import pdfplumber

try:  # pdfminer avisa assim quando o PDF tem senha
    from pdfminer.pdfdocument import PDFPasswordIncorrect
except Exception:  # pragma: no cover
    PDFPasswordIncorrect = None


class SenhaNecessaria(Exception):
    """O PDF está protegido por senha (ou a senha informada está errada)."""


VAL = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"
MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
_MES = r"(?:JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[A-Z]*\.?"

BANCOS = [  # (nome exibido, padrão no texto já normalizado)
    ("Nubank", r"NUBANK|NU PAGAMENTOS"),
    ("Itaú", r"\bITAU\b|ITAUCARD|PERSONNALITE"),
    ("Bradesco", r"BRADESCO|BRADESCARD"),
    ("Banco do Brasil", r"BANCO DO BRASIL|OUROCARD"),
    ("Caixa", r"CAIXA ECONOMICA|\bCAIXA\b"),
    ("Santander", r"SANTANDER"),
    ("Inter", r"BANCO INTER\b|\bINTER&CO|BANCOINTER"),
    ("C6 Bank", r"\bC6 ?BANK\b|BANCO C6"),
    ("BTG Pactual", r"\bBTG\b"),
    ("XP", r"\bXP INVESTIMENTOS|BANCO XP|CARTAO XP"),
    ("Mercado Pago", r"MERCADO PAGO"),
    ("PicPay", r"PICPAY"),
    ("Neon", r"\bNEON\b"),
    ("Next", r"\bNEXT\b"),
    ("Original", r"BANCO ORIGINAL"),
    ("Porto Bank", r"PORTO SEGURO|PORTO BANK"),
    ("Sicredi", r"SICREDI"),
    ("Sicoob", r"SICOOB"),
    ("Banrisul", r"BANRISUL"),
    ("Will Bank", r"WILL BANK"),
    ("Pan", r"BANCO PAN\b"),
    ("Safra", r"SAFRA"),
    ("Riachuelo", r"MIDWAY|CARTAO RIACHUELO"),
    ("Renner", r"REALIZE|CARTAO RENNER"),
]


def num(s):
    return float(s.replace(".", "").replace(",", "."))


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s):
    return sem_acento(s).upper()


def _linhas(words, tol=3):
    """Agrupa palavras em linhas pela posição vertical."""
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    linhas, cur, top = [], [], None
    for w in words:
        if top is None or abs(w["top"] - top) <= tol:
            cur.append(w)
            top = w["top"] if top is None else top
        else:
            linhas.append(cur)
            cur, top = [w], w["top"]
    if cur:
        linhas.append(cur)
    return [" ".join(x["text"] for x in sorted(l, key=lambda w: w["x0"])) for l in linhas]


def _ano_para(d, m, venc):
    """Lançamento sem ano: é do ano do vencimento, ou do anterior se o mês vem depois."""
    y = venc.year if m <= venc.month else venc.year - 1
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def banco_do_texto(texto_norm, primeira_pagina=""):
    """Banco que mais aparece, com peso maior para a primeira página (cabeçalho)."""
    pontos = {}
    for nome, pad in BANCOS:
        n = len(re.findall(pad, texto_norm)) + 5 * len(re.findall(pad, primeira_pagina))
        if n:
            pontos[nome] = n
    return max(pontos, key=pontos.get) if pontos else "Outro banco"


# --------------------------------------------------------------------------
# Santander
# --------------------------------------------------------------------------
TX_SAN = re.compile(rf"^(\d\d/\d\d)\s+(.+?)\s+(?:(\d\d/\d\d)\s+)?({VAL})(?:\s+({VAL}))?$")
IOF_SAN = re.compile(rf"^IOF DESPESA NO EXTERIOR\s+({VAL})$")
CARD_SAN = re.compile(r"XXXX\s+XXXX\s+(\d{4})")


def parse_santander(pdf, texto):
    if "SANTANDER" not in norm(texto) or "Detalhamento da Fatura" not in texto:
        return None
    full = texto
    meta = {"banco": "Santander"}
    m = re.search(rf"R\$\s?({VAL})\s+(\d\d/\d\d/\d{{4}})(?:\s+R\$\s?({VAL}))?", full)
    if not m:
        return None
    meta["total"] = num(m.group(1))
    dd, mm, yy = map(int, m.group(2).split("/"))
    venc = date(yy, mm, dd)
    meta["vencimento"] = venc.isoformat()
    meta["id"] = f"{yy:04d}-{mm:02d}"
    meta["limite"] = num(m.group(3)) if m.group(3) else None
    m = re.search(rf"Pagamento M[íi]nimo\s+R\$\s?({VAL})", full)
    meta["minimo"] = num(m.group(1)) if m else None
    m = re.search(rf"Compras parceladas com e sem juros: operações de\s+({VAL})", full)
    meta["parcelas_futuras"] = num(m.group(1)) if m else None
    m = re.search(rf"Saldo Desta Fatura\s+({VAL})", full)
    if m:
        meta["total"] = num(m.group(1))
    m = re.search(r"Juros: ([\d,]+)% a\.m\.", full)
    meta["juros_rotativo_am"] = m.group(1) if m else None
    meta["anuidade_cobrada"] = 0.0

    txs, card, secao, started = [], None, "Despesas", False
    for page in pdf.pages:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
        ptext = page.extract_text() or ""
        if not started and "Detalhamento da Fatura" not in ptext:
            continue
        started = True
        mid = page.width / 2
        two = any(re.fullmatch(r"\d\d/\d\d", w["text"]) and w["x0"] > mid - 10 for w in words)
        cols = [[w for w in words if w["x0"] < mid - 10], [w for w in words if w["x0"] >= mid - 10]] if two else [words]
        stop = False
        for col in cols:
            for ln in _linhas(col):
                ln = re.sub(r"^\d\s+(?=\d\d/\d\d)", "", ln.strip())
                if ln.startswith("Resumo da Fatura"):
                    stop = True
                    break
                c = CARD_SAN.search(ln)
                if c:
                    card = c.group(1)
                    continue
                for s in ("Pagamento e Demais Créditos", "Parcelamentos", "Despesas"):
                    if ln.startswith(s):
                        secao = s
                i = IOF_SAN.match(ln)
                if i and txs:
                    txs.append({**txs[-1], "descricao": "IOF EXTERIOR (" + txs[-1]["descricao"] + ")",
                                "valor": num(i.group(1)), "parcela": None, "usd": None, "tipo": "tarifa"})
                    continue
                t = TX_SAN.match(ln)
                if not t:
                    continue
                ddmm, desc, parc, v, usd = t.groups()
                v = num(v)
                desc = re.sub(r"\s+", " ", desc).strip()
                if "PAGAMENTO DE FATURA" in desc.upper():
                    tipo = "pagamento"
                elif v < 0 or secao.startswith("Pagamento"):
                    tipo, v = "credito", -abs(v)
                elif "ANUIDADE" in desc.upper():
                    tipo = "tarifa"
                    meta["anuidade_cobrada"] += v
                else:
                    tipo = "compra"
                d, mth = map(int, ddmm.split("/"))
                txs.append({"data": _ano_para(d, mth, venc), "descricao": desc, "parcela": parc,
                            "valor": v, "usd": num(usd) if usd else None, "cartao": card, "tipo": tipo})
            if stop:
                break
        if stop:
            break
    return meta, txs


# --------------------------------------------------------------------------
# Leitor genérico
# --------------------------------------------------------------------------
DATA_INI = re.compile(
    rf"^(?:\d\s+)?(?:(?P<d>\d{{1,2}})[/.-](?P<m>\d{{1,2}})(?:[/.-](?P<y>\d{{2,4}}))?"
    rf"|(?P<d2>\d{{1,2}})\s?(?:DE\s)?(?P<mn>{_MES})(?:\s?(?:DE\s)?(?P<y2>\d{{4}}))?)\s+(?P<resto>.+)$")
VALOR = re.compile(r"(?P<n1>[-−–](?=\d|R\$)|[-−–]\s(?=R\$))?(?:R\$\s?)?(?P<n2>[-−–](?=\d))?(?P<v>\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,3},\d{2})(?P<n3>\s?[-−–]|\s(?:C|CR)\b)?")
CARTAO = re.compile(r"(?:FINAL|TERMINADO EM|TERMINA EM|NUMERO)\s*:?\s*(?:[X*•.\d]{4}[\s.-]?){0,3}(\d{4})\b"
                    r"|(?:[X*•]{4}[\s.-]?){1,3}(\d{4})\b")
PARCELA = re.compile(r"\s(?:PARC(?:ELA)?\.?\s*)?(\d{1,2})\s?(?:/|DE)\s?(\d{1,2})$")
IGNORAR = re.compile(r"^(?:TOTAL|SUBTOTAL|SALDO|PAGAMENTO MINIMO|VALOR MINIMO|MINIMO|LIMITE|VENCIMENTO|"
                     r"FATURA ANTERIOR|ENCARGOS? (?:DO|PARA|NO)|JUROS (?:DO|PARA|NO|DE)|CET\b|TAXA|COTACAO|"
                     r"DOLAR|MOEDA|PERIODO|EMISSAO|FECHAMENTO|MELHOR DIA|PROXIMO|DATA)")
FUTURO = re.compile(r"PROXIMAS? FATURAS?|LANCAMENTOS FUTUROS|FATURAS FUTURAS|PARCELAS? FUTURAS?|"
                    r"COMPRAS PARCELADAS\s*-?\s*PROXIM|SALDO PARCELADO A VENCER")
VOLTA = re.compile(r"^(?:LANCAMENTOS|DESPESAS|COMPRAS|TRANSACOES|DETALHAMENTO|MOVIMENTACOES)\b")
PAGAMENTO = re.compile(r"PAGAMENTO|PAGTO|PGTO|PAG FATURA|PAGTO\. RECEBIDO")
CREDITO = re.compile(r"ESTORNO|CREDITO|DEVOLU|REEMBOLSO|CASHBACK|ANULAC|AJUSTE A CREDITO|BONIFICA")
TARIFA = re.compile(r"ANUIDADE|\bIOF\b|JUROS|MULTA|ENCARGO|TARIFA|MORA\b")


def _meta_generica(t):
    """Lê total, vencimento, mínimo, limite e juros do texto normalizado."""
    meta = {}

    def busca(pads, janela=60):
        for p in pads:
            m = re.search(p + rf"[^\d-]{{0,{janela}}}?(?:R\$\s?)?({VAL})", t)
            if m:
                return num(m.group(1))
        return None

    meta["total"] = busca([r"TOTAL\s+(?:DESTA|DA|DE\s+SUA|DA\s+SUA)\s+FATURA(?!\s+ANTERIOR)",
                           r"SALDO\s+(?:TOTAL\s+)?DESTA\s+FATURA", r"VALOR\s+TOTAL\s+(?:DA|DESTA)\s+FATURA",
                           r"TOTAL\s+A\s+PAGAR", r"VALOR\s+(?:TOTAL\s+)?A\s+PAGAR", r"VALOR\s+DA\s+FATURA",
                           r"FATURA\s+ATUAL", r"VALOR\s+TOTAL(?!\s+DE\s+COMPRAS)", r"TOTAL\s+DA\s+FATURA"])
    venc = None
    for p in (r"VENC(?:IMENTO|E EM|E)?\s*(?:DA FATURA)?[^\d\n]{0,30}?(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})",
              rf"VENC(?:IMENTO|E EM|E)?\s*(?:DA FATURA)?[^\d\n]{{0,30}}?(\d{{1,2}})\s?(?:DE\s)?({_MES})\s?(?:DE\s)?(\d{{4}})"):
        m = re.search(p, t)
        if m:
            d, mm, y = m.groups()
            mm = int(mm) if mm.isdigit() else MESES[mm[:3]]
            y = int(y) + (2000 if len(y) == 2 else 0)
            try:
                venc = date(y, mm, int(d))
                break
            except ValueError:
                pass
    if not venc:  # cabeçalho "Vencimento" com a data na linha de baixo
        m = re.search(r"VENCIMENTO[\s\S]{0,160}?\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t)
        if m:
            try:
                venc = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
    meta["vencimento"] = venc
    meta["minimo"] = busca([r"(?:PAGAMENTO|VALOR)\s+MINIMO"])
    meta["limite"] = busca([r"LIMITE\s+(?:TOTAL|DE\s+CREDITO|DO\s+CARTAO)(?!\s+(?:DISPONIVEL|UTILIZADO))"], 40)
    meta["parcelas_futuras"] = busca([r"SALDO\s+PARCELADO\s+A\s+VENCER", r"TOTAL\s+(?:DE\s+)?(?:PROXIMAS|FUTURAS)\s+FATURAS",
                                      r"COMPRAS\s+PARCELADAS[^\n]{0,40}OPERACOES\s+DE", r"PARCELAS\s+A\s+VENCER"])
    m = re.search(r"ROTATIVO[^%\n]{0,120}?(\d{1,2},\d{1,2})\s?%", t)
    meta["juros_rotativo_am"] = m.group(1) if m else None
    return meta


def _ler_linhas(linhas, venc, escolha):
    """Transforma linhas de texto em lançamentos. escolha: 0 = primeiro valor, -1 = último."""
    txs, cartao, futuro = [], None, False
    for bruto in linhas:
        ln = norm(re.sub(r"\s+", " ", bruto)).strip()
        if not ln:
            continue
        c = CARTAO.search(ln)
        if c and not DATA_INI.match(ln):
            cartao = c.group(1) or c.group(2)
            continue
        if FUTURO.search(ln):
            futuro = True
            continue
        if futuro and VOLTA.match(ln) and not FUTURO.search(ln):
            futuro = False
            continue
        if futuro:
            continue
        m = DATA_INI.match(ln)
        if not m:
            i = re.match(rf"^IOF\b.*?(?:R\$\s?)?({VAL})$", ln)
            if i and txs and not IGNORAR.match(ln):  # IOF de compra no exterior, sem data própria
                txs.append({**txs[-1], "descricao": "IOF EXTERIOR (" + txs[-1]["descricao"] + ")",
                            "valor": num(i.group(1)), "parcela": None, "tipo": "tarifa"})
            continue
        resto = m.group("resto")
        vals = list(VALOR.finditer(resto))
        if not vals:
            continue
        # o(s) valor(es) precisam estar no fim da linha
        fim = resto[vals[-1].end():].strip()
        if fim and not re.fullmatch(r"(?:[A-Z]{1,3}|US\$|USD|BRL)?", fim):
            continue
        # junta valores que fazem parte da "cauda" (ex.: valor em reais e em dólar)
        cauda = [vals[-1]]
        for v in reversed(vals[:-1]):
            entre = resto[v.end():cauda[0].start()]
            if re.fullmatch(r"\s*(?:US\$|USD|R\$|\$)?\s*", entre):
                cauda.insert(0, v)
            else:
                break
        alvo = cauda[escolha]
        desc = resto[:cauda[0].start()].strip(" -–:")
        if not desc or IGNORAR.match(desc) or re.fullmatch(r"[\d\s/.,-]+", desc):
            continue
        neg = bool(alvo.group("n1") or alvo.group("n2") or alvo.group("n3"))
        v = num(alvo.group("v"))
        parc = None
        p = PARCELA.search(" " + desc)
        if p:
            k, n = int(p.group(1)), int(p.group(2))
            if 1 <= k <= n <= 48 and n >= 2:
                parc = f"{k:02d}/{n:02d}"
                desc = (" " + desc)[:p.start()].strip()
        desc = re.sub(r"\s+", " ", desc).strip(" -–")
        if not desc:
            continue
        if PAGAMENTO.search(desc) and "MINIMO" not in desc:
            tipo, v = "pagamento", -abs(v)
        elif neg or CREDITO.search(desc):
            tipo, v = "credito", -abs(v)
        elif TARIFA.search(desc):
            tipo = "tarifa"
        else:
            tipo = "compra"
        # data
        if m.group("d"):
            d, mth, y = int(m.group("d")), int(m.group("m")), m.group("y")
        else:
            d, mth, y = int(m.group("d2")), MESES[m.group("mn")[:3]], m.group("y2")
        if not (1 <= mth <= 12 and 1 <= d <= 31):
            continue
        if y:
            y = int(y) + (2000 if len(y) == 2 else 0)
            try:
                data = date(y, mth, d).isoformat()
            except ValueError:
                data = None
        else:
            data = _ano_para(d, mth, venc) if venc else f"????-{mth:02d}-{d:02d}"
        txs.append({"data": data, "descricao": desc, "parcela": parc, "valor": v, "usd": None,
                    "cartao": cartao, "tipo": tipo})
    return txs


def _gastos(txs):
    return round(sum(t["valor"] for t in txs if t["tipo"] in ("compra", "tarifa", "credito")), 2)


def parse_generico(pdf, texto):
    t = norm(texto)
    meta = _meta_generica(t)
    meta["banco"] = banco_do_texto(t, norm(pdf.pages[0].extract_text() or "") if pdf.pages else "")
    venc = meta["vencimento"]

    # Duas formas de montar as linhas: página inteira e página em duas colunas.
    modos = {"pagina": [], "colunas": []}
    for page in pdf.pages:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
        modos["pagina"] += _linhas(words)
        mid = page.width / 2
        esq = [w for w in words if w["x1"] <= mid + 5]
        dir_ = [w for w in words if w["x0"] >= mid - 5]
        if len(esq) + len(dir_) >= len(words) * 0.9:  # quase nada cruza o meio
            modos["colunas"] += _linhas(esq) + _linhas(dir_)
        else:
            modos["colunas"] += _linhas(words)

    melhor = None
    for linhas in modos.values():
        for escolha in (0, -1):
            txs = _ler_linhas(linhas, venc, escolha)
            if not txs:
                continue
            g = _gastos(txs)
            # perto do total é melhor; empate: mais lançamentos
            nota = (abs(g - meta["total"]) if meta["total"] is not None else 0, -len(txs))
            if melhor is None or nota < melhor[0]:
                melhor = (nota, txs)
    if not melhor:
        return None
    txs = melhor[1]

    avisos = []
    if not venc:
        datas = sorted(x["data"] for x in txs if x["data"] and not x["data"].startswith("?"))
        if not datas:
            raise ValueError("Não encontrei o vencimento nem datas completas nos lançamentos.")
        ultimo = date.fromisoformat(datas[-1])
        venc = (ultimo.replace(day=1) + timedelta(days=40)).replace(day=10)
        avisos.append("vencimento não encontrado; usei o mês seguinte ao último lançamento")
        for x in txs:
            if x["data"] and x["data"].startswith("?"):
                _, mth, d = x["data"].split("-")
                x["data"] = _ano_para(int(d), int(mth), venc)
    if meta["total"] is None:
        meta["total"] = _gastos(txs)
        avisos.append("total da fatura não encontrado; usei a soma dos lançamentos")
    if meta["parcelas_futuras"] is None:
        fut = 0.0
        for x in txs:
            if x["parcela"] and x["tipo"] == "compra":
                k, n = map(int, x["parcela"].split("/"))
                fut += x["valor"] * (n - k)
        meta["parcelas_futuras"] = round(fut, 2)
    meta["vencimento"] = venc.isoformat()
    meta["id"] = f"{venc.year:04d}-{venc.month:02d}"
    meta["anuidade_cobrada"] = round(sum(x["valor"] for x in txs if "ANUIDADE" in x["descricao"] and x["valor"] > 0), 2)
    if avisos:
        meta["avisos"] = avisos
    return meta, txs


LEITORES = [parse_santander, parse_generico]


def _eh_senha(e):
    """pdfplumber embrulha o erro do pdfminer; procura PDFPasswordIncorrect na cadeia."""
    vistos = 0
    while e is not None and vistos < 5:
        if (PDFPasswordIncorrect and isinstance(e, PDFPasswordIncorrect)) or "Password" in type(e).__name__:
            return True
        e = (e.args[0] if e.args and isinstance(e.args[0], BaseException) else None) or e.__cause__ or e.__context__
        vistos += 1
    return False


def _abrir(path, senha):
    try:
        return pdfplumber.open(path, password=senha or "")
    except Exception as e:  # noqa: BLE001
        if _eh_senha(e):
            raise SenhaNecessaria("senha errada" if senha else "PDF protegido por senha") from None
        raise


def parse_pdf(path, senha=None):
    pdf = _abrir(path, senha)
    with pdf:
        try:
            texto = "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception as e:  # noqa: BLE001
            if _eh_senha(e):
                raise SenhaNecessaria("senha errada" if senha else "PDF protegido por senha") from None
            raise
        if len(texto.strip()) < 50:
            raise ValueError("Este PDF parece ser uma imagem (escaneado). Baixe a fatura em PDF pelo app ou site do banco.")
        for leitor in LEITORES:
            r = leitor(pdf, texto)
            if r:
                meta, txs = r
                meta["soma_lancamentos"] = _gastos(txs)
                meta["n_lancamentos"] = len(txs)
                meta["leitor"] = leitor.__name__.replace("parse_", "")
                return meta, txs
    raise ValueError("Não encontrei lançamentos nesta fatura.")


if __name__ == "__main__":
    import json
    import sys
    m, t = parse_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(m, ensure_ascii=False, indent=1))
    print(len(t))
    for x in t[:5] + t[-5:]:
        print(x)
