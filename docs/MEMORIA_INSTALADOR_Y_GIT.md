# Memoria de instalador y Git

## Objetivo

Generar un instalador unico de Windows para HE1 con nombre corto:

- `installer/HE1_Setup.exe`

## Flujo correcto de build

1. Recompilar la aplicacion desde la raiz del repo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build\build_he1_installer.ps1
```

2. Verificar que exista el artefacto final:

```text
installer/HE1_Setup.exe
```

## Regla de empaquetado

- El instalador debe quedar como un unico `.exe`.
- Debe instalar en `Program Files\HE1`.
- Debe crear accesos directos en escritorio y menu Inicio.
- No debe depender de un ZIP portable para la entrega normal.

## Archivos relevantes

- `installer/renombrador_pdf.iss`
- `build/build_he1_installer.ps1`
- `installer/HE1_Setup.exe`

## Antes de commit

1. Revisar cambios:

```powershell
git status --short
```

2. No incluir artefactos temporales de build:

- `dist/`
- `build_artifacts/`

## Commit

```powershell
git add app/ui/main_window.py app/services/folder_flatten_service.py installer/renombrador_pdf.iss installer/HE1_Setup.exe docs/MEMORIA_INSTALADOR_Y_GIT.md
git commit -m "Add folder flattening and HE1 installer"
```

## Push

```powershell
git push origin HEAD
```

Si el `push` falla, revisar:

- rama actual
- credenciales del remoto
- conectividad con `origin`

## Nota operativa

Si hace falta regenerar el instalador, primero confirmar que `HE1_Setup.exe` fue actualizado y luego decidir si se conserva o se reemplaza el binario anterior `Instalador_HE1.exe` en el historial del repositorio.
