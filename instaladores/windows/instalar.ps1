# Instalador do Financeiro para Windows 10 e 11. Não precisa ser administrador nem de internet:
# o Python oficial (python.org, pacote NuGet) e as bibliotecas já vêm dentro do pacote.
# Instala em %LOCALAPPDATA%\Financeiro. Rodar de novo atualiza o app e mantém as faturas.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Origem = $PSScriptRoot
$Raiz   = Join-Path $env:LOCALAPPDATA 'Financeiro'
$PyDir  = Join-Path $Raiz 'python'
$AppDir = Join-Path $Raiz 'app'
$Dados  = Join-Path $Raiz 'dados'
$PyZip  = Get-ChildItem $Origem -Filter 'python-*.zip' | Select-Object -First 1
$PyVer  = if ($PyZip) { $PyZip.BaseName -replace '^python-', '' } else { '' }

function Passo($t) { Write-Host ''; Write-Host "==> $t" -ForegroundColor Cyan }

Write-Host 'Instalando o Financeiro (painel das faturas do cartão)...' -ForegroundColor Green
if (-not $PyZip) { throw 'Pacote incompleto: falta o Python. Baixe o Financeiro-Windows.zip de novo.' }
New-Item -ItemType Directory -Force -Path $Raiz, $Dados | Out-Null

Passo 'Fechando o Financeiro, se estiver aberto'
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($Raiz, [StringComparison]::OrdinalIgnoreCase) } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500

$versaoInstalada = Join-Path $PyDir 'versao.txt'
if (-not (Test-Path $versaoInstalada) -or (Get-Content $versaoInstalada) -ne $PyVer) {
  Passo "Instalando o Python $PyVer (cópia própria do Financeiro, não mexe em outro Python)"
  if (Test-Path $PyDir) { Remove-Item $PyDir -Recurse -Force }
  $tmp = Join-Path $env:TEMP ('financeiro-py-' + [guid]::NewGuid())
  Expand-Archive $PyZip.FullName -DestinationPath $tmp -Force
  Move-Item (Join-Path $tmp 'tools') $PyDir
  Remove-Item $tmp -Recurse -Force
  Set-Content $versaoInstalada $PyVer
}
$py = Join-Path $PyDir 'python.exe'

Passo 'Instalando as bibliotecas de leitura de PDF (sem internet, versões fixas e conferidas)'
& $py -m pip install -q --disable-pip-version-check --no-warn-script-location --no-index `
  --find-links (Join-Path $Origem 'wheels') --require-hashes --only-binary=:all: `
  -r (Join-Path $Origem 'app\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as bibliotecas.' }

Passo 'Copiando o app'
if (Test-Path $AppDir) { Remove-Item $AppDir -Recurse -Force }
Copy-Item (Join-Path $Origem 'app') $AppDir -Recurse
Get-ChildItem $Raiz -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
& $py -I -c "import sys; sys.path.insert(0, r'$AppDir'); import leitor, categorias" 2>$null
if ($LASTEXITCODE -ne 0) { throw 'O app não abriu no teste rápido. Rode o instalador de novo.' }

Passo 'Criando os atalhos "Financeiro" no Menu Iniciar e na Área de Trabalho'
$sh = New-Object -ComObject WScript.Shell
foreach ($pasta in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
  $l = $sh.CreateShortcut((Join-Path $pasta 'Financeiro.lnk'))
  $l.TargetPath = Join-Path $PyDir 'pythonw.exe'
  $l.Arguments = '-I "' + (Join-Path $AppDir 'abrir.py') + '"'
  $l.WorkingDirectory = $AppDir
  $l.IconLocation = (Join-Path $AppDir 'icone\financeiro.ico') + ',0'
  $l.Description = 'Painel das faturas do cartão. Tudo fica neste computador.'
  $l.Save()
}

Write-Host ''
Write-Host 'Pronto! Abra pelo atalho "Financeiro" na Área de Trabalho ou no Menu Iniciar.' -ForegroundColor Green
Write-Host "Suas faturas ficam só neste computador, em $Dados"
