"""Abre o Financeiro numa janela própria (Windows e Linux).

- Liga o servidor local (só 127.0.0.1) se ele ainda não estiver ligado.
- Abre o painel numa janela de aplicativo do Edge, Chrome, Chromium ou Brave,
  com perfil separado (sem abas, sem histórico do seu navegador).
- Quando a janela fecha, desliga o servidor.
- Sem esses navegadores, abre no navegador padrão; o servidor desliga sozinho
  uns minutos depois que a aba for fechada.

No macOS o app nativo (instaladores/macos) faz esse papel.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = int(os.environ.get("FATURAS_PORT", "47821"))
URL = f"http://localhost:{PORT}/"
APP = Path(__file__).resolve().parent
WINDOWS = os.name == "nt"


def pasta_base():
    """Pasta da instalação: a que contém app/ (e python/ ou venv/, e dados/)."""
    return APP.parent


BASE = pasta_base()
DADOS = Path(os.environ.get("FATURAS_DATA", BASE / "dados"))


def aviso(texto):
    if WINDOWS:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, texto, "Financeiro", 0x40)
    elif shutil.which("zenity"):
        subprocess.run(["zenity", "--info", "--title=Financeiro", f"--text={texto}"], check=False)
    elif shutil.which("kdialog"):
        subprocess.run(["kdialog", "--title", "Financeiro", "--msgbox", texto], check=False)
    else:
        print(texto)


def no_ar():
    try:
        with urllib.request.urlopen(URL + "api/saude", timeout=1) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def acha_navegador_app():
    if WINDOWS:
        bases = [os.environ.get(k) for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        rel = [("Microsoft", "Edge", "Application", "msedge.exe"), ("Google", "Chrome", "Application", "chrome.exe"),
               ("BraveSoftware", "Brave-Browser", "Application", "brave.exe")]
        for r in rel:
            for b in bases:
                if b and Path(b, *r).exists():
                    return str(Path(b, *r))
        return None
    for nome in ("microsoft-edge", "microsoft-edge-stable", "google-chrome", "google-chrome-stable",
                 "chromium", "chromium-browser", "brave-browser", "brave"):
        p = shutil.which(nome)
        if p:
            return p
    return None


def python_do_servidor():
    if WINDOWS:
        p = BASE / "python" / "python.exe"
        return str(p) if p.exists() else sys.executable.replace("pythonw.exe", "python.exe")
    return sys.executable


def ligar_servidor(ocioso):
    DADOS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, FATURAS_DATA=str(DADOS), FATURAS_PORT=str(PORT), FATURAS_DESLIGAR_OCIOSO=str(ocioso))
    log = open(DADOS / "servidor.log", "w", encoding="utf-8")
    extra = {"creationflags": 0x08000000} if WINDOWS else {"start_new_session": True}
    srv = subprocess.Popen([python_do_servidor(), "-I", str(APP / "server.py")], cwd=str(APP), env=env,
                           stdout=log, stderr=log, stdin=subprocess.DEVNULL, **extra)
    for _ in range(150):
        if no_ar():
            return srv
        if srv.poll() is not None:
            break
        time.sleep(0.2)
    aviso("O Financeiro não conseguiu ligar. Veja o arquivo servidor.log em:\n" + str(DADOS))
    sys.exit(1)


def main():
    nav = acha_navegador_app()
    srv = None
    if not no_ar():
        # Com janela de app, o servidor desliga quando ela fecha; sem ela, por ociosidade.
        srv = ligar_servidor(ocioso=900 if nav else 180)
    if not nav:
        webbrowser.open(URL)
        return
    perfil = BASE / "janela"
    try:
        subprocess.run([nav, f"--app={URL}", f"--user-data-dir={perfil}", "--no-first-run",
                        "--no-default-browser-check", "--disable-sync", "--disable-extensions",
                        "--window-size=1320,880"], check=False)
    finally:
        if srv is not None:
            srv.terminate()


if __name__ == "__main__":
    main()
