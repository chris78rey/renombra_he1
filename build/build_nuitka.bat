@echo off
setlocal

REM =========================
REM BUILD MAS CERRADO CON NUITKA
REM =========================

cd /d "%~dp0\.."

python -m nuitka ^
  --standalone ^
  --windows-console-mode=disable ^
  --enable-plugin=pyqt6 ^
  --include-data-dir=config=config ^
  --include-data-dir=datos_base=datos_base ^
  --output-dir=dist_nuitka ^
  --assume-yes-for-downloads ^
  app\main.py

if errorlevel 1 (
  echo ERROR en build Nuitka.
  exit /b 1
)

echo BUILD NUITKA OK.
endlocal
