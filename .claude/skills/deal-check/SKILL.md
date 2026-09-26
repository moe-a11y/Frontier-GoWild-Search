---
name: deal-check
description: Check on, run, or troubleshoot the scheduled Frontier deal checker on this Windows PC (Task Scheduler task "Frontier Deal Check"). Use when asked whether the deal check/email is working, why a report didn't arrive, to run it now, or to reschedule/pause it.
---

# Operating the scheduled deal checker (Windows)

The job: Task Scheduler task **"Frontier Deal Check"** → `pythonw.exe -X utf8 windows\run_dealcheck.pyw`
→ `gowild_deal_report.main()`. Mon/Tue/Wed at 00:01 **Pacific** (03:01 on Eastern time).
Python: `%LOCALAPPDATA%\Programs\Python\Python312\`. Logs: `results/dealcheck.log`, `results/dealcheck.err.log`.
Reports: `results/deal_report_*.txt`. Email creds: `.env` (gitignored; Gmail App Password).

## 1. Status check (always start here)
```powershell
Get-ScheduledTask -TaskName "Frontier Deal Check" | Select-Object State
Get-ScheduledTaskInfo -TaskName "Frontier Deal Check" | Select-Object LastRunTime, LastTaskResult, NextRunTime
Get-Content results\dealcheck.log -Tail 30; Get-Content results\dealcheck.err.log -Tail 30
Get-ChildItem results\deal_report_*.txt | Sort-Object LastWriteTime | Select-Object -Last 3 Name, LastWriteTime
```
`LastTaskResult`: `0` ok · `267009` still running · `1` Python raised (traceback in err log; a
"Frontier deal checker FAILED" email is also sent) · `3221225786` (0xC000013A) killed by Ctrl+C/console close.

## 2. Common failures
| Symptom | Cause / fix |
|---|---|
| `PermissionError` opening `results/dealcheck.log` | An orphaned headless Chrome holds the log. Find the holder with the Windows Restart Manager (`RmGetList` via ctypes) or Resource Monitor → CPU → Associated Handles; confirm its command line has `--headless=new` and a temp `--user-data-dir`, then `taskkill /T /F /PID <pid>`. Never kill the user's normal Chrome. |
| Report says `[PARTIAL]` / "Captcha-blocked" | PerimeterX blocked routes even after backoff. One-off: ignore. Recurring: raise `BETWEEN_REQUESTS`, or try `DEAL_HEADLESS=0`; last resort, migrate `build_driver()` to SeleniumBase UC mode / nodriver. |
| Zero domestic GoWild fares every run | Dates must be Pacific (`ORIGIN_TZ`); check the log header's "CONUS (next day)" date is tomorrow in PT. |
| `ModuleNotFoundError` | `python -m pip install -r requirements.txt` with the Python312 interpreter. |
| No email but report saved | `.env` missing / `SMTP_PASSWORD` blank or revoked (err log shows `Email failed`). |
| Cruise section failed | VacationsToGo needs a visible window; the user must be logged in (locked is OK). |

## 3. Run it now
`Start-ScheduledTask -TaskName "Frontier Deal Check"` (full run ≈ 30–60 min; sends the real email).
Tail the log to follow it. For a quick check without emailing, fetch one route with
`gowild_deal_report.build_driver()` + `_fetch_route()` instead of a full run.

## 4. Change the schedule
Edit `windows/install_dealcheck_task.ps1` (days/time are in Pacific) and re-run it:
`powershell -ExecutionPolicy Bypass -File windows\install_dealcheck_task.ps1`. Don't re-register
while the task is Running. Pause/resume: `Disable-ScheduledTask` / `Enable-ScheduledTask`.
