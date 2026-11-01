#!/bin/bash
# Remove o Financeiro do Linux. Pergunta antes de apagar as faturas.
set -euo pipefail
BASE="${XDG_DATA_HOME:-$HOME/.local/share}/financeiro"
pkill -f "$BASE/app/server.py" 2>/dev/null || true
rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/financeiro.desktop"
rm -rf "$BASE/app" "$BASE/venv" "$BASE/janela"
read -r -p "Apagar também as faturas salvas em $BASE/dados? (s/N) " r
if [[ "$r" =~ ^[sS] ]]; then rm -rf "$BASE"; echo "Tudo apagado."; else echo "Suas faturas continuam em $BASE/dados"; fi
