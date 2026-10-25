; HSYNC Desktop — Windows installer (Inno Setup 6)
;
; Per-user install (no admin). The frozen GUI is self-contained (it embeds the
; hsync client engine), so nothing else is required.
;
; Built by .github/workflows/release.yml (windows-amd64 matrix entry), which
; compiles the .exe first and passes:
;   /DAppVersion=<semver>     /DSourceExe=<path to hsync-desktop.exe>
;   /DOutDir=<output dir>     /DIconPath=<path to icon.ico>   (optional)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
; Numeric file version (up to four dot-separated numbers). The workflow passes
; the SemVer stripped of its prerelease/build suffix.
#ifndef VersionInfoVersion
  #define VersionInfoVersion "0.0.0.0"
#endif
#ifndef SourceExe
  #define SourceExe "hsync-desktop.exe"
#endif
#ifndef OutDir
  #define OutDir "."
#endif

[Setup]
AppId={{7B2D4C55-9E3A-4C7B-8A12-3D4E5F607182}
AppName=HSYNC Desktop
AppVersion={#AppVersion}
AppVerName=HSYNC Desktop {#AppVersion}
VersionInfoVersion={#VersionInfoVersion}
AppPublisher=HSYNC
AppPublisherURL=https://github.com/albertsdk/hsync-desktop
DefaultDirName={localappdata}\Programs\HSYNC Desktop
DefaultGroupName=HSYNC
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutDir}
OutputBaseFilename=hsync-desktop-{#AppVersion}-windows-amd64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Qt 6.12 (PySide6) supports Windows 10 1809+ (build 17763) and Windows 11 only,
; and the frozen bundle is x64: refuse older systems and Arm64.
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
#ifdef IconPath
SetupIconFile={#IconPath}
#endif
UninstallDisplayName=HSYNC Desktop
UninstallDisplayIcon={app}\hsync-desktop.exe

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\HSYNC"; Filename: "{app}\hsync-desktop.exe"
Name: "{group}\Uninstall HSYNC"; Filename: "{uninstallexe}"
Name: "{userdesktop}\HSYNC"; Filename: "{app}\hsync-desktop.exe"; \
    Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\hsync-desktop.exe"; \
    Description: "Launch HSYNC Desktop"; Flags: postinstall nowait skipifsilent
