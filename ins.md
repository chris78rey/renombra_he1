# Memoria de instalador HE1

## Objetivo

El artefacto que se debe entregar al usuario final es un solo archivo:

`installer/HE1_Setup.exe`

Ese archivo debe comportarse como un instalador de Windows normal:

- instala la aplicacion en `Program Files`
- crea acceso directo en escritorio
- crea acceso directo en menu Inicio
- deja los archivos internos dentro de la carpeta instalada

El usuario final no debe recibir `dist`, `build_artifacts`, `_internal` ni carpetas sueltas.

## Flujo actual del repo

Hoy el build del instalador se hace con:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build\build_he1_installer.ps1
```

Ese script hace tres cosas:

1. recompila la aplicacion con `build\build_windows.bat`
2. arma una carpeta temporal con la salida de PyInstaller
3. empaqueta todo en un instalador unico `HE1_Setup.exe`

El script usa 7-Zip SFX, no deja al usuario con un `.exe` suelto que dependa de `_internal` aparte.

## Archivos clave

- `build/build_he1_installer.ps1`: genera el instalador final
- `build/build_windows.bat`: recompila la aplicacion
- `installer/renombrador_pdf.iss`: archivo legado de Inno Setup, ya no es el flujo principal actual
- `installer/HE1_Setup.exe`: salida final que se debe distribuir

## Verificacion

Despues de generar el instalador, comprobar:

- existe `installer/HE1_Setup.exe`
- al ejecutarlo instala la app en `Program Files`
- crea acceso directo en escritorio
- la app abre desde el acceso directo
- no se entrega `_internal` por separado

## Regla operativa

Si se vuelve a tocar el empaquetado, mantener esta regla:

- PyInstaller genera la carpeta tecnica
- el instalador final debe seguir siendo un solo `.exe`
- no se debe pedir al usuario que mueva carpetas internas
