
from __future__ import annotations

import csv

from typing import List

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QFrame,
    QDialog,
)

from app.models import MatchResult, ValidNameRule
from app.services.pdf_service import PdfScanner
from app.services.rename_service import RenameService
from app.services.rules_service import RuleEngine
from app.services.sqlite_rule_service import SQLiteRuleRepository


class AnalyzeWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, config: dict, folder: str, rules: List[ValidNameRule]):
        super().__init__()
        self.config = config
        self.folder = folder
        self.rules = rules

    def run(self):
        try:
            self.progress.emit("Leyendo PDFs...")
            scanner = PdfScanner(self.config)
            candidates = scanner.scan_folder(self.folder)

            self.progress.emit(f"Aplicando reglas a {len(candidates)} PDF(s)...")
            engine = RuleEngine(self.config)
            results = [engine.match(item, self.rules) for item in candidates]
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class CatalogDialog(QDialog):
    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Catálogo interno de nombres válidos")
        self.resize(1100, 700)

        layout = QVBoxLayout(self)

        title = QLabel("Catálogo interno del proyecto")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        help_label = QLabel("Aquí se muestran los nombres finales válidos que la aplicación usará como fuente de verdad.")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        table = QTableWidget(len(rows), 7)
        table.setHorizontalHeaderLabels(["Nombre PDF", "Activo", "Orden", "Descripción", "Palabras nombre", "Palabras texto", "Regex texto"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)

        for i, row in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(str(row.get("nombre_pdf", ""))))
            table.setItem(i, 1, QTableWidgetItem(str(row.get("activo", ""))))
            table.setItem(i, 2, QTableWidgetItem(str(row.get("orden", ""))))
            table.setItem(i, 3, QTableWidgetItem(str(row.get("nota", ""))))
            table.setItem(i, 4, QTableWidgetItem(str(row.get("palabras_nombre", ""))))
            table.setItem(i, 5, QTableWidgetItem(str(row.get("palabras_texto", ""))))
            table.setItem(i, 6, QTableWidgetItem(str(row.get("regex_texto", ""))))

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(table, stretch=1)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_close.setMinimumHeight(48)
        layout.addWidget(btn_close)


class EditableCatalogDialog(QDialog):
    HEADERS = [
        "Si el nombre contiene",
        "Renombrar como",
        "Si el texto del PDF contiene",
        "Regex en texto",
        "Activo",
        "Prioridad",
        "Nota",
        "Tipo",
    ]
    FIELDS = ["palabras_nombre", "nombre_pdf", "palabras_texto", "regex_texto", "activo", "orden", "nota", "es_base"]

    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar reglas de cambio de nombre")
        self.resize(1100, 700)
        self.saved = False

        layout = QVBoxLayout(self)

        title = QLabel("Reglas de cambio de nombre")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        help_label = QLabel(
            "Ejemplo: si un archivo se llama F_otros.pdf y quiere cambiarlo a xyz.pdf, "
            "escriba OTROS en 'Si el nombre contiene' y xyz.pdf en 'Renombrar como'. "
            "Puede separar varias palabras con | o ;. Las filas Base no se eliminan; agregue filas nuevas para reglas propias."
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.table = QTableWidget(len(rows), len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)

        for row_index, row in enumerate(rows):
            self._set_row(row_index, row)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table, stretch=1)

        button_row = QHBoxLayout()
        btn_add = QPushButton("Agregar regla")
        btn_add.clicked.connect(self.add_row)
        btn_delete = QPushButton("Eliminar seleccionadas")
        btn_delete.clicked.connect(self.delete_selected_rows)
        btn_save = QPushButton("Guardar cambios")
        btn_save.clicked.connect(self.save)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.reject)

        for button in (btn_add, btn_delete, btn_save, btn_close):
            button.setMinimumHeight(48)
            button_row.addWidget(button)
        layout.addLayout(button_row)

    def _set_row(self, row_index: int, row: dict):
        for col_index, field in enumerate(self.FIELDS):
            value = str(row.get(field, ""))
            if field == "es_base":
                value = "Base" if value.strip().upper() == "S" else "Personalizada"
            item = QTableWidgetItem(value)
            if field == "es_base":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, col_index, item)

    def add_row(self):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        self._set_row(
            row_index,
            {
                "nombre_pdf": "NUEVO.pdf",
                "activo": "S",
                "orden": "9999",
                "nota": "",
                "palabras_nombre": "",
                "palabras_texto": "",
                "regex_texto": "",
                "es_base": "N",
            },
        )
        self.table.selectRow(row_index)

    def delete_selected_rows(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        if not selected_rows:
            QMessageBox.warning(self, "Sin seleccion", "Seleccione una o mas reglas para eliminar")
            return
        base_rows = [row for row in selected_rows if self._is_base_row(row)]
        if base_rows:
            QMessageBox.warning(
                self,
                "Reglas base protegidas",
                "No se pueden eliminar las reglas base. Seleccione solo reglas personalizadas para borrar.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Eliminar reglas",
            f"Se eliminaran {len(selected_rows)} regla(s). Desea continuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for row in selected_rows:
            self.table.removeRow(row)

    def _is_base_row(self, row_index: int) -> bool:
        item = self.table.item(row_index, self.FIELDS.index("es_base"))
        return bool(item and item.text().strip().lower() == "base")

    def rows(self) -> list[dict]:
        data = []
        for row_index in range(self.table.rowCount()):
            row = {}
            for col_index, field in enumerate(self.FIELDS):
                item = self.table.item(row_index, col_index)
                value = item.text().strip() if item else ""
                if field == "es_base":
                    value = "S" if value.lower() == "base" else "N"
                row[field] = value
            data.append(row)
        return data

    def save(self):
        self.saved = True
        self.accept()


class CreditsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Autores")
        self.resize(760, 520)

        credits = config.get("credits", {})
        app_name = config.get("app_name", "Renombrador PDF")
        version = credits.get("version", "1.0")
        authors = credits.get("authors") or [credits.get("author", "Equipo de implementacion")]
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
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(f"Versión {version} · Año {year}")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "font-size: 16px; color: #475569; font-weight: 600; padding-bottom: 8px;"
        )
        layout.addWidget(subtitle)

        if organization:
            org_label = QLabel(organization)
            org_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            org_label.setStyleSheet(
                "font-size: 15px; color: #0f172a; font-weight: 700; padding: 4px 0 12px 0;"
            )
            layout.addWidget(org_label)

        authors_title = QLabel("AUTORES")
        authors_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        authors_title.setStyleSheet(
            "background-color: #1d4ed8; color: white; font-size: 24px; "
            "font-weight: 900; padding: 14px; border-radius: 14px; letter-spacing: 1px;"
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
            author_label = QLabel(author)
            author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            author_label.setStyleSheet(
                "font-size: 22px; font-weight: 800; color: #0f172a; padding: 12px; "
                "background-color: white; border-radius: 12px; border: 1px solid #bfdbfe;"
            )
            authors_layout.addWidget(author_label)

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


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.setWindowTitle(config.get("app_name", "Renombrador PDF"))
        self.resize(1680, 980)

        self.pdf_folder = ""
        self.rules: List[ValidNameRule] = []
        self.results: List[MatchResult] = []
        self.scan_thread = None
        self.scan_worker = None
        self.auto_apply_after_scan = False

        self.rule_repo = SQLiteRuleRepository(config)
        self.rule_repo.initialize()

        self.pdf_scanner = PdfScanner(config)
        self.rule_engine = RuleEngine(config)
        self.rename_service = RenameService(config)

        self._build_menu()
        self._build_minimal_ui()
        self._load_rules_on_start()

    def _build_menu(self):
        help_menu = self.menuBar().addMenu("Autores")
        help_menu.addAction("Ver autores").triggered.connect(self.show_credits)

    def _build_minimal_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 28, 28, 28)
        main_layout.setSpacing(18)

        title = QLabel(self.config.get("app_name", "Renombrador PDF"))
        title.setObjectName("titleLabel")
        subtitle = QLabel("Seleccione la carpeta con PDFs y ejecute el renombrado.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitleLabel")
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        folder_card = self._build_card()
        folder_layout = QVBoxLayout(folder_card)
        lbl_folder = QLabel("Carpeta con PDFs")
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Seleccione la carpeta que contiene los PDFs")
        btn_folder = self._big_button("Elegir carpeta")
        btn_folder.clicked.connect(self.select_folder)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, stretch=1)
        folder_row.addWidget(btn_folder)
        folder_layout.addWidget(lbl_folder)
        folder_layout.addLayout(folder_row)
        main_layout.addWidget(folder_card)

        action_card = self._build_card()
        action_layout = QVBoxLayout(action_card)
        self.btn_apply_all = self._big_button("Aplicar renombrado")
        self.btn_apply_all.clicked.connect(self.run_minimal_rename)
        self.btn_scan = self.btn_apply_all
        action_layout.addWidget(self.btn_apply_all)
        main_layout.addWidget(action_card)

        self.processing_status = QLabel("")
        self.processing_status.setObjectName("statusLabel")
        main_layout.addWidget(self.processing_status)

        self.catalog_status = QLineEdit()
        self.catalog_status.hide()
        self.lbl_total = self._metric_box("Total", "0")
        self.lbl_ready = self._metric_box("Listos", "0")
        self.lbl_review = self._metric_box("Revisar", "0")
        self.lbl_nomatch = self._metric_box("Sin match", "0")
        for metric in (self.lbl_total, self.lbl_ready, self.lbl_review, self.lbl_nomatch):
            metric["box"].hide()

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Archivo actual", "Sugerido", "Manual", "Confianza", "Estado", "Motivo", "Destino", "Ruta"])
        self.table.hide()

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.hide()

        main_layout.addStretch(1)
        self.setCentralWidget(central)
        self._apply_accessible_style()

    def _build_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        title = QLabel(self.config.get("app_name", "Renombrador PDF"))
        title.setObjectName("titleLabel")

        subtitle = QLabel("Flujo simple: 1) elegir carpeta, 2) analizar, 3) revisar, 4) hacer respaldo, 5) renombrar.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitleLabel")

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        workflow_tab = QWidget()
        results_tab = QWidget()
        log_tab = QWidget()

        workflow_layout = QVBoxLayout(workflow_tab)
        workflow_layout.setContentsMargins(10, 10, 10, 10)
        workflow_layout.setSpacing(14)

        results_layout = QVBoxLayout(results_tab)
        results_layout.setContentsMargins(10, 10, 10, 10)
        results_layout.setSpacing(12)

        activity_layout = QVBoxLayout(log_tab)
        activity_layout.setContentsMargins(10, 10, 10, 10)
        activity_layout.setSpacing(12)

        self.tabs.addTab(workflow_tab, "1. Preparar")
        self.tabs.addTab(results_tab, "2. Revisar resultados")
        self.tabs.addTab(log_tab, "Registro")
        main_layout.addWidget(self.tabs, stretch=1)

        top_card = self._build_card()
        top_layout = QVBoxLayout(top_card)

        row1 = QHBoxLayout()
        lbl_catalog = QLabel("Catálogo interno:")
        self.catalog_status = QLineEdit()
        lbl_catalog.setText("Reglas activas:")
        self.catalog_status.setReadOnly(True)
        self.catalog_status.setPlaceholderText("La tabla local se carga al abrir la aplicación")

        btn_reload_rules = self._big_button("Recargar catálogo")
        btn_reload_rules.clicked.connect(self.load_rules)
        btn_reload_rules.setText("Recargar reglas")

        btn_view_catalog = self._big_button("Ver catálogo")
        btn_view_catalog.clicked.connect(self.show_catalog)
        btn_view_catalog.setText("Editar reglas")

        row1.addWidget(lbl_catalog)
        row1.addWidget(self.catalog_status, stretch=1)
        row1.addWidget(btn_reload_rules)
        row1.addWidget(btn_view_catalog)
        top_layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_folder = QLabel("Carpeta con PDFs:")
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Seleccionar la carpeta que contiene los PDFs")
        btn_folder = self._big_button("Elegir carpeta")
        btn_folder.clicked.connect(self.select_folder)
        row2.addWidget(lbl_folder)
        row2.addWidget(self.folder_edit, stretch=1)
        row2.addWidget(btn_folder)
        top_layout.addLayout(row2)

        workflow_layout.addWidget(top_card)

        metrics_card = self._build_card()
        metrics_layout = QGridLayout(metrics_card)
        self.lbl_total = self._metric_box("Total", "0")
        self.lbl_ready = self._metric_box("Listos", "0")
        self.lbl_review = self._metric_box("Revisar", "0")
        self.lbl_nomatch = self._metric_box("Sin match", "0")
        metrics_layout.addWidget(self.lbl_total["box"], 0, 0)
        metrics_layout.addWidget(self.lbl_ready["box"], 0, 1)
        metrics_layout.addWidget(self.lbl_review["box"], 0, 2)
        metrics_layout.addWidget(self.lbl_nomatch["box"], 0, 3)
        workflow_layout.addWidget(metrics_card)

        actions_card = self._build_card()
        actions_layout = QGridLayout(actions_card)
        self.btn_scan = self._big_button("1. Analizar PDFs")
        self.btn_scan.clicked.connect(self.analyze_pdfs)
        btn_preview = self._big_button("Previsualizar destino")
        btn_preview.clicked.connect(self.preview_targets)
        btn_backup = self._big_button("Crear respaldo")
        btn_backup.clicked.connect(self.create_backup)
        btn_apply = self._big_button("2. Aplicar renombrado")
        btn_apply.clicked.connect(self.apply_rename)
        btn_export = self._big_button("Exportar auditoría")
        btn_export.clicked.connect(self.export_audit)

        actions_layout.addWidget(self.btn_scan, 0, 0)
        actions_layout.addWidget(btn_apply, 0, 1)
        actions_layout.addWidget(btn_preview, 1, 0)
        actions_layout.addWidget(btn_backup, 1, 1)
        workflow_layout.addWidget(actions_card)

        self.processing_status = QLabel("")
        self.processing_status.setObjectName("statusLabel")
        workflow_layout.addWidget(self.processing_status)
        workflow_layout.addStretch(1)

        results_actions = self._build_card()
        results_actions_layout = QHBoxLayout(results_actions)
        btn_results_scan = self._big_button("Analizar PDFs")
        btn_results_scan.clicked.connect(self.analyze_pdfs)
        btn_results_preview = self._big_button("Previsualizar destino")
        btn_results_preview.clicked.connect(self.preview_targets)
        btn_results_backup = self._big_button("Crear respaldo")
        btn_results_backup.clicked.connect(self.create_backup)
        btn_results_apply = self._big_button("Aplicar renombrado")
        btn_results_apply.clicked.connect(self.apply_rename)
        for button in (
            btn_results_scan,
            btn_results_apply,
            btn_results_preview,
            btn_results_backup,
        ):
            results_actions_layout.addWidget(button)
        results_layout.addWidget(results_actions)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Archivo actual", "Sugerido", "Manual", "Confianza", "Estado", "Motivo", "Destino", "Ruta"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_table_menu)
        self.table.verticalHeader().setDefaultSectionSize(36)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        results_layout.addWidget(self.table, stretch=1)

        log_card = self._build_card()
        log_layout = QVBoxLayout(log_card)
        log_title = QLabel("Mensajes del sistema")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(420)
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log)
        activity_layout.addWidget(log_card, stretch=1)

        self.setCentralWidget(central)
        self._apply_accessible_style()

    def _build_card(self) -> QFrame:
        box = QFrame()
        box.setObjectName("card")
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return box

    def _metric_box(self, title: str, value: str) -> dict:
        card = self._build_card()
        layout = QVBoxLayout(card)
        lbl_title = QLabel(title)
        lbl_title.setObjectName("metricTitle")
        lbl_value = QLabel(value)
        lbl_value.setObjectName("metricValue")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        return {"box": card, "value": lbl_value}

    def _big_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(56)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _apply_accessible_style(self):
        font = QFont()
        font.setPointSize(int(self.config.get("ui", {}).get("base_font_size", 12)))
        self.setFont(font)

        self.setStyleSheet(
            '''
            QWidget { font-size: 13pt; }
            QMainWindow { background: #f4f6f8; }
            QFrame#card { background: white; border: 1px solid #d7dde3; border-radius: 12px; }
            QLabel#titleLabel { font-size: 22pt; font-weight: 700; color: #1a2a33; }
            QLabel#subtitleLabel { font-size: 12pt; color: #51606b; margin-bottom: 4px; }
            QLabel#statusLabel { font-size: 12pt; color: #1b5b7d; font-weight: 600; padding: 8px; }
            QLabel#metricTitle { font-size: 11pt; color: #52616d; }
            QLabel#metricValue { font-size: 24pt; font-weight: 700; color: #173b52; }
            QPushButton {
                font-size: 13pt; font-weight: 600; padding: 12px 18px; border-radius: 12px;
                border: 1px solid #1d6fa5; background: #1f86c7; color: white;
            }
            QPushButton:hover { background: #1871a8; }
            QPushButton:pressed { background: #135980; }
            QLineEdit, QTextEdit, QTableWidget {
                background: white; border: 1px solid #c6d1da; border-radius: 10px; padding: 8px;
            }
            QHeaderView::section {
                background: #eaf2f8; padding: 8px; border: 1px solid #d5e1ea; font-weight: 600;
            }
            '''
        )

    def log_message(self, text: str):
        self.log.append(text)

    def _load_rules_on_start(self):
        try:
            self.rules = self.rule_repo.load_rules()
            self.catalog_status.setText(f"{len(self.rules)} reglas activas en base local")
            self.log_message(f"Catálogo interno cargado: {len(self.rules)} reglas activas")
        except Exception as exc:
            self.catalog_status.setText("Error al cargar catálogo")
            QMessageBox.critical(self, "Error al iniciar", str(exc))

    def load_rules(self):
        try:
            self.rules = self.rule_repo.load_rules()
            self.catalog_status.setText(f"{len(self.rules)} reglas activas en base local")
            self.log_message(f"Catálogo recargado: {len(self.rules)} reglas activas")
        except Exception as exc:
            QMessageBox.critical(self, "Error de catálogo", str(exc))

    def show_catalog(self):
        try:
            rows = self.rule_repo.list_catalog_rows()
            dlg = EditableCatalogDialog(rows, self)
            while dlg.exec() == QDialog.DialogCode.Accepted and dlg.saved:
                try:
                    self.rule_repo.replace_catalog_rows(dlg.rows())
                    self.load_rules()
                    self.log_message("Reglas guardadas correctamente")
                    return
                except Exception as exc:
                    dlg.saved = False
                    QMessageBox.critical(self, "Error al guardar reglas", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error al abrir catálogo", str(exc))

    def export_rules_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar reglas",
            "reglas_renombrador.csv",
            "CSV (*.csv)",
        )
        if not path:
            return

        if not path.lower().endswith(".csv"):
            path = f"{path}.csv"

        rows = self.rule_repo.list_catalog_rows()
        headers = [
            "Si el nombre contiene",
            "Renombrar como",
            "Si el texto del PDF contiene",
            "Regex en texto",
            "Activo",
            "Prioridad",
            "Nota",
            "Tipo",
        ]

        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(
                        [
                            row.get("palabras_nombre", ""),
                            row.get("nombre_pdf", ""),
                            row.get("palabras_texto", ""),
                            row.get("regex_texto", ""),
                            row.get("activo", ""),
                            row.get("orden", ""),
                            row.get("nota", ""),
                            "Base" if row.get("es_base") == "S" else "Personalizada",
                        ]
                    )
            self.log_message(f"Reglas exportadas: {path}")
            QMessageBox.information(self, "Reglas exportadas", f"Archivo creado:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar reglas", str(exc))

    def import_rules_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar reglas",
            "",
            "CSV (*.csv)",
        )
        if not path:
            return

        confirm = QMessageBox.question(
            self,
            "Importar reglas",
            "Se importaran las reglas del CSV y se reemplazara el catalogo editable.\n\n"
            "Las reglas base del sistema se mantendran protegidas.\n\n"
            "Desea continuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            rows = self._read_rules_csv(path)
            self.rule_repo.replace_catalog_rows(rows)
            self.load_rules()
            self.log_message(f"Reglas importadas: {path}")
            QMessageBox.information(self, "Reglas importadas", f"Reglas importadas correctamente:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al importar reglas", str(exc))

    def _read_rules_csv(self, path: str) -> list[dict]:
        expected = {
            "Si el nombre contiene": "palabras_nombre",
            "Renombrar como": "nombre_pdf",
            "Si el texto del PDF contiene": "palabras_texto",
            "Regex en texto": "regex_texto",
            "Activo": "activo",
            "Prioridad": "orden",
            "Nota": "nota",
            "Tipo": "es_base",
        }

        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [name for name in expected if name not in (reader.fieldnames or [])]
            if missing:
                raise ValueError("Faltan columnas requeridas: " + ", ".join(missing))

            rows = []
            for index, csv_row in enumerate(reader, start=2):
                nombre_pdf = (csv_row.get("Renombrar como") or "").strip()
                if not nombre_pdf:
                    raise ValueError(f"La fila {index} no tiene valor en 'Renombrar como'")
                row = {}
                for csv_name, field_name in expected.items():
                    value = (csv_row.get(csv_name) or "").strip()
                    if field_name == "es_base":
                        value = "S" if value.lower() == "base" else "N"
                    row[field_name] = value
                rows.append(row)

        if not rows:
            raise ValueError("El CSV no tiene reglas para importar")
        return rows

    def show_credits(self):
        dlg = CreditsDialog(self.config, self)
        dlg.exec()

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de PDFs")
        if path:
            self.pdf_folder = path
            self.folder_edit.setText(path)

    def analyze_pdfs(self):
        if self.scan_thread and self.scan_thread.isRunning():
            QMessageBox.information(self, "Analisis en curso", "Ya hay un analisis de PDFs ejecutandose")
            return
        self.pdf_folder = self.folder_edit.text().strip()
        if not self.rules:
            QMessageBox.warning(self, "Falta catálogo", "La tabla interna no tiene reglas activas")
            return
        if not self.pdf_folder:
            QMessageBox.warning(self, "Falta carpeta", "Debe seleccionar la carpeta con PDFs")
            return
        self._set_scan_busy(True, "Iniciando analisis de PDFs...")
        self.scan_thread = QThread(self)
        self.scan_worker = AnalyzeWorker(self.config, self.pdf_folder, list(self.rules))
        self.scan_worker.moveToThread(self.scan_thread)

        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self._set_scan_status)
        self.scan_worker.finished.connect(self._finish_scan)
        self.scan_worker.failed.connect(self._fail_scan)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.failed.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_worker.failed.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self._clear_scan_worker)
        self.scan_thread.start()
        self.log_message("Analisis iniciado en segundo plano")

    def run_minimal_rename(self):
        if self.scan_thread and self.scan_thread.isRunning():
            QMessageBox.information(self, "Proceso en curso", "Ya hay un renombrado ejecutandose")
            return

        self.auto_apply_after_scan = True
        self.analyze_pdfs()

    def _finish_scan(self, results: list):
        self.results = results
        self.populate_table()
        self._refresh_metrics()
        self._set_scan_busy(False, f"Analisis completado: {len(self.results)} PDF(s)")
        self.log_message(f"PDFs analizados: {len(self.results)}")
        if self.auto_apply_after_scan:
            self._apply_minimal_rename_after_scan()

    def _apply_minimal_rename_after_scan(self):
        self.auto_apply_after_scan = False
        if not self.results:
            self.processing_status.setText("Completado: no se encontraron PDFs")
            return

        try:
            self._set_scan_busy(True, "Creando respaldo...")
            backup = self.rename_service.backup_folder(self.pdf_folder)
            self.log_message(f"Respaldo creado: {backup}")

            self._set_scan_busy(True, "Renombrando archivos...")
            self.results = self.rename_service.preview_targets(self.results)
            self.results = self.rename_service.apply(self.results)
            self.populate_table()
            self._refresh_metrics()

            renamed = sum(1 for item in self.results if item.status == "RENOMBRADO")
            errors = sum(1 for item in self.results if item.status == "ERROR")
            if errors:
                self.processing_status.setText(f"Completado con errores: {renamed} renombrados, {errors} errores")
            else:
                self.processing_status.setText("Completado")
            self.log_message("Renombrado ejecutado")
        except Exception as exc:
            self.processing_status.setText("Error durante el renombrado")
            QMessageBox.critical(self, "Error al renombrar", str(exc))
            self.log_message(f"Error al renombrar: {exc}")
        finally:
            self._set_scan_busy(False, self.processing_status.text())

    def _fail_scan(self, message: str):
        self.auto_apply_after_scan = False
        self._set_scan_busy(False, "Error durante el analisis")
        QMessageBox.critical(self, "Error al analizar PDFs", message)
        self.log_message(f"Error al analizar PDFs: {message}")

    def _clear_scan_worker(self):
        self.scan_thread = None
        self.scan_worker = None

    def _set_scan_status(self, message: str):
        self.processing_status.setText(message)
        self.log_message(message)

    def _set_scan_busy(self, busy: bool, message: str):
        self.btn_scan.setEnabled(not busy)
        self.processing_status.setText(message)

    def preview_targets(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "Debe analizar PDFs primero")
            return
        self.sync_manual_values_from_table()
        self.results = self.rename_service.preview_targets(self.results)
        self.populate_table()
        self._refresh_metrics()
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(1)
        self.log_message("Previsualización completada")

    def create_backup(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Falta carpeta", "Debe seleccionar la carpeta")
            return
        try:
            backup = self.rename_service.backup_folder(folder)
            self.log_message(f"Respaldo creado: {backup}")
            QMessageBox.information(self, "Respaldo creado", f"Respaldo creado en:\n{backup}")
        except Exception as exc:
            QMessageBox.critical(self, "Error en respaldo", str(exc))

    def apply_rename(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "Debe analizar PDFs primero")
            return
        self.sync_manual_values_from_table()
        self.results = self.rename_service.preview_targets(self.results)
        confirm = QMessageBox.question(self, "Confirmar renombrado", "Se van a renombrar físicamente los archivos.\n\n¿Desea continuar?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.results = self.rename_service.apply(self.results)
        self.populate_table()
        self._refresh_metrics()
        if hasattr(self, "tabs"):
            self.tabs.setCurrentIndex(1)
        self.log_message("Renombrado ejecutado")

    def export_audit(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Falta carpeta", "Debe seleccionar la carpeta")
            return
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "No hay resultados para exportar")
            return
        self.sync_manual_values_from_table()
        try:
            csv_path, json_path = self.rename_service.export_audit(self.results, folder)
            self.log_message(f"Auditoría exportada: {csv_path}")
            self.log_message(f"Auditoría exportada: {json_path}")
            QMessageBox.information(self, "Auditoría exportada", f"CSV:\n{csv_path}\n\nJSON:\n{json_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))

    def manual_assign(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "Debe analizar PDFs primero")
            return
        selected_rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()})
        if not selected_rows:
            QMessageBox.warning(self, "Sin selección", "Debe seleccionar una o más filas")
            return
        options = [rule.final_name for rule in self.rules]
        value, ok = QInputDialog.getItem(self, "Asignación manual", "Nombre final:", options, 0, False)
        if ok and value:
            for row in selected_rows:
                self.results[row].final_name_manual = value
                self.results[row].status = "MANUAL"
                self.results[row].reason = "Asignado manualmente por el usuario"
            self.populate_table()
            self._refresh_metrics()
            self.log_message(f"Asignación manual aplicada a {len(selected_rows)} archivo(s)")

    def open_table_menu(self, pos):
        menu = QMenu(self)
        action_manual = menu.addAction("Asignar nombre manual")
        selected_action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if selected_action == action_manual:
            self.manual_assign()

    def sync_manual_values_from_table(self):
        for row in range(self.table.rowCount()):
            if row >= len(self.results):
                continue
            item = self.table.item(row, 2)
            self.results[row].final_name_manual = item.text().strip() if item else ""

    def _build_friendly_reason(self, result) -> str:
        nombre_actual = (result.original_name or "").strip()
        nombre_manual = (result.final_name_manual or "").strip()
        nombre_sugerido = (result.suggested_final_name or "").strip()
        nombre_final = nombre_manual or nombre_sugerido
        status = (result.status or "").strip().upper()
        motivo_original = (result.reason or "").strip()

        def norm(value: str) -> str:
            return value.strip().upper()


        if not nombre_final:
            if motivo_original:
                return f"No se pudo determinar el nombre final. Detalle: {motivo_original}"
            return "No se pudo determinar el nombre final"

        if norm(nombre_actual) == norm(nombre_final):
            return f"El archivo ya tiene el nombre correcto: {nombre_final}"

        if status == "MANUAL":
            return f"El archivo actual es {nombre_actual} y se renombrará manualmente a {nombre_final}"

        if status == "RENOMBRADO":
            return f"El archivo {nombre_actual} fue renombrado a {nombre_final}"

        if status == "YA_OK":
            return f"El archivo ya estaba correcto: {nombre_final}"

        if status == "SIN_MATCH":
            if motivo_original:
                return f"No se encontró una regla automática para {nombre_actual}. Detalle: {motivo_original}"
            return f"No se encontró una regla automática para {nombre_actual}"

        if status == "REVISAR":
            if motivo_original:
                return (
                    f"El archivo actual es {nombre_actual} y podría corresponder a {nombre_final}. "
                    f"Se recomienda revisar antes de renombrar. Detalle: {motivo_original}"
                )
            return (
                f"El archivo actual es {nombre_actual} y podría corresponder a {nombre_final}. "
                "Se recomienda revisar antes de renombrar"
            )

        if status in {"LISTO", "PENDIENTE"}:
            if motivo_original:
                return (
                    f"El archivo actual es {nombre_actual} y debe renombrarse como {nombre_final}. "
                    f"Detalle: {motivo_original}"
                )
            return f"El archivo actual es {nombre_actual} y debe renombrarse como {nombre_final}"

        if motivo_original:
            return (
                f"El archivo actual es {nombre_actual} y el sistema propone {nombre_final}. "
                f"Detalle: {motivo_original}"
            )

        return f"El archivo actual es {nombre_actual} y el sistema propone {nombre_final}"

    def populate_table(self):
        self.table.setRowCount(len(self.results))
        for row, result in enumerate(self.results):
            motivo_legible = self._build_friendly_reason(result)
            valores = [
                result.original_name,
                result.suggested_final_name,
                result.final_name_manual,
                str(result.confidence),
                result.status,
                motivo_legible,
                str(result.target_path or ""),
                str(result.original_path),
            ]
            for col, valor in enumerate(valores):
                cell = QTableWidgetItem(valor)
                if col in (0, 1, 2, 3, 4, 6, 7):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col == 4:
                    estado = (result.status or "").upper()
                    if estado == "LISTO":
                        cell.setText("Listo")
                    elif estado == "REVISAR":
                        cell.setText("Revisar")
                    elif estado == "SIN_MATCH":
                        cell.setText("Sin coincidencia")
                    elif estado == "MANUAL":
                        cell.setText("Manual")
                    elif estado == "RENOMBRADO":
                        cell.setText("Renombrado")
                    elif estado == "YA_OK":
                        cell.setText("Correcto")
                    elif estado == "PENDIENTE":
                        cell.setText("Pendiente")
                if col == 5:
                    cell.setToolTip(motivo_legible)
                self.table.setItem(row, col, cell)
        self.table.resizeRowsToContents()

    def _refresh_metrics(self):
        total = len(self.results)
        ready = sum(1 for x in self.results if x.status in {"LISTO", "MANUAL", "RENOMBRADO", "YA_OK"})
        review = sum(1 for x in self.results if x.status == "REVISAR")
        no_match = sum(1 for x in self.results if x.status == "SIN_MATCH")
        self.lbl_total["value"].setText(str(total))
        self.lbl_ready["value"].setText(str(ready))
        self.lbl_review["value"].setText(str(review))
        self.lbl_nomatch["value"].setText(str(no_match))
