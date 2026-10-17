# Empaquetado Windows (Fase 8, F8-2, RF-28): binario onefile sin consola + instalador.
#
# Requiere ejecutarse en Windows, con el proyecto instalado (uv pip install -e ".[packaging]")
# — PyInstaller no hace *cross-compiling*: el `.exe` solo puede construirse en Windows.
#
# El instalador (Inno Setup, `packaging/vigia-eew.iss`) se construye si `ISCC.exe` está
# en el PATH; sin él se produce solo el `.exe`, que es lo que había antes de T-150.
# Instalar Inno Setup: `winget install JRSoftware.InnoSetup`.
#
# Firma de código: fuera de alcance de v1 (PRD §8) porque requiere un certificado de pago.
# Si se dispone de uno, firmar el .exe con `signtool sign /fd SHA256 /a dist\vigia-eew.exe`
# ANTES de construir el instalador, y el propio instalador después.

$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Raiz "dist"

Write-Host "== Vigía-eew — empaquetado Windows =="

# El mismo gate que CI corre antes de cualquier empaquetado (REQ-OPS-007): el
# icono del .exe es `packaging/icon.ico`, y uno inválido produce un binario con
# el icono genérico sin que nada lo reporte.
python (Join-Path $Raiz "scripts\check_packaging_assets.py") $Raiz

$Version = (python -c "import tomllib; print(tomllib.load(open(r'$Raiz\pyproject.toml','rb'))['project']['version'])").Trim()

Write-Host "-- 1/2: binario onefile (PyInstaller) --"

pyinstaller --noconfirm --clean `
    --distpath $Dist `
    --workpath (Join-Path $Raiz "build") `
    (Join-Path $Raiz "packaging\vigia-eew.spec")

$Exe = Join-Path $Dist "vigia-eew.exe"
if (-not (Test-Path $Exe)) {
    throw "No se generó $Exe"
}

Write-Host "-- 2/2: instalador (Inno Setup) --"
$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($null -eq $Iscc) {
    Write-Warning "   (omitido: ISCC.exe no está en el PATH — winget install JRSoftware.InnoSetup)"
    Write-Host "== Listo: $Exe (sin instalador) =="
    exit 0
}

& $Iscc.Source "/DAppVersion=$Version" (Join-Path $Raiz "packaging\vigia-eew.iss")
if ($LASTEXITCODE -ne 0) {
    throw "ISCC falló con código $LASTEXITCODE"
}

$Setup = Join-Path $Dist "vigia-eew-$Version-setup.exe"
if (-not (Test-Path $Setup)) {
    throw "No se generó $Setup"
}

Write-Host "== Listo: $Exe y $Setup =="
