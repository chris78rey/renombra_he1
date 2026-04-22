from __future__ import annotations

import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from app.config import load_config
from app.ui.main_window import MainWindow
from app.ui.oracle_login_dialog import OracleLoginDialog


def main():
    app = QApplication(sys.argv)

    font = QFont()
    font.setPointSize(12)
    app.setFont(font)

    config = load_config()

    login = OracleLoginDialog(config=config)
    if login.exec() != OracleLoginDialog.DialogCode.Accepted:
        sys.exit(0)

    window = MainWindow(config)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
