; PDF-Equilibrist — Script NSIS (licence zlib, usage commercial libre)
; =====================================================================
; Prérequis : NSIS 3.x
; Compiler :
;   makensis installer\PDF-Equilibrist.nsi
;   → installer\Output\PDF-Equilibrist-Setup.exe
;
; Images requises (BMP — NSIS n'accepte pas PNG) :
;   assets\installer\wizard_banner.bmp   164×314 px  (page Bienvenue/Fin)
;   assets\installer\wizard_header.bmp   150×57  px  (en-tête pages intérieures)

!include "MUI2.nsh"
!include "LogicLib.nsh"

; ── Définitions ───────────────────────────────────────────────────────────────
!define APP_NAME      "PDF-Equilibrist"
!define APP_VERSION   "1.0.0"
!define APP_PUBLISHER "PDF Equilibrist"
!define APP_EXE       "PDF-Equilibrist.exe"
!define PROG_ID       "PDFEquilibrist.Document"
!define SOURCE_DIR    "..\dist\PDF-Equilibrist"
!define REG_UNINST    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

; ── Paramètres généraux ───────────────────────────────────────────────────────
Name            "${APP_NAME} ${APP_VERSION}"
OutFile         "Output\PDF-Equilibrist-Setup.exe"
InstallDir      "$LOCALAPPDATA\Programs\${APP_NAME}"
InstallDirRegKey HKCU "${REG_UNINST}" "InstallLocation"
RequestExecutionLevel user   ; pas de UAC — installation per-user dans %LocalAppData%
Unicode         True
SetCompressor   /SOLID lzma

; ── MUI2 — Apparence ──────────────────────────────────────────────────────────
!define MUI_ICON    "..\assets\logo\PDF-Equilibrist-logo.ico"
!define MUI_UNICON  "..\assets\logo\PDF-Equilibrist-logo.ico"

; Bannière gauche pages Bienvenue / Fin : 164×314 px BMP
!define MUI_WELCOMEFINISHPAGE_BITMAP   "..\assets\installer\wizard_banner.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "..\assets\installer\wizard_banner.bmp"

; En-tête pages intérieures : 150×57 px BMP (différent d'Inno Setup !)
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP         "..\assets\installer\wizard_header.bmp"
!define MUI_HEADERIMAGE_RIGHT

!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "Bienvenue dans l'installation de ${APP_NAME}"
!define MUI_WELCOMEPAGE_TEXT  "Cet assistant va installer ${APP_NAME} ${APP_VERSION} \
sur votre ordinateur.$\r$\n$\r$\nAucun droit administrateur requis — installation \
personnelle dans votre profil utilisateur.$\r$\n$\r$\nCliquez sur Suivant pour continuer."

!define MUI_FINISHPAGE_RUN      "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Lancer ${APP_NAME}"

; ── Pages installeur ──────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; ── Pages désinstalleur ───────────────────────────────────────────────────────
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ── Langues ───────────────────────────────────────────────────────────────────
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "English"

; ── Section principale (obligatoire) ─────────────────────────────────────────
Section "PDF-Equilibrist" SecMain
    SectionIn RO

    SetOutPath "$INSTDIR"
    SetOverwrite on

    ; Copier tout le dossier onedir PyInstaller
    File /r "${SOURCE_DIR}\*.*"

    ; ── Raccourci Menu Démarrer ───────────────────────────────────────────────
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Désinstaller ${APP_NAME}.lnk" \
                   "$INSTDIR\Uninstall.exe"

    ; ── Association .pdf ──────────────────────────────────────────────────────
    ; Copier fichier.ico dans un emplacement stable (le registre ne peut pas
    ; pointer vers $INSTDIR si celui-ci change lors d'une mise à jour)
    CreateDirectory "$LOCALAPPDATA\PDFEquilibrist"
    CopyFiles /SILENT "$INSTDIR\assets\logo\fichier.ico" \
                      "$LOCALAPPDATA\PDFEquilibrist\fichier.ico"

    ; ProgID
    WriteRegStr HKCU "Software\Classes\${PROG_ID}" \
                     "" "PDF Equilibrist Document"
    WriteRegStr HKCU "Software\Classes\${PROG_ID}\DefaultIcon" \
                     "" "$LOCALAPPDATA\PDFEquilibrist\fichier.ico"
    WriteRegStr HKCU "Software\Classes\${PROG_ID}\shell\open\command" \
                     "" '"$INSTDIR\${APP_EXE}" "%1"'

    ; OpenWithProgids → "Ouvrir avec..."
    WriteRegStr HKCU "Software\Classes\.pdf\OpenWithProgids" "${PROG_ID}" ""
    ; Nettoyer les éventuels doublons (entrées directes exe d'anciennes versions)
    DeleteRegValue HKCU "Software\Classes\.pdf\OpenWithProgids" "${APP_EXE}"

    ; Registered Applications (panneau Programmes par défaut Windows)
    WriteRegStr HKCU "Software\${APP_NAME}\Capabilities" \
                     "ApplicationName"        "PDF Equilibrist"
    WriteRegStr HKCU "Software\${APP_NAME}\Capabilities" \
                     "ApplicationDescription" "Éditeur PDF léger — modifier, convertir, protéger"
    WriteRegStr HKCU "Software\${APP_NAME}\Capabilities\FileAssociations" \
                     ".pdf" "${PROG_ID}"
    WriteRegStr HKCU "Software\RegisteredApplications" \
                     "${APP_NAME}" "Software\${APP_NAME}\Capabilities"

    ; Nom affiché dans "Ouvrir avec..." à la place du nom de l'exe
    WriteRegStr HKCU "Software\Classes\Applications\${APP_EXE}" \
                     "FriendlyAppName" "PDF Equilibrist"
    WriteRegStr HKCU "Software\Classes\Applications\${APP_EXE}\DefaultIcon" \
                     "" "$LOCALAPPDATA\PDFEquilibrist\fichier.ico"
    WriteRegStr HKCU "Software\Classes\Applications\${APP_EXE}\shell\open\command" \
                     "" '"$INSTDIR\${APP_EXE}" "%1"'

    ; ── Désinstalleur ─────────────────────────────────────────────────────────
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    WriteRegStr   HKCU "${REG_UNINST}" "DisplayName"          "${APP_NAME}"
    WriteRegStr   HKCU "${REG_UNINST}" "DisplayVersion"       "${APP_VERSION}"
    WriteRegStr   HKCU "${REG_UNINST}" "Publisher"            "${APP_PUBLISHER}"
    WriteRegStr   HKCU "${REG_UNINST}" "DisplayIcon"          "$INSTDIR\${APP_EXE}"
    WriteRegStr   HKCU "${REG_UNINST}" "InstallLocation"      "$INSTDIR"
    WriteRegStr   HKCU "${REG_UNINST}" "UninstallString"      '"$INSTDIR\Uninstall.exe"'
    WriteRegStr   HKCU "${REG_UNINST}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKCU "${REG_UNINST}" "NoModify"             1
    WriteRegDWORD HKCU "${REG_UNINST}" "NoRepair"             1

    ; Notifier l'explorateur des changements d'association
    System::Call 'Shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'

SectionEnd

; ── Section optionnelle — raccourci Bureau ────────────────────────────────────
Section /o "Raccourci sur le Bureau" SecDesktop
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}"
SectionEnd

; ── Désinstalleur ─────────────────────────────────────────────────────────────
Section "Uninstall"

    ; Supprimer les fichiers installés
    RMDir /r "$INSTDIR"

    ; Supprimer les raccourcis
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Désinstaller ${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; Supprimer les clés registre
    DeleteRegKey   HKCU "Software\Classes\${PROG_ID}"
    DeleteRegKey   HKCU "Software\Classes\Applications\${APP_EXE}"
    DeleteRegValue HKCU "Software\Classes\.pdf\OpenWithProgids" "${PROG_ID}"
    DeleteRegKey   HKCU "Software\${APP_NAME}"
    DeleteRegValue HKCU "Software\RegisteredApplications" "${APP_NAME}"
    DeleteRegKey   HKCU "${REG_UNINST}"

    ; Notifier l'explorateur
    System::Call 'Shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'

SectionEnd
