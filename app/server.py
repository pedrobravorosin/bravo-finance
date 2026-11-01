#!/usr/bin/env python3
"""Servidor local do Financeiro (painel de faturas de cartão).

- Escuta só em 127.0.0.1 (nada fica acessível pela rede).
- Porta própria (padrão 47821, mude com FATURAS_PORT).
- Lê os PDFs aqui mesmo com pdfplumber; nenhum dado sai da máquina.
- Uma fatura por banco e por mês. Faturas de bancos diferentes no mesmo mês
  aparecem somadas no painel.
"""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from categorias import CATEGORIAS, categoria, normaliza  # noqa: E402
from leitor import SenhaNecessaria, parse_pdf  # noqa: E402

PORT = int(os.environ.get("FATURAS_PORT", "47821"))
DATA = Path(os.environ.get("FATURAS_DATA", BASE / "data"))
FAT = DATA / "faturas"
PDFS = DATA / "pdfs"
OVR = DATA / "categorias.json"
PREFS = DATA / "preferencias.json"
REGRAS_USUARIO = DATA / "regras.json"  # opcional: {"Categoria": "REGEX", ...} com nomes só seus
PUBLIC = BASE / "public"
MAX_UPLOAD = 30 * 1024 * 1024
LOCK = threading.Lock()
ULTIMO_USO = time.monotonic()
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon"}

for d in (FAT, PDFS):
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
os.chmod(DATA, 0o700)


def overrides():
    try:
        return json.loads(OVR.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_json(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
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


class H(BaseHTTPRequestHandler):
    server_version = "faturas"

    def log_message(self, fmt, *a):  # não registra URLs nem dados
        pass

    def _host_ok(self):
        return self.headers.get("Host", "") in ALLOWED_HOSTS

    def _mut_ok(self):
        # Cabeçalho próprio obriga preflight CORS: outro site no navegador não consegue gravar aqui.
        return self._host_ok() and self.headers.get("X-Faturas") == "1"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, msg):
        self._send(code, {"erro": msg})

    def do_GET(self):
        global ULTIMO_USO
        ULTIMO_USO = time.monotonic()
        if not self._host_ok():
            return self._err(403, "host não permitido")
        p = urlparse(self.path).path
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
        rel = "index.html" if p in ("", "/") else p.lstrip("/")
        f = (PUBLIC / rel).resolve()
        if PUBLIC.resolve() not in f.parents or not f.is_file():
            return self._err(404, "não encontrado")
        self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))

    def do_POST(self):
        if not self._mut_ok():
            return self._err(403, "não permitido")
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_UPLOAD:
            return self._err(413, "arquivo vazio ou grande demais")
        body = self.rfile.read(n)
        if p == "/api/faturas":
            if not body.startswith(b"%PDF"):
                return self._err(400, "o arquivo não é um PDF")
            with tempfile.NamedTemporaryFile(suffix=".pdf", dir=PDFS, delete=False) as tmp:
                tmp.write(body)
            os.chmod(tmp.name, 0o600)
            senha = unquote(self.headers.get("X-Senha", "")) or None  # usada só para abrir, nunca gravada
            try:
                meta, txs = parse_pdf(tmp.name, senha)
            except SenhaNecessaria as e:
                os.unlink(tmp.name)
                return self._send(401, {"erro": f"Fatura protegida por senha ({e}).", "senha": True})
            except Exception as e:  # noqa: BLE001
                os.unlink(tmp.name)
                return self._err(422, f"Não consegui ler a fatura: {e}")
            chave = f"{meta['id']}__{slug(meta.get('banco') or 'cartao')}"
            with LOCK:
                antiga = FAT / f"{meta['id']}.json"  # formato antigo (um banco por mês)
                if antiga.exists() and json.loads(antiga.read_text(encoding="utf-8"))["meta"].get("banco") == meta.get("banco"):
                    antiga.unlink()
                    (PDFS / f"{meta['id']}.pdf").unlink(missing_ok=True)
                existia = (FAT / f"{chave}.json").exists()
                os.replace(tmp.name, PDFS / f"{chave}.pdf")
                write_json(FAT / f"{chave}.json", {"meta": meta, "transacoes": txs})
            return self._send(200, {"ok": True, "meta": meta, "chave": chave, "substituida": existia})
        return self._err(404, "não encontrado")

    def do_PUT(self):
        if not self._mut_ok():
            return self._err(403, "não permitido")
        rota = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
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
        except (ValueError, KeyError, AttributeError):
            return self._err(400, "inválido")
        if cat not in CATEGORIAS:
            return self._err(400, "categoria inválida")
        with LOCK:
            ov = overrides()
            ov[est] = cat
            write_json(OVR, ov)
        self._send(200, {"ok": True})

    def do_DELETE(self):
        if not self._mut_ok():
            return self._err(403, "não permitido")
        m = re.fullmatch(r"/api/faturas/(\d{4}-\d{2}(?:__[a-z0-9-]+)?)", urlparse(self.path).path)
        if not m:
            return self._err(404, "não encontrado")
        with LOCK:
            for f in (FAT / f"{m.group(1)}.json", PDFS / f"{m.group(1)}.pdf"):
                f.unlink(missing_ok=True)
        self._send(200, {"ok": True})


def vigia_ociosidade(srv, limite):
    """Desliga sozinho quando nenhuma janela do painel fala com o servidor por `limite` segundos.
    A página avisa que está aberta a cada 20 s (veja app.js)."""
    while True:
        time.sleep(5)
        if time.monotonic() - ULTIMO_USO > limite:
            srv.shutdown()
            return


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Financeiro em http://localhost:{PORT}", flush=True)
    ocioso = int(os.environ.get("FATURAS_DESLIGAR_OCIOSO", "0"))  # segundos; 0 = nunca
    if ocioso > 0:
        threading.Thread(target=vigia_ociosidade, args=(srv, ocioso), daemon=True).start()
    srv.serve_forever()
