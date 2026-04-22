Sí, eso está mal según la regla funcional que se describió.

`PI.pdf` debe quedar sin numeración cuando solo existe **un** archivo que resuelve a ese nombre.
La numeración `_01`, `_02`, `_03` solo debería aparecer cuando **dos o más PDFs distintos** terminan con el mismo nombre final canónico.

## Impacto y riesgos

Lo que hoy está pasando es esto:

* la tabla de válidos sí define `PI.pdf` como nombre canónico
* la lógica heredada también resuelve `PLANILLA -> PI.pdf`
* pero en la UI existe una rutina de deduplicación que renombra en bloque por destino propuesto

En el código actual, la parte que fuerza sufijos está aquí:

`app/ui/main_window.py`

```python
def _apply_renames_with_dedup(self, results: list):
    candidates = [
        r for r in results
        if r.get("suggested_final_name") and r["original_name"] != r["suggested_final_name"]
    ]

    groups: dict[str, list] = {}
    for item in candidates:
        dest = item["suggested_final_name"]
        groups.setdefault(dest, []).append(item)

    for dest, items in sorted(groups.items()):
        if len(items) == 1:
            self._rename_file(items[0], dest)
        else:
            for idx, item in enumerate(items, start=1):
                suffix = Path(dest).suffix
                stem = Path(dest).stem
                new_name = f"{stem}_{idx:02d}{suffix}"
                self._rename_file(item, new_name)
```

Ese bloque es el que decide cuándo poner `_01`, `_02`, etc.
Si la agrupación detecta más de un candidato para `PI.pdf`, numera todo.
Eso se ve alineado con el repo actual.

También está claro que la regla canónica de planilla es `PI.pdf` y no `PI_10.pdf`:

```sql
('PI.pdf', 'S', 1, 'Planilla Individual', ...)
```

Y la regla heredada sigue diciendo:

```python
if "PLANILLA" in name_upper:
    return "PI.pdf", "HARDCODE:PLANILLA"
```

Con eso, el comportamiento esperado sí es `PI.pdf`. No `PI_10.pdf`.

### Punto importante

Con lo que se ve en el repomix actual, si hubiera duplicado debería generar `PI_01.pdf`, `PI_02.pdf`, etc., no `PI_10.pdf`.
Eso sugiere una de estas dos cosas:

1. en el ejecutable que se está probando hay una versión anterior distinta a la del repomix
2. existe otra rutina de renombre no incluida en ese flujo que está conservando un sufijo previo

## Preparación

Antes de tocar nada:

### Backup de código

```bash
git checkout -b fix/dedup-renombrado-pi
git add .
git commit -m "backup antes de corregir deduplicacion de nombres PDF"
```

### Validación rápida

Buscar si hay más de una rutina de renombre:

```bash
grep -Rni "_apply_renames_with_dedup\|rename_file\|PI_10\|_{idx:02d}" app datos_base
```

Si aparece otra función aparte de `app/ui/main_window.py`, ahí puede estar saliendo el `PI_10.pdf`.

## Implementación paso a paso

La corrección segura es esta:

* primero separar los que van a nombre directo
* solo numerar si realmente hay **colisión real dentro del lote**
* si hay un solo archivo para `PI.pdf`, dejar `PI.pdf`
* si ya existe un `PI.pdf` correcto en carpeta, el nuevo no debe pasar a `PI_01.pdf` automáticamente sin control; debe tratarse como colisión o buscar el siguiente sufijo según una regla explícita

### Archivo a modificar

`app/ui/main_window.py`

### Reemplazar completo el método `_apply_renames_with_dedup` por este

```python
def _apply_renames_with_dedup(self, results: list):
    """
    Regla correcta:
    - Si solo un archivo resuelve a PI.pdf -> queda PI.pdf
    - Solo usar _01, _02, _03... cuando DOS O MAS archivos del mismo lote
      resuelvan al mismo nombre final.
    - No numerar por costumbre.
    - No pisar archivos existentes.
    """
    from pathlib import Path

    # ============================================================
    # NUEVO: candidatos reales a renombrar
    # ============================================================
    candidates = [
        r for r in results
        if r.get("suggested_final_name")
        and r["original_name"] != r["suggested_final_name"]
    ]

    # ============================================================
    # NUEVO: agrupar por nombre final canónico propuesto
    # ============================================================
    groups: dict[str, list] = {}
    for item in candidates:
        dest = (item["suggested_final_name"] or "").strip()
        if not dest:
            continue
        groups.setdefault(dest, []).append(item)

    renamed = 0

    for dest, items in sorted(groups.items()):
        # ========================================================
        # CASO 1: solo un archivo quiere ese nombre
        # Debe quedar exactamente con el nombre canónico
        # ========================================================
        if len(items) == 1:
            item = items[0]
            orig = Path(item["original_path"])
            target = orig.parent / dest

            # Si el destino ya existe y NO es el mismo archivo, no se renombra.
            # Esto protege integridad y evita "inventar" sufijos sin necesidad.
            if target.exists() and orig.resolve() != target.resolve():
                self._log(
                    f"  ⚠ COLISION: {item['original_name']} no se renombró porque ya existe {dest}"
                )
                continue

            self._rename_file(item, dest)
            renamed += 1
            continue

        # ========================================================
        # CASO 2: varios archivos del mismo lote resuelven al mismo
        # nombre canónico -> aquí sí aplicar _01, _02, _03...
        # ========================================================
        suffix = Path(dest).suffix
        stem = Path(dest).stem

        # Orden estable para no tener resultados aleatorios
        items_sorted = sorted(items, key=lambda x: x["original_name"].upper())

        for idx, item in enumerate(items_sorted, start=1):
            new_name = f"{stem}_{idx:02d}{suffix}"
            orig = Path(item["original_path"])
            target = orig.parent / new_name

            # Buscar siguiente libre si ya existe en disco
            if target.exists() and orig.resolve() != target.resolve():
                seq = idx
                while True:
                    seq += 1
                    candidate_name = f"{stem}_{seq:02d}{suffix}"
                    candidate_target = orig.parent / candidate_name
                    if not candidate_target.exists():
                        new_name = candidate_name
                        break

            self._rename_file(item, new_name)
            renamed += 1

    self._log(f"Total renombrados: {renamed}")
```

## Qué protege esta versión

* si solo hay una planilla, queda `PI.pdf`
* solo numera cuando el mismo lote trae varias planillas que resuelven a `PI.pdf`
* no convierte una colisión simple en numeración automática sin control
* evita sobreescritura
* deja trazabilidad en log

## Pruebas de verificación y regresión

### Caso 1

Carpeta con solo un archivo tipo planilla:

```text
PI_10.pdf
```

Resultado esperado:

```text
PI.pdf
```

### Caso 2

Carpeta con dos archivos distintos que ambos resuelven a `PI.pdf`:

```text
PI_10.pdf
PLANILLA_X.pdf
```

Resultado esperado:

```text
PI_01.pdf
PI_02.pdf
```

### Caso 3

Carpeta con un archivo a renombrar y ya existe un `PI.pdf` previo:

```text
PI.pdf
PI_10.pdf
```

Resultado esperado con este fix:

* no se renombra automáticamente a `PI_01.pdf`
* se registra colisión en log

Eso es importante porque respeta la regla funcional que se pidió.

### Regresión obligatoria

Debe seguir funcionando igual:

* `OTROS -> ORS.pdf`
* `NOTASDEEVOLUCION -> 002.pdf`
* nombres ya correctos no deben cambiarse
* no debe sobreescribir archivos existentes

## Plan de reversión

Si algo sale mal:

```bash
git restore app/ui/main_window.py
```

o si ya hubo commit:

```bash
git reset --hard HEAD~1
```

## Conclusión técnica

Sí hay un problema de lógica en la deduplicación.
La regla correcta es:

* `PI.pdf` cuando hay un solo match
* `PI_01.pdf`, `PI_02.pdf`, `PI_03.pdf` solo cuando hay varios matches reales al mismo nombre final

Y además, si realmente apareció `PI_10.pdf`, con honestidad técnica eso no coincide exactamente con el bloque actual del repomix, porque ese bloque generaría `_01`, `_02`, no `_10`. Entonces conviene revisar si el `.exe` fue construido con otra versión distinta del código fuente actual.

Si se desea, en el siguiente paso se puede dejar el parche completo sobre `app/ui/main_window.py` ya integrado con comentarios de inicio y fin para copiar y pegar sin riesgo.


----


Sí. Se deja el parche quirúrgico para que `PI.pdf` quede sin numeración cuando solo exista un archivo, y que `_01`, `_02`, `_03` aparezcan únicamente cuando varios archivos del mismo lote terminen en el mismo nombre final. La función actual agrupa por `suggested_final_name` y numera solo cuando `len(items) > 1`; además el catálogo base sigue teniendo `PI.pdf` como nombre válido.  

## Impacto y riesgos

El cambio toca solo la deduplicación en UI, no la lectura Oracle ni la extracción de texto PDF. Eso protege la estabilidad del motor actual. El riesgo real está en dos puntos:

1. que exista ya un `PI.pdf` en disco y otro archivo quiera renombrarse también a `PI.pdf`
2. que el ejecutable de Windows haya sido construido con una versión previa distinta al código del repomix, porque `PI_10.pdf` no sale de la función actual mostrada; la función actual generaría `_01`, `_02`, etc., no `_10`. 

## Preparación

### Backup obligatorio

```bash
git checkout -b fix/renombrado-dedup-pi
git add .
git commit -m "backup antes de corregir deduplicacion de nombres PDF"
```

### Validación rápida antes de tocar

```bash
grep -Rni "_apply_renames_with_dedup\|suggested_final_name\|PI_10\|_{idx:02d}" app
```

Si aparece otra función de renombre además de `app/ui/main_window.py`, allí puede estar la causa del `PI_10.pdf`.

---

## Implementación paso a paso

### Archivo exacto

`app/ui/main_window.py`

### Reemplazo completo del método actual

Reemplazar solo este método:

```python
def _apply_renames_with_dedup(self, results: list):
    """
    Regla funcional:
    - Si un solo archivo resuelve a PI.pdf -> queda PI.pdf
    - Solo usar _01, _02, _03... cuando DOS o más archivos del mismo lote
      resuelvan al mismo nombre final.
    - No sobrescribir archivos existentes.
    - Si existe colisión con un archivo ya presente en disco, se registra y se omite.
    """
    from pathlib import Path

    # ============================================================
    # NUEVO: solo procesa archivos con destino sugerido y que
    # realmente necesiten cambio de nombre
    # ============================================================
    candidates = [
        r for r in results
        if r.get("suggested_final_name")
        and r["original_name"] != r["suggested_final_name"]
    ]

    # ============================================================
    # NUEVO: agrupar por nombre final canónico propuesto
    # Ejemplo:
    #   PI_10.pdf -> PI.pdf
    #   PLANILLA.pdf -> PI.pdf
    # Ambos quedan dentro del grupo "PI.pdf"
    # ============================================================
    groups: dict[str, list] = {}
    for item in candidates:
        dest = (item["suggested_final_name"] or "").strip()
        if not dest:
            continue
        groups.setdefault(dest, []).append(item)

    renamed = 0

    for dest, items in sorted(groups.items()):
        suffix = Path(dest).suffix
        stem = Path(dest).stem

        # ========================================================
        # CASO 1: solo un archivo quiere ese nombre final
        # Debe quedar EXACTAMENTE con el nombre canónico.
        # Ejemplo:
        #   PI_10.pdf -> PI.pdf
        # ========================================================
        if len(items) == 1:
            item = items[0]
            orig = Path(item["original_path"])
            target = orig.parent / dest

            # Si el destino ya existe y es otro archivo distinto,
            # no se inventa sufijo automáticamente.
            if target.exists():
                try:
                    same_file = orig.resolve() == target.resolve()
                except Exception:
                    same_file = False

                if not same_file:
                    self._log(
                        f"  ⚠ COLISION: {item['original_name']} no se renombró porque ya existe {dest}"
                    )
                    continue

            self._rename_file(item, dest)
            renamed += 1
            continue

        # ========================================================
        # CASO 2: varios archivos del mismo lote resuelven al mismo
        # nombre canónico -> aquí sí se numeran.
        # Ejemplo:
        #   PI_10.pdf y PLANILLA_X.pdf
        #   -> PI_01.pdf y PI_02.pdf
        # ========================================================
        items_sorted = sorted(
            items,
            key=lambda x: (
                str(Path(x["original_path"]).parent).upper(),
                x["original_name"].upper(),
            ),
        )

        for idx, item in enumerate(items_sorted, start=1):
            new_name = f"{stem}_{idx:02d}{suffix}"
            orig = Path(item["original_path"])
            target = orig.parent / new_name

            # Si ya existe, busca el siguiente libre.
            # Esto evita sobreescritura accidental.
            if target.exists():
                seq = idx
                while True:
                    seq += 1
                    candidate_name = f"{stem}_{seq:02d}{suffix}"
                    candidate_target = orig.parent / candidate_name
                    if not candidate_target.exists():
                        new_name = candidate_name
                        break

            self._rename_file(item, new_name)
            renamed += 1

    self._log(f"Total renombrados: {renamed}")
```

### No tocar este método salvo que se quiera endurecer la colisión

Se recomienda dejar `_rename_file` como está por ahora para no abrir otro frente, porque ya renombra respetando exactamente el nombre final entregado por la lógica superior. 

---

## Pruebas de verificación y regresión

### Caso 1: una sola planilla

Entrada:

```text
PI_10.pdf
```

Salida esperada:

```text
PI.pdf
```

### Caso 2: dos archivos distintos que resuelven al mismo nombre

Entrada:

```text
PI_10.pdf
PLANILLA_X.pdf
```

Salida esperada:

```text
PI_01.pdf
PI_02.pdf
```

### Caso 3: ya existe un PI.pdf correcto en la carpeta

Entrada:

```text
PI.pdf
PI_10.pdf
```

Salida esperada:

* `PI.pdf` se mantiene
* `PI_10.pdf` no se renombra
* log: `COLISION`

### Regresión de no-rotura

Debe seguir funcionando igual:

* `OTROS` → `ORS.pdf`
* `NOTAS DE EVOLUCION` → `002.pdf`
* archivos ya correctos no deben cambiar
* no debe sobreescribir archivos existentes
* el instalador Inno Setup y el build Windows siguen siendo los mismos porque solo cambia lógica Python interna. 

---

## Plan de reversión

### Rollback de código

```bash
git restore app/ui/main_window.py
```

o, si ya hubo commit:

```bash
git reset --hard HEAD~1
```

### Pánico en menos de 2 minutos

```bash
git checkout -- app/ui/main_window.py
python app/main.py
```

---

## Observación técnica final

La función actual del repomix ya está pensada para dejar nombre directo cuando hay un solo archivo y numerar solo cuando hay varios. Por eso, si en pantalla o en el `.exe` aparece `PI_10.pdf` como resultado final, lo más probable es que el ejecutable haya sido construido con otra versión o exista otra rutina paralela de renombre fuera de este bloque. 

Si se desea, en el siguiente paso se deja también el parche para que la tabla de la UI muestre el `suggested_final_name` final real después de deduplicar, para que no confunda al operador.
