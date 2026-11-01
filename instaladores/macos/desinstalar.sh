#!/bin/bash
# Remove o Financeiro do macOS. Pergunta antes de apagar as faturas.
# Uso: bash instaladores/macos/desinstalar.sh [--pasta "Caminho/relativo/à/pasta/de/usuário"]
set -euo pipefail
PASTA_REL="Library/Application Support/Financeiro"
[ "${1:-}" = "--pasta" ] && PASTA_REL="${2#"$HOME"/}"
BASE="$HOME/$PASTA_REL"
osascript -e 'tell application "Financeiro" to quit' 2>/dev/null || true
rm -rf "$HOME/Applications/Financeiro.app" "$BASE/app" "$BASE/venv"
echo "App removido. Se o ícone continuar no Dock, arraste-o para fora."
read -r -p "Apagar também as faturas salvas em $BASE/dados? (s/N) " r
if [[ "$r" =~ ^[sS] ]]; then rm -rf "$BASE"; echo "Tudo apagado."; else echo "Suas faturas continuam em $BASE/dados"; fi
