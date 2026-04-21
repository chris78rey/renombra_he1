
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import List

from app.models import ValidNameRule


class SQLiteRuleRepository:
    def __init__(self, config: dict):
        self.config = config
        self.base_dir = Path(__file__).resolve().parents[2]
        self.db_cfg = config.get("database", {})
        self.db_path = self.base_dir / self.db_cfg.get("sqlite_path", "config/catalogo_reglas.db")
        self.seed_sql_path = self.base_dir / self.db_cfg.get("seed_sql_path", "datos_base/nombres_validos.sql")

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS pdf_nombres_validos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_pdf TEXT NOT NULL UNIQUE,
                    activo TEXT NOT NULL DEFAULT 'S',
                    orden INTEGER NOT NULL DEFAULT 9999,
                    nota TEXT DEFAULT '',
                    created_at_utc TEXT DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS app_keywords_reglas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_pdf TEXT NOT NULL,
                    palabras_nombre TEXT DEFAULT '',
                    palabras_texto TEXT DEFAULT '',
                    regex_texto TEXT DEFAULT '',
                    activo TEXT NOT NULL DEFAULT 'S',
                    UNIQUE(nombre_pdf)
                )
                '''
            )
            conn.execute(
                '''
                CREATE VIEW IF NOT EXISTS vw_reglas AS
                SELECT
                    p.nombre_pdf,
                    p.activo,
                    p.orden,
                    COALESCE(p.nota, '') AS nota,
                    COALESCE(k.palabras_nombre, '') AS palabras_nombre,
                    COALESCE(k.palabras_texto, '') AS palabras_texto,
                    COALESCE(k.regex_texto, '') AS regex_texto
                FROM pdf_nombres_validos p
                LEFT JOIN app_keywords_reglas k
                    ON k.nombre_pdf = p.nombre_pdf
                '''
            )
            conn.commit()

        if self.count_valid_names() == 0 and self.seed_sql_path.exists():
            self.seed_from_sql_file(self.seed_sql_path)

    def count_valid_names(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM pdf_nombres_validos").fetchone()
            return int(row[0] or 0)

    def seed_from_sql_file(self, sql_path: Path) -> int:
        content = sql_path.read_text(encoding="utf-8", errors="ignore")
        pattern = re.compile(
            r"Values\s*\(\s*'(?P<nombre>[^']+)'\s*,\s*'(?P<activo>[^']+)'\s*,\s*(?P<orden>\d+)\s*,\s*'(?P<nota>[^']*)'",
            flags=re.IGNORECASE | re.MULTILINE,
        )
        rows = []
        for match in pattern.finditer(content):
            rows.append(
                (
                    match.group("nombre").strip(),
                    match.group("activo").strip().upper(),
                    int(match.group("orden")),
                    match.group("nota").strip(),
                )
            )
        if not rows:
            raise ValueError(f"No se pudieron extraer registros desde {sql_path}")
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                '''
                INSERT OR IGNORE INTO pdf_nombres_validos (nombre_pdf, activo, orden, nota)
                VALUES (?, ?, ?, ?)
                ''',
                rows,
            )
            conn.commit()
        return len(rows)

    def load_rules(self) -> List[ValidNameRule]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                '''
                SELECT nombre_pdf, activo, orden, nota, palabras_nombre, palabras_texto, regex_texto
                FROM vw_reglas
                WHERE UPPER(COALESCE(activo, 'S')) = 'S'
                ORDER BY orden, nombre_pdf
                '''
            ).fetchall()

        rules: List[ValidNameRule] = []
        for row in rows:
            rules.append(
                ValidNameRule(
                    final_name=row["nombre_pdf"].strip(),
                    description=(row["nota"] or "").strip(),
                    active=(row["activo"] or "S").strip().upper() == "S",
                    order=int(row["orden"] or 9999),
                    keywords_name=self._split_keywords(row["palabras_nombre"] or ""),
                    keywords_text=self._split_keywords(row["palabras_texto"] or ""),
                    text_regex=(row["regex_texto"] or "").strip(),
                )
            )
        return rules

    def list_catalog_rows(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                '''
                SELECT
                    nombre_pdf,
                    activo,
                    orden,
                    nota,
                    COALESCE(palabras_nombre, '') AS palabras_nombre,
                    COALESCE(palabras_texto, '') AS palabras_texto,
                    COALESCE(regex_texto, '') AS regex_texto
                FROM vw_reglas
                ORDER BY orden, nombre_pdf
                '''
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _split_keywords(value: str) -> List[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.replace(";", "|").split("|") if item.strip()]
