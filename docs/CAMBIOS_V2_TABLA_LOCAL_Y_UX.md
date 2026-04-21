
# CAMBIOS V2 - tabla local dentro del proyecto + UX amigable

## Qué cambia
1. Se elimina la dependencia operativa del Excel.
2. La fuente de verdad pasa a una base local SQLite dentro del proyecto.
3. La tabla local se siembra automáticamente desde `datos_base/nombres_validos.sql`.
4. La interfaz usa botones grandes, tipografía más amplia y flujo lineal visible.

## Archivos a agregar
- `app/services/sqlite_rule_service.py`

## Archivos a reemplazar
- `app/ui/main_window.py`
- `app/main.py`
- `config/app_config.json`
- `requirements.txt`

## Cómo correr
```bash
cd renombrador_pdf_pyqt6
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app\main.py
```

## Qué genera en el primer arranque
- `config/catalogo_reglas.db`

## Fuente de datos inicial
- `datos_base/nombres_validos.sql`
