import os
import re
import fitz
import unicodedata
from dataclasses import dataclass
from typing import Optional

try:
    import jaydebeapi
except ImportError:
    jaydebeapi = None

print("=== RENOMBRADO FINAL ORACLE PRIMERO ===\n")

# ─── Configuración ─────────────────────────────────────────
DRY_RUN = True  # True = solo simula, False = renombra
ORACLE_USER = os.getenv("ORACLE_USER", "DIGITALIZACION")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "DIGITALIZACION")
ORACLE_TARGETS = os.getenv("ORACLE_TARGETS", "172.16.60.21:1521:prdsgh2")
ORACLE_JDBC_JAR = os.getenv("ORACLE_JDBC_JAR", "../jdbc/ojdbc8.jar")
RULE_DELIMITER = "|"
SIMILARITY_THRESHOLD = 0.90

# ─── Modelo ────────────────────────────────────────────────
@dataclass
class OraclePdfRule:
    nombre_pdf: str
    activo: str
    orden: int
    nota: Optional[str]
    regla_similaridad: Optional[str]
    regla_lee_documento: Optional[str]


# ─── Normalización ────────────────────────────────────────
def _norm_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.upper()
    value = re.sub(r"[^A-Z0-9\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _norm_cmp(value: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]+", "", _norm_text(value))


def _clean_noise(filename: str) -> str:
    filename = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    filename = re.sub(r"[_\-.]+", " ", filename)
    filename = re.sub(
        r"\bSCAN\b|\bDOC\b|\bDOCUMENTO\b|\bIMG\b|\bIMAGE\b",
        " ", filename, flags=re.IGNORECASE,
    )
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename


def _split_patterns(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in str(value).split(RULE_DELIMITER) if x.strip()]


# ─── Jaro-Winkler ─────────────────────────────────────────
def _jaro_similarity(s1: str, s2: str) -> float:
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
        start, end = max(0, i - match_distance), min(i + match_distance + 1, len2)
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


def _jaro_winkler(s1: str, s2: str, prefix_scale: float = 0.1) -> float:
    jaro = _jaro_similarity(s1, s2)
    prefix = 0
    for c1, c2 in zip(s1[:4], s2[:4]):
        if c1 == c2:
            prefix += 1
        else:
            break
    return jaro + (prefix * prefix_scale * (1 - jaro))


def _calc_similarity(filename: str, pattern: str) -> float:
    a = _norm_cmp(_clean_noise(filename))
    b = _norm_cmp(pattern)
    if not a or not b:
        return 0.0
    return _jaro_winkler(a, b)


# ─── Oracle ───────────────────────────────────────────────
def _parse_target(raw: str):
    parts = raw.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Target inválido: {raw} (host:puerto:SID)")
    return parts[0], int(parts[1]), parts[2]


def _jdbc_url(host: str, port: int, sid: str) -> str:
    return f"jdbc:oracle:thin:@{host}:{port}:{sid}"


def connect():
    if jaydebeapi is None:
        raise RuntimeError("Falta jaydebeapi: pip install jaydebeapi JPype1")
    jar = os.path.abspath(ORACLE_JDBC_JAR)
    if not os.path.exists(jar):
        raise FileNotFoundError(f"JAR no encontrado: {jar}")
    driver = "oracle.jdbc.OracleDriver"
    last_exc = None
    for raw in ORACLE_TARGETS.split(","):
        if not raw.strip():
            continue
        host, port, sid = _parse_target(raw)
        try:
            conn = jaydebeapi.connect(
                driver, _jdbc_url(host, port, sid),
                [ORACLE_USER, ORACLE_PASSWORD], jars=[jar],
            )
            print(f"[OK] Oracle: {host}:{port}:{sid}")
            return conn
        except Exception as exc:
            last_exc = exc
            print(f"[WARN] Falló {host}:{port}:{sid} -> {exc}")
    raise RuntimeError(f"No se pudo conectar a Oracle: {last_exc}")


def fetch_rules() -> list[OraclePdfRule]:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT NOMBRE_PDF, ACTIVO, NVL(ORDEN, 999999) AS ORDEN,
                   NOTA, REGLA_SIMILARIDAD, REGLA_LEE_DOCUMENTO
            FROM DIGITALIZACION.PDF_NOMBRES_VALIDOS
            WHERE UPPER(NVL(ACTIVO, 'S')) = 'S'
            ORDER BY NVL(ORDEN, 999999), NOMBRE_PDF
            """
        )
        rows = cur.fetchall()
        return [
            OraclePdfRule(
                nombre_pdf=str(row[0]),
                activo=str(row[1]),
                orden=int(row[2]) if row[2] is not None else 999999,
                nota=str(row[3]) if row[3] is not None else None,
                regla_similaridad=str(row[4]) if row[4] is not None else None,
                regla_lee_documento=str(row[5]) if row[5] is not None else None,
            )
            for row in rows
        ]
    finally:
        conn.close()


# ─── Resolución ────────────────────────────────────────────
_HARDCODED = {
    "PI.pdf":  ["PLANILLA"],
    "ORS.pdf": ["OTROS"],
    "002.pdf": ["NOTAS DE EVOLUCION"],
}


def resolve(filename: str, pdf_text: str, rules: list[OraclePdfRule]):
    name_cmp = _norm_cmp(_clean_noise(filename))

    # 0) Match exacto por nombre (case-insensitive)
    for rule in rules:
        rule_cmp = _norm_cmp(_clean_noise(rule.nombre_pdf))
        if rule_cmp and rule_cmp == name_cmp:
            return rule.nombre_pdf, f"EXACTO_NOMBRE:{rule.nombre_pdf}"

    # 1) Keywords hardcodeados legacy
    for rule in rules:
        for kw in _HARDCODED.get(rule.nombre_pdf, []):
            if _norm_cmp(kw) in name_cmp:
                return rule.nombre_pdf, f"KEYWORD_DURO:{kw}"

    # 2) Contenido del PDF
    text_cmp = _norm_cmp(pdf_text)
    for rule in rules:
        for pat in _split_patterns(rule.regla_lee_documento):
            pat_cmp = _norm_cmp(pat)
            if pat_cmp and pat_cmp in text_cmp:
                return rule.nombre_pdf, f"ORACLE_CONTENIDO:{pat}"

    # 3) Similitud difusa Jaro-Winkler (umbral 0.90, patrones >= 3 chars)
    best_score = -1.0
    best_rule = None
    best_pat = None
    for rule in rules:
        for pat in _split_patterns(rule.regla_similaridad):
            if len(pat) < 3:
                continue
            score = _calc_similarity(filename, pat)
            if score > best_score:
                best_score = score
                best_rule = rule
                best_pat = pat
    if best_rule and best_score >= SIMILARITY_THRESHOLD:
        return best_rule.nombre_pdf, f"ORACLE_NOMBRE:{best_pat}|score={best_score:.4f}"

    # 4) Sin coincidencia
    return None, f"SIN_COINCIDENCIA|max_score={best_score:.4f}"


# ─── PDF ──────────────────────────────────────────────────
def extract_text(path: str) -> str:
    parts = []
    doc = fitz.open(path)
    try:
        for page in doc:
            try:
                parts.append(page.get_text("text") or "")
            except Exception:
                continue
    finally:
        doc.close()
    return "\n".join(parts)


# ─── Main ────────────────────────────────────────────────
def main():
    base_dir = os.getcwd()
    try:
        rules = fetch_rules()
    except Exception as exc:
        print(f"[ERROR] No se pudieron cargar reglas de Oracle: {exc}")
        print("[INFO] Continuando sin reglas Oracle...")
        rules = []

    print(f"[OK] Reglas cargadas: {len(rules)}")
    print(f"[INFO] DRY_RUN={DRY_RUN}  umbral={SIMILARITY_THRESHOLD}\n")

    total = simulados = renombrados = sin_cambios = colisiones = errores = 0

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if not file.lower().endswith(".pdf"):
                continue
            total += 1
            path = os.path.join(root, file)
            try:
                text = extract_text(path)
                target, reason = resolve(file, text, rules)

                if not target:
                    sin_cambios += 1
                    print(f"  - Sin cambios: {file}  [{reason}]")
                    continue

                new_path = os.path.join(root, target)

                if os.path.abspath(path) == os.path.abspath(new_path):
                    sin_cambios += 1
                    print(f"  = Ya correcto: {file}  [{reason}]")
                    continue

                if os.path.exists(new_path):
                    colisiones += 1
                    print(f"  ⚠ Colisión: {file} -> {new_path}  [{reason}]")
                    continue

                if DRY_RUN:
                    simulados += 1
                    print(f"  ✓ Simulado: {file} -> {target}  [{reason}]")
                else:
                    os.rename(path, new_path)
                    renombrados += 1
                    print(f"  ✓ Renombrado: {file} -> {target}  [{reason}]")
            except Exception as exc:
                errores += 1
                print(f"  X Error: {file}  [{exc}]")

    print(f"\n=== RESUMEN ===")
    print(f"Total PDFs : {total}")
    print(f"Simulados  : {simulados}")
    print(f"Renombrados: {renombrados}")
    print(f"Sin cambios: {sin_cambios}")
    print(f"Colisiones : {colisiones}")
    print(f"Errores    : {errores}")
    print(f"\nTERMINADO")


if __name__ == "__main__":
    main()
