#define MyAppName "ThisTinti Local"
#ifndef MyAppVersion
  #define MyAppVersion "3.4.0-alpha.7-rc.15"
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
VersionInfoVersion=3.4.0.19
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
Source: "stop_running_thistinti.ps1"; Flags: dontcopy

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

function StopRunningInstalledThisTinti(): Boolean;
var
  ResultCode: Integer;
  PowerShellPath: String;
  ScriptPath: String;
  Parameters: String;
begin
  Result := True;
  if not FileExists(ExpandConstant('{app}\{#MyAppExeName}')) then
    Exit;

  ExtractTemporaryFile('stop_running_thistinti.ps1');
  ScriptPath := ExpandConstant('{tmp}\stop_running_thistinti.ps1');
  PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Parameters :=
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + ScriptPath +
    '" -InstallDir "' + ExpandConstant('{app}') + '"';

  if not Exec(PowerShellPath, Parameters, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := False;
    Exit;
  end;
  Result := ResultCode = 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not StopRunningInstalledThisTinti() then
    Result :=
      'ThisTinti e ancora in esecuzione e non puo essere aggiornato in sicurezza. ' +
      'Chiudi ThisTinti e riprova.';
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
    wpLicense,
    'Approvazione specifica delle clausole',
    'Conferma separata richiesta prima dell’installazione'
  );
  SpecificApprovalCheck := TNewCheckBox.Create(SpecificApprovalPage);
  SpecificApprovalCheck.Parent := SpecificApprovalPage.Surface;
  SpecificApprovalCheck.Left := 0;
  SpecificApprovalCheck.Top := 8;
  SpecificApprovalCheck.Width := SpecificApprovalPage.SurfaceWidth;
  SpecificApprovalCheck.Height := 100;
  SpecificApprovalCheck.Caption :=
    'Ai sensi degli artt. 1341 e 1342 c.c., ove applicabili, approvo specificamente le clausole 3, 4, 5, 7, 8, 9, 10, 11 e 12: limiti d''uso, verifica umana, responsabilità dell''utilizzatore, sicurezza e backup, assenza di garanzie, limitazione di responsabilità, modifiche di terzi, assenza di supporto e componenti di terze parti.';
  if WizardSilent and SilentTermsAccepted() then
    SpecificApprovalCheck.Checked := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = SpecificApprovalPage.ID then
  begin
    if WizardSilent and SilentTermsAccepted() then
      Exit;
    if not SpecificApprovalCheck.Checked then
    begin
      MsgBox('Per continuare devi approvare specificamente le clausole indicate.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox('ThisTinti è stato rimosso. I dati locali restano in %LOCALAPPDATA%\ThisTinti per evitare perdite involontarie. Eliminali manualmente soltanto dopo aver creato e verificato un backup.', mbInformation, MB_OK);
end;
