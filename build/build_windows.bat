@echo off
setlocal

REM =========================
REM BUILD RAPIDO CON PYINSTALLER
REM =========================

cd /d "%~dp0\.."

if exist dist rmdir /s /q dist
if exist build_artifacts rmdir /s /q build_artifacts

set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" set PYTHON_EXE=.venv\Scripts\python.exe

%PYTHON_EXE% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --paths "." ^
  --name RenombradorPDFHospitalario ^
  --workpath build_artifacts ^
  --specpath build_artifacts ^
  --add-data "%CD%\config;config" ^
  --add-data "%CD%\datos_base;datos_base" ^
  app\main.py

if errorlevel 1 (
  echo ERROR en build.
  exit /b 1
)

echo BUILD OK.
endlocal
