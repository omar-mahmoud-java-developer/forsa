REM Run once in a Command Prompt. Replace @PROJECT_DIR@ and @PYTHON@.
schtasks /Create /SC DAILY /ST 09:00 /TN "JobRadarMorning" /TR "cmd /c cd /d @PROJECT_DIR@ && @PYTHON@ -m job_radar run" /F
schtasks /Create /SC DAILY /ST 17:00 /TN "JobRadarEvening" /TR "cmd /c cd /d @PROJECT_DIR@ && @PYTHON@ -m job_radar run" /F
