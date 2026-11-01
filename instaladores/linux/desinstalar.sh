#!/bin/sh
# Remove o Bravo Finance instalado pelo instalar.sh. Suas faturas ficam guardadas,
# a não ser que você responda "s" no fim.
set -eu
D="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$D/bravo-finance-app" "$D/applications/bravo-finance.desktop" "$D/icons/hicolor/256x256/apps/bravo-finance.png" \
  "$HOME/.local/bin/bravo-finance"
echo "Bravo Finance removido."
if [ -d "$D/bravo-finance" ]; then
  printf "Apagar também suas faturas e configurações (%s)? [s/N] " "$D/bravo-finance"
  read -r r || r=n
  [ "$r" = "s" ] || [ "$r" = "S" ] && rm -rf "$D/bravo-finance" && echo "Dados apagados." || echo "Dados mantidos."
fi
