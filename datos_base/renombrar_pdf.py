import os
import re
import fitz
import unicodedata
from dataclasses import dataclass

# ============================================================
# CONFIGURACION
# ============================================================
DRY_RUN = True

# Conexión Oracle vía JDBC/JayDeBeApi, alineada al proyecto
ORACLE_USER = os.getenv("ORACLE_USER", "ADMINISTRATIVO")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")
ORACLE_TARGETS = os.getenv("ORACLE_TARGETS", "localhost:1521:xe")
ORACLE_JDBC_JAR = os.getenv("ORACLE_JDBC_JAR", "ojdbc8.jar")

# Similitud difusa para REGLA_SIMILARIDAD de Oracle
SIMILARITY_THRESHOLD = 0.90
SIMILARITY_ALGORITHM = "JARO_WINKLER"

# Delimitador para múltiples reglas en una sola columna Oracle
# Ejemplo: 'PLANILLA|PLANILLA INDIVIDUAL|PLANI'
RULE_DELIMITER = "|"

try:
    import jaydebeapi
except ImportError:
    jaydebeapi = None

print("=== RENOMBRADO FINAL ORACLE FIRST + HARDCODE FALLBACK ===\n")


# ============================================================
# MODELOS
# ============================================================
@dataclass
class ReglaOracle:
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



def partir_reglas_multiples(valor: str | None) -> list[str]:
    if not valor:
        return []
    partes = [x.strip() for x in str(valor).split(RULE_DELIMITER)]
    return [x for x in partes if x]


def limpiar_ruido_nombre_archivo(nombre: str) -> str:
    nombre = re.sub(r"\.pdf$", "", nombre, flags=re.IGNORECASE)
    nombre = re.sub(r"[_\-.]+", " ", nombre)
    nombre = re.sub(
        r"\bSCAN\b|\bDOC\b|\bDOCUMENTO\b|\bIMG\b|\bIMAGE\b", " ", nombre, flags=re.IGNORECASE
    )
    nombre = re.sub(r"\s+", " ", nombre).strip()
    return nombre


# ============================================================
# SIMILITUD DIFUSA
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
    return 1.0 - (levenshtein_distance(a, b) / max(len(a), len(b)))


def jaro_similarity(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
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
            if s2_matches[j] or s1[i] != s2[j]:
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
        (matches / len1) + (matches / len2) + ((matches - transpositions / 2) / matches)
    ) / 3.0


def jaro_winkler_similarity(s1: str, s2: str, prefix_scale: float = 0.1) -> float:
    jaro = jaro_similarity(s1, s2)
    prefix = 0
    for c1, c2 in zip(s1[:4], s2[:4]):
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
# ORACLE
# ============================================================
def _parse_target(target: str):
    parts = target.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Target Oracle inválido: {target}")
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
                driver, url, [ORACLE_USER, ORACLE_PASSWORD], jars=[ORACLE_JDBC_JAR]
            )
            print(f"[OK] Conectado a Oracle: {host}:{port}:{sid}")
            return conn
        except Exception as exc:
            last_exc = exc
            print(f"[WARN] Falló Oracle {host}:{port}:{sid} -> {exc}")
    raise RuntimeError(f"No se pudo conectar a Oracle. Último error: {last_exc}")


def cargar_reglas_oracle() -> list[ReglaOracle]:
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
            WHERE UPPER(NVL(ACTIVO, 'S')) = 'S'
            ORDER BY NVL(ORDEN, 999999), NOMBRE_PDF
            """
        )
        reglas = []
        for row in cur.fetchall():
            reglas.append(
                ReglaOracle(
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
# MOTOR ORACLE
# ============================================================
def resolver_por_oracle_contenido(texto_pdf: str, reglas: list[ReglaOracle]):
    texto_compacto = normalizar_compacto(texto_pdf)
    for regla in reglas:
        patrones = partir_reglas_multiples(regla.regla_lee_documento)
        for patron in patrones:
            patron_cmp = normalizar_compacto(patron)
            if patron_cmp and patron_cmp in texto_compacto:
                return regla.nombre_pdf, f"ORACLE_CONTENIDO:{patron}"
    return None, "ORACLE_CONTENIDO_SIN_MATCH"


def resolver_por_oracle_nombre(nombre_archivo: str, reglas: list[ReglaOracle]):
    mejor_score = -1.0
    mejor_regla = None
    mejor_patron = None
    for regla in reglas:
        patrones = partir_reglas_multiples(regla.regla_similaridad)
        for patron in patrones:
            score = calcular_similitud(nombre_archivo, patron)
            if score > mejor_score:
                mejor_score = score
                mejor_regla = regla
                mejor_patron = patron
    if mejor_regla is not None and mejor_score >= SIMILARITY_THRESHOLD:
        return (
            mejor_regla.nombre_pdf,
            f"ORACLE_NOMBRE:{mejor_patron}|score={mejor_score:.4f}|umbral={SIMILARITY_THRESHOLD:.4f}",
        )
    return None, f"ORACLE_NOMBRE_SIN_MATCH|max_score={mejor_score:.4f}"


def resolver_por_oracle(nombre_archivo: str, texto_pdf: str, reglas: list[ReglaOracle]):
    nombre_destino, motivo = resolver_por_oracle_contenido(texto_pdf, reglas)
    if nombre_destino:
        return nombre_destino, motivo
    return resolver_por_oracle_nombre(nombre_archivo, reglas)


# ============================================================
# FALLBACK HARDCODE (legado)
# ============================================================
def resolver_por_hardcode(nombre_archivo: str, texto_pdf: str):
    texto_compacto = normalizar_compacto(texto_pdf)
    nombre_upper = (nombre_archivo or "").upper()
    if "NOTASDEEVOLUCION" in texto_compacto:
        return "002.pdf", "HARDCODE_CONTENIDO:NOTASDEEVOLUCION"
    if "OTROS" in nombre_upper:
        return "ORS.pdf", "HARDCODE_NOMBRE:OTROS"
    if "PLANILLA" in nombre_upper:
        return "PI.pdf", "HARDCODE_NOMBRE:PLANILLA"
    return None, "HARDCODE_SIN_MATCH"


# ============================================================
# RESOLUCION FINAL: ORACLE PRIMERO -> HARDCODE DESPUES
# ============================================================
def resolver_nombre_final(
    nombre_archivo: str, texto_pdf: str, reglas_oracle: list[ReglaOracle]
):
    nombre_destino, motivo = resolver_por_oracle(nombre_archivo, texto_pdf, reglas_oracle)
    if nombre_destino:
        return nombre_destino, motivo
    nombre_destino, motivo = resolver_por_hardcode(nombre_archivo, texto_pdf)
    if nombre_destino:
        return nombre_destino, motivo
    return None, "SIN_COINCIDENCIA"


# ============================================================
# PROCESO PRINCIPAL
# ============================================================
def renombrar_pdfs(base_dir: str, dry_run: bool = True):
    reglas_oracle = []
    oracle_disponible = True
    try:
        reglas_oracle = cargar_reglas_oracle()
        print(f"[OK] Reglas Oracle cargadas: {len(reglas_oracle)}")
    except Exception as exc:
        oracle_disponible = False
        print(f"[WARN] Oracle no disponible. Solo fallback hardcode. Detalle: {exc}")

    print(f"Algoritmo similitud: {SIMILARITY_ALGORITHM}")
    print(f"Umbral similitud: {SIMILARITY_THRESHOLD}")
    print(f"Modo simulación: {'SI' if dry_run else 'NO'}")
    print(f"Oracle disponible: {'SI' if oracle_disponible else 'NO'}")
    print(f"Delimitador reglas múltiples: {RULE_DELIMITER}\n")

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
                nombre_destino, motivo = resolver_nombre_final(
                    nombre_archivo=file, texto_pdf=texto_pdf, reglas_oracle=reglas_oracle
                )
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
