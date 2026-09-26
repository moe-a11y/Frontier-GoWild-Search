"""Task Scheduler entry point for the deal checker (Windows counterpart of
launchd/com.frontier.dealcheck.plist). Registered by install_dealcheck_task.ps1.

Runs under pythonw.exe so there is no console window: closing a console (even
by accident) kills the ~1h run with 0xC000013A. Output is appended to the same
results/dealcheck*.log files the launchd job used.
"""

import os
import sys
import traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.makedirs("results", exist_ok=True)

# Line-buffered so the logs can be tailed while the job runs.
sys.stdout = open("results/dealcheck.log", "a", encoding="utf-8", buffering=1)
sys.stderr = open("results/dealcheck.err.log", "a", encoding="utf-8", buffering=1)
stamp = f"===== {datetime.now():%Y-%m-%d %H:%M:%S} ====="
print(stamp)
print(stamp, file=sys.stderr)

try:
    import gowild_deal_report

    gowild_deal_report.main()
except BaseException:
    tb = traceback.format_exc()
    print(tb, file=sys.stderr)
    # A crashed run sends no report, so send the error instead — otherwise a
    # broken job just looks like a quiet week.
    try:
        gowild_deal_report.send_email(
            "Frontier deal checker FAILED",
            f"The scheduled run crashed at {datetime.now():%Y-%m-%d %H:%M}.\n\n{tb}\n"
            "Full logs: results/dealcheck.log and results/dealcheck.err.log",
            gowild_deal_report.load_env(),
        )
    except Exception:
        traceback.print_exc()
    sys.exit(1)
