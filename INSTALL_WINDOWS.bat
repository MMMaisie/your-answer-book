@echo off
cd /d "%~dp0"
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto failed
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Installation finished. Run START_LOCAL.bat.
pause
exit /b 0
:failed
echo Installation failed. Install Python 3.11 or newer from python.org and try again.
pause
exit /b 1
