Sí, ahí ya se ve claro.

Actualmente hay dos cosas importantes:

1. La tabla `PDF_NOMBRES_VALIDOS` ya tiene el catálogo central y además ya empezó a manejar reglas por base de datos con:

* `REGLA_SIMILARIDAD`
* `REGLA_LEE_DOCUMENTO` 

2. El código viejo todavía tiene reglas quemadas en local, por ejemplo:

* si encuentra `NOTASDEEVOLUCION` en el PDF lo cambia a `002.pdf`
* si el nombre contiene `OTROS` lo cambia a `ORS.pdf`
* si el nombre contiene `PLANILLA` lo cambia a `PI.pdf` 

Entonces sí: el siguiente paso correcto es quitar la lógica fija del cliente y hacer que todo salga desde Oracle.

## Impacto y riesgos

Lo que puede salir mal:

* que dos reglas de Oracle coincidan con el mismo archivo
* que un PDF sin texto no pueda resolverse por contenido
* que un rename pise otro archivo existente
* que una mala carga en Oracle cambie el comportamiento de todos los equipos a la vez

Lo que se va a proteger:

* prioridad de evaluación fija
* modo simulación antes de renombrar
* no sobrescribir archivos existentes
* log detallado de por qué se decidió cada nombre
* fallback seguro: si no hay coincidencia, no se renombra

## Preparación

### Backup obligatorio

Antes de cambiar nada:

```bash
git checkout -b feature/oracle-reglas-centralizadas
git add .
git commit -m "backup antes de migrar reglas locales a Oracle"
```

Respaldar tabla:

```sql
CREATE TABLE PDF_NOMBRES_VALIDOS_BKP_20260422 AS
SELECT *
FROM PDF_NOMBRES_VALIDOS;
```

Validación rápida antes:

```sql
SELECT NOMBRE_PDF,
       ACTIVO,
       ORDEN,
       NOTA,
       REGLA_SIMILARIDAD,
       REGLA_LEE_DOCUMENTO
FROM PDF_NOMBRES_VALIDOS
ORDER BY ORDEN, NOMBRE_PDF;
```

## Implementación paso a paso

### 1) Regla funcional recomendada

Se recomienda que el motor evalúe así, en este orden:

1. `REGLA_LEE_DOCUMENTO`
2. `REGLA_SIMILARIDAD`
3. si no encuentra nada, deja el archivo como está

Así se evita que un nombre “parecido” gane antes que una evidencia fuerte dentro del PDF.

---

### 2) Archivo nuevo

**Ruta exacta:** `app/services/oracle_rule_service.py`

```python
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

from app.services.oracle_client import connect_with_failover


@dataclass
class OraclePdfRule:
    nombre_pdf: str
    activo: str
    orden: int
    nota: str | None
    regla_similaridad: str | None
    regla_lee_documento: str | None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.upper()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _normalize_compact(value: str | None) -> str:
    value = _normalize_text(value)
    value = re.sub(r"[^A-Z0-9]+", "", value)
    return value


def fetch_oracle_pdf_rules() -> List[OraclePdfRule]:
    conn = connect_with_failover()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                NOMBRE_PDF,
                ACTIVO,
                NVL(ORDEN, 999999) AS ORDEN,
                NOTA,
                REGLA_SIMILARIDAD,
                REGLA_LEE_DOCUMENTO
            FROM PDF_NOMBRES_VALIDOS
            WHERE ACTIVO = 'S'
            ORDER BY NVL(ORDEN, 999999), NOMBRE_PDF
            """
        )
        rows = cur.fetchall()

        result: List[OraclePdfRule] = []
        for row in rows:
            result.append(
                OraclePdfRule(
                    nombre_pdf=row[0],
                    activo=row[1],
                    orden=int(row[2]) if row[2] is not None else 999999,
                    nota=row[3],
                    regla_similaridad=row[4],
                    regla_lee_documento=row[5],
                )
            )
        return result
    finally:
        conn.close()


def resolve_pdf_name_from_rules(
    original_filename: str,
    pdf_text: str,
    rules: List[OraclePdfRule],
) -> tuple[Optional[str], str]:
    """
    Devuelve:
      (nombre_destino, motivo)
    """

    normalized_name = _normalize_text(original_filename)
    normalized_name_compact = _normalize_compact(original_filename)

    normalized_pdf_text = _normalize_text(pdf_text)
    normalized_pdf_text_compact = _normalize_compact(pdf_text)

    # ==========================================
    # PRIORIDAD 1: regla por contenido del PDF
    # ==========================================
    for rule in rules:
        token = (rule.regla_lee_documento or "").strip()
        if not token:
            continue

        token_normalized = _normalize_text(token)
        token_compact = _normalize_compact(token)

        if not token_compact:
            continue

        if (
            token_normalized in normalized_pdf_text
            or token_compact in normalized_pdf_text_compact
        ):
            return rule.nombre_pdf, f"contenido_pdf:{token}"

    # ==========================================
    # PRIORIDAD 2: regla por similitud de nombre
    # ==========================================
    for rule in rules:
        token = (rule.regla_similaridad or "").strip()
        if not token:
            continue

        token_normalized = _normalize_text(token)
        token_compact = _normalize_compact(token)

        if not token_compact:
            continue

        if (
            token_normalized in normalized_name
            or token_compact in normalized_name_compact
        ):
            return rule.nombre_pdf, f"nombre_archivo:{token}"

    return None, "sin_coincidencia"
```

---

### 3) Archivo a reemplazar

**Ruta exacta:** `app/services/rename_service.py`

> Si ya existe, se recomienda reemplazarlo completo por esta versión o adaptar la función central de renombrado.
> Esta versión no rompe el cliente porque solo cambia la fuente de reglas.

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import fitz

from app.services.oracle_rule_service import (
    fetch_oracle_pdf_rules,
    resolve_pdf_name_from_rules,
)


@dataclass
class RenameResult:
    original_path: str
    target_path: str | None
    status: str
    reason: str


def extract_pdf_text(pdf_path: str) -> str:
    text_parts: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            try:
                text_parts.append(page.get_text("text") or "")
            except Exception:
                continue
    finally:
        doc.close()

    return "\n".join(text_parts)


def rename_pdfs_from_oracle_rules(base_dir: str, dry_run: bool = True) -> List[RenameResult]:
    rules = fetch_oracle_pdf_rules()
    results: List[RenameResult] = []

    for root, _, files in os.walk(base_dir):
        for file_name in files:
            if not file_name.lower().endswith(".pdf"):
                continue

            original_path = os.path.join(root, file_name)

            try:
                pdf_text = extract_pdf_text(original_path)
                target_name, reason = resolve_pdf_name_from_rules(
                    original_filename=file_name,
                    pdf_text=pdf_text,
                    rules=rules,
                )

                if not target_name:
                    results.append(
                        RenameResult(
                            original_path=original_path,
                            target_path=None,
                            status="SIN_CAMBIOS",
                            reason=reason,
                        )
                    )
                    continue

                target_path = os.path.join(root, target_name)

                if os.path.abspath(original_path) == os.path.abspath(target_path):
                    results.append(
                        RenameResult(
                            original_path=original_path,
                            target_path=target_path,
                            status="YA_CORRECTO",
                            reason=reason,
                        )
                    )
                    continue

                if os.path.exists(target_path):
                    results.append(
                        RenameResult(
                            original_path=original_path,
                            target_path=target_path,
                            status="COLISION",
                            reason=f"{reason}|destino_ya_existe",
                        )
                    )
                    continue

                if not dry_run:
                    os.rename(original_path, target_path)

                results.append(
                    RenameResult(
                        original_path=original_path,
                        target_path=target_path,
                        status="RENOMBRADO" if not dry_run else "SIMULADO",
                        reason=reason,
                    )
                )

            except Exception as exc:
                results.append(
                    RenameResult(
                        original_path=original_path,
                        target_path=None,
                        status="ERROR",
                        reason=str(exc),
                    )
                )

    return results
```

---

### 4) Ajuste del punto de entrada

**Ruta exacta:** donde hoy se llama al proceso de renombrado desde UI o main.

Si existe algo parecido a lógica local/SQLite, se debe cambiar por:

```python
from app.services.rename_service import rename_pdfs_from_oracle_rules

base_dir = r"C:\RUTA\DE\TRABAJO"

# primero simulación
results = rename_pdfs_from_oracle_rules(base_dir=base_dir, dry_run=True)

for item in results:
    print(item.status, item.original_path, item.target_path, item.reason)

# luego ejecución real
# results = rename_pdfs_from_oracle_rules(base_dir=base_dir, dry_run=False)
```

---

### 5) SQL de validación recomendada en Oracle

Conviene detectar reglas duplicadas o peligrosas:

```sql
SELECT REGLA_SIMILARIDAD, COUNT(*)
FROM PDF_NOMBRES_VALIDOS
WHERE ACTIVO = 'S'
  AND REGLA_SIMILARIDAD IS NOT NULL
GROUP BY REGLA_SIMILARIDAD
HAVING COUNT(*) > 1;
```

```sql
SELECT REGLA_LEE_DOCUMENTO, COUNT(*)
FROM PDF_NOMBRES_VALIDOS
WHERE ACTIVO = 'S'
  AND REGLA_LEE_DOCUMENTO IS NOT NULL
GROUP BY REGLA_LEE_DOCUMENTO
HAVING COUNT(*) > 1;
```

Y conviene además ver cuáles registros realmente ya tienen regla cargada. En lo compartido, por ahora se ve al menos:

* `PI.pdf` con `REGLA_SIMILARIDAD = 'F_NOMBRE'`
* `CC.pdf` con `REGLA_LEE_DOCUMENTO = 'HOJA DE COBERTURA'` 

## Mejora importante para no romper

La tabla actualmente permite una sola cadena por columna. Eso sirve, pero queda limitada.

Se recomienda a mediano plazo esta estructura:

```sql
CREATE TABLE PDF_NOMBRE_REGLAS (
    ID_REGLA            NUMBER GENERATED BY DEFAULT AS IDENTITY,
    NOMBRE_PDF          VARCHAR2(100) NOT NULL,
    TIPO_REGLA          VARCHAR2(30) NOT NULL,   -- NOMBRE | CONTENIDO
    PATRON              VARCHAR2(4000) NOT NULL,
    ACTIVO              CHAR(1) DEFAULT 'S' NOT NULL,
    PRIORIDAD           NUMBER DEFAULT 100 NOT NULL,
    OBSERVACION         VARCHAR2(500),
    CREATED_AT_UTC      TIMESTAMP DEFAULT SYSTIMESTAMP,
    UPDATED_AT_UTC      TIMESTAMP
);
```

Porque así un mismo `NOMBRE_PDF` puede tener varias expresiones de búsqueda sin agregar más columnas ni tocar el cliente.

## Pruebas de verificación y regresión

### Verificación funcional nueva

* archivo con texto `HOJA DE COBERTURA` debe terminar como `CC.pdf`
* archivo cuyo nombre coincida con token configurado en `REGLA_SIMILARIDAD` debe renombrarse al `NOMBRE_PDF` correspondiente
* archivo sin coincidencia no debe cambiarse
* archivo ya llamado correctamente no debe moverse
* si ya existe el destino, debe reportarse `COLISION`

### Regresión de no-rotura

Debe seguir funcionando igual:

* conexión Oracle por JDBC/failover, porque ya existe `oracle_client.py` y no conviene tocar esa parte 
* lectura de texto PDF con `fitz`
* recorrido recursivo de carpetas
* modo escritorio / cliente no web sin depender de Excel ni reglas por equipo

### Validación antes y después

Antes:

```sql
SELECT COUNT(*) AS TOTAL_REGLAS_ACTIVAS
FROM PDF_NOMBRES_VALIDOS
WHERE ACTIVO = 'S';
```

Después de pruebas:

* contar PDFs simulados
* contar PDFs renombrados
* contar colisiones
* contar errores
* revisar 10 casos manuales

## Plan de reversión

### Rollback de código

```bash
git log --oneline -n 5
git reset --hard <commit_backup>
```

### Rollback de datos Oracle

```sql
TRUNCATE TABLE PDF_NOMBRES_VALIDOS;

INSERT INTO PDF_NOMBRES_VALIDOS
SELECT *
FROM PDF_NOMBRES_VALIDOS_BKP_20260422;

COMMIT;
```

### Script de emergencia en menos de 2 minutos

```bash
git reset --hard HEAD~1
```

Y en Oracle:

```sql
ROLLBACK;
```

o si ya se hizo commit:

```sql
TRUNCATE TABLE PDF_NOMBRES_VALIDOS;

INSERT INTO PDF_NOMBRES_VALIDOS
SELECT *
FROM PDF_NOMBRES_VALIDOS_BKP_20260422;

COMMIT;
```

## Conclusión técnica

Sí conviene centralizar todo en Oracle.
De hecho, con lo que se compartió, el sistema ya está a medio camino: el proyecto ya tiene conexión Oracle lista y el catálogo ya existe en `PDF_NOMBRES_VALIDOS`; lo que falta es reemplazar la lógica hardcodeada de renombrado para que consulte la tabla y aplique prioridad por contenido y luego por nombre.  

Se recomienda como decisión de estabilidad:

* dejar Oracle como única fuente de verdad
* mantener `dry_run=True` por defecto
* no sobrescribir archivos
* registrar el motivo exacto del rename

Si se quiere, en el siguiente paso se puede dejar ya el parche completo sobre las rutas reales del proyecto para copiar y pegar sin adaptar nada.
