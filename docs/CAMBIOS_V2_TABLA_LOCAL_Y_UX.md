# CAMBIO FINAL - Oracle como fuente de reglas

## Estado final

- SQLite queda fuera del flujo de reglas.
- El cliente ya no usa catálogo local para renombrar.
- La fuente de verdad es Oracle, tabla `PDF_NOMBRES_VALIDOS`.
- El motor evalúa en este orden:
  1. `REGLA_LEE_DOCUMENTO` (contenido del PDF)
  2. `REGLA_SIMILARIDAD` (similitud Jaro-Winkler, umbral 0.85)
  3. keywords hardcodeados legacy (`PLANILLA`→PI.pdf, `OTROS`→ORS.pdf, `NOTAS DE EVOLUCION`→002.pdf)
  4. si no hay coincidencia, no se renombra

## Múltiples patrones por columna

Se permite usar `|` como delimitador en:
- `REGLA_SIMILARIDAD`
- `REGLA_LEE_DOCUMENTO`

Ejemplo en Oracle:
```sql
UPDATE PDF_NOMBRES_VALIDOS
   SET REGLA_SIMILARIDAD = 'PLANILLA|PLANILLA INDIVIDUAL|PLANI',
       REGLA_LEE_DOCUMENTO = 'HOJA DE COBERTURA|COBERTURA IESS'
 WHERE NOMBRE_PDF = 'PI.pdf';
```

## UI

- Se elimina el menú "Reglas".
- La interfaz ya no administra reglas locales.
- Solo queda la opción "Autores" dentro del menú principal.

## Dependencias

```bash
pip install PyQt6 PyMuPDF jaydebeapi JPype1
```

## Variables de entorno

```bash
export ORACLE_USER=DIGITALIZACION
export ORACLE_PASSWORD=DIGITALIZACION
export ORACLE_TARGETS=172.16.60.21:1521:prdsgh2
export ORACLE_JDBC_JAR=jdbc/ojdbc8.jar
```
