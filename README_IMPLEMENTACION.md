# Renombrador PDF Hospitalario - implementación base en PyQt6

## 1. Impacto y riesgos

### Qué se va a resolver
- Leer un Excel donde ya existe el **nombre final correcto**.
- Analizar una carpeta de PDFs cuyo nombre actual todavía no está completamente definido por el sistema generador.
- Sugerir automáticamente el nombre final.
- Permitir corrección manual.
- Renombrar físicamente los archivos.
- Generar auditoría CSV y JSON.

### Riesgos identificados
1. **Riesgo funcional**: el nombre actual del sistema no está estandarizado todavía.
   - Protección: la lógica no depende únicamente del nombre actual. También usa texto interno del PDF y reglas del Excel.
2. **Riesgo de sobreescritura**: dos archivos pueden terminar con el mismo nombre final.
   - Protección: el sistema numera duplicados como `_1`, `_2`, `_3`, etc.
3. **Riesgo de pérdida de datos**: renombrado físico irreversible si se hace sin respaldo.
   - Protección: botón de backup completo de la carpeta antes de aplicar cambios.
4. **Riesgo legal/licenciamiento**: **PyQt6** tiene implicaciones GPL/comerciales.
   - Protección: si la distribución final va a ser cerrada o comercial, conviene evaluar migración a **PySide6** antes de publicar masivamente.
5. **Riesgo de OCR**: esta base no usa OCR. Solo usa texto extraíble con `PyMuPDF (fitz)`.
   - Implicación: si un PDF es imagen pura, puede quedar sin match automático.

## 2. Dependencias del diseño
- `openpyxl/pandas` para leer Excel.
- `PyMuPDF` para extraer texto de PDFs.
- `PyQt6` para interfaz.
- `PyInstaller` o `Nuitka` para distribución.
- `Inno Setup` para instalador Windows.

## 3. Estructura del proyecto
```text
renombrador_pdf_pyqt6/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ models.py
│  ├─ services/
│  │  ├─ excel_service.py
│  │  ├─ pdf_service.py
│  │  ├─ rules_service.py
│  │  └─ rename_service.py
│  └─ ui/
│     └─ main_window.py
├─ build/
│  ├─ build_windows.bat
│  └─ build_nuitka.bat
├─ config/
│  └─ app_config.json
├─ installer/
│  └─ renombrador_pdf.iss
├─ requirements.txt
└─ README_IMPLEMENTACION.md
```

## 4. Qué toma como verdad
La verdad del nombre correcto está en el Excel, no en el nombre actual del archivo.

### Columnas mínimas requeridas en Excel
Debe existir al menos una de estas columnas:
- `NOMBRE_FINAL`
- `NOMBRE_PDF`
- `FINAL_NAME`

### Columnas opcionales recomendadas
- `NOTA`
- `ACTIVO`
- `ORDEN`
- `PALABRAS_NOMBRE`
- `PALABRAS_TEXTO`
- `REGEX_TEXTO`

## 5. Flujo técnico
1. Cargar Excel.
2. Convertir cada fila activa en una regla válida.
3. Escanear PDFs de una carpeta raíz.
4. Extraer texto de las primeras páginas.
5. Intentar match por este orden:
   - coincidencia directa del código final dentro del nombre actual,
   - reglas heredadas embebidas,
   - keywords de nombre,
   - keywords de texto,
   - regex de texto,
   - asignación manual.
6. Mostrar sugerencia y confianza.
7. Crear backup.
8. Previsualizar destino.
9. Renombrar.
10. Exportar auditoría.

## 6. Regla heredada ya identificada desde el material existente
Del repositorio analizado ya existen estas reglas mínimas:
- `PLANILLA` en nombre actual -> `PI.pdf`
- `OTROS` en nombre actual -> `ORS.pdf`
- `NOTAS DE EVOLUCION` en contenido -> `002.pdf`

Estas fueron incorporadas en `config/app_config.json` como reglas base.

## 7. Validación antes y después

### Antes
- Confirmar que el Excel abre y tiene columna de nombre final.
- Confirmar que la carpeta contiene PDFs.
- Ejecutar solo análisis y exportar auditoría sin renombrar.
- Revisar manualmente los estados `REVISAR` y `SIN_MATCH`.

### Después
- Confirmar que cada PDF quedó con un nombre permitido por Excel.
- Confirmar que no se perdió cantidad de archivos.
- Confirmar que no hubo errores en el log.
- Confirmar que los archivos duplicados quedaron con sufijo `_n`.
- Confirmar que existe CSV y JSON de auditoría.

## 8. Checklist de no-rotura
- [ ] Carga Excel sin error.
- [ ] Analiza PDFs sin bloquear UI en lotes pequeños.
- [ ] Si no puede leer texto, no revienta la ejecución.
- [ ] No sobreescribe archivos existentes.
- [ ] Permite asignación manual.
- [ ] Exporta auditoría.
- [ ] Crea backup antes de renombrar.
- [ ] Funciona aunque el Excel tenga solo la columna del nombre final.
- [ ] Respeta reglas heredadas mínimas.

## 9. Preparación de entorno
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app\main.py
```

## 10. Build distribuible
### Rápido
```bash
build\build_windows.bat
```

### Más cerrado
```bash
build\build_nuitka.bat
```

### Instalador
Abrir `installer/renombrador_pdf.iss` con Inno Setup y compilar.

## 11. Plan de reversión

### Backup obligatorio
Antes de aplicar renombrado, usar el botón **Crear backup**.
Eso duplica toda la carpeta raíz a una carpeta hermana con timestamp.

### Pánico < 2 min
1. Cerrar la app.
2. Eliminar la carpeta renombrada.
3. Renombrar la carpeta backup con su nombre original.

### Git rollback
```bash
git restore .
```

## 12. Mejoras inmediatas sugeridas para la siguiente iteración
- Agregar vista previa del PDF.
- Soportar OCR solo para PDFs imagen.
- Agregar plantillas de Excel de ejemplo.
- Agregar hilo en segundo plano con `QThread` para lotes grandes.
- Guardar perfiles de configuración por área hospitalaria.
