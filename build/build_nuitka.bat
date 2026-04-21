@echo off
setlocal

REM =========================
REM BUILD MAS CERRADO CON NUITKA
REM =========================

python -m nuitka ^
  --standalone ^
  --windows-console-mode=disable ^
  --enable-plugin=pyqt6 ^
  --include-data-dir=config=config ^
  --output-dir=dist_nuitka ^
  --assume-yes-for-downloads ^
  app\main.py

if errorlevel 1 (
  echo ERROR en build Nuitka.
  exit /b 1
)

echo BUILD NUITKA OK.
endlocal
