$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean `
    --distpath release/windows `
    --workpath build/windows `
    3DEnhancer.spec

Write-Host ""
Write-Host "Ejecutable creado en: release/windows/3D Enhancer.exe"
