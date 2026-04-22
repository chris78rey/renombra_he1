from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.oracle_rule_service import (
    OraclePdfRule,
    fetch_oracle_pdf_rules,
    resolve_pdf_name_from_rules,
)
from app.services.pdf_service import PdfScanner


class CreditsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Autores")
        self.resize(760, 520)

        credits = config.get("credits", {})
        app_name = config.get("app_name", "Renombrador PDF")
        version = credits.get("version", "1.0")
        authors = credits.get("authors") or [credits.get("author", "Equipo de implementación")]
        year = credits.get("year", "2026")
        organization = credits.get("organization", "")
        description = credits.get(
            "description",
            "Herramienta para analizar, auditar y renombrar PDFs hospitalarios.",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(app_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1a2a33;")
        layout.addWidget(title)

        subtitle = QLabel(f"Versión {version} · Año {year}")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "font-size: 16px; color: #475569; font-weight: 600; padding-bottom: 8px;"
        )
        layout.addWidget(subtitle)

        if organization:
            org = QLabel(organization)
            org.setAlignment(Qt.AlignmentFlag.AlignCenter)
            org.setStyleSheet(
                "font-size: 15px; color: #0f172a; font-weight: 700; padding: 4px 0 12px 0;"
            )
            layout.addWidget(org)

        authors_title = QLabel("AUTORES")
        authors_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        authors_title.setStyleSheet(
            "background-color: #1d4ed8; color: white; font-size: 24px; "
            "font-weight: 900; padding: 14px; border-radius: 14px;"
        )
        layout.addWidget(authors_title)

        authors_box = QFrame()
        authors_box.setStyleSheet(
            "background-color: #eff6ff; border: 3px solid #2563eb; border-radius: 18px;"
        )
        authors_layout = QVBoxLayout(authors_box)
        authors_layout.setContentsMargins(20, 20, 20, 20)
        authors_layout.setSpacing(12)
        for author in authors:
            lbl = QLabel(author)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "font-size: 22px; font-weight: 800; color: #0f172a; padding: 12px; "
                "background-color: white; border-radius: 12px; border: 1px solid #bfdbfe;"
            )
            authors_layout.addWidget(lbl)

        layout.addWidget(authors_box)

        desc_title = QLabel("Descripción")
        desc_title.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #0f172a; margin-top: 8px;"
        )
        layout.addWidget(desc_title)

        desc_box = QTextEdit()
        desc_box.setReadOnly(True)
        desc_box.setText(description)
        desc_box.setStyleSheet(
            "font-size: 15px; background-color: #ffffff; border: 1px solid #cbd5e1; "
            "border-radius: 12px; padding: 10px;"
        )
        layout.addWidget(desc_box, stretch=1)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_close.setMinimumHeight(52)
        btn_close.setStyleSheet(
            "font-size: 16px; font-weight: 800; background-color: #1d4ed8; color: white; "
            "border-radius: 12px; padding: 10px 18px;"
        )
        layout.addWidget(btn_close)


class RenameWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, config: dict, folder: str):
        super().__init__()
        self.config = config
        self.folder = folder

    def run(self):
        try:
            self.progress.emit("Escaneando PDFs...")
            scanner = PdfScanner(self.config)
            candidates = scanner.scan_folder(self.folder)
            self.progress.emit(f"Evaluando {len(candidates)} archivo(s) con reglas Oracle...")
            rules = fetch_oracle_pdf_rules()
            results = []
            for candidate in candidates:
                target, reason = resolve_pdf_name_from_rules(
                    candidate.original_name,
                    candidate.detected_text or "",
                    rules,
                )
                results.append({
                    "original_name": candidate.original_name,
                    "original_path": str(candidate.original_path),
                    "suggested_final_name": target or "",
                    "target_path": (
                        str(candidate.original_path.parent / target)
                        if target and target != candidate.original_name
                        else ""
                    ),
                    "status": reason,
                    "reason": reason,
                })
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.folder = ""
        self.results: list = []
        self.worker: RenameWorker | None = None
        self.thread: QThread | None = None
        self.setWindowTitle(config.get("app_name", "Renombrador PDF"))
        self.resize(1400, 800)
        self._build_menu()
        self._build_ui()
        self._apply_style()

    # ── Menú ────────────────────────────────────────────────
    def _build_menu(self):
        authors_menu = self.menuBar().addMenu("Autores")
        authors_menu.addAction("Ver autores").triggered.connect(self.show_credits)

    # ── UI ─────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Título
        title = QLabel(self.config.get("app_name", "Renombrador PDF"))
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1a2a33;")
        layout.addWidget(title)

        subtitle = QLabel(
            "1) Seleccionar carpeta  2) Simular  3) Revisar  4) Aplicar"
        )
        subtitle.setStyleSheet("font-size: 12px; color: #51606b; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # Carpeta
        folder_card = self._card()
        folder_layout = QVBoxLayout(folder_card)
        lbl = QLabel("Carpeta con PDFs")
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Seleccione la carpeta que contiene los PDFs")
        btn_folder = QPushButton("Elegir carpeta")
        btn_folder.setMinimumHeight(44)
        btn_folder.clicked.connect(self.select_folder)
        row = QHBoxLayout()
        row.addWidget(self.folder_edit, stretch=1)
        row.addWidget(btn_folder)
        folder_layout.addWidget(lbl)
        folder_layout.addLayout(row)
        layout.addWidget(folder_card)

        # Acciones
        actions_card = self._card()
        actions_layout = QHBoxLayout(actions_card)
        self.btn_simulate = QPushButton("1. Simular renombrado")
        self.btn_simulate.setMinimumHeight(52)
        self.btn_simulate.clicked.connect(self.run_simulation)
        self.btn_apply = QPushButton("2. Aplicar renombrado")
        self.btn_apply.setMinimumHeight(52)
        self.btn_apply.clicked.connect(self.run_apply)
        actions_layout.addWidget(self.btn_simulate)
        actions_layout.addWidget(self.btn_apply)
        layout.addWidget(actions_card)

        # Estado
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "font-size: 13px; color: #1b5b7d; font-weight: 600; padding: 6px;"
        )
        layout.addWidget(self.status_label)

        # Tabla
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Archivo actual", "Sugerido", "Destino", "Motivo"]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        header = self.table.horizontalHeader()
        for i in range(4):
            header.setSectionResizeMode(
                i,
                QHeaderView.ResizeMode.Stretch
                if i == 3
                else QHeaderView.ResizeMode.ResizeToContents,
            )
        self.table.verticalHeader().setDefaultSectionSize(32)
        layout.addWidget(self.table, stretch=1)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        layout.addWidget(self.log)

    def _card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: white; border: 1px solid #d7dde3; "
            "border-radius: 12px; }"
        )
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        return card

    def _apply_style(self):
        font = QFont()
        font.setPointSize(13)
        self.setFont(font)
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f6f8; }
            QPushButton {
                font-size: 14px; font-weight: 600;
                border-radius: 12px; padding: 10px 18px;
                border: 1px solid #1d6fa5; background: #1f86c7; color: white;
            }
            QPushButton:hover { background: #1871a8; }
            QPushButton:pressed { background: #135980; }
            QPushButton:disabled { background: #94b8d0; }
            QLineEdit, QTextEdit, QTableWidget {
                background: white; border: 1px solid #c6d1da; border-radius: 10px; padding: 6px;
            }
            QHeaderView::section {
                background: #eaf2f8; padding: 8px;
                border: 1px solid #d5e1ea; font-weight: 600;
            }
            """
        )

    def log(self, text: str):
        self.log.append(text)

    # ── Acciones ───────────────────────────────────────────
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta", self.folder or "."
        )
        if folder:
            self.folder = folder
            self.folder_edit.setText(folder)

    def run_simulation(self):
        self._run(dry_run=True)

    def run_apply(self):
        confirm = QMessageBox.question(
            self,
            "Confirmar renombrado",
            "Se van a renombrar físicamente los archivos.\n\n¿Desea continuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._run(dry_run=False)

    def _run(self, dry_run: bool):
        if not self.folder:
            QMessageBox.warning(self, "Falta carpeta", "Seleccione la carpeta primero")
            return
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "En curso", "Ya hay un proceso ejecutándose")
            return

        self.btn_simulate.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.status_label.setText(
            "Procesando..." if dry_run else "Renombrando..."
        )
        self.log("-" * 50)
        self.log(
            f"Inicio: {'simulación' if dry_run else 'aplicación'}"
            f" en {self.folder}"
        )

        self.thread = QThread(self)
        self.worker = RenameWorker(self.config, self.folder)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.progress.connect(self.status_label.setText)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.start()

    def _on_finished(self, results: list):
        self.results = results
        self._populate_table()
        ok = sum(1 for r in results if "ORACLE" in r["status"] or "HARDCODE" in r["status"])
        self.status_label.setText(f"{len(results)} archivos evaluados, {ok} con coincidencia Oracle/hardcode")
        self.log(f"Completado: {len(results)} archivos")
        self.btn_simulate.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.thread = None
        self.worker = None

    def _on_failed(self, msg: str):
        self.status_label.setText("Error")
        self.log(f"ERROR: {msg}")
        QMessageBox.critical(self, "Error", msg)
        self.btn_simulate.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.thread = None
        self.worker = None

    def _populate_table(self):
        self.table.setRowCount(len(self.results))
        for row, item in enumerate(self.results):
            self.table.setItem(row, 0, QTableWidgetItem(item["original_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(item["suggested_final_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(item["target_path"]))
            self.table.setItem(row, 3, QTableWidgetItem(item["reason"]))
        self.table.resizeRowsToContents()

    def show_credits(self):
        dlg = CreditsDialog(self.config, self)
        dlg.exec()
