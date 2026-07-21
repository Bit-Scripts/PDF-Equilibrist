# distribute.ps1
# Construit l'exe PyInstaller et prépare le dossier de distribution
# avec les PDFs de documentation inclus.
#
# Usage :
#   .\tools\distribute.ps1
#   .\tools\distribute.ps1 -SkipBuild   # si l'exe est déjà compilé
#   .\tools\distribute.ps1 -ZipOutput   # crée aussi un .zip

param(
    [switch]$SkipBuild,
    [switch]$ZipOutput
)

$Root    = Split-Path $PSScriptRoot -Parent
$Dist    = "$Root\dist"
$Package = "$Root\release"
$ExeName = "PDF-Equilibrist.exe"

Set-Location $Root

# ── 1. Préparer les assets ────────────────────────────────────────────────────
Write-Host "`nPrepare assets..." -ForegroundColor Cyan
python tools/prepare_build.py
if ($LASTEXITCODE -ne 0) { Write-Host "Erreur prepare_build.py" -ForegroundColor Red; exit 1 }

# ── 2. Generer la doc PDF ─────────────────────────────────────────────────────
Write-Host "`nGeneration documentation PDF..." -ForegroundColor Cyan
python tools/build_docs_pdf.py
if ($LASTEXITCODE -ne 0) { Write-Host "Erreur build_docs_pdf.py" -ForegroundColor Red; exit 1 }

# ── 3. Compiler l'exe ────────────────────────────────────────────────────────
if (-not $SkipBuild) {
    Write-Host "`nCompilation PyInstaller..." -ForegroundColor Cyan
    pyinstaller PDF-Equilibrist.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { Write-Host "Erreur PyInstaller" -ForegroundColor Red; exit 1 }
}

if (-not (Test-Path "$Dist\$ExeName")) {
    Write-Host "Exe introuvable : $Dist\$ExeName" -ForegroundColor Red
    exit 1
}

# ── 4. Dossier release/ ───────────────────────────────────────────────────────
Write-Host "`nPreparation du dossier release/..." -ForegroundColor Cyan

# Nettoyer et recréer
if (Test-Path $Package) { Remove-Item $Package -Recurse -Force }
New-Item -ItemType Directory $Package | Out-Null

# Copier l'exe
Copy-Item "$Dist\$ExeName" "$Package\$ExeName"

# Copier les PDFs de documentation
$DocsDir = "$Package\Documentation"
New-Item -ItemType Directory $DocsDir | Out-Null
Copy-Item "$Root\docs\pdf\*.pdf" $DocsDir

# ── 5. Résumé ────────────────────────────────────────────────────────────────
Write-Host "`nContenu du dossier release/ :" -ForegroundColor Green
Get-ChildItem $Package -Recurse | ForEach-Object {
    $rel = $_.FullName.Replace($Package, "").TrimStart("\")
    $size = if ($_.PSIsContainer) { "" } else { "  ($([math]::Round($_.Length/1024)) Ko)" }
    Write-Host "  $rel$size"
}

# ── 6. Zip optionnel ─────────────────────────────────────────────────────────
if ($ZipOutput) {
    $ZipPath = "$Root\PDF-Equilibrist.zip"
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    Compress-Archive -Path "$Package\*" -DestinationPath $ZipPath
    $zipSize = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
    Write-Host "`nZip cree : PDF-Equilibrist.zip  ($zipSize Mo)" -ForegroundColor Green
}

Write-Host "`nDistribution prete dans : $Package" -ForegroundColor Green
