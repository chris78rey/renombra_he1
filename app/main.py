from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app.config import load_config
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    config = load_config()
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
