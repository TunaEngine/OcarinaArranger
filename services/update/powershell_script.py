"""Helpers for generating the PowerShell installer script."""

from __future__ import annotations

import logging
import tempfile
import textwrap
from pathlib import Path


__all__ = ["write_portable_update_script"]


_LOGGER = logging.getLogger(__name__)


_PORTABLE_UPDATE_SCRIPT = textwrap.dedent(
    """
    param(
        [int]$ProcessId,
        [string]$StagePath,
        [string]$InstallPath,
        [string]$ExecutablePath,
        [string]$LogPath = '',
        [string]$FailureMarkerPath = ''
    )

    $ErrorActionPreference = 'Stop'

    function Write-Log {
        param([string]$Message)

        $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        $line = "$timestamp $Message"

        if ($LogPath -ne '') {
            try {
                $logDirectory = Split-Path -Path $LogPath -Parent
                if ($logDirectory -and -not (Test-Path -LiteralPath $logDirectory)) {
                    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
                }
                Add-Content -LiteralPath $LogPath -Value $line
            }
            catch {
                # Swallow logging errors so installation can proceed.
            }
        }

        Write-Output $line
    }

    function Clear-FailureMarker {
        if ($FailureMarkerPath -eq '') {
            return
        }

        try {
            if (Test-Path -LiteralPath $FailureMarkerPath) {
                Remove-Item -LiteralPath $FailureMarkerPath -Force
            }
        }
        catch {
            Write-Log ("Failed to remove failure marker: " + $_.Exception.Message)
        }
    }

    function Write-FailureMarker {
        param([string]$Reason, [string]$Advice)

        if ($FailureMarkerPath -eq '') {
            return
        }

        try {
            $directory = Split-Path -Path $FailureMarkerPath -Parent
            if ($directory -and -not (Test-Path -LiteralPath $directory)) {
                New-Item -ItemType Directory -Path $directory -Force | Out-Null
            }

            $payload = @{
                reason = $Reason
                advice = $Advice
                recorded_at = (Get-Date -Format 'o')
            } | ConvertTo-Json -Compress

            $encoding = New-Object System.Text.UTF8Encoding($false)
            [System.IO.File]::WriteAllText($FailureMarkerPath, $payload, $encoding)
        }
        catch {
            Write-Log ("Failed to record failure marker: " + $_.Exception.Message)
        }
    }

    function Move-ItemWithRetry {
        param(
            [string]$SourcePath,
            [string]$DestinationPath,
            [string]$Description
        )

        $maxAttempts = 8
        $delay = 250

        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            try {
                Move-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force -ErrorAction Stop
                return
            }
            catch {
                if ($attempt -eq $maxAttempts) {
                    throw
                }

                $wait = [Math]::Min($delay, 4000)
                Write-Log ($Description + " attempt $attempt failed: " + $_.Exception.Message + ". Retrying in " + $wait + " ms.")
                Start-Sleep -Milliseconds $wait
                $delay = $delay * 2
            }
        }
    }

    function Clear-ItemAttributes {
        param([string]$TargetPath)

        try {
            if ($TargetPath -eq '') {
                return
            }

            Write-Log ("Clearing restrictive attributes from " + $TargetPath + ".")
            & attrib.exe '-R' '-S' '-H' $TargetPath '/S' '/D' | Out-Null
        }
        catch {
            Write-Log ("Failed to adjust attributes on " + $TargetPath + ": " + $_.Exception.Message)
        }
    }

    Write-Log "Waiting for process $ProcessId to exit before installing update."
    while (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Start-Sleep -Milliseconds 500
    }
    Write-Log "Process $ProcessId has exited."

    Clear-FailureMarker

    $installParent = Split-Path -Path $InstallPath -Parent
    $installName = Split-Path -Path $InstallPath -Leaf
    $backupPath = Join-Path -Path $installParent -ChildPath ($installName + '.backup')

    if (Test-Path -LiteralPath $backupPath) {
        Write-Log "Removing previous backup at $backupPath."
        Remove-Item -LiteralPath $backupPath -Recurse -Force
    }

    try {
        if (Test-Path -LiteralPath $InstallPath) {
            Write-Log "Moving existing installation from $InstallPath to backup at $backupPath."
            Move-ItemWithRetry -SourcePath $InstallPath -DestinationPath $backupPath -Description "Moving existing installation"
        }

        Clear-ItemAttributes -TargetPath $StagePath
        Write-Log "Moving staged update from $StagePath to $InstallPath."
        Move-ItemWithRetry -SourcePath $StagePath -DestinationPath $InstallPath -Description "Moving staged update"

        if (Test-Path -LiteralPath $backupPath) {
            Write-Log "Removing backup at $backupPath after successful install."
            Remove-Item -LiteralPath $backupPath -Recurse -Force
        }
    }
    catch {
        $failure = $_
        $rawMessage = $failure.Exception.Message
        Write-Log ("Installer script failed: " + $rawMessage)
        if (Test-Path -LiteralPath $backupPath) {
            try {
                Write-Log "Attempting to restore backup from $backupPath to $InstallPath."
                if (Test-Path -LiteralPath $InstallPath) {
                    Remove-Item -LiteralPath $InstallPath -Recurse -Force
                }

                Move-Item -LiteralPath $backupPath -Destination $InstallPath -Force
            }
            catch {
                $restoreError = $_
                Write-Log ("Failed to restore backup: " + $restoreError.Exception.Message)
            }
        }

        if (Test-Path -LiteralPath $StagePath) {
            try {
                Write-Log "Removing staged update at $StagePath after failure."
                Remove-Item -LiteralPath $StagePath -Recurse -Force
            }
            catch {
                $stageError = $_
                Write-Log ("Failed to remove staged update: " + $stageError.Exception.Message)
            }
        }

        $advice = 'Please try again after restarting Ocarina Arranger.'
        if ($rawMessage -match 'in use' -or $rawMessage -match 'used by another process') {
            $advice = 'Close any other programs that might be using the installation folder (for example File Explorer or Command Prompt) and try again.'
        }
        elseif ($rawMessage -match 'access is denied') {
            $advice = 'Ensure you have permission to modify the installation folder and try again.'
        }

        Write-FailureMarker $rawMessage $advice

        $exeDir = Split-Path -Path $ExecutablePath
        Write-Log "Relaunching previous application version at $ExecutablePath due to failure."
        try {
            Start-Process -FilePath $ExecutablePath -WorkingDirectory $exeDir
        }
        catch {
            $launchError = $_
            Write-Log ("Failed to relaunch application: " + $launchError.Exception.Message)
        }
        exit 1
    }

    Clear-FailureMarker

    $exeDir = Split-Path -Path $ExecutablePath
    Write-Log "Launching updated application at $ExecutablePath."
    Start-Process -FilePath $ExecutablePath -WorkingDirectory $exeDir
    Write-Log "Installer script completed successfully."
    """
).strip()



def write_portable_update_script() -> Path:
    """Write the PowerShell installer script to a temporary directory."""

    script_dir = Path(tempfile.mkdtemp(prefix="ocarina-update-script-"))
    script_path = script_dir / "install.ps1"
    script_path.write_text(_PORTABLE_UPDATE_SCRIPT, encoding="utf-8")
    _LOGGER.debug("Wrote portable update script to %s", script_path)
    return script_path
