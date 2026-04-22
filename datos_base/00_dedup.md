Sí. Se deja listo para pegar.

El problema actual es que la app agrupa por `suggested_final_name` de forma global y por eso mezcla `PI.pdf` de carpetas distintas. La función actual está en `app/ui/main_window.py` y hoy agrupa así, sin considerar la carpeta padre.  

## Archivo a modificar

`app/ui/main_window.py`

## Reemplazo exacto

Se recomienda reemplazar completos estos dos métodos dentro de la clase `MainWindow`:

```python
def _apply_renames_with_dedup(self, results: list):
    """
    REGLA FUNCIONAL CORRECTA
    ----------------------------------------------------------------
    1) La deduplicación debe ser POR CARPETA + NOMBRE FINAL.
    2) Si en una carpeta solo hay un archivo que resuelve a PI.pdf,
       debe quedar exactamente PI.pdf.
    3) Solo usar _01, _02, _03... cuando dentro de la MISMA carpeta
       existan varios archivos que resuelvan al mismo nombre final.
    4) No sobreescribir archivos existentes.
    5) Si el nombre final directo ya existe en esa carpeta y pertenece
       a otro archivo, registrar colisión y omitir.
    """

    from pathlib import Path

    # ============================================================
    # NUEVO: tomar solo archivos que realmente necesitan renombre
    # ============================================================
    candidates = [
        r for r in results
        if r.get("suggested_final_name")
        and r["original_name"] != r["suggested_final_name"]
    ]

    # ============================================================
    # NUEVO: agrupar por (carpeta_padre, nombre_final)
    # Esto corrige el error actual:
    # Antes mezclaba PI.pdf de varias carpetas distintas.
    # ============================================================
    groups: dict[tuple[str, str], list] = {}

    for item in candidates:
        dest = (item.get("suggested_final_name") or "").strip()
        if not dest:
            continue

        orig = Path(item["original_path"])
        parent_dir = str(orig.parent.resolve())
        key = (parent_dir, dest)

        groups.setdefault(key, []).append(item)

    renamed = 0

    # ============================================================
    # Procesar cada grupo de manera aislada por carpeta
    # ============================================================
    for (parent_dir, dest), items in sorted(groups.items()):
        suffix = Path(dest).suffix
        stem = Path(dest).stem

        # ========================================================
        # CASO 1:
        # En esa carpeta solo existe un archivo para ese nombre final
        # Resultado esperado: nombre directo, sin _01
        # ========================================================
        if len(items) == 1:
            item = items[0]
            orig = Path(item["original_path"])
            target = orig.parent / dest

            if target.exists():
                try:
                    same_file = orig.resolve() == target.resolve()
                except Exception:
                    same_file = False

                if not same_file:
                    self._log(
                        f"  ⚠ COLISION EN CARPETA: {item['original_name']} no se renombró porque ya existe {dest} en {orig.parent}"
                    )
                    continue

            self._rename_file(item, dest)
            renamed += 1
            continue

        # ========================================================
        # CASO 2:
        # En esa MISMA carpeta hay varios archivos que resuelven
        # al mismo nombre final -> aquí sí se numera.
        # ========================================================
        items_sorted = sorted(
            items,
            key=lambda x: x["original_name"].upper()
        )

        for idx, item in enumerate(items_sorted, start=1):
            new_name = f"{stem}_{idx:02d}{suffix}"
            orig = Path(item["original_path"])
            target = orig.parent / new_name

            # Si ya existe, buscar el siguiente libre
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


def _rename_file(self, item: dict, final_name: str):
    """
    Renombra respetando exactamente el nombre final calculado.
    No cambia mayúsculas/minúsculas.
    No sobreescribe archivos existentes.
    """
    from pathlib import Path

    try:
        final_name = (final_name or "").strip()

        if not final_name:
            raise ValueError("Nombre final vacío")

        orig = Path(item["original_path"])
        target = orig.parent / final_name

        # Si ya existe otro archivo con ese nombre, no sobreescribir
        if target.exists():
            try:
                same_file = orig.resolve() == target.resolve()
            except Exception:
                same_file = False

            if not same_file:
                raise FileExistsError(
                    f"Ya existe el archivo destino: {target.name}"
                )

        orig.rename(target)
        self._log(f"  ✓ {item['original_name']} -> {final_name}")

    except Exception as exc:
        self._log(f"  X {item['original_name']}: {exc}")
```

## Cómo queda el comportamiento

Con este cambio:

En `5935675`, si solo hay una planilla:

```text
PI_01.pdf  ->  PI.pdf
```

En `5935677`, si solo hay una planilla:

```text
PI_02.pdf  ->  PI.pdf
```

En `5935678`, si solo hay una planilla:

```text
PI_03.pdf  ->  PI.pdf
```

En `5935679`, si solo hay una planilla:

```text
PI_04.pdf  ->  PI.pdf
```

Y solo si dentro de una misma carpeta hay dos archivos que resuelven a `PI.pdf`, entonces sí quedarán como `PI_01.pdf` y `PI_02.pdf`.

## Validación rápida

Después de pegar, ejecutar y probar una carpeta raíz que contenga varias subcarpetas como las de la captura. Si cada subcarpeta tiene una sola planilla, todas deben terminar con `PI.pdf`, no con numeración corrida global. La lógica anterior numeraba globalmente porque agrupaba solo por destino propuesto. 

## Rollback

Si algo falla:

```bash
git restore app/ui/main_window.py
```

Si se desea, en el siguiente paso se puede dejar también el método `_populate_table` ajustado para que la tabla muestre el nombre final real después de renombrar y no solo el sugerido original.
