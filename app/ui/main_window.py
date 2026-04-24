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

from app.services.oracle_client import (
    clear_oracle_session,
    clear_remembered_credentials,
)
from app.services.oracle_rule_service import (
    OraclePdfRule,
    fetch_oracle_pdf_rules,
    resolve_pdf_name_from_rules,
)
from app.services.folder_flatten_service import flatten_request_result_folders
from app.services.pdf_service import PdfScanner
from app.ui.oracle_login_dialog import OracleLoginDialog


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
            "Herramienta para analizar y renombrar PDFs hospitalarios.",
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
            self.progress.emit("Aplanando carpetas de solicitudes/resultados...")
            flatten_result = flatten_request_result_folders(self.folder)

            if flatten_result.moved:
                self.progress.emit(
                    f"Se movieron {flatten_result.moved} PDF(s) desde subcarpetas."
                )
            if flatten_result.errors:
                self.progress.emit(
                    f"Aplanado con advertencias: {len(flatten_result.errors)} error(es)."
                )

            self.progress.emit("Escaneando PDFs...")
            scanner = PdfScanner(self.config)
            candidates = scanner.scan_folder(self.folder)
            self.progress.emit(
                f"Evaluando {len(candidates)} archivo(s) con reglas Oracle..."
            )
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
                    "suggested_final_name": (target or "").strip(),
                    "target_path": (
                        str(candidate.original_path.parent / (target or "").strip())
                        if target and target.strip() != candidate.original_name
                        else ""
                    ),
                    "status": reason,
                    "reason": reason,
                })

            if (
                flatten_result.moved
                or flatten_result.removed_dirs
                or flatten_result.skipped_dirs
            ):
                results.insert(
                    0,
                    {
                        "original_name": "[APLANADO DE CARPETAS]",
                        "original_path": self.folder,
                        "suggested_final_name": "",
                        "target_path": "",
                        "status": "INFO",
                        "reason": (
                            f"PDFs movidos: {flatten_result.moved} | "
                            f"Carpetas eliminadas: {flatten_result.removed_dirs} | "
                            f"Carpetas no eliminadas por no estar vacias: "
                            f"{flatten_result.skipped_dirs}"
                        ),
                    },
                )

            for err in flatten_result.errors:
                results.insert(
                    0,
                    {
                        "original_name": "[ERROR APLANADO]",
                        "original_path": self.folder,
                        "suggested_final_name": "",
                        "target_path": "",
                        "status": "ERROR",
                        "reason": err,
                    },
                )

            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.folder = config.get("last_folder") or config.get("default_folder") or ""
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
        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addAction("Autores").triggered.connect(self.show_credits)

        oracle_menu = self.menuBar().addMenu("Oracle")
        oracle_menu.addAction("Volver a pedir credenciales").triggered.connect(self.relogin_oracle)

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

        subtitle = QLabel("1) Seleccionar carpeta  2) Renombrar PDFs")
        subtitle.setStyleSheet("font-size: 12px; color: #51606b; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # Carpeta
        folder_card = self._card()
        folder_layout = QVBoxLayout(folder_card)
        lbl = QLabel("Carpeta con PDFs")
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Seleccione la carpeta que contiene los PDFs")
        self.folder_edit.setText(self.folder)

        btn_folder = QPushButton("Elegir carpeta")
        btn_folder.setMinimumHeight(44)
        btn_folder.clicked.connect(self.select_folder)

        row = QHBoxLayout()
        row.addWidget(self.folder_edit, stretch=1)
        row.addWidget(btn_folder)
        folder_layout.addWidget(lbl)
        folder_layout.addLayout(row)
        layout.addWidget(folder_card)

        # Acciones — un solo botón
        actions_card = self._card()
        actions_layout = QHBoxLayout(actions_card)
        self.btn_rename = QPushButton("Renombrar PDFs")
        self.btn_rename.setMinimumHeight(56)
        self.btn_rename.clicked.connect(self.run_rename)
        actions_layout.addWidget(self.btn_rename)
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

    def _log(self, text: str):
        self.log.append(text)

    # ── Acciones ───────────────────────────────────────────
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta", self.folder or "."
        )
        if folder:
            self.folder = folder
            self.folder_edit.setText(folder)

    def run_rename(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Validación", "Se requiere seleccionar la carpeta.")
            return

        if not Path(folder).exists():
            QMessageBox.warning(self, "Validación", "La carpeta seleccionada no existe.")
            return

        answer = QMessageBox.question(
            self,
            "Confirmar renombrado",
            "Se van a renombrar físicamente los archivos.\n\n¿Desea continuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.folder = folder
        self._run()

    def _run(self):
        if not self.folder:
            QMessageBox.warning(self, "Falta carpeta", "Seleccione la carpeta primero")
            return
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "En curso", "Ya hay un proceso ejecutándose")
            return

        self.btn_rename.setEnabled(False)
        self.status_label.setText("Procesando renombrado...")
        self._log("-" * 50)
        self._log(f"Inicio en {self.folder}")

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
        self.btn_rename.setEnabled(True)
        self.status_label.setText("Renombrado terminado.")
        self._apply_renames_with_dedup(results)
        self._populate_table()
        self._log(f"Total archivos evaluados: {len(results)}")

        renamed = sum(
            1 for r in results
            if r.get("suggested_final_name") and r["original_name"] != r["suggested_final_name"]
        )
        ok = sum(
            1 for r in results
            if any(x in r["status"] for x in ["EXACTO", "ORACLE"])
        )
        self.status_label.setText(
            f"{len(results)} evaluados, {renamed} renombrados, {ok} con coincidencia Oracle"
        )
        self.thread = None
        self.worker = None

    def _on_failed(self, msg: str):
        self.status_label.setText("Error")
        self._log(f"ERROR: {msg}")
        QMessageBox.critical(self, "Error", msg)
        self.btn_rename.setEnabled(True)
        self.thread = None
        self.worker = None

    def _apply_renames_with_dedup(self, results: list):
        """
        Regla funcional:
        - Un solo archivo que resuelve a PI.pdf queda como PI.pdf.
        - Solo se usa _01, _02, ... si varios archivos del mismo lote
          resuelven al mismo nombre final.
        - No se sobrescriben archivos existentes.
        """
        candidates = [
            r for r in results
            if r.get("suggested_final_name")
            and r["original_name"] != r["suggested_final_name"]
        ]

        groups: dict[tuple[str, str], list] = {}
        for item in candidates:
            dest = (item["suggested_final_name"] or "").strip()
            if not dest:
                continue
            orig = Path(item["original_path"])
            groups.setdefault((str(orig.parent.resolve()), dest), []).append(item)

        renamed = 0
        for (parent_dir, dest), items in sorted(groups.items()):
            suffix = Path(dest).suffix
            stem = Path(dest).stem

            if len(items) == 1:
                item = items[0]
                orig = Path(item["original_path"])
                target = orig.parent / dest

                if target.exists():
                    try:
                        same_file = orig.resolve() == target.resolve()
                    except Exception:
                        same_file = False

                    if not same_file:
                        self._log(
                            f"  COLISION EN CARPETA: {item['original_name']} no se renombro porque ya existe {dest} en {orig.parent}"
                        )
                        continue

                self._rename_file(item, dest)
                renamed += 1
                continue

            items_sorted = sorted(
                items,
                key=lambda x: x["original_name"].upper(),
            )

            for idx, item in enumerate(items_sorted, start=1):
                new_name = f"{stem}_{idx:02d}{suffix}"
                orig = Path(item["original_path"])
                target = orig.parent / new_name

                if target.exists():
                    try:
                        same_file = orig.resolve() == target.resolve()
                    except Exception:
                        same_file = False

                    if not same_file:
                        seq = idx
                        while True:
                            seq += 1
                            candidate_name = f"{stem}_{seq:02d}{suffix}"
                            candidate_target = orig.parent / candidate_name
                            if not candidate_target.exists():
                                new_name = candidate_name
                                break

                self._rename_file(item, new_name)
                renamed += 1

        self._log(f"Total renombrados: {renamed}")

    def _rename_file(self, item: dict, final_name: str):
        try:
            # Respetar EXACTAMENTE el nombre entregado por Oracle
            # No forzar .pdf en minúscula ni alterar mayúsculas/minúsculas
            final_name = (final_name or "").strip()

            if not final_name:
                raise ValueError("Nombre final vacío")

            orig = Path(item["original_path"])
            target = orig.parent / final_name

            if target.exists():
                try:
                    same_file = orig.resolve() == target.resolve()
                except Exception:
                    same_file = False

                if not same_file:
                    raise FileExistsError(
                        f"Ya existe el archivo destino: {target.name}"
                    )
                self._log(f"  = {item['original_name']} ya estaba como {final_name}")
                return

            orig.rename(target)
            self._log(f"  ✓ {item['original_name']} -> {final_name}")
        except Exception as exc:
            self._log(f"  X {item['original_name']}: {exc}")

    def _populate_table(self):
        self.table.setRowCount(len(self.results))
        for row, item in enumerate(self.results):
            self.table.setItem(row, 0, QTableWidgetItem(item["original_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(item["suggested_final_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(item["target_path"]))
            self.table.setItem(row, 3, QTableWidgetItem(item["reason"]))
        self.table.resizeRowsToContents()

    def relogin_oracle(self):
        clear_oracle_session()
        clear_remembered_credentials()

        dlg = OracleLoginDialog(config=self.config, parent=self)
        if dlg.exec() == OracleLoginDialog.DialogCode.Accepted:
            QMessageBox.information(
                self, "Oracle", "Credenciales actualizadas correctamente."
            )
        else:
            QMessageBox.warning(
                self, "Oracle", "No se actualizaron las credenciales."
            )

    def show_credits(self):
        dlg = CreditsDialog(self.config, self)
        dlg.exec()
