from __future__ import annotations

import os
os.environ.setdefault("JAVA_TOOL_OPTIONS", "-Doracle.jdbc.timezoneAsRegion=false -Duser.timezone=UTC")

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jaydebeapi


# ============================================================
# CONFIGURACION BASE
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[2]

ORACLE_TARGETS = os.environ.get("ORACLE_TARGETS", "172.16.60.21:1521:prdsgh2")
ORACLE_OWNER = os.environ.get("ORACLE_OWNER", "DIGITALIZACION")
ORACLE_TABLE = os.environ.get("ORACLE_TABLE", "PDF_NOMBRES_VALIDOS")
ORACLE_JDBC_JAR = os.environ.get(
    "ORACLE_JDBC_JAR", str(BASE_DIR / "jdbc" / "ojdbc8.jar")
)

# Credenciales por defecto opcionales (fallback si no hay sesión activa).
DEFAULT_ORACLE_USER = os.environ.get("ORACLE_USER", "")
DEFAULT_ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "")


# ============================================================
# SESION ORACLE EN MEMORIA
# ============================================================
@dataclass
class OracleSession:
    user: str
    password: str


_current_session: Optional[OracleSession] = None


def set_oracle_session(user: str, password: str) -> None:
    global _current_session
    _current_session = OracleSession(user=user.strip(), password=password)


def clear_oracle_session() -> None:
    global _current_session
    _current_session = None


def get_oracle_session() -> Optional[OracleSession]:
    return _current_session


def has_oracle_session() -> bool:
    return (
        _current_session is not None
        and bool(_current_session.user)
        and bool(_current_session.password)
    )


# ============================================================
# UTILIDADES
# ============================================================
def _parse_target(raw: str) -> Tuple[str, int, str]:
    parts = raw.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Target inválido: {raw!r} (host:puerto:SID)")
    return parts[0], int(parts[1]), parts[2]


def _jdbc_url(host: str, port: int, sid: str) -> str:
    return f"jdbc:oracle:thin:@{host}:{port}:{sid}"


def list_targets() -> List[Tuple[str, int, str]]:
    return [_parse_target(t) for t in ORACLE_TARGETS.split(",") if t.strip()]


def _resolve_credentials() -> Tuple[str, str]:
    # 1) sesión digitada por el usuario
    if has_oracle_session():
        session = get_oracle_session()
        if session:
            return session.user, session.password

    # 2) fallback a variables de entorno / defaults
    if DEFAULT_ORACLE_USER and DEFAULT_ORACLE_PASSWORD:
        return DEFAULT_ORACLE_USER, DEFAULT_ORACLE_PASSWORD

    raise RuntimeError(
        "No hay credenciales Oracle disponibles. Se requiere iniciar sesión."
    )


# ============================================================
# CONEXION
# ============================================================
def connect_with_failover():
    jar = Path(ORACLE_JDBC_JAR).expanduser().resolve()
    if not jar.exists():
        raise FileNotFoundError(f"No existe el JAR Oracle: {jar}")

    user, password = _resolve_credentials()
    driver = "oracle.jdbc.OracleDriver"
    last_exc = None

    for host, port, sid in list_targets():
        url = _jdbc_url(host, port, sid)
        try:
            conn = jaydebeapi.connect(
                driver,
                url,
                [user, password],
                jars=[str(jar)],
            )
            conn.jconn.setAutoCommit(False)  # type: ignore
            return conn
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError(
        f"No se pudo conectar a Oracle. Último error: {last_exc}"
    )


# ============================================================
# DIAGNOSTICO / PRUEBA DE LOGIN
# ============================================================
def test_oracle_login(user: str, password: str) -> Dict[str, Any]:
    if not user or not password:
        return {
            "status": "ERROR",
            "message": "Usuario y clave son obligatorios.",
        }

    jar = Path(ORACLE_JDBC_JAR).expanduser().resolve()
    if not jar.exists():
        return {
            "status": "ERROR",
            "message": f"No existe el JAR Oracle: {jar}",
        }

    driver = "oracle.jdbc.OracleDriver"
    last_exc = None

    for host, port, sid in list_targets():
        url = _jdbc_url(host, port, sid)
        try:
            conn = jaydebeapi.connect(
                driver,
                url,
                [user.strip(), password],
                jars=[str(jar)],
            )
            try:
                cur = conn.cursor()
                cur.execute("SELECT USER FROM dual")
                row = cur.fetchone()
                connected_user = row[0] if row else user.strip()
            finally:
                conn.close()

            return {
                "status": "OK",
                "message": "Conexión exitosa.",
                "user": connected_user,
                "target": f"{host}:{port}:{sid}",
            }
        except Exception as exc:
            last_exc = exc
            continue

    return {
        "status": "ERROR",
        "message": f"No se pudo iniciar sesión en Oracle. Detalle: {last_exc}",
    }


def oracle_diagnostics() -> Dict[str, Any]:
    results: Dict[str, Any] = {"status": "OK", "targets": [], "errors": []}
    jar = Path(ORACLE_JDBC_JAR).expanduser().resolve()

    if not jar.exists():
        results["status"] = "ERROR"
        results["errors"].append(f"JAR no encontrado: {jar}")
        return results

    results["jar"] = str(jar)
    results["has_session"] = has_oracle_session()
    results["owner"] = ORACLE_OWNER
    results["table"] = ORACLE_TABLE

    try:
        conn = connect_with_failover()
        try:
            cur = conn.cursor()
            cur.execute("SELECT USER FROM dual")
            row = cur.fetchone()
            results["connected_user"] = row[0] if row else None
            results["targets"].append({"status": "OK"})
        finally:
            conn.close()
    except Exception as exc:
        results["status"] = "ERROR"
        results["errors"].append(str(exc))

    return results


if __name__ == "__main__":
    print(oracle_diagnostics())
