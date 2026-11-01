#!/bin/bash
# Gera, para Linux 64 bits (x86_64):
#   dist/BravoFinance-Linux-amd64.deb         (Ubuntu, Debian, Mint, Pop!_OS...)
#   dist/BravoFinance-Linux-x86_64.tar.gz    (qualquer distribuição, instala sem root)
# Roda em Linux com: bash, curl, tar, dpkg-deb, Python 3.13 com pip.
. "$(dirname "$0")/comum.sh"
command -v dpkg-deb >/dev/null || { echo "ERRO: precisa do dpkg-deb" >&2; exit 1; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
L="$RAIZ/instaladores/linux"

echo "== Python $PY_VERSAO (python-build-standalone, x86_64)"
TGZ="$CACHE/$(pbs_arquivo x86_64-unknown-linux-gnu)"
baixar "$PBS_BASE/$(pbs_arquivo x86_64-unknown-linux-gnu)" "$TGZ" "$PY_LINUX_X86_64_SHA256"
O="$T/origem"; mkdir -p "$O"
tar -xzf "$TGZ" -C "$O"
LIB="$O/python/lib/python3.13"
enxugar_python "$LIB"
rm -rf "$O/python/include" "$O/python/share" "$O/python/lib/pkgconfig" "$O/python/lib"/{libtcl,libtk,tcl,tk,itcl,thread}* \
  "$O/python/bin"/{pip*,idle*,pydoc*,2to3*,python3*-config}

# Tira símbolos de depuração das bibliotecas (~110 MB a menos). O executável fica como está:
# o strip quebra o binário do python-build-standalone.
strip --strip-debug "$O/python/lib/libpython3.13.so.1.0"
find "$LIB/lib-dynload" -name '*.so' -exec strip --strip-debug {} +
"$O/python/bin/python3" -c 'import ssl, ctypes, sqlite3, _decimal' || { echo "ERRO: Python quebrado" >&2; exit 1; }

echo "== Bibliotecas (manylinux x86_64, com hash conferido)"
instalar_libs "$LIB/site-packages" manylinux_2_28_x86_64 manylinux_2_17_x86_64 manylinux2014_x86_64

echo "== App"
copiar_app "$O/app"
rm -f "$O/app/icone/bravo-finance.icns" "$O/app/icone/bravo-finance.ico"
cp "$RAIZ/LICENSE" "$O/LICENCA.txt"
pre_compilar "$O/app" "$LIB"
checar_privacidade "$O"

echo "== Pacote .deb"
P="$T/deb"
mkdir -p "$P/DEBIAN" "$P/opt/bravo-finance" "$P/usr/bin" "$P/usr/share/applications" \
  "$P/usr/share/icons/hicolor/256x256/apps" "$P/usr/share/icons/hicolor/512x512/apps" "$P/usr/share/doc/bravo-finance"
cp -R "$O/python" "$O/app" "$P/opt/bravo-finance/"
install -m 755 "$L/bravo-finance" "$P/usr/bin/bravo-finance"
install -m 644 "$L/bravo-finance.desktop" "$P/usr/share/applications/"
install -m 644 "$O/app/icone/bravo-finance-256.png" "$P/usr/share/icons/hicolor/256x256/apps/bravo-finance.png"
"$PY_HOST" -c "from PIL import Image; Image.open('$O/app/icone/bravo-finance.png').resize((512,512), Image.LANCZOS).save('$P/usr/share/icons/hicolor/512x512/apps/bravo-finance.png')" 2>/dev/null \
  || rmdir "$P/usr/share/icons/hicolor/512x512/apps"
install -m 644 "$RAIZ/LICENSE" "$P/usr/share/doc/bravo-finance/copyright"
chmod -R u=rwX,go=rX "$P/opt" "$P/usr"
cat > "$P/DEBIAN/control" <<FIM
Package: bravo-finance
Version: $VERSAO_APP
Architecture: amd64
Maintainer: Bravo Finance <noreply@users.noreply.github.com>
Installed-Size: $(du -sk "$P/opt" "$P/usr" | awk '{s+=$1} END {print s}')
Section: misc
Priority: optional
Homepage: https://github.com/pedrobravorosin/bravo-finance
Description: Painel local de faturas de cartão de crédito
 Lê as faturas em PDF no seu computador e mostra gastos por categoria,
 parcelas futuras e assinaturas. Funciona sem internet e sem conta;
 nenhum dado sai do computador.
FIM
DEB="$DIST/BravoFinance-Linux-amd64.deb"
dpkg-deb --root-owner-group -Zxz --build "$P" "$DEB" >/dev/null

echo "== Pacote portátil .tar.gz"
Q="$T/tar/bravo-finance"; mkdir -p "$Q"
cp -R "$O/python" "$O/app" "$O/LICENCA.txt" "$Q/"
install -m 755 "$L/instalar.sh" "$L/desinstalar.sh" "$Q/"
install -m 644 "$L/bravo-finance.desktop" "$Q/"
printf 'Bravo Finance %s para Linux 64 bits\n\nPara instalar (sem root e sem internet), abra um terminal nesta pasta e rode:\n\n  sh instalar.sh\n\nDepois abra o Bravo Finance pelo menu de aplicativos.\n' "$VERSAO_APP" > "$Q/LEIA-ME.txt"
tar -C "$T/tar" -czf "$DIST/BravoFinance-Linux-x86_64.tar.gz" bravo-finance
ls -la "$DEB" "$DIST/BravoFinance-Linux-x86_64.tar.gz"
