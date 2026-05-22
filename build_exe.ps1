$ErrorActionPreference = "Stop"

python -B -m unittest discover -s hateneko\tests

Get-Process |
  Where-Object { $_.ProcessName -eq "HataNeko" } |
  Stop-Process -Force

pyinstaller --noconfirm --clean HataNeko.spec

$dataDir = Join-Path (Resolve-Path "dist\HataNeko").Path "HataNekoData"
if (Test-Path -LiteralPath $dataDir) {
  Remove-Item -LiteralPath $dataDir -Recurse -Force
}

$zipPath = Join-Path (Resolve-Path "dist").Path "HataNeko-windows.zip"
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath "dist\HataNeko" -DestinationPath $zipPath -Force

Write-Host "Built dist\HataNeko\HataNeko.exe"
Write-Host "Packed dist\HataNeko-windows.zip"
