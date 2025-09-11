@echo off
setlocal

:: --- プロジェクトのパスを設定（任意） ---
set PROJECT_NAME=LTCOSCReader
set ENTRY_SCRIPT=ltc_reader.py

:: --- PyInstallerのオプションをまとめる ---
set OPTIONS=--name %PROJECT_NAME% ^
 --onefile ^
 --windowed ^
 --add-data "libs\libltc.dll;libs" ^
 --add-data "config.json;."

:: --- 仮想環境を有効化（必要なら） ---
:: call venv\Scripts\activate.bat

:: --- 古いビルドを削除 ---
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec

:: --- PyInstallerでビルド ---
pyinstaller %OPTIONS% %ENTRY_SCRIPT%

:: --- ビルド完了メッセージ ---
echo.
echo =====================================
echo Build complete! Check /dist folder.
echo =====================================

pause
endlocal
