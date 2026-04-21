from __future__ import annotations

import re
from typing import List

from app.models import MatchResult, PdfCandidate, ValidNameRule
from app.services.pdf_service import PdfScanner


class RuleEngine:
    def __init__(self, config: dict):
        self.config = config
        self.built_in_rules = config.get("built_in_rules", [])

    def match(self, candidate: PdfCandidate, rules: List[ValidNameRule]) -> MatchResult:
        result = MatchResult(
            original_path=candidate.original_path,
            original_name=candidate.original_name,
            status="PENDIENTE",
        )

        name_norm = PdfScanner.normalize_name(candidate.original_name)

        # 1) Match directo por código ya presente en el nombre actual.
        for rule in rules:
            code_norm = PdfScanner.normalize_name(rule.final_name)
            if code_norm and code_norm in name_norm:
                result.suggested_final_name = rule.final_name
                result.confidence = 100
                result.reason = f"Coincidencia directa: el nombre actual ya contiene {rule.final_name}"
                result.details.append(result.reason)
                result.status = "LISTO"
                return result

        # 2) Reglas heredadas embebidas.
        built_in_match = self._apply_built_in_rules(candidate)
        if built_in_match:
            target = built_in_match["target"]
            if self._exists_in_rules(target, rules):
                result.suggested_final_name = target
                result.confidence = built_in_match["score"]
                result.reason = built_in_match["reason"]
                result.details.append(result.reason)
                result.status = "LISTO" if result.confidence >= 90 else "REVISAR"
                return result

        # 3) Puntaje por keywords/regex de la tabla local.
        best_score = 0
        best_rule = None
        best_reasons: List[str] = []

        for rule in rules:
            score, reasons = self._score_rule(candidate, name_norm, rule)
            if score > best_score:
                best_score = score
                best_rule = rule
                best_reasons = reasons

        if best_rule:
            result.suggested_final_name = best_rule.final_name
            result.confidence = best_score
            result.reason = "; ".join(best_reasons)
            result.details.extend(best_reasons)
            result.status = "LISTO" if best_score >= 80 else "REVISAR"
        else:
            result.status = "SIN_MATCH"
            result.reason = "No se encontró coincidencia automática"

        return result

    def _score_rule(self, candidate: PdfCandidate, name_norm: str, rule: ValidNameRule):
        score = 0
        reasons: List[str] = []

        for kw in rule.keywords_name:
            kw_norm = PdfScanner.normalize_name(kw)
            if kw_norm and kw_norm in name_norm:
                score += 30
                reasons.append(f"Keyword en nombre: {kw}")

        for kw in rule.keywords_text:
            text_kw = PdfScanner.normalize_text(kw)
            if text_kw and text_kw in candidate.normalized_text:
                score += 35
                reasons.append(f"Keyword en contenido: {kw}")

        if rule.text_regex and candidate.detected_text:
            try:
                if re.search(rule.text_regex, candidate.detected_text, flags=re.IGNORECASE):
                    score += 40
                    reasons.append(f"Regex en contenido: {rule.text_regex}")
            except re.error:
                reasons.append(f"Regex inválido en catálogo: {rule.text_regex}")

        if not candidate.extracted_ok and rule.keywords_name:
            reasons.append("No se pudo leer texto del PDF; solo se evaluó nombre")

        return score, reasons

    def _apply_built_in_rules(self, candidate: PdfCandidate):
        file_upper = candidate.original_name.upper()
        text_norm = candidate.normalized_text
        for rule in self.built_in_rules:
            rule_type = rule.get("type")
            pattern = str(rule.get("pattern", ""))
            if rule_type == "filename_contains" and pattern.upper() in file_upper:
                return rule
            if rule_type == "text_contains" and PdfScanner.normalize_text(pattern) in text_norm:
                return rule
        return None

    @staticmethod
    def _exists_in_rules(target: str, rules: List[ValidNameRule]) -> bool:
        target_upper = target.strip().upper()
        return any(r.final_name.strip().upper() == target_upper for r in rules)
