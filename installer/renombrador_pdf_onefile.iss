#define MyAppName "Renombrador PDF Hospitalario"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Hospital de Especialidades Fuerzas Armadas No. 1"
#define MyAppExeName "HE1_Movable.exe"

[Setup]
AppId={{B950D7E2-4F7C-4781-8F2B-1C5F4674F002}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\HE1\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayName={#MyAppName}
OutputDir=.
OutputBaseFilename=HE1_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "HE1_Movable.exe"; DestDir: "{app}"; DestName: "RenombradorPDFHospitalario.exe"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\RenombradorPDFHospitalario.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\RenombradorPDFHospitalario.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\RenombradorPDFHospitalario.exe"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\RenombradorPDFHospitalario.exe"
Type: dirifempty; Name: "{app}"
