@echo off
for %%f in (*.pdf) do (
    mkdir "%%~nf"
    move "%%f" "%%~nf\"
)
pause