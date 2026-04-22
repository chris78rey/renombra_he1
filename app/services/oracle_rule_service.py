from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.services.oracle_client import connect_with_failover

# ─── Keywords hardcodeados (comportamiento actual del script) ──
# Mantienen compatibilidad con reglas fijas que antes estaban queimadas
_HARDCODED_KEYWORDS = {
    "PI.pdf":     ["PLANILLA"],
    "ORS.pdf":    ["OTROS"],
    "002.pdf":    ["NOTAS DE EVOLUCION"],
    "053.pdf":    ["053"],
    "006.pdf":    ["006"],
    "007.pdf":    ["007"],
    "017.pdf":    ["PROTOCOLO QUIRURGICO"],
    "018.pdf":    ["PROTOCOLO ANESTESICO"],
    "018A.pdf":   ["PROTOCOLO TRANSANESTESICO"],
    "113.pdf":    ["BITACORA UTI"],
    "114.pdf":    ["BITACORA NEONATAL"],
    "115.pdf":    ["BITACORA PEDIATRICA"],
    "010A.pdf":   ["LABORATORIO PEDIDO"],
    "010B.pdf":   ["LABORATORIO INFORME"],
    "012A.pdf":   ["IMAGEN PEDIDO"],
    "012B.pdf":   ["IMAGEN INFORME"],
    "033.pdf":    ["ODONTOLOGIA"],
    "013A.pdf":   ["013A"],
    "013B.pdf":   ["013B"],
    "08.pdf":     ["FORMULARIO 08"],
    "FSCS.pdf":   ["FSCS"],
    "FSICS.pdf":  ["FSICS"],
    "FRDCS.pdf":  ["FRDCS"],
    "ANX2.pdf":   ["ANEXO 2"],
    "HR.pdf":     ["HISTORIA RADIOLOGICA"],
    "RHD.pdf":    ["RHD"],
    "IMT.pdf":    ["IMT"],
    "CEC.pdf":    ["CEC"],
    "RAD.pdf":    ["RAD"],
    "ITS.pdf":    ["ITS"],
    "RVD.pdf":    ["RVD"],
    "119.pdf":    ["119"],
    "PTR.pdf":    ["PTR"],
    "RTR.pdf":    ["RTR"],
    "CV.pdf":     ["CODIGO VALIDACION"],
    "AES.pdf":    ["ACTA ENTREGA"],
    "CC.pdf":     ["COBERTURA"],
}

# ─── Configuración hardcodeada ───────────────────────────────
SIMILARITY_THRESHOLD = 0.85
# ─────────────────────────────────────────────────────────────


@dataclass
class OraclePdfRule:
    nombre_pdf: str
    activo: str
    orden: int
    nota: Optional[str]
    regla_similaridad: Optional[str]
    regla_lee_documento: Optional[str]


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
    """Elimina ruido de nombres de archivo para comparación limpia."""
    filename = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    filename = re.sub(
        r"\bSCAN\b|\bDOC\b|\bDOCUMENTO\b|\bIMG\b|\bIMAGE\b", " ", filename, flags=re.IGNORECASE
    )
    filename = re.sub(r"\b\d{1,8}\b", " ", filename)
    filename = re.sub(r"[_\-.]+", " ", filename)
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename


# ─── Algoritmos de similitud ─────────────────────────────────
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


def _calcular_similitud(nombre_archivo: str, patron_regla: str) -> float:
    a = _normalize_compact(_clean_noise(nombre_archivo))
    b = _normalize_compact(patron_regla)
    if not a or not b:
        return 0.0
    return _jaro_winkler_similarity(a, b)


# ─── Fetch desde Oracle ──────────────────────────────────────
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
            WHERE ACTIVO = 'S'
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


# ─── Resolución ────────────────────────────────────────────────
def resolve_pdf_name_from_rules(
    original_filename: str,
    pdf_text: str,
    rules: List[OraclePdfRule],
) -> Tuple[Optional[str], str]:
    """
    Evalúa reglas en orden de prioridad:
      1. CONTENIDO  → REGLA_LEE_DOCUMENTO (subcadena normalizada)
      2. SIMILITUD  → REGLA_SIMILARIDAD  (Jaro-Winkler, umbral 0.90)

    Retorna (nombre_destino, motivo) o (None, "sin_coincidencia")
    """
    norm_name = _normalize_text(original_filename)
    norm_name_cmp = _normalize_compact(original_filename)
    norm_text = _normalize_text(pdf_text)
    norm_text_cmp = _normalize_compact(pdf_text)

    # PRIORIDAD 0: keywords hardcodeados (compatibilidad con script original)
    name_clean_cmp = _normalize_compact(_clean_noise(original_filename))
    for rule in rules:
        for kw in _HARDCODED_KEYWORDS.get(rule.nombre_pdf, []):
            if _normalize_compact(kw) in name_clean_cmp:
                return rule.nombre_pdf, f"keyword_duro:{kw}"

    # PRIORIDAD 1: contenido del PDF
    for rule in rules:
        token = (rule.regla_lee_documento or "").strip()
        if not token:
            continue
        token_cmp = _normalize_compact(token)
        if not token_cmp:
            continue
        if token_cmp in norm_text_cmp:
            return rule.nombre_pdf, f"contenido_pdf:{token}"

    # PRIORIDAD 2: similitud difusa del nombre
    best_score = -1.0
    best_rule: Optional[OraclePdfRule] = None

    for rule in rules:
        token = (rule.regla_similaridad or "").strip()
        if not token:
            continue
        score = _calcular_similitud(original_filename, token)
        if score > best_score:
            best_score = score
            best_rule = rule

    if best_rule is not None and best_score >= SIMILARITY_THRESHOLD:
        return (
            best_rule.nombre_pdf,
            f"similitud:{best_rule.regla_similaridad}|score={best_score:.4f}|umbral={SIMILARITY_THRESHOLD:.4f}",
        )

    return None, f"sin_coincidencia|max_score={best_score:.4f}"
