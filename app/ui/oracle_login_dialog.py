from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.oracle_client import set_oracle_session, test_oracle_login


class OracleLoginDialog(QDialog):
    def __init__(self, config: dict | None = None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.login_result: dict | None = None

        self.setWindowTitle("Inicio de sesión Oracle")
        self.setModal(True)
        self.resize(520, 260)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel("Conexión a Oracle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #0f172a;")
        root.addWidget(title)

        subtitle = QLabel(
            "La aplicación usará el usuario y la clave digitados para consultar las reglas."
        )
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #475569;")
        root.addWidget(subtitle)

        card = QWidget()
        card.setStyleSheet(
            "QWidget { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; }"
        )
        form = QFormLayout(card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("Usuario Oracle")
        self.txt_user.setMinimumHeight(36)

        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Clave Oracle")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setMinimumHeight(36)

        form.addRow("Usuario:", self.txt_user)
        form.addRow("Clave:", self.txt_password)

        root.addWidget(card)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #334155; font-size: 12px;")
        root.addWidget(self.lbl_status)

        buttons = QHBoxLayout()
        root.addLayout(buttons)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setMinimumHeight(40)

        self.btn_login = QPushButton("Ingresar")
        self.btn_login.clicked.connect(self._do_login)
        self.btn_login.setMinimumHeight(40)
        self.btn_login.setStyleSheet(
            "QPushButton { background: #1d4ed8; color: white; font-weight: 700; "
            "border-radius: 8px; padding: 8px 14px; }"
            "QPushButton:hover { background: #1e40af; }"
        )

        buttons.addStretch()
        buttons.addWidget(btn_cancel)
        buttons.addWidget(self.btn_login)

    def _do_login(self):
        user = self.txt_user.text().strip()
        password = self.txt_password.text()

        if not user:
            QMessageBox.warning(self, "Validación", "Se requiere el usuario Oracle.")
            self.txt_user.setFocus()
            return

        if not password:
            QMessageBox.warning(self, "Validación", "Se requiere la clave Oracle.")
            self.txt_password.setFocus()
            return

        self.btn_login.setEnabled(False)
        self.lbl_status.setText("Probando conexión...")

        result = test_oracle_login(user=user, password=password)

        self.btn_login.setEnabled(True)
        self.login_result = result

        if result.get("status") == "OK":
            set_oracle_session(user=user, password=password)
            self.lbl_status.setText(
                f"Conectado como {result.get('user')} en {result.get('target')}"
            )
            self.accept()
            return

        msg = result.get("message", "No se pudo iniciar sesión.")
        self.lbl_status.setText(msg)
        QMessageBox.critical(self, "Error de conexión", msg)
