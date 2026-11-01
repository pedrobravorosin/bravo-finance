#!/bin/sh
# Instala o Bravo Finance só para o seu usuário, sem root e sem internet.
# Uso: sh instalar.sh   (rode de dentro da pasta extraída)
set -eu
ORIGEM="$(cd "$(dirname "$0")" && pwd)"
DESTINO="${XDG_DATA_HOME:-$HOME/.local/share}/bravo-finance-app"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONES="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
BIN="$HOME/.local/bin"

[ "$(uname -m)" = "x86_64" ] || { echo "Este pacote é para Linux 64 bits (x86_64)."; exit 1; }
echo "Instalando o Bravo Finance em $DESTINO ..."
rm -rf "$DESTINO"
mkdir -p "$DESTINO" "$APPS" "$ICONES" "$BIN"
cp -R "$ORIGEM/python" "$ORIGEM/app" "$DESTINO/"
cp "$ORIGEM/LICENCA.txt" "$DESTINO/" 2>/dev/null || true
cp "$ORIGEM/desinstalar.sh" "$DESTINO/"
chmod -R go-w "$DESTINO"
cat > "$BIN/bravo-finance" <<FIM
#!/bin/sh
exec "$DESTINO/python/bin/python3" -I -s "$DESTINO/app/abrir.py" "\$@"
FIM
chmod 755 "$BIN/bravo-finance"
cp "$DESTINO/app/icone/bravo-finance-256.png" "$ICONES/bravo-finance.png"
sed "s|^Exec=.*|Exec=$BIN/bravo-finance|" "$ORIGEM/bravo-finance.desktop" > "$APPS/bravo-finance.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
echo "Pronto. Abra o Bravo Finance pelo menu de aplicativos."
echo "Para remover: sh \"$DESTINO/desinstalar.sh\""
