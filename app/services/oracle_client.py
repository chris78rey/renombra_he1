from __future__ import annotations

import base64
import os

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jaydebeapi
import jpype
from PyQt6.QtCore import QSettings

from app.config import resource_path


# ============================================================
# CONFIGURACION BASE
# ============================================================
ORACLE_TARGETS = os.environ.get("ORACLE_TARGETS", "172.16.60.21:1521:prdsgh2")
ORACLE_OWNER = os.environ.get("ORACLE_OWNER", "DIGITALIZACION")
ORACLE_TABLE = os.environ.get("ORACLE_TABLE", "PDF_NOMBRES_VALIDOS")
ORACLE_JDBC_JAR = os.environ.get(
    "ORACLE_JDBC_JAR", str(resource_path("jdbc", "ojdbc8.jar"))
)

APP_ORG = "Hospital"
APP_NAME = "RenombradorPDFHospitalario"

DEFAULT_ORACLE_USER = os.environ.get("ORACLE_USER", "")
DEFAULT_ORACLE_PASSWORD = os.environ.get("ORACLE_PASSWORD", "")


# ============================================================
# SESION EN MEMORIA
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
# PERSISTENCIA LOCAL DE CREENCIALES (QSettings + Base64)
# ============================================================
def _settings() -> QSettings:
    return QSettings(APP_ORG, APP_NAME)


def _b64_encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _b64_decode(value: str) -> str:
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


def _jvm_path() -> Path:
    embedded = resource_path("runtime", "jre", "bin", "server", "jvm.dll")
    if embedded.exists():
        return embedded

    try:
        default_jvm = jpype.getDefaultJVMPath()
    except Exception:
        default_jvm = ""
    return Path(default_jvm) if default_jvm else embedded


def _jdbc_jar_path() -> Path:
    return Path(ORACLE_JDBC_JAR).expanduser().resolve()


def _ensure_jvm_started(jar: Optional[Path] = None) -> None:
    jar_path = (jar or _jdbc_jar_path()).resolve()

    if jpype.isJVMStarted():
        if jar_path.exists():
            jpype.addClassPath(str(jar_path))
        return

    jvm_path = _jvm_path()
    if not jvm_path.exists():
        raise FileNotFoundError(
            f"No se encontro la JVM para JPype: {jvm_path}"
        )

    jpype.startJVM(
        str(jvm_path),
        f"-Djava.class.path={jar_path}",
        "-Doracle.jdbc.timezoneAsRegion=false",
        "-Duser.timezone=UTC",
        convertStrings=True,
    )


def save_remembered_credentials(user: str, password: str) -> None:
    s = _settings()
    s.setValue("oracle/remember_enabled", True)
    s.setValue("oracle/user", user.strip())
    s.setValue("oracle/password_b64", _b64_encode(password))
    s.sync()


def load_remembered_credentials() -> Optional[OracleSession]:
    s = _settings()
    remember_enabled = s.value("oracle/remember_enabled", False, type=bool)
    if not remember_enabled:
        return None

    user = s.value("oracle/user", "", type=str).strip()
    password_b64 = s.value("oracle/password_b64", "", type=str).strip()

    if not user or not password_b64:
        return None

    try:
        password = _b64_decode(password_b64)
    except Exception:
        return None

    return OracleSession(user=user, password=password)


def clear_remembered_credentials() -> None:
    s = _settings()
    s.remove("oracle/remember_enabled")
    s.remove("oracle/user")
    s.remove("oracle/password_b64")
    s.sync()


def restore_session_from_saved_credentials() -> bool:
    creds = load_remembered_credentials()
    if not creds:
        return False
    set_oracle_session(creds.user, creds.password)
    return True


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
    # 1) sesión activa en memoria
    if has_oracle_session():
        session = get_oracle_session()
        if session:
            return session.user, session.password

    # 2) credenciales guardadas localmente
    remembered = load_remembered_credentials()
    if remembered:
        set_oracle_session(remembered.user, remembered.password)
        return remembered.user, remembered.password

    # 3) fallback a variables de entorno
    if DEFAULT_ORACLE_USER and DEFAULT_ORACLE_PASSWORD:
        return DEFAULT_ORACLE_USER, DEFAULT_ORACLE_PASSWORD

    raise RuntimeError("No hay credenciales Oracle disponibles.")


# ============================================================
# CONEXION
# ============================================================
def connect_with_failover():
    jar = _jdbc_jar_path()
    if not jar.exists():
        raise FileNotFoundError(f"No existe el JAR Oracle: {jar}")

    _ensure_jvm_started(jar)

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
# TEST DE LOGIN
# ============================================================
def test_oracle_login(user: str, password: str) -> Dict[str, Any]:
    if not user or not password:
        return {
            "status": "ERROR",
            "message": "Usuario y clave son obligatorios.",
        }

    jar = _jdbc_jar_path()
    if not jar.exists():
        return {
            "status": "ERROR",
            "message": f"No existe el JAR Oracle: {jar}",
        }

    try:
        _ensure_jvm_started(jar)
        jpype.JClass("oracle.jdbc.OracleDriver")
    except Exception as exc:
        return {
            "status": "ERROR",
            "message": f"No se pudo cargar el driver JDBC Oracle: {exc}",
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
    jar = _jdbc_jar_path()

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
