#!/bin/bash
# Instalador do Financeiro para macOS 11 ou mais novo.
# Usa só ferramentas da Apple: o Python 3 e o compilador Swift das Command Line Tools.
# Uso: bash instaladores/macos/instalar.sh [--pasta "Caminho/relativo/à/pasta/de/usuário"] [--sem-dock]
set -euo pipefail

PASTA_REL="Library/Application Support/Financeiro"
DOCK=1
while [ $# -gt 0 ]; do
  case "$1" in
    --pasta) PASTA_REL="${2#"$HOME"/}"; shift 2 ;;
    --sem-dock) DOCK=0; shift ;;
    *) echo "Opção desconhecida: $1"; exit 2 ;;
  esac
done
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
BASE="$HOME/$PASTA_REL"
APPDEST="$HOME/Applications/Financeiro.app"
passo() { printf '\n==> %s\n' "$1"; }

echo "Instalando o Financeiro em: $BASE"

passo "Conferindo as ferramentas da Apple (Python 3 e Swift)"
if ! xcode-select -p >/dev/null 2>&1 || ! xcrun --find swiftc >/dev/null 2>&1; then
  echo "Faltam as Command Line Tools da Apple. Vai abrir uma janela pedindo para instalar."
  echo "Clique em Instalar, espere terminar e rode este instalador de novo."
  xcode-select --install 2>/dev/null || true
  exit 1
fi
PY=/usr/bin/python3
"$PY" -c 'import sys; assert sys.version_info >= (3, 9)' || { echo "É preciso Python 3.9 ou mais novo."; exit 1; }

passo "Fechando o Financeiro, se estiver aberto"
osascript -e 'tell application "Financeiro" to quit' 2>/dev/null || true
sleep 1

passo "Copiando o app"
mkdir -p "$BASE/dados" "$HOME/Applications"
chmod 700 "$BASE" "$BASE/dados"
rsync -a --delete --exclude '__pycache__' --exclude '.venv' "$RAIZ/app/" "$BASE/app/"

passo "Preparando o Python do Financeiro (bibliotecas com versões fixas e conferidas)"
[ -x "$BASE/venv/bin/python3" ] || "$PY" -m venv "$BASE/venv"
"$BASE/venv/bin/python3" -m pip install -q --disable-pip-version-check --require-hashes --only-binary=:all: \
  -r "$BASE/app/requirements.txt"
"$BASE/venv/bin/python3" -I -c "import sys; sys.path.insert(0, '$BASE/app'); import leitor, categorias"

passo "Montando o app nativo (Swift + WebKit)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
APPTMP="$TMP/Financeiro.app"
mkdir -p "$APPTMP/Contents/MacOS" "$APPTMP/Contents/Resources" "$TMP/AppIcon.iconset"
xcrun swiftc -O -o "$APPTMP/Contents/MacOS/Financeiro" "$AQUI/main.swift" -framework Cocoa -framework WebKit
cp "$AQUI/Info.plist" "$APPTMP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :FinanceiroPasta $PASTA_REL" "$APPTMP/Contents/Info.plist"
for t in 16 32 128 256 512; do
  sips -z $t $t "$RAIZ/app/icone/financeiro.png" --out "$TMP/AppIcon.iconset/icon_${t}x${t}.png" >/dev/null
  sips -z $((t*2)) $((t*2)) "$RAIZ/app/icone/financeiro.png" --out "$TMP/AppIcon.iconset/icon_${t}x${t}@2x.png" >/dev/null
done
iconutil -c icns "$TMP/AppIcon.iconset" -o "$APPTMP/Contents/Resources/AppIcon.icns"
codesign --force --sign - "$APPTMP"
rm -rf "$APPDEST"
mv "$APPTMP" "$APPDEST"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APPDEST" || true

if [ "$DOCK" = 1 ] && ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Applications/Financeiro.app"; then
  passo "Colocando o ícone no Dock"
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>file://$APPDEST/</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
  killall Dock || true
fi

echo
echo "Pronto! Abra o Financeiro pelo Dock, pelo Launchpad ou em ~/Applications."
echo "Suas faturas ficam só neste Mac, em: $BASE/dados"
