
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

    def _extract_seed_rows(self, sql_path: Path) -> list[tuple[str, str, int, str]]:
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
        return rows

    def seed_from_sql_file(self, sql_path: Path) -> int:
        rows = self._extract_seed_rows(sql_path)
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

    def base_name_set(self) -> set[str]:
        if not self.seed_sql_path.exists():
            return set()
        return {row[0].strip().upper() for row in self._extract_seed_rows(self.seed_sql_path)}

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
        base_names = self.base_name_set()
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
        result = []
        for row in rows:
            data = dict(row)
            data["es_base"] = "S" if data["nombre_pdf"].strip().upper() in base_names else "N"
            result.append(data)
        return result

    def replace_catalog_rows(self, rows: list[dict]) -> None:
        normalized_rows = []
        seen_names = set()
        base_names = self.base_name_set()
        current_rows = {row["nombre_pdf"].strip().upper(): row for row in self.list_catalog_rows()}
        seed_rows = {}
        if self.seed_sql_path.exists():
            seed_rows = {row[0].strip().upper(): row for row in self._extract_seed_rows(self.seed_sql_path)}

        for index, row in enumerate(rows, start=1):
            nombre_pdf = str(row.get("nombre_pdf", "")).strip()
            if not nombre_pdf:
                raise ValueError(f"La fila {index} no tiene nombre PDF")

            key = nombre_pdf.upper()
            if key in seen_names:
                raise ValueError(f"Nombre PDF duplicado: {nombre_pdf}")
            seen_names.add(key)

            activo = str(row.get("activo", "S")).strip().upper() or "S"
            if activo not in {"S", "N"}:
                raise ValueError(f"Activo debe ser S o N en {nombre_pdf}")

            try:
                orden = int(row.get("orden", 9999) or 9999)
            except ValueError as exc:
                raise ValueError(f"Orden invalido en {nombre_pdf}") from exc

            normalized_rows.append(
                {
                    "nombre_pdf": nombre_pdf,
                    "activo": activo,
                    "orden": orden,
                    "nota": str(row.get("nota", "")).strip(),
                    "palabras_nombre": str(row.get("palabras_nombre", "")).strip(),
                    "palabras_texto": str(row.get("palabras_texto", "")).strip(),
                    "regex_texto": str(row.get("regex_texto", "")).strip(),
                }
            )

        for base_name in sorted(base_names):
            if base_name in seen_names:
                continue
            base_row = current_rows.get(base_name)
            seed_row = seed_rows.get(base_name)
            if not base_row and not seed_row:
                continue
            normalized_rows.append(
                {
                    "nombre_pdf": str(base_row.get("nombre_pdf") if base_row else seed_row[0]).strip(),
                    "activo": str(base_row.get("activo") if base_row else seed_row[1]).strip().upper() or "S",
                    "orden": int(base_row.get("orden") if base_row else seed_row[2] or 9999),
                    "nota": str(base_row.get("nota") if base_row else seed_row[3]).strip(),
                    "palabras_nombre": str(base_row.get("palabras_nombre", "") if base_row else "").strip(),
                    "palabras_texto": str(base_row.get("palabras_texto", "") if base_row else "").strip(),
                    "regex_texto": str(base_row.get("regex_texto", "") if base_row else "").strip(),
                }
            )

        if not normalized_rows:
            raise ValueError("Debe existir al menos una regla en el catalogo")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM app_keywords_reglas")
            conn.execute("DELETE FROM pdf_nombres_validos")
            conn.executemany(
                '''
                INSERT INTO pdf_nombres_validos (nombre_pdf, activo, orden, nota)
                VALUES (:nombre_pdf, :activo, :orden, :nota)
                ''',
                normalized_rows,
            )
            conn.executemany(
                '''
                INSERT INTO app_keywords_reglas (
                    nombre_pdf,
                    palabras_nombre,
                    palabras_texto,
                    regex_texto,
                    activo
                )
                VALUES (
                    :nombre_pdf,
                    :palabras_nombre,
                    :palabras_texto,
                    :regex_texto,
                    :activo
                )
                ''',
                normalized_rows,
            )
            conn.commit()

    @staticmethod
    def _split_keywords(value: str) -> List[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.replace(";", "|").split("|") if item.strip()]
