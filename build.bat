@echo off
setlocal

:: --- �v���W�F�N�g�̃p�X��ݒ�i�C�Ӂj ---
set PROJECT_NAME=LTCOSCReader
set ENTRY_SCRIPT=ltc_reader.py

:: --- PyInstaller�̃I�v�V�������܂Ƃ߂� ---
set OPTIONS=--name %PROJECT_NAME% ^
 --onefile ^
 --windowed ^
 --add-data "libs\libltc.dll;libs" ^
 --add-data "config.json;."

:: --- ���z����L�����i�K�v�Ȃ�j ---
:: call venv\Scripts\activate.bat

:: --- �Â��r���h���폜 ---
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec

:: --- PyInstaller�Ńr���h ---
pyinstaller %OPTIONS% %ENTRY_SCRIPT%

:: --- �r���h�������b�Z�[�W ---
echo.
echo =====================================
echo Build complete! Check /dist folder.
echo =====================================

pause
endlocal
