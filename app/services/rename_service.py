from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.models import PdfCandidate
from app.services.oracle_rule_service import (
    OraclePdfRule,
    fetch_oracle_pdf_rules,
    resolve_pdf_name_from_rules,
)


@dataclass
class RenameResult:
    original_path: str
    target_path: str | None
    status: str
    reason: str


def resolve_candidate_name(
    candidate: PdfCandidate,
    rules: List[OraclePdfRule],
) -> tuple[str | None, str]:
    """Oracle primero → hardcode legado después."""
    target_name, reason = resolve_pdf_name_from_rules(
        original_filename=candidate.original_name,
        pdf_text=candidate.detected_text or "",
        rules=rules,
    )
    if target_name:
        return target_name, reason

    # Fallback hardcode legado
    text_cmp = candidate.normalized_text or ""
    name_upper = (candidate.original_name or "").upper()

    if "NOTASDEEVOLUCION" in text_cmp:
        return "002.pdf", "HARDCODE:NOTASDEEVOLUCION"
    if "OTROS" in name_upper:
        return "ORS.pdf", "HARDCODE:OTROS"
    if "PLANILLA" in name_upper:
        return "PI.pdf", "HARDCODE:PLANILLA"

    return None, "SIN_COINCIDENCIA"


def apply_rename_plan(
    candidates: List[PdfCandidate],
    dry_run: bool = True,
) -> List[RenameResult]:
    """
    Oracle primero → hardcode fallback.
    dry_run=True por seguridad.
    No sobrescribe archivos existentes.
    """
    results: List[RenameResult] = []
    rules = fetch_oracle_pdf_rules()

    for candidate in candidates:
        original_path = str(candidate.original_path)

        if not candidate.extracted_ok:
            results.append(
                RenameResult(
                    original_path=original_path,
                    target_path=None,
                    status="ERROR_LECTURA_PDF",
                    reason=candidate.error or "No se pudo leer el PDF",
                )
            )
            continue

        target_name, reason = resolve_candidate_name(candidate, rules)

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

        target_path = str(candidate.original_path.parent / target_name)

        if str(candidate.original_path) == target_path:
            results.append(
                RenameResult(
                    original_path=original_path,
                    target_path=target_path,
                    status="YA_CORRECTO",
                    reason=reason,
                )
            )
            continue

        if Path(target_path).exists():
            results.append(
                RenameResult(
                    original_path=original_path,
                    target_path=target_path,
                    status="COLISION",
                    reason=f"{reason}|DESTINO_EXISTE",
                )
            )
            continue

        if not dry_run:
            candidate.original_path.rename(Path(target_path))

        results.append(
            RenameResult(
                original_path=original_path,
                target_path=target_path,
                status="SIMULADO" if dry_run else "RENOMBRADO",
                reason=reason,
            )
        )

    return results
