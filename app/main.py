
from __future__ import annotations

import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from app.config import load_config
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    font = QFont()
    font.setPointSize(12)
    app.setFont(font)
    config = load_config()
    window = MainWindow(config)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
