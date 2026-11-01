# Versões fixas e hashes conferidos de tudo que entra nos instaladores.
# Mude aqui para atualizar; os scripts de construção conferem cada hash.
VERSAO_APP=1.0.0

PY_VERSAO=3.13.17
# Windows: Python oficial da Python Software Foundation (pacote NuGet "python", x64).
# SHA512 do catálogo NuGet: DmZ5KLtPGVc8bNiPZRM7LgeyQ6XHFvM1tWqma7nsb4IyglbSLDop4joCdqxcam14YhH+q1JIkK0eVmKRlsaynA==
PY_WIN_URL="https://api.nuget.org/v3-flatcontainer/python/$PY_VERSAO/python.$PY_VERSAO.nupkg"
PY_WIN_SHA256=dce409744b088f94c6e37ba41f8100c384c27e029e843237364c602d30d475e5

# macOS e Linux: Python independente (python-build-standalone, o mesmo usado pelo uv),
# relocável e sem dependências do sistema.
PBS_DATA=20261021
PBS_BASE="https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_DATA"
PY_MAC_ARM64_SHA256=9c985cbf327425873469896ce748c7134b6deca8edb81e93c589ad2fc5aff445
PY_MAC_X86_64_SHA256=b7d7c2dd63545cabe996191b6f20f0b652c7de123d9ca451dda7e5f1ebbcbbbc
PY_LINUX_X86_64_SHA256=cbda6f7767884fc456860b11fd184391a9320cae00a86c0f49a1c7ac6e236f7a
pbs_arquivo() { echo "cpython-$PY_VERSAO+$PBS_DATA-$1-install_only.tar.gz"; }
