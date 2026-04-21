
from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
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


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.setWindowTitle(config.get("app_name", "Renombrador PDF"))
        self.resize(1680, 980)

        self.pdf_folder = ""
        self.rules: List[ValidNameRule] = []
        self.results: List[MatchResult] = []

        self.rule_repo = SQLiteRuleRepository(config)
        self.rule_repo.initialize()

        self.pdf_scanner = PdfScanner(config)
        self.rule_engine = RuleEngine(config)
        self.rename_service = RenameService(config)

        self._build_ui()
        self._load_rules_on_start()

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

        top_card = self._build_card()
        top_layout = QVBoxLayout(top_card)

        row1 = QHBoxLayout()
        lbl_catalog = QLabel("Catálogo interno:")
        self.catalog_status = QLineEdit()
        self.catalog_status.setReadOnly(True)
        self.catalog_status.setPlaceholderText("La tabla local se carga al abrir la aplicación")

        btn_reload_rules = self._big_button("Recargar catálogo")
        btn_reload_rules.clicked.connect(self.load_rules)

        btn_view_catalog = self._big_button("Ver catálogo")
        btn_view_catalog.clicked.connect(self.show_catalog)

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

        main_layout.addWidget(top_card)

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
        main_layout.addWidget(metrics_card)

        actions_card = self._build_card()
        actions_layout = QGridLayout(actions_card)
        btn_scan = self._big_button("1. Analizar PDFs")
        btn_scan.clicked.connect(self.analyze_pdfs)
        btn_manual = self._big_button("2. Asignar nombre manual")
        btn_manual.clicked.connect(self.manual_assign)
        btn_preview = self._big_button("3. Previsualizar destino")
        btn_preview.clicked.connect(self.preview_targets)
        btn_backup = self._big_button("4. Crear respaldo")
        btn_backup.clicked.connect(self.create_backup)
        btn_apply = self._big_button("5. Aplicar renombrado")
        btn_apply.clicked.connect(self.apply_rename)
        btn_export = self._big_button("Exportar auditoría")
        btn_export.clicked.connect(self.export_audit)

        actions_layout.addWidget(btn_scan, 0, 0)
        actions_layout.addWidget(btn_manual, 0, 1)
        actions_layout.addWidget(btn_preview, 0, 2)
        actions_layout.addWidget(btn_backup, 1, 0)
        actions_layout.addWidget(btn_apply, 1, 1)
        actions_layout.addWidget(btn_export, 1, 2)
        main_layout.addWidget(actions_card)

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

        main_layout.addWidget(self.table, stretch=1)

        log_card = self._build_card()
        log_layout = QVBoxLayout(log_card)
        log_title = QLabel("Mensajes del sistema")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log)
        main_layout.addWidget(log_card)

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
            dlg = CatalogDialog(rows, self)
            dlg.exec()
        except Exception as exc:
            QMessageBox.critical(self, "Error al abrir catálogo", str(exc))

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de PDFs")
        if path:
            self.pdf_folder = path
            self.folder_edit.setText(path)

    def analyze_pdfs(self):
        self.pdf_folder = self.folder_edit.text().strip()
        if not self.rules:
            QMessageBox.warning(self, "Falta catálogo", "La tabla interna no tiene reglas activas")
            return
        if not self.pdf_folder:
            QMessageBox.warning(self, "Falta carpeta", "Debe seleccionar la carpeta con PDFs")
            return
        candidates = self.pdf_scanner.scan_folder(self.pdf_folder)
        self.results = [self.rule_engine.match(item, self.rules) for item in candidates]
        self.populate_table()
        self._refresh_metrics()
        self.log_message(f"PDFs analizados: {len(self.results)}")

    def preview_targets(self):
        if not self.results:
            QMessageBox.warning(self, "Sin datos", "Debe analizar PDFs primero")
            return
        self.sync_manual_values_from_table()
        self.results = self.rename_service.preview_targets(self.results)
        self.populate_table()
        self._refresh_metrics()
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
