# register_filetype.ps1
# Enregistre PDF-Equilibrist comme application "Ouvrir avec..." pour les fichiers .pdf
# Nécessite d'être lancé en tant qu'Administrateur pour HKLM (tous les utilisateurs)
# ou sans droits élevés pour HKCU (utilisateur courant uniquement)
#
# Usage :
#   .\tools\register_filetype.ps1 -ExePath "C:\chemin\vers\PDF-Equilibrist.exe"
#   .\tools\register_filetype.ps1 -ExePath "C:\chemin\vers\PDF-Equilibrist.exe" -Unregister

param(
    [Parameter(Mandatory=$true)]
    [string]$ExePath,

    [switch]$Unregister
)

$AppName    = "PDF-Equilibrist"
$AppDesc    = "PDF Equilibrist — Éditeur PDF"
$ProgID     = "PDFEquilibrist.Document"

# Clé utilisateur (pas besoin de droits admin)
$RegBase    = "HKCU:\Software\Classes"

if ($Unregister) {
    Write-Host "Suppression de l'association..."
    Remove-Item -Path "$RegBase\$ProgID"          -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "$RegBase\.pdf\OpenWithProgids\$ProgID" -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts\$ProgID" -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Association supprimée."
    exit 0
}

if (-not (Test-Path $ExePath)) {
    Write-Error "Fichier introuvable : $ExePath"
    exit 1
}

Write-Host "Enregistrement de $AppName pour les fichiers .pdf..."

# ── ProgID : descripteur de l'application ─────────────────────────────────────
New-Item -Path "$RegBase\$ProgID"                           -Force | Out-Null
Set-ItemProperty -Path "$RegBase\$ProgID" -Name "(Default)" -Value $AppDesc

# Icône de l'application
New-Item -Path "$RegBase\$ProgID\DefaultIcon"               -Force | Out-Null
Set-ItemProperty -Path "$RegBase\$ProgID\DefaultIcon" -Name "(Default)" -Value "`"$ExePath`",0"

# Commande d'ouverture : passe le fichier en argument
New-Item -Path "$RegBase\$ProgID\shell\open\command"        -Force | Out-Null
Set-ItemProperty -Path "$RegBase\$ProgID\shell\open\command" -Name "(Default)" `
    -Value "`"$ExePath`" `"%1`""

# ── Association .pdf → OpenWithProgids ────────────────────────────────────────
# Ajoute PDF-Equilibrist dans la liste "Ouvrir avec..." sans en faire le défaut
New-Item -Path "$RegBase\.pdf\OpenWithProgids"              -Force | Out-Null
New-ItemProperty -Path "$RegBase\.pdf\OpenWithProgids" -Name $ProgID -Value "" `
    -PropertyType String -Force | Out-Null

# ── Forcer le rafraîchissement de l'explorateur ───────────────────────────────
$signature = @'
[DllImport("shell32.dll")]
public static extern void SHChangeNotify(int wEventId, int uFlags, IntPtr dwItem1, IntPtr dwItem2);
'@
$shell = Add-Type -MemberDefinition $signature -Name "Shell32" -Namespace "Win32" -PassThru
$shell::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Host ""
Write-Host "✓ PDF-Equilibrist est maintenant disponible dans 'Ouvrir avec...' pour les .pdf"
Write-Host "  Exe : $ExePath"
Write-Host ""
Write-Host "Pour définir PDF-Equilibrist comme application par défaut :"
Write-Host "  Paramètres Windows → Applications par défaut → .pdf"
