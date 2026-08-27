from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installer_stops_only_the_installed_copy_before_upgrade() -> None:
    installer = (ROOT / "installer" / "windows" / "ThisTinti.iss").read_text(encoding="utf-8")
    helper = (ROOT / "installer" / "windows" / "stop_running_thistinti.ps1").read_text(encoding="utf-8")

    assert 'Source: "stop_running_thistinti.ps1"; Flags: dontcopy' in installer
    assert "function PrepareToInstall(var NeedsRestart: Boolean): String;" in installer
    assert "StopRunningInstalledThisTinti" in installer
    assert '-InstallDir "' in installer

    assert 'Get-Process -Name "ThisTinti"' in helper
    assert "GetFullPath($_.Path) -ieq $TargetExe" in helper
    assert "Stop-Process -Id $Process.Id -Force" in helper
    assert "taskkill" not in helper.lower()
    assert "/im" not in helper.lower()


def test_running_upgrade_workflow_reproduces_locked_executable_case() -> None:
    workflow = (ROOT / ".github" / "workflows" / "windows-running-upgrade.yml").read_text(encoding="utf-8")

    assert "Launch previous Windows alpha and keep it running" in workflow
    assert '"--no-browser"' in workflow
    assert "18765" in workflow
    assert "Verify the baseline instance is healthy" in workflow
    assert "Upgrade while previous ThisTinti is running" in workflow
    assert "Verify the old installed process was closed" in workflow
    assert "local_distribution_smoke.py" in workflow
