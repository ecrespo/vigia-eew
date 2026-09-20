; Windows installer (Inno Setup) -- Start Menu entries, optional desktop icon
; and optional autostart (RF-28, T-150).
;
; The .exe alone is not an installed application: dropped anywhere it has no
; Start Menu entry, no uninstaller, and no way into the configuration except a
; command line. This script is the Windows half of the same gap the .desktop
; file closes on Linux.
;
; Built by `packaging/build_windows.ps1` when ISCC.exe is on the PATH:
;     ISCC /DAppVersion=1.0.0 packaging\vigia-eew.iss
; Code signing is out of scope for v1 (PRD §8): unsigned, SmartScreen warns on
; first run. Sign `dist\vigia-eew.exe` before building the installer, and the
; installer itself afterwards, when a certificate exists.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Vigía-eew"
#define AppExe "vigia-eew.exe"
#define AppPublisher "Ernesto Crespo"
#define AppUrl "https://github.com/ecrespo/vigia-eew"

[Setup]
AppId={{9F2C7E1A-5B34-4E1D-9C2A-4B7E6D0A1C55}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
DefaultDirName={autopf}\Vigia-eew
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=vigia-eew-{#AppVersion}-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install: no elevation prompt, and the scheduled task the agent
; installs for autostart is a per-user one too.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
en.SettingsShortcut=Settings
es.SettingsShortcut=Configuración
en.AutostartTask=Start {#AppName} when I sign in
es.AutostartTask=Iniciar {#AppName} al iniciar sesión
en.DesktopTask=Create a desktop shortcut
es.DesktopTask=Crear un acceso directo en el escritorio

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopTask}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "{cm:AutostartTask}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
; The second entry is the point: on any session where the tray menu is not
; reachable, this is the way into the configuration panel.
Name: "{group}\{#AppName} — {cm:SettingsShortcut}"; Filename: "{app}\{#AppExe}"; Parameters: "--settings"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Autostart is the agent's own business (`--install-autostart` registers the
; scheduled task); the installer only asks whether to call it.
Filename: "{app}\{#AppExe}"; Parameters: "--install-autostart"; Tasks: autostart; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Leaving a scheduled task behind that points at a deleted binary is the kind
; of debris that outlives the uninstall.
Filename: "{app}\{#AppExe}"; Parameters: "--uninstall-autostart"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveAutostart"
