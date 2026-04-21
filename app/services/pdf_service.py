from __future__ import annotations

import re
from pathlib import Path
from typing import List

import fitz

from app.models import PdfCandidate


class PdfScanner:
    def __init__(self, config: dict):
        self.extract_pages = int(config["pdf"].get("extract_pages", 5))
        self.max_chars = int(config["pdf"].get("max_chars", 50000))

    def scan_folder(self, folder: str) -> List[PdfCandidate]:
        pdfs = sorted(Path(folder).rglob("*.pdf"))
        return [self._read_pdf(path) for path in pdfs]

    def _read_pdf(self, path: Path) -> PdfCandidate:
        candidate = PdfCandidate(original_path=path, original_name=path.name)
        try:
            doc = fitz.open(path)
            chunks = []
            for idx, page in enumerate(doc):
                if idx >= self.extract_pages:
                    break
                chunks.append(page.get_text("text"))
            doc.close()
            text = "\n".join(chunks)[: self.max_chars]
            candidate.detected_text = text
            candidate.normalized_text = self.normalize_text(text)
            candidate.extracted_ok = True
            return candidate
        except Exception as exc:
            candidate.extracted_ok = False
            candidate.error = str(exc)
            return candidate

    @staticmethod
    def normalize_text(value: str) -> str:
        text = value.upper()
        text = re.sub(r"\s+", "", text)
        return text

    @staticmethod
    def normalize_name(value: str) -> str:
        name = Path(value).stem.upper()
        name = re.sub(r"[^A-Z0-9]+", "", name)
        return name
