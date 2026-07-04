# Empaquetado Windows (Fase 8, F8-2, RF-28): binario onefile, sin consola.
#
# Requiere ejecutarse en Windows, con el proyecto instalado (uv pip install -e ".[packaging]")
# — PyInstaller no hace *cross-compiling*: el `.exe` solo puede construirse en Windows.
#
# Firma de código: fuera de alcance de v1 (PRD §8) porque requiere un certificado de pago.
# Si se dispone de uno, firmar el .exe resultante con `signtool sign /fd SHA256 /a
# dist\vigia-eew.exe` antes de distribuirlo.

$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Raiz "dist"

Write-Host "== Vigía-eew — empaquetado Windows =="
Write-Host "-- binario onefile (PyInstaller) --"

pyinstaller --noconfirm --clean `
    --distpath $Dist `
    --workpath (Join-Path $Raiz "build") `
    (Join-Path $Raiz "packaging\vigia-eew.spec")

$Exe = Join-Path $Dist "vigia-eew.exe"
if (-not (Test-Path $Exe)) {
    throw "No se generó $Exe"
}

Write-Host "== Listo: $Exe =="
