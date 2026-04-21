Para correrlo **ahora mismo dentro del proyecto**, lo correcto sería ejecutarlo **desde la raíz de ese módulo**, o sea desde la carpeta que contiene `app/`, `config/`, `installer/` y `requirements.txt`, porque `app/main.py` carga `config/app_config.json` usando la raíz del proyecto, no la carpeta `app/`. 

La estructura esperada quedó así: `app/main.py`, `config/app_config.json`, `requirements.txt` y `README_IMPLEMENTACION.md`. 

### Cómo correrlo en desarrollo

**Windows / PowerShell o CMD**

```bash
cd ruta\del\proyecto\renombrador_pdf_pyqt6
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app\main.py
```

Eso coincide con el README que quedó dentro del proyecto. 

### Si ya existe un venv del proyecto mayor

Si ya hay entorno virtual activo y no se quiere crear otro:

```bash
cd ruta\del\proyecto\renombrador_pdf_pyqt6
pip install -r requirements.txt
python app\main.py
```

Las dependencias que necesita son `PyQt6`, `PyMuPDF`, `openpyxl`, `pandas` y `python-dateutil`.

### Cómo saber si se lo está corriendo desde la carpeta correcta

En esa carpeta deben verse al menos estos archivos:

```bash
app\
config\
requirements.txt
README_IMPLEMENTACION.md
```

Si se intenta correr desde `app\`, puede fallar la carga de configuración porque el código busca `config/app_config.json` desde la raíz del módulo. 

### Build rápido a ejecutable

Si primero se quiere probar como app distribuible:

```bash
cd ruta\del\proyecto\renombrador_pdf_pyqt6
build\build_windows.bat
```

Y si se quiere el build más cerrado:

```bash
build\build_nuitka.bat
```

Eso también quedó documentado en el README. 

### Orden real de uso al abrir la app

1. Cargar el Excel.
2. Seleccionar la carpeta de PDFs.
3. Analizar PDFs.
4. Previsualizar destino.
5. Crear backup.
6. Aplicar renombrado.

### Si no abre

Los errores más probables serían estos:

* falta instalar dependencias de `requirements.txt`
* se lo está corriendo desde la carpeta equivocada y no encuentra `config/app_config.json` 
* el Excel no tiene una columna reconocible como nombre final (`NOMBRE_FINAL`, `NOMBRE_PDF`, `FINAL_NAME`, etc.) 

Comando mínimo final:

```bash
cd ruta\del\proyecto\renombrador_pdf_pyqt6
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app\main.py
```

Si se quiere, en el siguiente paso se le puede dejar al programador un `run.bat` y un `run.ps1` para que lo abra con doble clic.
