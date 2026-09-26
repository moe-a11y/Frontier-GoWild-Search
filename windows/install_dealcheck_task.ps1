# Registers (or re-registers) the "Frontier Deal Check" scheduled task:
# Tue/Wed/Thu at 00:01 *Pacific*, running windows\run_dealcheck.pyw windowless.
# Re-run this after moving the project folder or changing the PC's time zone.
#
#   powershell -ExecutionPolicy Bypass -File windows\install_dealcheck_task.ps1

$ErrorActionPreference = "Stop"
$TaskName = "Frontier Deal Check"
$Pythonw = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\pythonw.exe"
$Runner = Join-Path $PSScriptRoot "run_dealcheck.pyw"
$ProjectDir = Split-Path $PSScriptRoot -Parent

# -X utf8: the report contains characters (e.g. the cruise rating star) that the
# default cp1252 codepage cannot write.
$action = New-ScheduledTaskAction -Execute $Pythonw -Argument "-X utf8 `"$Runner`"" `
    -WorkingDirectory $ProjectDir
# GoWild seats for SFO/SJC open at midnight Pacific, so fire at 00:01 PT expressed
# in this PC's zone (03:01 on Eastern time), shifting the weekdays if the local
# date differs from the Pacific one. Assumes a US zone (same DST switchover).
$pt = [TimeZoneInfo]::FindSystemTimeZoneById("Pacific Standard Time")
$ptRun = [TimeZoneInfo]::ConvertTime([DateTime]::Now, $pt).Date.AddMinutes(1)
$localRun = [TimeZoneInfo]::ConvertTime($ptRun, $pt, [TimeZoneInfo]::Local)
$shift = ($localRun.Date - $ptRun.Date).Days
$days = "Tuesday", "Wednesday", "Thursday" |
    ForEach-Object { [DayOfWeek]((([int][DayOfWeek]$_) + $shift + 7) % 7) }
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $localRun.ToString("HH:mm")

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
