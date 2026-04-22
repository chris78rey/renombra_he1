from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

import jaydebeapi


ORACLE_USER = os.environ.get("ORACLE_USER", "DIGITALIZACION")
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "DIGITALIZACION")
ORACLE_TARGETS = os.environ.get("ORACLE_TARGETS", "172.16.60.21:1521:prdsgh2")
ORACLE_OWNER = os.environ.get("ORACLE_OWNER", "DIGITALIZACION")
ORACLE_TABLE = os.environ.get("ORACLE_TABLE", "DIGITALIZACION")

BASE_DIR = Path(__file__).resolve().parents[2]
ORACLE_JDBC_JAR = os.environ.get(
    "ORACLE_JDBC_JAR", str(BASE_DIR / "jdbc" / "ojdbc8.jar")
)


def _parse_target(raw: str) -> Tuple[str, int, str]:
    parts = raw.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Target inválido: {raw!r} (host:puerto:SID)")
    return parts[0], int(parts[1]), parts[2]


def _jdbc_url(host: str, port: int, sid: str) -> str:
    return f"jdbc:oracle:thin:@{host}:{port}:{sid}"


def list_targets() -> List[Tuple[str, int, str]]:
    return [_parse_target(t) for t in ORACLE_TARGETS.split(",") if t.strip()]


def connect_with_failover():
    jar = Path(ORACLE_JDBC_JAR).expanduser().resolve()
    if not jar.exists():
        raise FileNotFoundError(f"No existe el JAR Oracle: {jar}")

    driver = "oracle.jdbc.OracleDriver"
    last_exc = None

    for host, port, sid in list_targets():
        url = _jdbc_url(host, port, sid)
        try:
            conn = jaydebeapi.connect(
                driver,
                url,
                [ORACLE_USER, ORACLE_PASSWORD],
                jars=[str(jar)],
            )
            conn.jconn.setAutoCommit(False)  # type: ignore
            return conn
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError(f"No se pudo conectar a Oracle. Último error: {last_exc}")


def oracle_diagnostics() -> dict:
    results = {"status": "OK", "targets": [], "errors": []}
    jar = Path(ORACLE_JDBC_JAR).expanduser().resolve()
    if not jar.exists():
        results["status"] = "ERROR"
        results["errors"].append(f"JAR no encontrado: {jar}")
        return results

    for host, port, sid in list_targets():
        try:
            conn = connect_with_failover()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT SYSDATE, BANNER FROM v$version WHERE ROWNUM = 1"
                )
                row = cur.fetchone()
                results["targets"].append({
                    "host": f"{host}:{port}:{sid}",
                    "status": "OK",
                    "version": row[1] if row else "desconocida",
                    "connected_at": str(row[0]) if row else None,
                })
            finally:
                conn.close()
            break
        except Exception as exc:
            results["errors"].append(f"{host}:{port}:{sid}: {exc}")

    if not results["targets"]:
        results["status"] = "ERROR"

    return results
