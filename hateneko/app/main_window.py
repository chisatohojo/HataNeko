from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from hateneko.app.actions import CATEGORY_TO_STATUS, STATUS_LABELS
from hateneko.app.image_viewer import ImageViewer
from hateneko.app.logger import ActionLogger
from hateneko.app.settings import SettingsManager
from hateneko.app.thumbnail_list import ThumbnailList
from hateneko.core.file_manager import FileManager, MoveRecord
from hateneko.core.image_loader import ImageInfo, ImageLoader
from hateneko.core.scan_result import (
    STATUS_DELETED,
    STATUS_FIX,
    STATUS_NG,
    STATUS_OK,
    STATUS_SUSPICIOUS,
    STATUS_UNCONFIRMED,
    ScanResult,
)
from hateneko.core.scanner import build_default_scanner


MANUAL_STATUSES = {STATUS_OK, STATUS_FIX, STATUS_NG, STATUS_DELETED}


@dataclass(slots=True)
class UndoEntry:
    record: MoveRecord
    index: int
    previous_status: str
    previous_result: ScanResult | None


class ScanWorker(QObject):
    progress = Signal(str, object, int, int)
    finished = Signal()

    def __init__(self, paths: list[Path], settings: dict[str, Any]) -> None:
        super().__init__()
        self.paths = paths
        self.settings = dict(settings)

    @Slot()
    def run(self) -> None:
        scanner = build_default_scanner(self.settings)
        context: dict[str, Any] = {}
        total = len(self.paths)
        for index, path in enumerate(self.paths, start=1):
            result = scanner.scan_image(path, context)
            self.progress.emit(str(path), result, index, total)
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("破綻ねこ")
        self.resize(1280, 820)

        self.settings = SettingsManager()
        self.loader = ImageLoader()
        self.file_manager = FileManager()
        self.logger = ActionLogger()

        self.folder_path: Path | None = None
        self.image_paths: list[Path] = []
        self.statuses: dict[str, str] = {}
        self.scan_results: dict[str, ScanResult] = {}
        self.undo_stack: list[UndoEntry] = []
        self.current_index = -1
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None

        self._build_ui()
        self._install_shortcuts()
        self._sync_settings_controls()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)
        self.setCentralWidget(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([290, 680, 310])
        root_layout.addWidget(splitter, stretch=1)
        root_layout.addWidget(self._build_bottom_bar())

        self.statusBar().showMessage("フォルダを選択してください。")

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.folder_button = QPushButton("フォルダ選択")
        self.folder_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.folder_button.clicked.connect(self.select_folder)
        layout.addWidget(self.folder_button)

        self.filter_combo = QComboBox()
        for key, label in STATUS_LABELS.items():
            self.filter_combo.addItem(label, key)
        self.filter_combo.currentIndexChanged.connect(self._populate_thumbnails)
        layout.addWidget(self.filter_combo)

        self.thumbnail_list = ThumbnailList(int(self.settings.get("thumbnail_size", 160)))
        self.thumbnail_list.image_selected.connect(self._select_path_from_list)
        layout.addWidget(self.thumbnail_list, stretch=1)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.title_label = QLabel("未選択")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.viewer = ImageViewer()
        self.viewer.set_show_overlay(bool(self.settings.get("show_overlay", True)))
        layout.addWidget(self.viewer, stretch=1)

        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_progress.setTextVisible(True)
        layout.addWidget(self.scan_progress)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        info_group = QGroupBox("ファイル情報")
        info_layout = QFormLayout(info_group)
        self.file_name_label = QLabel("-")
        self.position_label = QLabel("-")
        self.resolution_label = QLabel("-")
        self.file_size_label = QLabel("-")
        self.status_label = QLabel("-")
        self.scan_status_label = QLabel("-")
        for label in [
            self.file_name_label,
            self.position_label,
            self.resolution_label,
            self.file_size_label,
            self.status_label,
            self.scan_status_label,
        ]:
            label.setWordWrap(True)
        info_layout.addRow("ファイル名", self.file_name_label)
        info_layout.addRow("位置", self.position_label)
        info_layout.addRow("解像度", self.resolution_label)
        info_layout.addRow("サイズ", self.file_size_label)
        info_layout.addRow("ステータス", self.status_label)
        info_layout.addRow("スキャン", self.scan_status_label)
        layout.addWidget(info_group)

        issues_group = QGroupBox("破綻候補リスト")
        issues_layout = QVBoxLayout(issues_group)
        self.issue_list = QListWidget()
        issues_layout.addWidget(self.issue_list)
        layout.addWidget(issues_group, stretch=1)

        settings_group = QGroupBox("設定")
        settings_layout = QFormLayout(settings_group)
        self.delete_mode_combo = QComboBox()
        self.delete_mode_combo.addItem("Deletedフォルダ", "move_to_deleted_folder")
        self.delete_mode_combo.addItem("Windowsゴミ箱", "send_to_recycle_bin")
        self.delete_mode_combo.currentIndexChanged.connect(self._update_delete_mode)

        self.auto_advance_check = QCheckBox()
        self.auto_advance_check.toggled.connect(
            lambda value: self.settings.set("auto_advance_after_action", value)
        )
        self.overlay_check = QCheckBox()
        self.overlay_check.toggled.connect(self._update_overlay)

        self.target_width_spin = QSpinBox()
        self.target_width_spin.setRange(1, 50000)
        self.target_width_spin.valueChanged.connect(
            lambda value: self.settings.set("target_width", value)
        )
        self.target_height_spin = QSpinBox()
        self.target_height_spin.setRange(1, 50000)
        self.target_height_spin.valueChanged.connect(
            lambda value: self.settings.set("target_height", value)
        )
        self.aspect_tolerance_spin = QDoubleSpinBox()
        self.aspect_tolerance_spin.setRange(0.001, 1.0)
        self.aspect_tolerance_spin.setSingleStep(0.01)
        self.aspect_tolerance_spin.setDecimals(3)
        self.aspect_tolerance_spin.valueChanged.connect(
            lambda value: self.settings.set("allow_aspect_ratio_tolerance", value)
        )

        settings_layout.addRow("Delete", self.delete_mode_combo)
        settings_layout.addRow("自動送り", self.auto_advance_check)
        settings_layout.addRow("赤枠表示", self.overlay_check)
        settings_layout.addRow("基準幅", self.target_width_spin)
        settings_layout.addRow("基準高", self.target_height_spin)
        settings_layout.addRow("比率誤差", self.aspect_tolerance_spin)
        layout.addWidget(settings_group)

        return panel

    def _build_bottom_bar(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.prev_button = QPushButton("前へ")
        self.prev_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft))
        self.prev_button.clicked.connect(self.previous_image)

        self.next_button = QPushButton("次へ")
        self.next_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
        self.next_button.clicked.connect(self.next_image)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(lambda: self.move_current("ok"))
        self.fix_button = QPushButton("Fix")
        self.fix_button.clicked.connect(lambda: self.move_current("fix"))
        self.ng_button = QPushButton("NG")
        self.ng_button.clicked.connect(lambda: self.move_current("ng"))
        self.delete_button = QPushButton("Delete")
        self.delete_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_button.clicked.connect(lambda: self.move_current("deleted"))
        self.undo_button = QPushButton("Undo")
        self.undo_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.undo_button.clicked.connect(self.undo_last_action)
        self.scan_button = QPushButton("スキャン開始")
        self.scan_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.scan_button.clicked.connect(self.start_scan)

        for button in [
            self.prev_button,
            self.next_button,
            self.ok_button,
            self.fix_button,
            self.ng_button,
            self.delete_button,
            self.undo_button,
            self.scan_button,
        ]:
            layout.addWidget(button)
        layout.addStretch(1)
        return frame

    def _install_shortcuts(self) -> None:
        shortcuts = [
            ("Left", self.previous_image),
            ("A", self.previous_image),
            ("Right", self.next_image),
            ("D", self.next_image),
            ("1", lambda: self.move_current("ok")),
            ("2", lambda: self.move_current("fix")),
            ("3", lambda: self.move_current("ng")),
            ("Delete", lambda: self.move_current("deleted")),
            ("Ctrl+Z", self.undo_last_action),
            ("Space", self.viewer.toggle_zoom_mode),
            ("F5", self.reload_folder),
        ]
        for sequence, callback in shortcuts:
            QShortcut(QKeySequence(sequence), self, activated=callback)

    def _sync_settings_controls(self) -> None:
        delete_mode = self.settings.get("delete_mode", "move_to_deleted_folder")
        index = self.delete_mode_combo.findData(delete_mode)
        self.delete_mode_combo.setCurrentIndex(max(0, index))
        self.auto_advance_check.setChecked(bool(self.settings.get("auto_advance_after_action", True)))
        self.overlay_check.setChecked(bool(self.settings.get("show_overlay", True)))
        self.target_width_spin.setValue(int(self.settings.get("target_width", 1024)))
        self.target_height_spin.setValue(int(self.settings.get("target_height", 1536)))
        self.aspect_tolerance_spin.setValue(
            float(self.settings.get("allow_aspect_ratio_tolerance", 0.05))
        )

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "画像フォルダを選択")
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path) -> None:
        self.folder_path = folder
        self.file_manager.ensure_output_dirs(folder)
        self.logger.set_base_folder(folder)
        self.image_paths = self.loader.list_images(folder)
        self.statuses = {str(path): STATUS_UNCONFIRMED for path in self.image_paths}
        self.scan_results.clear()
        self.undo_stack.clear()
        self.current_index = 0 if self.image_paths else -1
        self.scan_progress.setValue(0)
        self._populate_thumbnails()
        self._show_current()
        self.statusBar().showMessage(f"{len(self.image_paths)} 件の画像を読み込みました。")

    def reload_folder(self) -> None:
        if self.folder_path is None:
            return
        previous_path = self._current_path()
        old_statuses = dict(self.statuses)
        old_results = dict(self.scan_results)
        self.image_paths = self.loader.list_images(self.folder_path)
        self.statuses = {
            str(path): old_statuses.get(str(path), STATUS_UNCONFIRMED)
            for path in self.image_paths
        }
        self.scan_results = {
            str(path): old_results[str(path)]
            for path in self.image_paths
            if str(path) in old_results
        }
        if previous_path in self.image_paths:
            self.current_index = self.image_paths.index(previous_path)
        else:
            self.current_index = 0 if self.image_paths else -1
        self._populate_thumbnails()
        self._show_current()
        self.statusBar().showMessage("フォルダを再読み込みしました。")

    def previous_image(self) -> None:
        self._move_visible_selection(-1)

    def next_image(self) -> None:
        self._move_visible_selection(1)

    def move_current(self, category: str) -> None:
        path = self._current_path()
        if path is None or self.folder_path is None:
            return

        previous_status = self.statuses.get(str(path), STATUS_UNCONFIRMED)
        previous_result = self.scan_results.get(str(path))
        index = self.current_index

        try:
            record = self.file_manager.move_to_category(
                path,
                self.folder_path,
                category,
                str(self.settings.get("delete_mode", "move_to_deleted_folder")),
            )
        except Exception as exc:
            QMessageBox.warning(self, "移動できません", str(exc))
            return

        if record.destination is None:
            self._remove_path_at(index)
            self.logger.log(record.action, source=str(path))
            QMessageBox.information(self, "Undo対象外", "Windowsゴミ箱への移動はUndo対象外です。")
        else:
            destination = record.destination
            self.image_paths[index] = destination
            self.statuses.pop(str(path), None)
            self.statuses[str(destination)] = CATEGORY_TO_STATUS[category]
            if previous_result:
                self.scan_results.pop(str(path), None)
                previous_result.file_path = str(destination)
                self.scan_results[str(destination)] = previous_result
            self.undo_stack.append(
                UndoEntry(
                    record=record,
                    index=index,
                    previous_status=previous_status,
                    previous_result=previous_result,
                )
            )
            self.logger.log(record.action, source=str(path), destination=str(destination))

        if self.image_paths:
            if bool(self.settings.get("auto_advance_after_action", True)):
                self.current_index = min(index + 1, len(self.image_paths) - 1)
            else:
                self.current_index = min(index, len(self.image_paths) - 1)
        else:
            self.current_index = -1

        self._populate_thumbnails()
        self._show_current()

    def undo_last_action(self) -> None:
        if not self.undo_stack:
            self.statusBar().showMessage("Undoできる操作がありません。")
            return

        entry = self.undo_stack.pop()
        try:
            restored = self.file_manager.undo_move(entry.record)
        except Exception as exc:
            QMessageBox.warning(self, "Undoできません", str(exc))
            return

        destination = entry.record.destination
        if destination is not None:
            self.statuses.pop(str(destination), None)
            self.scan_results.pop(str(destination), None)

        if entry.index < len(self.image_paths):
            self.image_paths[entry.index] = restored
            self.current_index = entry.index
        else:
            self.image_paths.append(restored)
            self.current_index = len(self.image_paths) - 1

        self.statuses[str(restored)] = entry.previous_status
        if entry.previous_result is not None:
            entry.previous_result.file_path = str(restored)
            self.scan_results[str(restored)] = entry.previous_result

        self.logger.log("undo", source=str(destination), destination=str(restored))
        self._populate_thumbnails()
        self._show_current()
        self.statusBar().showMessage("直前の移動を戻しました。")

    def start_scan(self) -> None:
        if not self.image_paths or self._scan_thread is not None:
            return

        paths = [path for path in self.image_paths if path.exists()]
        self.scan_progress.setRange(0, max(1, len(paths)))
        self.scan_progress.setValue(0)
        self.scan_button.setEnabled(False)
        self.statusBar().showMessage("スキャン中...")

        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(paths, self.settings.data)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.start()

    @Slot(str, object, int, int)
    def _on_scan_progress(
        self,
        path_str: str,
        result: ScanResult,
        done: int,
        total: int,
    ) -> None:
        self.scan_results[path_str] = result
        old_status = self.statuses.get(path_str, STATUS_UNCONFIRMED)
        if old_status not in MANUAL_STATUSES:
            self.statuses[path_str] = STATUS_SUSPICIOUS if result.issues else STATUS_UNCONFIRMED
        self.logger.log(
            "scan",
            file=path_str,
            status=result.status,
            issues=result.issue_types,
        )
        self.scan_progress.setValue(done)
        self.scan_progress.setFormat(f"{done} / {total}")

        if str(self._current_path()) == path_str:
            self._show_current()
        self._populate_thumbnails(keep_selection=True)

    @Slot()
    def _on_scan_finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.statusBar().showMessage("スキャンが完了しました。")
        self._scan_thread = None
        self._scan_worker = None
        self._populate_thumbnails(keep_selection=True)
        self._show_current()

    def _populate_thumbnails(self, keep_selection: bool = False) -> None:
        current = self._current_path() if keep_selection else None
        if current is None and self.current_index >= 0:
            current = self.image_paths[self.current_index]
        filter_status = self.filter_combo.currentData() or "all"
        self.thumbnail_list.set_images(
            self.image_paths,
            self.statuses,
            self.scan_results,
            filter_status,
        )
        visible = self.thumbnail_list.visible_paths()
        if current in visible:
            self.thumbnail_list.select_path(current)
        elif visible and not keep_selection:
            self.current_index = self.image_paths.index(visible[0])
            self.thumbnail_list.select_path(visible[0])
        elif not visible:
            self.thumbnail_list.select_path(None)

    def _select_path_from_list(self, path_str: str) -> None:
        path = Path(path_str)
        if path in self.image_paths:
            self.current_index = self.image_paths.index(path)
            self._show_current()

    def _show_current(self) -> None:
        path = self._current_path()
        if path is None:
            self.title_label.setText("未選択")
            self.viewer.set_image(None)
            self._set_empty_info()
            return

        result = self.scan_results.get(str(path))
        issues = result.issues if result else []
        self.viewer.set_image(path, issues)
        self.thumbnail_list.select_path(path)
        self.title_label.setText(path.name)
        self._update_info(path, self.loader.get_info(path), result)

    def _update_info(
        self,
        path: Path,
        info: ImageInfo,
        result: ScanResult | None,
    ) -> None:
        self.file_name_label.setText(path.name)
        self.position_label.setText(f"{self.current_index + 1} / {len(self.image_paths)}")
        if info.width is None or info.height is None:
            self.resolution_label.setText("読み込みエラー")
        else:
            self.resolution_label.setText(f"{info.width} x {info.height}")
        self.file_size_label.setText(self._format_size(info.size_bytes))
        status = self.statuses.get(str(path), STATUS_UNCONFIRMED)
        self.status_label.setText(STATUS_LABELS.get(status, status))

        self.issue_list.clear()
        if result is None:
            self.scan_status_label.setText("-")
            return

        self.scan_status_label.setText(STATUS_LABELS.get(result.status, result.status))
        for issue in result.issues:
            self.issue_list.addItem(f"[{issue.severity}] {issue.message}")

    def _set_empty_info(self) -> None:
        for label in [
            self.file_name_label,
            self.position_label,
            self.resolution_label,
            self.file_size_label,
            self.status_label,
            self.scan_status_label,
        ]:
            label.setText("-")
        self.issue_list.clear()

    def _move_visible_selection(self, delta: int) -> None:
        visible = self.thumbnail_list.visible_paths()
        if not visible:
            return
        current = self._current_path()
        if current in visible:
            index = visible.index(current)
            target_index = max(0, min(len(visible) - 1, index + delta))
        else:
            target_index = 0
        target = visible[target_index]
        self.current_index = self.image_paths.index(target)
        self._show_current()

    def _current_path(self) -> Path | None:
        if 0 <= self.current_index < len(self.image_paths):
            return self.image_paths[self.current_index]
        return None

    def _remove_path_at(self, index: int) -> None:
        if not (0 <= index < len(self.image_paths)):
            return
        path = self.image_paths.pop(index)
        self.statuses.pop(str(path), None)
        self.scan_results.pop(str(path), None)

    def _update_delete_mode(self) -> None:
        value = self.delete_mode_combo.currentData()
        if value:
            self.settings.set("delete_mode", value)

    def _update_overlay(self, enabled: bool) -> None:
        self.settings.set("show_overlay", enabled)
        self.viewer.set_show_overlay(enabled)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        value = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{size_bytes} B"


def run_app() -> int:
    app = QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()

