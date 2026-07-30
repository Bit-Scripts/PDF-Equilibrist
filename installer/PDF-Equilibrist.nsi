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
!ifndef APP_VERSION
  !define APP_VERSION "1.0.0"
!endif
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
SetCompressor   lzma

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

!define MUI_FINISHPAGE_RUN      "$INSTDIR\${APP_EXE}"

; ── Langues ───────────────────────────────────────────────────────────────────
; Déclarées ici (après APP_NAME/APP_VERSION, avant toute référence $(...)) :
; les constantes ${LANG_FRENCH}/${LANG_ENGLISH} utilisées par LangString
; n'existent qu'une fois ces macros insérées, et LangString a lui-même besoin
; de ${APP_NAME}/${APP_VERSION} déjà définis ci-dessus. Les chaînes MUI
; natives (Suivant/Annuler, titres de page standard…) sont déjà traduites
; automatiquement par NSIS ; seules les chaînes que CE script écrit
; lui-même ont besoin d'une traduction explicite via LangString.
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "English"

LangString MSG_APP_RUNNING ${LANG_FRENCH}  "${APP_NAME} est en cours d'exécution.$\r$\n$\r$\nVeuillez fermer l'application avant de continuer."
LangString MSG_APP_RUNNING ${LANG_ENGLISH} "${APP_NAME} is currently running.$\r$\n$\r$\nPlease close the application before continuing."

LangString WELCOME_TITLE ${LANG_FRENCH}  "Bienvenue dans l'installation de ${APP_NAME}"
LangString WELCOME_TITLE ${LANG_ENGLISH} "Welcome to the ${APP_NAME} Setup Wizard"

LangString WELCOME_TEXT ${LANG_FRENCH} "Cet assistant va installer ${APP_NAME} ${APP_VERSION} \
sur votre ordinateur.$\r$\n$\r$\nAucun droit administrateur requis — installation \
personnelle dans votre profil utilisateur.$\r$\n$\r$\nCliquez sur Suivant pour continuer."
LangString WELCOME_TEXT ${LANG_ENGLISH} "This wizard will install ${APP_NAME} ${APP_VERSION} \
on your computer.$\r$\n$\r$\nNo administrator rights required — this installs \
into your own user profile.$\r$\n$\r$\nClick Next to continue."

LangString FINISH_RUN_TEXT ${LANG_FRENCH}  "Lancer ${APP_NAME}"
LangString FINISH_RUN_TEXT ${LANG_ENGLISH} "Launch ${APP_NAME}"

LangString UNINSTALL_SHORTCUT ${LANG_FRENCH}  "Désinstaller ${APP_NAME}"
LangString UNINSTALL_SHORTCUT ${LANG_ENGLISH} "Uninstall ${APP_NAME}"

LangString APP_DESCRIPTION ${LANG_FRENCH}  "Éditeur PDF léger — modifier, convertir, protéger"
LangString APP_DESCRIPTION ${LANG_ENGLISH} "Lightweight PDF editor — edit, convert, protect"

LangString SEC_MAIN_NAME ${LANG_FRENCH}  "${APP_NAME}"
LangString SEC_MAIN_NAME ${LANG_ENGLISH} "${APP_NAME}"

LangString SEC_DESKTOP_NAME ${LANG_FRENCH}  "Raccourci sur le Bureau"
LangString SEC_DESKTOP_NAME ${LANG_ENGLISH} "Desktop shortcut"

; Doivent être définis après les LangString correspondantes ($(...) est résolu
; à l'exécution, mais MUI_PAGE_WELCOME/MUI_PAGE_FINISH lisent ces !define au
; moment de leur !insertmacro plus bas — l'ordre texte du script ne change
; rien ici puisque la valeur reste la chaîne littérale "$(WELCOME_TITLE)".
!define MUI_WELCOMEPAGE_TITLE   "$(WELCOME_TITLE)"
!define MUI_WELCOMEPAGE_TEXT    "$(WELCOME_TEXT)"
!define MUI_FINISHPAGE_RUN_TEXT "$(FINISH_RUN_TEXT)"

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

; Vérifie que l'application n'est pas en cours d'exécution avant d'installer
; ou de désinstaller (fichiers verrouillés sinon). Détection par titre de
; fenêtre (fiable : main_window.py fixe ce titre une fois pour toutes, il ne
; change jamais même quand un document est ouvert). Pas de fermeture forcée
; pour ne pas risquer de perdre un travail non sauvegardé.
!macro CHECK_APP_RUNNING
    check_app_running:
        FindWindow $0 "" "PDF Equilibrist"
        ${If} $0 <> 0
            MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION \
                "$(MSG_APP_RUNNING)" \
                IDRETRY check_app_running
            Abort
        ${EndIf}
!macroend

; ── Fonctions d'initialisation ────────────────────────────────────────────────
!insertmacro MUI_RESERVEFILE_LANGDLL

Function .onInit
    ; Sélecteur de langue FR/EN — sans cet appel, NSIS choisit silencieusement
    ; la première langue déclarée (French) quelle que soit la langue système,
    ; malgré les deux MUI_LANGUAGE déclarées plus haut. Présélectionne déjà
    ; la langue de l'OS de l'utilisateur.
    !insertmacro MUI_LANGDLL_DISPLAY
    !insertmacro CHECK_APP_RUNNING
FunctionEnd

Function un.onInit
    !insertmacro MUI_LANGDLL_DISPLAY
    !insertmacro CHECK_APP_RUNNING
FunctionEnd

; ── Section principale (obligatoire) ─────────────────────────────────────────
Section "$(SEC_MAIN_NAME)" SecMain
    SectionIn RO

    SetOutPath "$INSTDIR"
    SetOverwrite on

    ; Copier tout le dossier onedir PyInstaller
    File /r "${SOURCE_DIR}\*.*"

    ; ── Raccourci Menu Démarrer ───────────────────────────────────────────────
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\$(UNINSTALL_SHORTCUT).lnk" \
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
                     "ApplicationDescription" "$(APP_DESCRIPTION)"
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
Section /o "$(SEC_DESKTOP_NAME)" SecDesktop
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}"
SectionEnd

; ── Désinstalleur ─────────────────────────────────────────────────────────────
Section "Uninstall"

    ; Supprimer les fichiers installés
    RMDir /r "$INSTDIR"

    ; Supprimer les raccourcis — dossier entier plutôt que fichiers nommés
    ; individuellement : le nom du raccourci "Désinstaller"/"Uninstall" dépend
    ; de la langue choisie, qui peut différer entre l'install et la désinstall
    ; (le sélecteur de langue MUI_LANGDLL_DISPLAY est redemandé à chaque fois).
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
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
