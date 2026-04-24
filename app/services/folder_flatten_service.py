from __future__ import annotations

import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


TARGET_FOLDER_WORDS = {
    "SOLICITUD",
    "SOLICITUDES",
    "RESULTADO",
    "RESULTADOS",
}


@dataclass
class FlattenResult:
    moved: int = 0
    removed_dirs: int = 0
    skipped_dirs: int = 0
    errors: list[str] = field(default_factory=list)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.upper()
    value = re.sub(r"[^A-Z0-9]+", "", value)
    return value.strip()


def _is_target_folder(folder_name: str) -> bool:
    normalized = _normalize(folder_name)
    if not normalized:
        return False

    if any(word in normalized for word in TARGET_FOLDER_WORDS):
        return True

    typo_patterns = (
        "SOLICITUDE",
        "SOLICITU",
        "RESULYTADO",
        "RESULYTADOS",
        "RESUTADO",
        "RESUTADOS",
    )
    return any(pattern in normalized for pattern in typo_patterns)


def _unique_target_path(parent: Path, original_name: str, source_folder: Path) -> Path:
    candidate = parent / original_name
    if not candidate.exists():
        return candidate

    stem = Path(original_name).stem
    suffix = Path(original_name).suffix or ".pdf"
    folder_tag = _normalize(source_folder.name) or "SUBCARPETA"

    seq = 1
    while True:
        safe_name = f"__aplanado__{folder_tag}_{seq:03d}__{stem}{suffix}"
        candidate = parent / safe_name
        if not candidate.exists():
            return candidate
        seq += 1


def flatten_request_result_folders(base_folder: str | Path) -> FlattenResult:
    """
    Move PDFs from folders named like solicitudes/resultados to their parent.
    """
    base = Path(base_folder).resolve()
    result = FlattenResult()

    if not base.exists() or not base.is_dir():
        result.errors.append(f"La carpeta base no existe o no es valida: {base}")
        return result

    target_dirs = sorted(
        [
            path
            for path in base.rglob("*")
            if path.is_dir() and path != base and _is_target_folder(path.name)
        ],
        key=lambda p: len(p.parts),
        reverse=True,
    )

    for folder in target_dirs:
        try:
            parent = folder.parent
            pdfs = sorted(
                path
                for path in folder.rglob("*")
                if path.is_file() and path.suffix.lower() == ".pdf"
            )

            for pdf in pdfs:
                target = _unique_target_path(parent, pdf.name, folder)
                shutil.move(str(pdf), str(target))
                result.moved += 1

            try:
                folder.rmdir()
                result.removed_dirs += 1
            except OSError:
                result.skipped_dirs += 1

        except Exception as exc:
            result.errors.append(f"{folder}: {exc}")

    return result
