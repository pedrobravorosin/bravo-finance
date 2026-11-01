#!/bin/bash
# Gera os pacotes de instalação em dist/:
#   Financeiro-Windows.zip  (traz Python oficial e bibliotecas: instala sem internet)
#   Financeiro-macOS.zip    (instala com as ferramentas da Apple)
#   Financeiro-Linux.tar.gz (instala com o Python do sistema)
# Requer: bash, curl, python3 com pip, zip, tar, sha256sum (ou shasum).
set -euo pipefail
cd "$(dirname "$0")/.."
RAIZ="$PWD"
DIST="$RAIZ/dist"
CACHE="${CACHE:-$RAIZ/.cache}"

# Python oficial para Windows (Python Software Foundation, pacote NuGet "python", x64).
# Hash conferido com o catálogo do NuGet (SHA512 u9pNz2iK...AeHMDw==).
PY_VER=3.12.10
PY_SHA256=0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
rm -rf "$DIST"; mkdir -p "$DIST" "$CACHE"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

copiar_app() {  # destino
  mkdir -p "$1"
  (cd "$RAIZ/app" && tar cf - --exclude='__pycache__' --exclude='*.pyc' .) | (cd "$1" && tar xf -)
}

# Trava de privacidade: nenhum dado de fatura vai nos pacotes.
checar() {
  if find "$1" \( -name '*.pdf' -o -path '*/dados/*' -o -name 'preferencias.json' -o -name 'categorias.json' -o -name 'regras.json' \) | grep -q .; then
    echo "ERRO: arquivo de dados pessoais dentro do pacote ($1)"; exit 1
  fi
}

echo "== Windows"
NUPKG="$CACHE/python.$PY_VER.nupkg"
[ -f "$NUPKG" ] || curl -fsSL -o "$NUPKG" "https://api.nuget.org/v3-flatcontainer/python/$PY_VER/python.$PY_VER.nupkg"
[ "$(sha "$NUPKG")" = "$PY_SHA256" ] || { echo "ERRO: hash do Python não confere"; exit 1; }
W="$T/win/Financeiro"; mkdir -p "$W/arquivos/wheels"
copiar_app "$W/arquivos/app"
cp "$NUPKG" "$W/arquivos/python-$PY_VER.zip"
python3 -m pip download -q --disable-pip-version-check --require-hashes --only-binary=:all: --no-deps \
  --platform win_amd64 --python-version 3.12 --implementation cp \
  -r "$RAIZ/app/requirements.txt" -d "$W/arquivos/wheels"
for f in instalar.ps1 desinstalar.ps1; do  # PowerShell 5.1 precisa de BOM UTF-8 para ler acentos
  printf '\xef\xbb\xbf' > "$W/arquivos/$f"; cat "$RAIZ/instaladores/windows/$f" >> "$W/arquivos/$f"
done
cp "$RAIZ/instaladores/windows/Instalar.bat" "$RAIZ/instaladores/windows/Desinstalar.bat" "$W/"
sed 's/$/\r/' "$RAIZ/instaladores/windows/LEIA-ME.txt" > "$W/LEIA-ME.txt"
cp "$RAIZ/LICENSE" "$W/LICENCA.txt"
checar "$W"
(cd "$T/win" && zip -qr -X "$DIST/Financeiro-Windows.zip" Financeiro)

echo "== macOS"
M="$T/mac/Financeiro"; mkdir -p "$M/instaladores"
copiar_app "$M/app"
cp -R "$RAIZ/instaladores/macos" "$M/instaladores/macos"
printf '#!/bin/bash\ncd "$(dirname "$0")"\nbash instaladores/macos/instalar.sh\necho\nread -r -p "Pressione Enter para fechar."\n' > "$M/Instalar.command"
printf '#!/bin/bash\ncd "$(dirname "$0")"\nbash instaladores/macos/desinstalar.sh\necho\nread -r -p "Pressione Enter para fechar."\n' > "$M/Desinstalar.command"
chmod +x "$M"/*.command "$M/instaladores/macos/"*.sh
cp "$RAIZ/instaladores/macos/LEIA-ME.txt" "$M/LEIA-ME.txt"; cp "$RAIZ/LICENSE" "$M/LICENCA.txt"
checar "$M"
(cd "$T/mac" && zip -qr -X -y "$DIST/Financeiro-macOS.zip" Financeiro)

echo "== Linux"
L="$T/linux/financeiro"; mkdir -p "$L/instaladores"
copiar_app "$L/app"
cp -R "$RAIZ/instaladores/linux" "$L/instaladores/linux"
chmod +x "$L/instaladores/linux/"*.sh
cp "$RAIZ/instaladores/linux/LEIA-ME.txt" "$L/LEIA-ME.txt"; cp "$RAIZ/LICENSE" "$L/LICENCA.txt"
checar "$L"
tar -C "$T/linux" -czf "$DIST/Financeiro-Linux.tar.gz" financeiro

(cd "$DIST" && for f in *; do echo "$(sha "$f")  $f"; done > SHA256SUMS.txt)
ls -la "$DIST"
