# Remove o Financeiro. Pergunta antes de apagar as faturas.
$Raiz = Join-Path $env:LOCALAPPDATA 'Financeiro'
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($Raiz, [StringComparison]::OrdinalIgnoreCase) } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
foreach ($d in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) {
  Remove-Item (Join-Path $d 'Financeiro.lnk') -ErrorAction SilentlyContinue
}
foreach ($p in 'app', 'python', 'janela') { Remove-Item (Join-Path $Raiz $p) -Recurse -Force -ErrorAction SilentlyContinue }
$r = Read-Host 'Apagar também as faturas salvas neste computador? (s/N)'
if ($r -match '^[sS]') { Remove-Item $Raiz -Recurse -Force -ErrorAction SilentlyContinue; Write-Host 'Tudo apagado.' }
else { Write-Host "App removido. Suas faturas continuam em $Raiz\dados" }
