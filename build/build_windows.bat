@echo off
setlocal

REM =========================
REM BUILD WINDOWS CON JRE EMBEBIDA + PYINSTALLER
REM =========================

cd /d "%~dp0\.."

if exist dist rmdir /s /q dist
if exist build_artifacts rmdir /s /q build_artifacts
if exist runtime\jre rmdir /s /q runtime\jre

set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" set PYTHON_EXE=.venv\Scripts\python.exe

set JLINK_EXE=C:\Program Files\Java\jdk-20\bin\jlink.exe
if not exist "%JLINK_EXE%" (
  for /f "delims=" %%I in ('where jlink.exe 2^>nul') do (
    set JLINK_EXE=%%I
    goto :jlink_found
  )
)
:jlink_found

if not exist "%JLINK_EXE%" (
  echo ERROR: no se encontro jlink.exe.
  exit /b 1
)

mkdir runtime 2>nul
"%JLINK_EXE%" ^
  --add-modules java.base,java.sql,java.naming,java.management,java.security.jgss,java.security.sasl,java.transaction.xa,java.logging,java.xml,jdk.crypto.ec,jdk.unsupported,jdk.zipfs ^
  --output runtime\jre ^
  --strip-debug ^
  --no-header-files ^
  --no-man-pages ^
  --compress=2

if errorlevel 1 (
  echo ERROR al crear runtime embebido.
  exit /b 1
)

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
  --add-data "%CD%\jdbc;jdbc" ^
  --add-data "%CD%\runtime;runtime" ^
  app\main.py

if errorlevel 1 (
  echo ERROR en build.
  exit /b 1
)

echo BUILD OK.
endlocal
