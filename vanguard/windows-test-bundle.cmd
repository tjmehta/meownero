@echo off
setlocal
cd /d "%~dp0"
py -3 -B "%~dp0windows-test-bundle.py"
set "TEST_EXIT=%ERRORLEVEL%"
echo.
echo If Python could not start, see READ-ME.md for the native Python requirement.
pause
exit /b %TEST_EXIT%
