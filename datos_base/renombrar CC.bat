@echo off
for /d %%d in (*) do (
    for %%f in ("%%d\*.pdf") do (
        ren "%%f" "CC.pdf"
    )
)
pause