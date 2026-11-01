"""Abre o Bravo Finance numa janela própria (Windows e Linux).

- Liga o servidor local (só 127.0.0.1, porta livre escolhida na hora) e recebe
  dele uma chave de uso único para entrar.
- Abre o painel numa janela de aplicativo do Edge, Chrome, Chromium ou Brave,
  com perfil separado e sem acesso à internet: todo endereço que não seja o do
  próprio computador vai para um proxy inexistente e falha.
- Quando a janela fecha, o servidor desliga.
- Sem esses navegadores, abre no navegador padrão; o servidor desliga sozinho
  uns minutos depois que a aba for fechada.

No macOS o app nativo (instaladores/macos) faz esse papel.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))
import blindagem  # noqa: E402

blindagem.ativar()
from server import DATA, NOME  # noqa: E402  (só constantes; não liga nada)

WINDOWS = os.name == "nt"

# Flags da janela: sem sincronização, extensões, atualizações, telemetria nem internet.
FLAGS_JANELA = [
    "--no-first-run", "--no-default-browser-check", "--disable-sync", "--disable-extensions",
    "--disable-background-networking", "--disable-component-update", "--disable-default-apps",
    "--disable-domain-reliability", "--disable-breakpad", "--disable-client-side-phishing-detection",
    "--metrics-recording-only", "--no-pings", "--disable-features=Translate,OptimizationHints,MediaRouter,"
    "AutofillServerCommunication,SpareRendererForSitePerProcess,msEdgeShopping,msEdgeCollections",
    "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>;127.0.0.1;localhost",
    "--window-size=1320,880",
]


def aviso(texto):
    if WINDOWS:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, texto, NOME, 0x40)
    elif shutil.which("zenity"):
        subprocess.run(["zenity", "--info", f"--title={NOME}", f"--text={texto}"], check=False)
    elif shutil.which("kdialog"):
        subprocess.run(["kdialog", "--title", NOME, "--msgbox", texto], check=False)
    else:
        print(texto, file=sys.stderr)


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
    exe = Path(sys.executable)
    if WINDOWS and exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")  # o servidor precisa de stdin/stdout
    return str(exe)


def ligar_servidor(janela):
    DATA.mkdir(parents=True, exist_ok=True)
    log = os.fdopen(os.open(DATA / "servidor.log", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w")
    extra = {"creationflags": 0x08000000} if WINDOWS else {"start_new_session": True}
    args = [python_do_servidor(), "-I", "-s", str(APP / "server.py")] + (["--janela"] if janela else [])
    srv = subprocess.Popen(args, cwd=str(APP), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, **extra)
    linha = srv.stdout.readline().decode("ascii", "ignore").split()
    if linha[:2] == ["BRAVO-FINANCE", "OCUPADO"]:
        aviso(f"O {NOME} já está aberto.")
        sys.exit(0)
    if len(linha) != 3 or linha[0] != "BRAVO-FINANCE":
        aviso(f"O {NOME} não conseguiu ligar. Veja o arquivo servidor.log em:\n{DATA}")
        sys.exit(1)
    return srv, f"http://127.0.0.1:{int(linha[1])}/entrar?t={linha[2]}"


def main():
    nav = acha_navegador_app()
    srv, url = ligar_servidor(janela=bool(nav))
    if not nav:
        srv.stdin.close()
        webbrowser.open(url)
        return
    # Perfil novo a cada abertura, apagado ao fechar: nada fica guardado pela janela.
    perfil = tempfile.mkdtemp(prefix="bravo-finance-janela-")
    try:
        subprocess.run([nav, f"--app={url}", f"--user-data-dir={perfil}", *FLAGS_JANELA], check=False)
    finally:
        try:
            srv.stdin.close()  # o servidor desliga
            srv.wait(timeout=10)
        except Exception:  # noqa: BLE001
            srv.kill()
        shutil.rmtree(perfil, ignore_errors=True)


if __name__ == "__main__":
    main()
