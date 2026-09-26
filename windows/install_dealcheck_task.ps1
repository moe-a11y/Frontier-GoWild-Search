# Registers (or re-registers) the "Frontier Deal Check" scheduled task:
# Tue/Wed/Thu at 00:01 local, running windows\run_dealcheck.cmd.
# Re-run this after moving the project folder.
#
#   powershell -ExecutionPolicy Bypass -File windows\install_dealcheck_task.ps1

$ErrorActionPreference = "Stop"
$TaskName = "Frontier Deal Check"
$Runner = Join-Path $PSScriptRoot "run_dealcheck.cmd"
$ProjectDir = Split-Path $PSScriptRoot -Parent

$action = New-ScheduledTaskAction -Execute $Runner -WorkingDirectory $ProjectDir
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday, Wednesday, Thursday -At "00:01"

# StartWhenAvailable: run a missed 00:01 slot as soon as possible (like launchd).
# WakeToRun: wake the PC from sleep for the run.
# The run takes ~1h (4 flight date groups x 2 origins), so allow 3h.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

# Interactive logon: the weekly cruise scrape must open a visible Chrome window
# (VacationsToGo blocks headless), which needs the user's desktop session.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Frontier GoWild + Discount Den + cruise deal report (gowild_deal_report.py)" `
    -Force | Out-Null

Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo |
    Select-Object TaskName, NextRunTime, LastRunTime
