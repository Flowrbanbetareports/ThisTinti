#define MyAppName "ThisTinti Local"
#ifndef MyAppVersion
  #define MyAppVersion "3.4.0-alpha.6-rc.1"
#endif
#define MyAppPublisher "Lorenzo Tinti"
#define MyAppExeName "ThisTinti.exe"

[Setup]
AppId={{92BFB96E-9D61-4E9D-A9AB-7D75A11F70E7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ThisTinti
DefaultGroupName=ThisTinti
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\release\windows
OutputBaseFilename=ThisTinti-Setup-{#MyAppVersion}-x64
SetupIconFile=..\assets\thistinti.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\..\legal\INSTALLER_TERMS.txt
InfoBeforeFile=..\..\DISCLAIMER.md
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern dynamic
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no
VersionInfoVersion=3.4.0.6
VersionInfoProductName={#MyAppName}
VersionInfoDescription=Local document integrity and discrepancy review platform
VersionInfoCompany={#MyAppPublisher}
VersionInfoCopyright=Copyright 2026 Lorenzo Tinti

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; GroupDescription: "Collegamenti:"; Flags: unchecked

[Files]
Source: "..\..\dist\ThisTinti\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ThisTinti"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\ThisTinti"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia ThisTinti Local"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  SpecificApprovalPage: TWizardPage;
  SpecificApprovalCheck: TNewCheckBox;

function SilentTermsAccepted(): Boolean;
begin
  Result := CompareText(ExpandConstant('{param:ACCEPTTHISTINTITERMS|}'), 'yes') = 0;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if WizardSilent and (not SilentTermsAccepted()) then
  begin
    SuppressibleMsgBox(
      'L''installazione silenziosa richiede il parametro /ACCEPTTHISTINTITERMS=yes per confermare le condizioni d''uso e le clausole specifiche.',
      mbError,
      MB_OK,
      IDOK
    );
    Result := False;
  end;
end;

procedure InitializeWizard();
begin
  SpecificApprovalPage := CreateCustomPage(
    wpSelectDir,
    'Approvazione specifica',
    'Conferma delle clausole rilevanti'
  );
  SpecificApprovalCheck := TNewCheckBox.Create(SpecificApprovalPage);
  SpecificApprovalCheck.Parent := SpecificApprovalPage.Surface;
  SpecificApprovalCheck.Left := 0;
  SpecificApprovalCheck.Top := 12;
  SpecificApprovalCheck.Width := SpecificApprovalPage.SurfaceWidth;
  SpecificApprovalCheck.Height := 78;
  SpecificApprovalCheck.WordWrap := True;
  SpecificApprovalCheck.Caption :=
    'Approvo specificamente i limiti d''uso, la verifica umana obbligatoria, l''assenza di garanzie e supporto e le limitazioni di responsabilità nei limiti di legge.';
  SpecificApprovalCheck.Checked := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = SpecificApprovalPage.ID then
  begin
    if not SpecificApprovalCheck.Checked then
    begin
      MsgBox(
        'Per continuare devi approvare specificamente le clausole indicate.',
        mbError,
        MB_OK
      );
      Result := False;
    end;
  end;
end;
