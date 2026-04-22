from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.services.oracle_client import connect_with_failover

RULE_DELIMITER = "|"
SIMILARITY_THRESHOLD = 0.75
SIMILARITY_ALGORITHM = "JARO_WINKLER"


@dataclass
class OraclePdfRule:
    nombre_pdf: str
    activo: str
    orden: int
    nota: Optional[str]
    regla_similaridad: Optional[str]
    regla_lee_documento: Optional[str]


# ─── Normalización ────────────────────────────────────────
def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.upper()
    value = re.sub(r"[^A-Z0-9\s]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _normalize_compact(value: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]+", "", _normalize_text(value))


def _clean_noise(filename: str) -> str:
    filename = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    filename = re.sub(r"[_\-.]+", " ", filename)
    filename = re.sub(
        r"\bSCAN\b|\bDOC\b|\bDOCUMENTO\b|\bIMG\b|\bIMAGE\b",
        " ",
        filename,
        flags=re.IGNORECASE,
    )
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename


def _split_patterns(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = [item.strip() for item in str(value).split(RULE_DELIMITER)]
    return [item for item in parts if item]


# ─── Similitud difusa ──────────────────────────────────────
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


def _jaro_winkler_similarity(s1: str, s2: str, prefix_scale: float = 0.1) -> float:
    jaro = _jaro_similarity(s1, s2)
    prefix = 0
    for c1, c2 in zip(s1[:4], s2[:4]):
        if c1 == c2:
            prefix += 1
        else:
            break
    return jaro + (prefix * prefix_scale * (1 - jaro))


def _levenshtein_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a:
        return 0.0
    if not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            ins = curr[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return 1.0 - (prev[-1] / max(len(a), len(b)))


def _calculate_similarity(filename: str, pattern: str) -> float:
    a = _normalize_compact(_clean_noise(filename))
    b = _normalize_compact(pattern)
    if not a or not b:
        return 0.0
    if SIMILARITY_ALGORITHM == "LEVENSHTEIN":
        return _levenshtein_ratio(a, b)
    return _jaro_winkler_similarity(a, b)





# ─── Fetch desde Oracle ───────────────────────────────────
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
def resolve_pdf_name_from_rules(
    original_filename: str,
    pdf_text: str,
    rules: List[OraclePdfRule],
) -> Tuple[Optional[str], str]:
    """
    Orden de evaluación:
      0. Keywords hardcodeados (compatibilidad legado)
      1. REGLA_LEE_DOCUMENTO (contenido del PDF)
      2. REGLA_SIMILARIDAD (similitud Jaro-Winkler, umbral 0.75)
      3. Sin coincidencia
    """
def resolve_pdf_name_from_rules(
    original_filename: str,
    pdf_text: str,
    rules: List[OraclePdfRule],
) -> Tuple[Optional[str], str]:
    """
    Orden de evaluación (Oracle único):
      0. Match exacto por nombre (case-insensitive)
      1. REGLA_LEE_DOCUMENTO (contenido del PDF)
      2. REGLA_SIMILARIDAD (Jaro-Winkler >= 0.75, patrones >= 3 chars)
      3. Sin coincidencia → no se renombra
    """
    norm_text_cmp = _normalize_compact(pdf_text)
    name_cmp = _normalize_compact(_clean_noise(original_filename))

    # PRIORIDAD 0: match exacto del nombre (case-insensitive)
    for rule in rules:
        rule_cmp = _normalize_compact(_clean_noise(rule.nombre_pdf))
        if rule_cmp and rule_cmp == name_cmp:
            return rule.nombre_pdf, f"EXACTO_NOMBRE:{rule.nombre_pdf}"



    # PRIORIDAD 2: contenido del PDF
    for rule in rules:
        for pattern in _split_patterns(rule.regla_lee_documento):
            pattern_cmp = _normalize_compact(pattern)
            if pattern_cmp and pattern_cmp in norm_text_cmp:
                return rule.nombre_pdf, f"ORACLE_CONTENIDO:{pattern}"

    # PRIORIDAD 3: similitud difusa del nombre (Jaro-Winkler)
    best_score = -1.0
    best_rule: Optional[OraclePdfRule] = None
    best_pattern: Optional[str] = None

    for rule in rules:
        for pattern in _split_patterns(rule.regla_similaridad):
            # Ignorar patrones demasiado cortos
            if len(pattern) < 3:
                continue
            score = _calculate_similarity(original_filename, pattern)
            if score > best_score:
                best_score = score
                best_rule = rule
                best_pattern = pattern

    if best_rule is not None and best_score >= SIMILARITY_THRESHOLD:
        return (
            best_rule.nombre_pdf,
            f"ORACLE_NOMBRE:{best_pattern}|score={best_score:.4f}|umbral={SIMILARITY_THRESHOLD:.4f}",
        )

    return None, f"SIN_COINCIDENCIA|max_score={best_score:.4f}"

