from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from app.models import MatchResult


class RenameService:
    def __init__(self, config: dict):
        self.config = config

    def backup_folder(self, source_folder: str) -> Path:
        src = Path(source_folder)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = src.parent / f"{src.name}_BACKUP_{stamp}"
        shutil.copytree(src, backup_dir)
        return backup_dir

    def preview_targets(self, results: Iterable[MatchResult]) -> List[MatchResult]:
        updated = list(results)
        grouped: dict[tuple[Path, str], List[MatchResult]] = {}

        for item in updated:
            final_name = item.effective_final_name()
            if not final_name:
                item.status = "SIN_DESTINO"
                item.reason = (item.reason + " | ").strip(" | ") + "No tiene nombre final"
                continue

            key = (item.original_path.parent, final_name.upper())
            grouped.setdefault(key, []).append(item)

        reserved: set[str] = set()
        for (folder, _final_name_upper), items in grouped.items():
            final_name = items[0].effective_final_name()
            if len(items) == 1:
                item = items[0]
                item.target_path = self._build_available_target(folder, final_name, reserved)
                reserved.add(str(item.target_path).upper())
                continue

            for index, item in enumerate(items, start=1):
                item.target_path = self._build_numbered_target(folder, final_name, index, reserved)
                reserved.add(str(item.target_path).upper())

        return updated

    def apply(self, results: Iterable[MatchResult]) -> List[MatchResult]:
        processed: List[MatchResult] = []
        for item in results:
            target = item.target_path
            if not target:
                item.status = "ERROR"
                item.reason = (item.reason + " | ").strip(" | ") + "Target no calculado"
                processed.append(item)
                continue

            if item.original_path.resolve() == target.resolve():
                item.status = "YA_OK"
                processed.append(item)
                continue

            try:
                item.original_path.rename(target)
                item.status = "RENOMBRADO"
                processed.append(item)
            except Exception as exc:
                item.status = "ERROR"
                item.reason = (item.reason + " | ").strip(" | ") + str(exc)
                processed.append(item)
        return processed

    def export_audit(self, results: Iterable[MatchResult], folder: str) -> tuple[Path, Path]:
        base = Path(folder)
        csv_path = base / self.config["output"]["audit_csv_name"]
        json_path = base / self.config["output"]["report_json_name"]

        fieldnames = [
            "original_path",
            "original_name",
            "suggested_final_name",
            "final_name_manual",
            "confidence",
            "status",
            "reason",
            "target_path",
            "details",
        ]

        with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for item in results:
                row = item.to_dict()
                row["details"] = " | ".join(item.details)
                writer.writerow(row)

        with json_path.open("w", encoding="utf-8") as fh:
            json.dump([item.to_dict() for item in results], fh, ensure_ascii=False, indent=2)

        return csv_path, json_path

    @staticmethod
    def _build_available_target(folder: Path, final_name: str, reserved: set[str]) -> Path:
        target = folder / final_name
        if not target.exists() and str(target).upper() not in reserved:
            return target

        stem = target.stem
        suffix = target.suffix
        idx = 1
        while True:
            candidate = folder / f"{stem}_{idx}{suffix}"
            if not candidate.exists() and str(candidate).upper() not in reserved:
                return candidate
            idx += 1

    @staticmethod
    def _build_numbered_target(folder: Path, final_name: str, index: int, reserved: set[str]) -> Path:
        target = folder / final_name
        stem = target.stem
        suffix = target.suffix
        idx = index
        while True:
            candidate = folder / f"{stem}_{idx}{suffix}"
            if not candidate.exists() and str(candidate).upper() not in reserved:
                return candidate
            idx += 1
