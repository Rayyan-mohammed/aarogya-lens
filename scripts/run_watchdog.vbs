' Runs the watchdog with no console window at all. A visible console popping up every
' 10 minutes could be closed or sent Ctrl+C mid-run, which killed runs halfway through
' restarting the tunnel. scripts\run_watchdog.bat stays for running it by hand.
CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""E:\aarogya-lens\scripts\watchdog.ps1""", 0, True
