from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from app.models import ValidNameRule


class ExcelRuleLoader:
    def __init__(self, config: dict):
        self.config = config
        self.columns_cfg = config["excel"]["columns"]
        self.sheet_name = config["excel"].get("sheet_name", 0)

    def load_rules(self, excel_path: str) -> List[ValidNameRule]:
        df = pd.read_excel(excel_path, sheet_name=self.sheet_name)
        df.columns = [str(c).strip() for c in df.columns]

        final_name_col = self._find_column(df, "final_name")
        if not final_name_col:
            raise ValueError(
                "No se encontró la columna obligatoria del nombre final. "
                "Columnas esperadas: "
                f"{self.columns_cfg['final_name']}"
            )

        description_col = self._find_column(df, "description")
        active_col = self._find_column(df, "active")
        order_col = self._find_column(df, "order")
        keywords_name_col = self._find_column(df, "keywords_name")
        keywords_text_col = self._find_column(df, "keywords_text")
        text_regex_col = self._find_column(df, "text_regex")

        rules: List[ValidNameRule] = []

        for _, row in df.iterrows():
            final_name = self._clean_str(row.get(final_name_col))
            if not final_name:
                continue

            active = True
            if active_col:
                active_raw = self._clean_str(row.get(active_col)).upper()
                active = active_raw not in {"N", "NO", "0", "FALSE", "INACTIVO"}

            rule = ValidNameRule(
                final_name=final_name,
                description=self._clean_str(row.get(description_col)) if description_col else "",
                active=active,
                order=self._safe_int(row.get(order_col), default=9999) if order_col else 9999,
                keywords_name=self._split_keywords(row.get(keywords_name_col)) if keywords_name_col else [],
                keywords_text=self._split_keywords(row.get(keywords_text_col)) if keywords_text_col else [],
                text_regex=self._clean_str(row.get(text_regex_col)) if text_regex_col else "",
            )
            rules.append(rule)

        rules.sort(key=lambda x: (x.order, x.final_name))
        return [r for r in rules if r.active]

    def _find_column(self, df: pd.DataFrame, field_name: str) -> Optional[str]:
        aliases = self.columns_cfg[field_name]
        normalized = {self._normalize(c): c for c in df.columns}
        for alias in aliases:
            found = normalized.get(self._normalize(alias))
            if found:
                return found
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return str(value).strip().upper().replace(" ", "_")

    @staticmethod
    def _clean_str(value) -> str:
        if value is None:
            return ""
        if pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _split_keywords(value) -> List[str]:
        raw = ExcelRuleLoader._clean_str(value)
        if not raw:
            return []
        return [item.strip() for item in raw.replace(";", "|").split("|") if item.strip()]

    @staticmethod
    def _safe_int(value, default: int = 9999) -> int:
        try:
            if pd.isna(value):
                return default
            return int(value)
        except Exception:
            return default
