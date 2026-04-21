@echo off
setlocal

REM =========================
REM BUILD RAPIDO CON PYINSTALLER
REM =========================

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name RenombradorPDFHospitalario ^
  --add-data "config;config" ^
  app\main.py

if errorlevel 1 (
  echo ERROR en build.
  exit /b 1
)

echo BUILD OK.
endlocal
