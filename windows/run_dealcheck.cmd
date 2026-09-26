@echo off
rem Task Scheduler entry point for the deal checker (Windows counterpart of
rem launchd/com.frontier.dealcheck.plist). Registered by install_dealcheck_task.ps1.
cd /d "%~dp0.."
if not exist results mkdir results

rem Without UTF-8 mode, printing emoji to a redirected stdout raises
rem UnicodeEncodeError under the default cp1252 codepage.
set PYTHONUTF8=1

set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
echo ===== %DATE% %TIME% =====>> results\dealcheck.log
echo ===== %DATE% %TIME% =====>> results\dealcheck.err.log
"%PY%" gowild_deal_report.py >> results\dealcheck.log 2>> results\dealcheck.err.log
