import sys
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()

def test_schedule_mac_install(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch("easyatcal.cli.Path.home") as mock_home:
            mock_home.return_value = tmp_path
            
            result = runner.invoke(app, ["schedule", "--install", "--interval-hours", "6"])
            
            assert result.exit_code == 0
            assert "Successfully installed background sync via launchd" in result.output
            
            plist_path = tmp_path / "Library/LaunchAgents/com.easyatcal.sync.plist"
            assert plist_path.exists()
            assert "StartInterval" in plist_path.read_text()

def test_schedule_linux_install(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="* * * * * old_cron")
        
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("", "")
            mock_popen.return_value = mock_proc
            
            result = runner.invoke(app, ["schedule", "--install", "--interval-hours", "6"])
            
            assert result.exit_code == 0
            assert "Successfully installed background sync via crontab" in result.output

def test_schedule_windows_install(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        result = runner.invoke(app, ["schedule", "--install", "--interval-hours", "6"])
        
        assert result.exit_code == 0
        assert "Successfully created Windows scheduled task" in result.output
