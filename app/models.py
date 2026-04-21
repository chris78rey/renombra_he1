from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class ValidNameRule:
    final_name: str
    description: str = ""
    active: bool = True
    order: int = 9999
    keywords_name: List[str] = field(default_factory=list)
    keywords_text: List[str] = field(default_factory=list)
    text_regex: str = ""


@dataclass
class PdfCandidate:
    original_path: Path
    original_name: str
    detected_text: str = ""
    normalized_text: str = ""
    extracted_ok: bool = False
    error: str = ""


@dataclass
class MatchResult:
    original_path: Path
    original_name: str
    suggested_final_name: str = ""
    final_name_manual: str = ""
    confidence: int = 0
    status: str = "PENDIENTE"
    reason: str = ""
    details: List[str] = field(default_factory=list)
    target_path: Optional[Path] = None

    def effective_final_name(self) -> str:
        return self.final_name_manual.strip() or self.suggested_final_name.strip()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["original_path"] = str(self.original_path)
        data["target_path"] = str(self.target_path) if self.target_path else ""
        return data
