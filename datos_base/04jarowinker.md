Sí, se puede hacer **sin tocar la tabla Oracle**.

La tabla se deja exactamente como está:

* `NOMBRE_PDF`
* `REGLA_SIMILARIDAD`
* `REGLA_LEE_DOCUMENTO` 

Y el umbral queda **hardcodeado en el cliente**.
Eso evita cambios en BD y mantiene Oracle solo como fuente central de reglas.

## Impacto y riesgos

Qué cambia:

* hoy `datos_base/renombrar_pdf.py` usa reglas fijas con `in`, por ejemplo `OTROS`, `PLANILLA` y `NOTASDEEVOLUCION`
* se reemplaza esa comparación simple por:

  * normalización fuerte
  * similitud difusa para `REGLA_SIMILARIDAD`
  * coincidencia normalizada para `REGLA_LEE_DOCUMENTO`

Riesgos:

* falsos positivos si el umbral queda bajo
* falsos negativos si el umbral queda demasiado alto
* PDFs sin texto seguirán dependiendo del nombre del archivo
* si Oracle tiene patrones muy cortos como `F_NOMBRE`, la similitud no ayudará mucho y esa regla no será buena semánticamente 

Protecciones:

* umbral hardcodeado alto
* prioridad: contenido primero, similitud después
* no sobrescribir archivos existentes
* dry run por defecto

---

## Preparación

### Backup obligatorio

```bash
git checkout -b feature/similitud-hardcode-sin-cambiar-oracle
git add .
git commit -m "backup antes de cambiar renombrado a similitud difusa"
```

### Archivo a respaldar

**Ruta exacta:** `datos_base/renombrar_pdf.py` 

Hacer copia:

```bash
cp datos_base/renombrar_pdf.py datos_base/renombrar_pdf.py.bak
```

---

## Implementación paso a paso

## 1) Reemplazar completo

**Ruta exacta:** `datos_base/renombrar_pdf.py`

```python
import os
import re
import fitz
import unicodedata
from dataclasses import dataclass

# ============================================================
# CONFIGURACION HARDOCODEADA
# No modifica Oracle
# ============================================================
DRY_RUN = True

# Umbral global para similitud por nombre de archivo
# Recomendado inicial: 0.90
SIMILARITY_THRESHOLD = 0.90

# Algoritmo permitido: "JARO_WINKLER" o "LEVENSHTEIN"
SIMILARITY_ALGORITHM = "JARO_WINKLER"

# Oracle por JDBC / JayDeBeApi (alineado al proyecto actual)
ORACLE_USER = os.getenv("ORACLE_USER", "ADMINISTRATIVO")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")
ORACLE_TARGETS = os.getenv("ORACLE_TARGETS", "localhost:1521:xe")
ORACLE_JDBC_JAR = os.getenv("ORACLE_JDBC_JAR", "ojdbc8.jar")

try:
    import jaydebeapi
except ImportError:
    jaydebeapi = None

print("=== RENOMBRADO FINAL DESDE ORACLE CON SIMILITUD DIFUSA ===\n")


@dataclass
class ReglaPdf:
    nombre_pdf: str
    activo: str
    orden: int
    nota: str | None
    regla_similaridad: str | None
    regla_lee_documento: str | None


# ============================================================
# NORMALIZACION
# ============================================================
def normalizar_texto(valor: str | None) -> str:
    if not valor:
        return ""

    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(ch for ch in valor if not unicodedata.combining(ch))
    valor = valor.upper()
    valor = re.sub(r"[^A-Z0-9\s]+", " ", valor)
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor


def normalizar_compacto(valor: str | None) -> str:
    valor = normalizar_texto(valor)
    return re.sub(r"[^A-Z0-9]+", "", valor)


def limpiar_ruido_nombre_archivo(nombre: str) -> str:
    nombre = re.sub(r"\.pdf$", "", nombre, flags=re.IGNORECASE)
    nombre = re.sub(r"\bSCAN\b|\bDOC\b|\bDOCUMENTO\b|\bIMG\b|\bIMAGE\b", " ", nombre, flags=re.IGNORECASE)
    nombre = re.sub(r"\b\d{1,8}\b", " ", nombre)
    nombre = re.sub(r"[_\-.]+", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre).strip()
    return nombre


# ============================================================
# ALGORITMOS DE SIMILITUD
# ============================================================
def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            ins = curr[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]


def levenshtein_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    dist = levenshtein_distance(a, b)
    return 1.0 - (dist / max(len(a), len(b)))


def jaro_similarity(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0

    len1 = len(s1)
    len2 = len(s2)

    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)

        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (
        (matches / len1) +
        (matches / len2) +
        ((matches - transpositions / 2) / matches)
    ) / 3.0


def jaro_winkler_similarity(s1: str, s2: str, prefix_scale: float = 0.1) -> float:
    jaro = jaro_similarity(s1, s2)

    prefix = 0
    max_prefix = 4
    for c1, c2 in zip(s1[:max_prefix], s2[:max_prefix]):
        if c1 == c2:
            prefix += 1
        else:
            break

    return jaro + (prefix * prefix_scale * (1 - jaro))


def calcular_similitud(texto_archivo: str, patron_regla: str) -> float:
    a = normalizar_compacto(limpiar_ruido_nombre_archivo(texto_archivo))
    b = normalizar_compacto(patron_regla)

    if not a or not b:
        return 0.0

    if SIMILARITY_ALGORITHM == "LEVENSHTEIN":
        return levenshtein_ratio(a, b)

    return jaro_winkler_similarity(a, b)


# ============================================================
# CONEXION ORACLE EXISTENTE EN ESTILO DEL PROYECTO
# ============================================================
def _parse_target(target: str):
    parts = target.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Target Oracle inválido: {target}. Se esperaba host:port:sid")
    host, port, sid = parts
    return host, int(port), sid


def _jdbc_url(host: str, port: int, sid: str) -> str:
    return f"jdbc:oracle:thin:@{host}:{port}:{sid}"


def connect_with_failover():
    if jaydebeapi is None:
        raise RuntimeError("Falta jaydebeapi. Instalar con: pip install jaydebeapi")

    if not os.path.exists(ORACLE_JDBC_JAR):
        raise FileNotFoundError(f"No existe el JAR Oracle: {ORACLE_JDBC_JAR}")

    targets = [_parse_target(t) for t in ORACLE_TARGETS.split(",")]
    driver = "oracle.jdbc.OracleDriver"
    last_exc = None

    for host, port, sid in targets:
        url = _jdbc_url(host, port, sid)
        try:
            conn = jaydebeapi.connect(
                driver,
                url,
                [ORACLE_USER, ORACLE_PASSWORD],
                jars=[ORACLE_JDBC_JAR],
            )
            return conn
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError(f"No se pudo conectar a Oracle. Último error: {last_exc}")


def cargar_reglas_desde_oracle() -> list[ReglaPdf]:
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

        reglas = []
        for row in cur.fetchall():
            reglas.append(
                ReglaPdf(
                    nombre_pdf=row[0],
                    activo=row[1],
                    orden=int(row[2]) if row[2] is not None else 999999,
                    nota=row[3],
                    regla_similaridad=row[4],
                    regla_lee_documento=row[5],
                )
            )
        return reglas
    finally:
        conn.close()


# ============================================================
# PDF
# ============================================================
def extraer_texto_pdf(path_pdf: str) -> str:
    partes = []
    doc = fitz.open(path_pdf)
    try:
        for page in doc:
            try:
                partes.append(page.get_text("text") or "")
            except Exception:
                continue
    finally:
        doc.close()

    return "\n".join(partes)


# ============================================================
# MOTOR DE RESOLUCION
# ============================================================
def resolver_por_contenido(texto_pdf: str, reglas: list[ReglaPdf]):
    texto_normal = normalizar_texto(texto_pdf)
    texto_compacto = normalizar_compacto(texto_pdf)

    for regla in reglas:
        patron = (regla.regla_lee_documento or "").strip()
        if not patron:
            continue

        patron_normal = normalizar_texto(patron)
        patron_compacto = normalizar_compacto(patron)

        if patron_normal and patron_normal in texto_normal:
            return regla.nombre_pdf, f"contenido:{patron}"

        if patron_compacto and patron_compacto in texto_compacto:
            return regla.nombre_pdf, f"contenido_compacto:{patron}"

    return None, "sin_coincidencia_contenido"


def resolver_por_similitud(nombre_archivo: str, reglas: list[ReglaPdf]):
    mejor_score = -1.0
    mejor_regla = None

    for regla in reglas:
        patron = (regla.regla_similaridad or "").strip()
        if not patron:
            continue

        score = calcular_similitud(nombre_archivo, patron)

        if score > mejor_score:
            mejor_score = score
            mejor_regla = regla

    if mejor_regla is not None and mejor_score >= SIMILARITY_THRESHOLD:
        return (
            mejor_regla.nombre_pdf,
            f"similitud:{mejor_regla.regla_similaridad}|score={mejor_score:.4f}|umbral={SIMILARITY_THRESHOLD:.4f}|algoritmo={SIMILARITY_ALGORITHM}"
        )

    return None, f"sin_coincidencia_similitud|max_score={mejor_score:.4f}"


def resolver_nombre_desde_reglas(nombre_archivo: str, texto_pdf: str, reglas: list[ReglaPdf]):
    # 1) contenido
    nombre_destino, motivo = resolver_por_contenido(texto_pdf, reglas)
    if nombre_destino:
        return nombre_destino, motivo

    # 2) similitud difusa
    return resolver_por_similitud(nombre_archivo, reglas)


# ============================================================
# PROCESO PRINCIPAL
# ============================================================
def renombrar_pdfs(base_dir: str, dry_run: bool = True):
    reglas = cargar_reglas_desde_oracle()

    print(f"Reglas activas cargadas desde Oracle: {len(reglas)}")
    print(f"Algoritmo de similitud: {SIMILARITY_ALGORITHM}")
    print(f"Umbral hardcodeado: {SIMILARITY_THRESHOLD}")
    print(f"Modo simulación: {'SI' if dry_run else 'NO'}\n")

    total = 0
    simulados = 0
    renombrados = 0
    sin_cambios = 0
    colisiones = 0
    errores = 0

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue

            total += 1
            path = os.path.join(root, file)

            try:
                texto_pdf = extraer_texto_pdf(path)
                nombre_destino, motivo = resolver_nombre_desde_reglas(file, texto_pdf, reglas)

                if not nombre_destino:
                    sin_cambios += 1
                    print(f" - Sin cambios: {path} | motivo={motivo}")
                    continue

                new_path = os.path.join(root, nombre_destino)

                if os.path.abspath(path) == os.path.abspath(new_path):
                    sin_cambios += 1
                    print(f" - Ya correcto: {path} | motivo={motivo}")
                    continue

                if os.path.exists(new_path):
                    colisiones += 1
                    print(f"⚠ Colisión: {path} -> {new_path} | motivo={motivo}")
                    continue

                if dry_run:
                    simulados += 1
                    print(f"✓ Simulado: {path} -> {new_path} | motivo={motivo}")
                else:
                    os.rename(path, new_path)
                    renombrados += 1
                    print(f"✓ Renombrado: {path} -> {new_path} | motivo={motivo}")

            except Exception as e:
                errores += 1
                print(f"X Error: {path} | detalle={e}")

    print("\n=== RESUMEN ===")
    print("Total PDFs:", total)
    print("Simulados:", simulados)
    print("Renombrados:", renombrados)
    print("Sin cambios:", sin_cambios)
    print("Colisiones:", colisiones)
    print("Errores:", errores)
    print("\nTERMINADO")


if __name__ == "__main__":
    base_dir = os.getcwd()
    renombrar_pdfs(base_dir=base_dir, dry_run=DRY_RUN)
```

---

## Pruebas de verificación y regresión

Debe probarse primero con:

```python
DRY_RUN = True
SIMILARITY_THRESHOLD = 0.90
SIMILARITY_ALGORITHM = "JARO_WINKLER"
```

Checklist:

* PDF con texto `HOJA DE COBERTURA` debe caer a `CC.pdf` porque esa regla ya está en Oracle en `REGLA_LEE_DOCUMENTO` 
* archivo con nombre sucio, distinto en mayúsculas/minúsculas, guiones o espacios debe poder caer por similitud
* si no pasa umbral, no debe renombrarse
* si destino existe, debe reportar colisión
* no debe sobrescribir
* debe seguir leyendo solo `.pdf`, igual que el script actual 

## Recomendación de arranque

Para no romper, se recomienda:

* arrancar con `JARO_WINKLER`
* umbral `0.90`
* revisar resultados del dry run
* si está muy estricto, bajar a `0.88`
* si está muy permisivo, subir a `0.92`

## Observación importante

Con la data actual, `PI.pdf` tiene `REGLA_SIMILARIDAD = 'F_NOMBRE'` y no algo semántico como `PLANILLA INDIVIDUAL` 

Entonces, aunque el algoritmo mejore, esa regla concreta puede seguir siendo mala porque el patrón base no ayuda mucho.
La mejora del algoritmo no corrige un patrón pobre; solo compara mejor.

## Plan de reversión

### Rollback de código

```bash
cp datos_base/renombrar_pdf.py.bak datos_base/renombrar_pdf.py
```

o por Git:

```bash
git reset --hard HEAD~1
```

### Rollback operativo rápido

Sin tocar código, también se puede neutralizar el cambio dejando el umbral imposible:

```python
SIMILARITY_THRESHOLD = 0.9999
```

Así prácticamente solo actuaría la regla por contenido.

## Conclusión

Sí, se puede dejar **sin modificar Oracle** y con **umbrales hardcodeados** en el cliente.
Eso mantiene la tabla actual intacta y cambia únicamente `datos_base/renombrar_pdf.py`, que hoy todavía trabaja con reglas fijas locales y comparación simple por substring

La opción más estable para arrancar es:

* contenido del PDF primero
* Jaro-Winkler para `REGLA_SIMILARIDAD`
* umbral hardcodeado `0.90`
* `dry_run=True` al inicio

Si se desea, el siguiente paso puede ser dejar una versión 2 con **archivo CSV de auditoría** para revisar exactamente qué score obtuvo cada PDF antes de renombrar.
