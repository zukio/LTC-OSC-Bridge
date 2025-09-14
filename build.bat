@echo off
setlocal

:: --- Virtual Environment Activation ---
echo Checking virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found at venv\Scripts\activate.bat
    echo Please create virtual environment first:
    echo   python -m venv venv
    echo   venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to activate virtual environment
    echo Please ensure venv directory exists and is properly set up
    pause
    exit /b 1
)

:: --- Project Settings ---
set PROJECT_NAME=LTCOSCReader
set ENTRY_SCRIPT=ltc_reader.py

:: --- PyInstaller Options ---
set OPTIONS=--name %PROJECT_NAME% ^
 --onefile ^
 --windowed ^
 --add-data "libs\libltc.dll;libs" ^
 --add-data "config.json;."

:: --- Clean Old Build Files ---
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec

:: --- Build with PyInstaller ---
echo Building with PyInstaller...
echo Python executable: 
where python
echo.
pyinstaller %OPTIONS% %ENTRY_SCRIPT%

:: --- Build Complete ---
echo.
echo =====================================
echo Build complete! Check /dist folder.
echo =====================================

pause
endlocal
