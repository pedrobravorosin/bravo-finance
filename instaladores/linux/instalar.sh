#!/bin/bash
# Instalador do Financeiro para Linux (Ubuntu, Debian, Fedora, Mint, Arch, openSUSE...).
# Usa o Python 3 do sistema (3.9 ou mais novo) num ambiente próprio, sem mexer no sistema.
# Uso: bash instaladores/linux/instalar.sh
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
BASE="${XDG_DATA_HOME:-$HOME/.local/share}/financeiro"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
passo() { printf '\n==> %s\n' "$1"; }

instalar_pacotes() {  # pede permissão antes de usar sudo
  local pkgs="$*"
  echo "Para continuar é preciso instalar pelo sistema: $pkgs"
  read -r -p "Posso instalar agora com sudo? (s/N) " r
  [[ "$r" =~ ^[sS] ]] || { echo "Instale e rode este instalador de novo."; exit 1; }
  if command -v apt-get >/dev/null; then sudo apt-get update && sudo apt-get install -y $pkgs
  elif command -v dnf >/dev/null; then sudo dnf install -y $pkgs
  elif command -v pacman >/dev/null; then sudo pacman -S --needed --noconfirm $pkgs
  elif command -v zypper >/dev/null; then sudo zypper install -y $pkgs
  else echo "Não reconheci o gerenciador de pacotes. Instale: $pkgs"; exit 1; fi
}

echo "Instalando o Financeiro em: $BASE"

passo "Conferindo o Python 3"
command -v python3 >/dev/null || instalar_pacotes python3
python3 -c 'import sys; assert sys.version_info >= (3, 9)' || { echo "É preciso Python 3.9 ou mais novo."; exit 1; }
if ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
  V=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
  if command -v apt-get >/dev/null; then instalar_pacotes "python$V-venv"; else instalar_pacotes python3-pip; fi
fi

passo "Fechando o Financeiro, se estiver aberto"
pkill -f "$BASE/app/server.py" 2>/dev/null || true

passo "Copiando o app"
mkdir -p "$BASE/dados" "$APPS"
chmod 700 "$BASE" "$BASE/dados"
rm -rf "$BASE/app"
cp -R "$RAIZ/app" "$BASE/app"
find "$BASE/app" -name '__pycache__' -prune -exec rm -rf {} +

passo "Preparando o Python do Financeiro (bibliotecas com versões fixas e conferidas)"
[ -x "$BASE/venv/bin/python3" ] || python3 -m venv "$BASE/venv"
"$BASE/venv/bin/python3" -m pip install -q --disable-pip-version-check --require-hashes --only-binary=:all: \
  -r "$BASE/app/requirements.txt"
"$BASE/venv/bin/python3" -I -c "import sys; sys.path.insert(0, '$BASE/app'); import leitor, categorias"

passo "Criando o atalho no menu de aplicativos"
cat > "$APPS/financeiro.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Financeiro
Comment=Painel das faturas do cartão (tudo fica neste computador)
Exec="$BASE/venv/bin/python3" -I "$BASE/app/abrir.py"
Icon=$BASE/app/icone/financeiro.png
Terminal=false
Categories=Office;Finance;
StartupNotify=true
DESK
chmod 644 "$APPS/financeiro.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

echo
echo "Pronto! Procure \"Financeiro\" no menu de aplicativos."
if ! command -v google-chrome >/dev/null && ! command -v chromium >/dev/null && ! command -v chromium-browser >/dev/null \
   && ! command -v microsoft-edge >/dev/null && ! command -v brave-browser >/dev/null; then
  echo "Dica: com Chrome, Chromium, Edge ou Brave instalado, ele abre numa janela própria."
  echo "Sem eles, abre no navegador padrão e desliga sozinho alguns minutos depois que a aba é fechada."
fi
echo "Suas faturas ficam só neste computador, em: $BASE/dados"
