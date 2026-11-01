#!/usr/bin/env python3
"""Servidor local do Bravo Finance (painel de faturas de cartão).

Segurança:
- Escuta só em 127.0.0.1, numa porta livre escolhida a cada abertura.
- Sem internet: o bloqueio de rede (blindagem.py) recusa qualquer conexão
  para fora do computador, e a página não carrega nada de fora (CSP).
- Chave por sessão: quem abre o app recebe uma chave de uso único e troca por
  um cookie de sessão. Sem ele, nenhum dado é entregue, nem para outros
  programas ou usuários do mesmo computador.
- Cada PDF é lido num processo separado, com tempo e memória limitados.
- Uma instância por usuário; os dados ficam numa pasta só do usuário.

Uso pelo app: python -I -s server.py --janela
  Escreve na saída "BRAVO-FINANCE <porta> <chave>" e desliga quando a
  entrada padrão fecha (ou seja, quando a janela do app fecha).
"""
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import blindagem  # noqa: E402

blindagem.ativar()
from categorias import CATEGORIAS, categoria, normaliza  # noqa: E402

NOME = "Bravo Finance"


def pasta_padrao():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / NOME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / NOME
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "bravo-finance"


DATA = Path(os.environ.get("BRAVO_DADOS") or pasta_padrao())
FAT = DATA / "faturas"
PDFS = DATA / "pdfs"
OVR = DATA / "categorias.json"
PREFS = DATA / "preferencias.json"
REGRAS_USUARIO = DATA / "regras.json"  # opcional: {"Categoria": "REGEX", ...} com nomes só seus
PUBLIC = BASE / "public"
FAVICON = BASE / "icone" / "favicon.png"
MAX_UPLOAD = 30 * 1024 * 1024
TEMPO_LEITURA = 120  # segundos por PDF
LOCK = threading.Lock()
ULTIMO_USO = time.monotonic()
PORT = 0  # definida ao ligar
CHAVE_ENTRADA = secrets.token_urlsafe(32)
SESSAO = secrets.token_urlsafe(32)
ENTRADA_USADA = False
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".png": "image/png"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def preparar_pastas():
    for d in (DATA, FAT, PDFS):
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass


def overrides():
    try:
        return json.loads(OVR.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_json(path, obj):
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    tmp.replace(path)


def slug(txt):
    t = unicodedata.normalize("NFD", txt).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "banco"


def regras_usuario():
    try:
        d = json.loads(REGRAS_USUARIO.read_text(encoding="utf-8"))
        return [(c, re.compile(r)) for c, r in d.items() if c in CATEGORIAS]
    except (FileNotFoundError, json.JSONDecodeError, re.error, AttributeError):
        return []


def classificar(desc, ov, extras):
    k = normaliza(desc)
    if k not in ov:
        for cat, rx in extras:
            if rx.search(k):
                return cat
    return categoria(desc, ov)


def arquivos():
    """Lê cada fatura salva: faturas/<AAAA-MM>__<banco>.json (ou <AAAA-MM>.json, formato antigo)."""
    out = []
    for f in sorted(FAT.glob("*.json")):
        m = re.fullmatch(r"(\d{4}-\d{2})(?:__([a-z0-9-]+))?", f.stem)
        if not m:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        d["chave"] = f.stem
        out.append(d)
    return out


def todas_faturas():
    """Junta as faturas de um mesmo mês (bancos diferentes) numa só para o painel."""
    ov, extras = overrides(), regras_usuario()
    meses, lista = {}, []
    for d in arquivos():
        meta = d["meta"]
        banco = meta.get("banco") or "Cartão"
        lista.append({"chave": d["chave"], "mes": meta["id"], "banco": banco, "total": meta["total"],
                      "vencimento": meta["vencimento"], "n_lancamentos": meta.get("n_lancamentos", len(d["transacoes"])),
                      "soma_lancamentos": meta.get("soma_lancamentos"), "parcelas_futuras": meta.get("parcelas_futuras"),
                      "avisos": meta.get("avisos", [])})
        for t in d["transacoes"]:
            t["banco"] = banco
            t["estabelecimento"] = normaliza(t["descricao"])
            t["categoria"] = "Tarifas e juros" if t["tipo"] == "tarifa" else classificar(t["descricao"], ov, extras)
        g = meses.get(meta["id"])
        if g is None:
            meses[meta["id"]] = {"meta": {**meta, "bancos": [banco]}, "transacoes": list(d["transacoes"])}
            continue
        gm = g["meta"]
        gm["bancos"].append(banco)
        gm["banco"] = ", ".join(gm["bancos"])
        for k in ("total", "soma_lancamentos", "parcelas_futuras", "limite", "minimo", "anuidade_cobrada", "n_lancamentos"):
            if meta.get(k) is not None or gm.get(k) is not None:
                gm[k] = round((gm.get(k) or 0) + (meta.get(k) or 0), 2)
        gm["vencimento"] = min(gm["vencimento"], meta["vencimento"])
        g["transacoes"] += d["transacoes"]
    return [meses[k] for k in sorted(meses)], lista


def ler_pdf(caminho, senha):
    """Lê o PDF num processo separado (leitor_isolado.py), com tempo limitado."""
    extra = {"creationflags": 0x08000000} if os.name == "nt" else {}  # sem janela de console
    python = sys.executable
    if os.name == "nt" and python.lower().endswith("pythonw.exe"):
        python = python[:-5] + ".exe"
    try:
        r = subprocess.run([python, "-I", "-s", str(BASE / "leitor_isolado.py")],
                           input=json.dumps({"pdf": str(caminho), "senha": senha}).encode(),
                           capture_output=True, timeout=TEMPO_LEITURA, cwd=str(BASE), **extra)
    except subprocess.TimeoutExpired:
        return {"erro": "A leitura demorou demais e foi interrompida. O PDF pode estar corrompido.", "senha": False}
    try:
        return json.loads(r.stdout.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"erro": "Não consegui ler a fatura (o leitor parou de forma inesperada).", "senha": False}


PAGINA_SEM_ACESSO = """<!doctype html><meta charset="utf-8"><title>Bravo Finance</title>
<body style="font:16px system-ui;margin:0;display:flex;height:100vh;align-items:center;justify-content:center;color:#555">
<p>Abra o Bravo Finance pelo ícone do aplicativo.</p></body>"""


class H(BaseHTTPRequestHandler):
    server_version = "BravoFinance"
    sys_version = ""

    def log_message(self, fmt, *a):  # não registra URLs nem dados
        pass

    # ---- verificações
    def _host_ok(self):
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def _sessao_ok(self):
        try:
            c = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        m = c.get("bf")
        return m is not None and hmac.compare_digest(m.value.encode(), SESSAO.encode())

    def _mesma_origem(self):
        origem = self.headers.get("Origin")
        if origem is not None and origem not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"):
            return False
        site = self.headers.get("Sec-Fetch-Site")
        return site in (None, "same-origin")

    def _liberado(self, gravar=False):
        global ULTIMO_USO
        if not (self._host_ok() and self._sessao_ok()):
            return False
        if gravar and not (self._mesma_origem() and self.headers.get("X-Faturas") == "1"):
            return False
        ULTIMO_USO = time.monotonic()
        return True

    def _tamanho(self):
        try:
            return int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return -1

    # ---- respostas
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _err(self, code, msg):
        self._send(code, {"erro": msg})

    def _negado(self):
        if self.command == "GET" and not urlparse(self.path).path.startswith("/api/"):
            return self._send(403, PAGINA_SEM_ACESSO, "text/html; charset=utf-8")
        return self._err(403, "não permitido")

    # ---- rotas
    def do_GET(self):
        global ENTRADA_USADA
        if not self._host_ok():
            return self._err(403, "não permitido")
        u = urlparse(self.path)
        if u.path == "/entrar":
            chave = (parse_qs(u.query).get("t") or [""])[0]
            with LOCK:
                valida = not ENTRADA_USADA and hmac.compare_digest(chave.encode(), CHAVE_ENTRADA.encode())
                if valida:
                    ENTRADA_USADA = True  # a chave vale uma vez só
            if not valida:
                return self._negado()
            return self._send(303, b"", "text/plain", {
                "Location": "/", "Set-Cookie": f"bf={SESSAO}; HttpOnly; SameSite=Strict; Path=/"})
        if not self._liberado():
            return self._negado()
        p = u.path
        if p == "/api/faturas":
            faturas, lista = todas_faturas()
            return self._send(200, {"faturas": faturas, "arquivos": lista, "categorias": CATEGORIAS})
        if p == "/api/preferencias":
            try:
                return self._send(200, json.loads(PREFS.read_text(encoding="utf-8")))
            except (FileNotFoundError, json.JSONDecodeError):
                return self._send(200, {})
        if p == "/api/saude":
            return self._send(200, {"ok": True})
        if p == "/favicon.png":
            return self._send(200, FAVICON.read_bytes(), "image/png")
        rel = "index.html" if p in ("", "/") else p.lstrip("/")
        f = (PUBLIC / rel).resolve()
        if PUBLIC.resolve() not in f.parents or not f.is_file() or f.suffix not in TYPES:
            return self._err(404, "não encontrado")
        self._send(200, f.read_bytes(), TYPES[f.suffix])

    def do_HEAD(self):
        return self._err(405, "não permitido")

    def do_POST(self):
        if not self._liberado(gravar=True):
            return self._negado()
        p = urlparse(self.path).path
        if p != "/api/faturas":
            return self._err(404, "não encontrado")
        n = self._tamanho()
        if n <= 0 or n > MAX_UPLOAD:
            return self._err(413, "arquivo vazio ou grande demais (máximo 30 MB)")
        body = self.rfile.read(n)
        if not body.startswith(b"%PDF"):
            return self._err(400, "o arquivo não é um PDF")
        with tempfile.NamedTemporaryFile(suffix=".pdf", dir=PDFS, delete=False) as tmp:
            tmp.write(body)
        try:
            os.chmod(tmp.name, 0o600)
        except OSError:
            pass
        senha = unquote(self.headers.get("X-Senha", ""))[:200] or None  # usada só para abrir, nunca gravada
        r = ler_pdf(tmp.name, senha)
        if "erro" in r:
            os.unlink(tmp.name)
            if r.get("senha"):
                return self._send(401, {"erro": r["erro"], "senha": True})
            return self._err(422, r["erro"])
        meta, txs = r["meta"], r["transacoes"]
        if not re.fullmatch(r"\d{4}-\d{2}", str(meta.get("id", ""))):
            os.unlink(tmp.name)
            return self._err(422, "Não consegui identificar o mês da fatura.")
        chave = f"{meta['id']}__{slug(meta.get('banco') or 'cartao')}"
        with LOCK:
            existia = (FAT / f"{chave}.json").exists()
            os.replace(tmp.name, PDFS / f"{chave}.pdf")
            write_json(FAT / f"{chave}.json", {"meta": meta, "transacoes": txs})
        return self._send(200, {"ok": True, "meta": meta, "chave": chave, "substituida": existia})

    def do_PUT(self):
        if not self._liberado(gravar=True):
            return self._negado()
        rota = urlparse(self.path).path
        n = self._tamanho()
        if rota == "/api/preferencias":
            if n <= 0 or n > 200_000:
                return self._err(413, "inválido")
            try:
                d = json.loads(self.rfile.read(n))
                assert isinstance(d, dict)
            except (ValueError, AssertionError):
                return self._err(400, "inválido")
            with LOCK:
                write_json(PREFS, d)
            return self._send(200, {"ok": True})
        if rota != "/api/categorias":
            return self._err(404, "não encontrado")
        if n <= 0 or n > 100_000:
            return self._err(413, "inválido")
        try:
            d = json.loads(self.rfile.read(n))
            est, cat = normaliza(d["estabelecimento"]), d["categoria"]
        except (ValueError, KeyError, AttributeError, TypeError):
            return self._err(400, "inválido")
        if cat not in CATEGORIAS:
            return self._err(400, "categoria inválida")
        with LOCK:
            ov = overrides()
            ov[est] = cat
            write_json(OVR, ov)
        self._send(200, {"ok": True})

    def do_DELETE(self):
        if not self._liberado(gravar=True):
            return self._negado()
        m = re.fullmatch(r"/api/faturas/(\d{4}-\d{2}(?:__[a-z0-9-]+)?)", urlparse(self.path).path)
        if not m:
            return self._err(404, "não encontrado")
        with LOCK:
            for f in (FAT / f"{m.group(1)}.json", PDFS / f"{m.group(1)}.pdf"):
                f.unlink(missing_ok=True)
        self._send(200, {"ok": True})


class Servidor(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16


def trava_instancia():
    """Garante um só Bravo Finance aberto por usuário (o arquivo fica travado enquanto o app roda)."""
    f = os.fdopen(os.open(DATA / ".em-uso", os.O_RDWR | os.O_CREAT, 0o600), "r+b")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def vigia_entrada(srv):
    """Modo janela: desliga quando o app fecha a entrada padrão."""
    try:
        while sys.stdin.buffer.read(1024):
            pass
    except (OSError, ValueError, AttributeError):
        pass
    srv.shutdown()


def vigia_ociosidade(srv, limite):
    """Modo navegador: desliga quando a página para de avisar que está aberta (a cada 20 s)."""
    while True:
        time.sleep(5)
        if time.monotonic() - ULTIMO_USO > limite:
            srv.shutdown()
            return


def main():
    global PORT
    janela = "--janela" in sys.argv
    preparar_pastas()
    trava = trava_instancia()
    if trava is None:
        print("BRAVO-FINANCE OCUPADO", flush=True)
        sys.exit(3)
    srv = Servidor(("127.0.0.1", int(os.environ.get("BRAVO_PORTA", "0"))), H)
    PORT = srv.server_address[1]
    print(f"BRAVO-FINANCE {PORT} {CHAVE_ENTRADA}", flush=True)
    if janela:
        threading.Thread(target=vigia_entrada, args=(srv,), daemon=True).start()
    else:
        threading.Thread(target=vigia_ociosidade, args=(srv, int(os.environ.get("BRAVO_OCIOSO", "180"))),
                         daemon=True).start()
    try:
        srv.serve_forever()
    finally:
        srv.server_close()
        trava.close()


if __name__ == "__main__":
    main()
