from __future__ import annotations

from pathlib import Path
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from app.models import MatchResult, ValidNameRule
from app.services.excel_service import ExcelRuleLoader
from app.services.pdf_service import PdfScanner
from app.services.rename_service import RenameService
from app.services.rules_service import RuleEngine


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.setWindowTitle(config.get("app_name", "Renombrador PDF"))
        self.resize(1500, 850)

        self.excel_path = ""
        self.pdf_folder = ""
        self.rules: List[ValidNameRule] = []
        self.results: List[MatchResult] = []

        self.excel_loader = ExcelRuleLoader(config)
        self.pdf_scanner = PdfScanner(config)
        self.rule_engine = RuleEngine(config)
        self.rename_service = RenameService(config)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)

        row1 = QHBoxLayout()
        self.excel_edit = QLineEdit()
        self.excel_edit.setPlaceholderText("Ruta del Excel con los nombres finales")
        btn_excel = QPushButton("Seleccionar Excel")
        btn_excel.clicked.connect(self.select_excel)
        btn_rules = QPushButton("Cargar Excel")
        btn_rules.clicked.connect(self.load_rules)
        row1.addWidget(QLabel("Excel:"))
        row1.addWidget(self.excel_edit)
        row1.addWidget(btn_excel)
        row1.addWidget(btn_rules)

        row2 = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Carpeta raíz con PDFs")
        btn_folder = QPushButton("Seleccionar carpeta")
        btn_folder.clicked.connect(self.select_folder)
        btn_scan = QPushButton("Analizar PDFs")
        btn_scan.clicked.connect(self.analyze_pdfs)
        row2.addWidget(QLabel("PDFs:"))
        row2.addWidget(self.folder_edit)
        row2.addWidget(btn_folder)
        row2.addWidget(btn_scan)

        row3 = QHBoxLayout()
        btn_manual = QPushButton("Asignar nombre manual")
        btn_manual.clicked.connect(self.manual_assign)
        btn_preview = QPushButton("Previsualizar destino")
        btn_preview.clicked.connect(self.preview_targets)
        btn_backup = QPushButton("Crear backup")
        btn_backup.clicked.connect(self.create_backup)
        btn_apply = QPushButton("Aplicar renombrado")
        btn_apply.clicked.connect(self.apply_rename)
        btn_export = QPushButton("Exportar auditoría")
        btn_export.clicked.connect(self.export_audit)
        row3.addWidget(btn_manual)
        row3.addWidget(btn_preview)
        row3.addWidget(btn_backup)
        row3.addWidget(btn_apply)
        row3.addWidget(btn_export)
        row3.addStretch()

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Archivo actual",
            "Sugerido",
            "Manual",
            "Confianza",
            "Estado",
            "Motivo",
            "Destino",
            "Ruta",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_table_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        main_layout.addLayout(row1)
        main_layout.addLayout(row2)
        main_layout.addLayout(row3)
        main_layout.addWidget(self.table, stretch=1)
        main_layout.addWidget(QLabel("Log:"))
        main_layout.addWidget(self.log, stretch=0)

        self.setCentralWidget(central)

    def log_message(self, text: str):
        self.log.append(text)

    def select_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Excel", "", "Excel (*.xlsx *.xls)")
        if path:
            self.excel_path = path
            self.excel_edit.setText(path)

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de PDFs")
        if path:
            self.pdf_folder = path
            self.folder_edit.setText(path)

    def load_rules(self):
        self.excel_path = self.excel_edit.text().strip()
        if not self.excel_path:
            QMessageBox.warning(self, "Falta Excel", "Debe seleccionar el Excel")
            return
        try:
            self.rules = self.excel_loader.load_rules(self.excel_path)
            self.log_message(f"Excel cargado. Reglas activas: {len(self.rules)}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al cargar Excel", str(exc))

    def analyze_pdfs(self):
        self.pdf_folder = self.folder_edit.text().strip()
        if not self.rules:
            QMessageBox.warning(self, "Falta Excel", "Primero cargue el Excel")
            return
        if not self.pdf_folder:
            QMessageBox.warning(self, "Falta carpeta", "Debe seleccionar la carpeta con PDFs")
            return

        candidates = self.pdf_scanner.scan_folder(self.pdf_folder)
        self.results = [self.rule_engine.match(item, self.rules) for item in candidates]
        self.populate_table()
        self.log_message(f"PDFs analizados: {len(self.results)}")

    def preview_targets(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "Debe analizar PDFs primero")
            return
        self.sync_manual_values_from_table()
        self.results = self.rename_service.preview_targets(self.results)
        self.populate_table()
        self.log_message("Previsualización completada")

    def create_backup(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Falta carpeta", "Debe seleccionar la carpeta")
            return
        try:
            backup = self.rename_service.backup_folder(folder)
            self.log_message(f"Backup creado: {backup}")
            QMessageBox.information(self, "Backup OK", f"Backup creado en:\n{backup}")
        except Exception as exc:
            QMessageBox.critical(self, "Error en backup", str(exc))

    def apply_rename(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "Debe analizar PDFs primero")
            return
        self.sync_manual_values_from_table()
        self.results = self.rename_service.preview_targets(self.results)

        confirm = QMessageBox.question(
            self,
            "Confirmar renombrado",
            "Se va a renombrar físicamente los archivos. ¿Desea continuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.results = self.rename_service.apply(self.results)
        self.populate_table()
        self.log_message("Renombrado ejecutado")

    def export_audit(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "No hay resultados para exportar")
            return
        folder = self.folder_edit.text().strip() or str(Path.cwd())
        csv_path, json_path = self.rename_service.export_audit(self.results, folder)
        self.log_message(f"Auditoría exportada: {csv_path}")
        self.log_message(f"Reporte JSON exportado: {json_path}")
        QMessageBox.information(self, "Exportación OK", f"CSV:\n{csv_path}\n\nJSON:\n{json_path}")

    def populate_table(self):
        self.table.setRowCount(len(self.results))
        for row, item in enumerate(self.results):
            values = [
                item.original_name,
                item.suggested_final_name,
                item.final_name_manual,
                str(item.confidence),
                item.status,
                item.reason,
                str(item.target_path) if item.target_path else "",
                str(item.original_path),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col in (0, 1, 2, 3, 4, 7):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, cell)

    def sync_manual_values_from_table(self):
        for row, item in enumerate(self.results):
            manual_item = self.table.item(row, 2)
            if manual_item:
                item.final_name_manual = manual_item.text().strip()

    def manual_assign(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "Debe analizar PDFs primero")
            return
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.warning(self, "Seleccione", "Debe seleccionar al menos una fila")
            return

        options = [rule.final_name for rule in self.rules]
        value, ok = QInputDialog.getItem(self, "Asignación manual", "Nombre final:", options, 0, False)
        if ok and value:
            for row in selected_rows:
                self.results[row].final_name_manual = value
                self.results[row].status = "MANUAL"
                self.results[row].reason = (self.results[row].reason + " | ").strip(" | ") + "Asignado manualmente"
            self.populate_table()
            self.log_message(f"Asignación manual aplicada a {len(selected_rows)} archivo(s)")

    def open_table_menu(self, pos):
        menu = QMenu(self)
        action_manual = menu.addAction("Asignar nombre manual")
        selected_action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if selected_action == action_manual:
            self.manual_assign()
