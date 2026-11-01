"""Testes de segurança do servidor e do bloqueio de rede. Rode: python -m unittest discover tests"""
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
APP = AQUI.parent / "app"
sys.path.insert(0, str(AQUI))
from gerar_exemplos import ESPERADO, PASTA, main as gerar  # noqa: E402


def ligar(dados):
    env = dict(os.environ, BRAVO_DADOS=str(dados))
    p = subprocess.Popen([sys.executable, "-I", "-s", str(APP / "server.py"), "--janela"], cwd=str(APP), env=env,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p, p.stdout.readline().decode().split()


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all((PASTA / n).exists() for n in ESPERADO):
            gerar()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.proc, linha = ligar(cls.tmp.name)
        assert linha[0] == "BRAVO-FINANCE", linha
        cls.porta, cls.chave = int(linha[1]), linha[2]
        cls.host = f"127.0.0.1:{cls.porta}"
        st, h, _ = cls.req("GET", f"/entrar?t={cls.chave}")
        assert st == 303, st
        cls.cookie = h["set-cookie"].split(";")[0]

    @classmethod
    def tearDownClass(cls):
        cls.proc.stdin.close()
        cls.proc.wait(timeout=10)
        cls.tmp.cleanup()

    @classmethod
    def req(cls, metodo, caminho, corpo=None, cab=None):
        c = http.client.HTTPConnection("127.0.0.1", cls.porta, timeout=60)
        h = {"Host": cls.host, **(cab or {})}
        c.request(metodo, caminho, body=corpo, headers=h)
        r = c.getresponse()
        dados = r.read()
        c.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, dados

    def com_sessao(self, metodo, caminho, corpo=None, cab=None):
        return self.req(metodo, caminho, corpo, {"Cookie": self.cookie, **(cab or {})})

    def test_sem_sessao_nada_e_entregue(self):
        for caminho in ("/", "/api/faturas", "/api/preferencias", "/app.js"):
            self.assertEqual(self.req("GET", caminho)[0], 403, caminho)
        self.assertEqual(self.req("GET", "/api/faturas", cab={"Cookie": "bf=errado"})[0], 403)

    def test_chave_vale_uma_vez(self):
        self.assertEqual(self.req("GET", f"/entrar?t={self.chave}")[0], 403)
        self.assertEqual(self.req("GET", "/entrar?t=chute")[0], 403)

    def test_cookie_protegido(self):
        st, h, _ = self.com_sessao("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("default-src 'none'", h["content-security-policy"])
        self.assertEqual(h["x-frame-options"], "DENY")

    def test_host_estranho_recusado(self):
        st, _, _ = self.req("GET", "/api/faturas", cab={"Cookie": self.cookie, "Host": "evil.example:80"})
        self.assertEqual(st, 403)

    def test_gravacao_exige_mesma_origem(self):
        corpo = json.dumps({"tema": "escuro"})
        self.assertEqual(self.com_sessao("PUT", "/api/preferencias", corpo)[0], 403)
        self.assertEqual(self.com_sessao("PUT", "/api/preferencias", corpo,
                                         {"X-Faturas": "1", "Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.com_sessao("PUT", "/api/preferencias", corpo,
                                         {"X-Faturas": "1", "Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.com_sessao("PUT", "/api/preferencias", corpo,
                                         {"X-Faturas": "1", "Origin": f"http://{self.host}"})[0], 200)

    def test_sem_travessia_de_pasta(self):
        for caminho in ("/../server.py", "/%2e%2e/server.py", "/vendor/../../server.py"):
            self.assertEqual(self.com_sessao("GET", caminho)[0], 404, caminho)

    def test_envio_de_fatura_e_senha(self):
        cab = {"X-Faturas": "1", "Content-Type": "application/pdf"}
        pdf = (PASTA / "estilo-nubank.pdf").read_bytes()
        st, _, d = self.com_sessao("POST", "/api/faturas", pdf, cab)
        self.assertEqual(st, 200, d)
        self.assertAlmostEqual(json.loads(d)["meta"]["total"], 1003.20)
        protegido = (PASTA / "estilo-duas-colunas.pdf").read_bytes()
        self.assertEqual(self.com_sessao("POST", "/api/faturas", protegido, cab)[0], 401)
        st, _, _ = self.com_sessao("POST", "/api/faturas", protegido, {**cab, "X-Senha": "12345"})
        self.assertEqual(st, 200)
        self.assertEqual(self.com_sessao("POST", "/api/faturas", b"nao e pdf", cab)[0], 400)
        st, _, d = self.com_sessao("GET", "/api/faturas")
        self.assertEqual(len(json.loads(d)["arquivos"]), 2)

    def test_uma_instancia_por_usuario(self):
        p, linha = ligar(self.tmp.name)
        p.wait(timeout=10)
        self.assertEqual(linha, ["BRAVO-FINANCE", "OCUPADO"])


class TestBlindagem(unittest.TestCase):
    def test_internet_bloqueada(self):
        codigo = (
            "import sys, socket, urllib.request; sys.path.insert(0, sys.argv[1]); import blindagem; blindagem.ativar()\n"
            "falhas = 0\n"
            "for f in (lambda: socket.create_connection(('1.1.1.1', 443), 2), lambda: socket.getaddrinfo('example.com', 443),\n"
            "          lambda: urllib.request.urlopen('https://example.com', timeout=2),\n"
            "          lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x', ('8.8.8.8', 53))):\n"
            "    try: f()\n"
            "    except PermissionError: falhas += 1\n"
            "s = socket.socket(); s.bind(('127.0.0.1', 0)); s.close()\n"
            "print(falhas)\n")
        r = subprocess.run([sys.executable, "-I", "-c", codigo, str(APP)], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), "4", r.stderr)

    def test_servidor_desliga_quando_a_janela_fecha(self):
        with tempfile.TemporaryDirectory() as d:
            p, linha = ligar(d)
            self.assertEqual(linha[0], "BRAVO-FINANCE")
            p.stdin.close()
            inicio = time.monotonic()
            p.wait(timeout=10)
            self.assertLess(time.monotonic() - inicio, 10)
            with self.assertRaises(OSError):
                socket.create_connection(("127.0.0.1", int(linha[1])), 1)


if __name__ == "__main__":
    unittest.main()
