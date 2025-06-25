@echo off
echo =====================================
echo TWCC Captioner - Build Executable
echo =====================================
echo.

echo Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo.
echo Starting build process...
python build_executable.py

echo.
echo Build process complete!
pause 