from __future__ import annotations

import os
os.environ.setdefault("JAVA_TOOL_OPTIONS", "-Doracle.jdbc.timezoneAsRegion=false -Duser.timezone=UTC")

from pathlib import Path
from typing import Any, Dict

import jaydebeapi


ORACLE_USER = os.environ.get("ORACLE_USER", "DIGITALIZACION")
ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "DIGITALIZACION")
ORACLE_TARGETS = os.environ.get("ORACLE_TARGETS", "172.16.60.21:1521:prdsgh2")
ORACLE_OWNER = os.environ.get("ORACLE_OWNER", "DIGITALIZACION")
ORACLE_TABLE = os.environ.get("ORACLE_TABLE", "DIGITALIZACION")

# JAR local del proyecto
BASE_DIR = Path(__file__).resolve().parents[2]
ORACLE_JDBC_JAR = os.environ.get("ORACLE_JDBC_JAR", str(BASE_DIR / "jdbc" / "ojdbc8.jar"))


def _parse_target(raw: str) -> tuple[str, int, str]:
    parts = raw.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Target inválido: {raw!r} (formato esperado: host:puerto:SID)")
    return parts[0], int(parts[1]), parts[2]


def _jdbc_url(host: str, port: int, sid: str) -> str:
    return f"jdbc:oracle:thin:@{host}:{port}:{sid}"


def connect_with_failover():
    jar = Path(ORACLE_JDBC_JAR).expanduser().resolve()
    if not jar.exists():
        raise FileNotFoundError(f"No existe el JAR Oracle: {jar}")

    targets = [_parse_target(t) for t in ORACLE_TARGETS.split(",")]
    driver = "oracle.jdbc.OracleDriver"
    last_exc = None

    for host, port, sid in targets:
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


def oracle_diagnostics() -> Dict[str, Any]:
    results: Dict[str, Any] = {"status": "OK", "targets": [], "errors": []}
    jar = Path(ORACLE_JDBC_JAR).expanduser().resolve()
    if not jar.exists():
        results["status"] = "ERROR"
        results["errors"].append(f"JAR no encontrado: {jar}")
        return results

    results["jar"] = str(jar)
    targets = [_parse_target(t) for t in ORACLE_TARGETS.split(",")]
    last_exc = None

    for host, port, sid in targets:
        target_str = f"{host}:{port}:{sid}"
        try:
            conn = connect_with_failover()
            try:
                cur = conn.cursor()
                cur.execute("SELECT SYSDATE, BANNER FROM v$version WHERE ROWNUM = 1")
                row = cur.fetchone()
                results["targets"].append({
                    "host": target_str,
                    "status": "OK",
                    "version": row[1] if row else "desconocida",
                    "connected_at": str(row[0]) if row else None,
                })
            finally:
                conn.close()
            break
        except Exception as exc:
            last_exc = exc
            results["errors"].append(f"{target_str}: {exc}")

    if not results["targets"]:
        results["status"] = "ERROR"
        if last_exc:
            results["errors"].append(str(last_exc))

    return results


if __name__ == "__main__":
    print(oracle_diagnostics())
