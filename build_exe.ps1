$ErrorActionPreference = "Stop"

python -B -m unittest discover -s hateneko\tests
pyinstaller --noconfirm --clean HataNeko.spec

Write-Host "Built dist\HataNeko\HataNeko.exe"
