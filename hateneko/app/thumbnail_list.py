from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from hateneko.app.actions import STATUS_COLORS, STATUS_LABELS
from hateneko.core.scan_result import ScanResult


class ThumbnailList(QListWidget):
    image_selected = Signal(str)

    def __init__(self, thumbnail_size: int = 160, parent=None) -> None:
        super().__init__(parent)
        self._thumbnail_size = thumbnail_size
        self.setIconSize(QSize(thumbnail_size, thumbnail_size))
        self.setSpacing(6)
        self.setUniformItemSizes(False)
        self.currentItemChanged.connect(self._emit_current_path)

    def set_thumbnail_size(self, size: int) -> None:
        self._thumbnail_size = size
        self.setIconSize(QSize(size, size))

    def set_images(
        self,
        paths: list[Path],
        statuses: dict[str, str],
        scan_results: dict[str, ScanResult],
        filter_status: str = "all",
    ) -> None:
        self.blockSignals(True)
        self.clear()
        for path in paths:
            status = statuses.get(str(path), "unconfirmed")
            if filter_status != "all" and status != filter_status:
                continue
            item = QListWidgetItem(self._thumbnail_icon(path), self._item_text(path, status, scan_results))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            item.setBackground(QColor(STATUS_COLORS.get(status, "#f3f4f6")))
            self.addItem(item)
        self.blockSignals(False)

    def select_path(self, path: str | Path | None) -> None:
        if path is None:
            self.setCurrentItem(None)
            return
        wanted = str(Path(path))
        self.blockSignals(True)
        for row in range(self.count()):
            item = self.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == wanted:
                self.setCurrentItem(item)
                break
        else:
            self.setCurrentItem(None)
        self.blockSignals(False)

    def visible_paths(self) -> list[Path]:
        return [
            Path(self.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.count())
        ]

    def _emit_current_path(self, current: QListWidgetItem | None, previous) -> None:
        if current is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        if path:
            self.image_selected.emit(path)

    def _thumbnail_icon(self, path: Path) -> QIcon:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            pixmap = QPixmap(self._thumbnail_size, self._thumbnail_size)
            pixmap.fill(QColor("#374151"))
        else:
            pixmap = QPixmap.fromImage(image).scaled(
                self._thumbnail_size,
                self._thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return QIcon(pixmap)

    @staticmethod
    def _item_text(
        path: Path,
        status: str,
        scan_results: dict[str, ScanResult],
    ) -> str:
        label = STATUS_LABELS.get(status, status)
        result = scan_results.get(str(path))
        if result and result.issues:
            label = f"{label} / {len(result.issues)}件"
        return f"{path.name}\n{label}"

