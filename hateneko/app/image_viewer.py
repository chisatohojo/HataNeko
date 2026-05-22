from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from hateneko.core.scan_result import Issue


class ImageViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._path: Path | None = None
        self._issues: list[Issue] = []
        self._fit_to_window = True
        self._show_overlay = True
        self._error: str | None = None
        self.setMinimumSize(420, 360)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_image(self, path: str | Path | None, issues: list[Issue] | None = None) -> None:
        self._path = Path(path) if path else None
        self._issues = issues or []
        self._error = None
        self._pixmap = QPixmap()

        if self._path is not None:
            reader = QImageReader(str(self._path))
            reader.setAutoTransform(True)
            image = reader.read()
            if image.isNull():
                self._error = reader.errorString() or "画像を読み込めませんでした。"
            else:
                self._pixmap = QPixmap.fromImage(image)
        self.update()

    def set_show_overlay(self, enabled: bool) -> None:
        self._show_overlay = enabled
        self.update()

    def toggle_zoom_mode(self) -> None:
        self._fit_to_window = not self._fit_to_window
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt method name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111827"))

        if self._pixmap.isNull():
            painter.setPen(QColor("#e5e7eb"))
            painter.setFont(QFont("Meiryo", 12))
            message = self._error or "画像を選択してください。"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, message)
            return

        target = self._target_rect()
        painter.drawPixmap(target, self._pixmap)

        if self._show_overlay and self._issues:
            self._draw_overlays(painter, target)

    def _target_rect(self) -> QRect:
        source_width = max(1, self._pixmap.width())
        source_height = max(1, self._pixmap.height())
        available = self.rect().adjusted(12, 12, -12, -12)

        if self._fit_to_window:
            scale = min(
                available.width() / source_width,
                available.height() / source_height,
                1.0 if source_width <= available.width() and source_height <= available.height() else 10.0,
            )
        else:
            scale = 1.0

        width = max(1, int(source_width * scale))
        height = max(1, int(source_height * scale))
        left = available.left() + (available.width() - width) // 2
        top = available.top() + (available.height() - height) // 2
        return QRect(left, top, width, height)

    def _draw_overlays(self, painter: QPainter, target: QRect) -> None:
        image_width = max(1, self._pixmap.width())
        image_height = max(1, self._pixmap.height())
        scale_x = target.width() / image_width
        scale_y = target.height() / image_height

        danger_pen = QPen(QColor("#ef4444"), 3)
        warning_pen = QPen(QColor("#f59e0b"), 3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for issue in self._issues:
            if issue.bbox is None:
                continue
            x, y, width, height = issue.bbox
            rect = QRect(
                target.left() + int(x * scale_x),
                target.top() + int(y * scale_y),
                max(8, int(width * scale_x)),
                max(8, int(height * scale_y)),
            )
            painter.setPen(danger_pen if issue.severity == "danger" else warning_pen)
            painter.drawRect(rect)

