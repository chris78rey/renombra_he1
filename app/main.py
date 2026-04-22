from __future__ import annotations

import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from app.config import load_config
from app.services.oracle_client import (
    get_oracle_session,
    restore_session_from_saved_credentials,
    test_oracle_login,
)
from app.ui.main_window import MainWindow
from app.ui.oracle_login_dialog import OracleLoginDialog


def _ensure_oracle_login(config: dict) -> bool:
    # 1) intentar restaurar credenciales guardadas
    if restore_session_from_saved_credentials():
        session = get_oracle_session()
        if session:
            result = test_oracle_login(session.user, session.password)
            if result.get("status") == "OK":
                return True

    # 2) si no hay credenciales válidas, pedir login
    login = OracleLoginDialog(config=config)
    return login.exec() == OracleLoginDialog.DialogCode.Accepted


def main():
    app = QApplication(sys.argv)

    font = QFont()
    font.setPointSize(12)
    app.setFont(font)

    config = load_config()

    if not _ensure_oracle_login(config):
        sys.exit(0)

    window = MainWindow(config)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
