"""
Shape Editor Tab - Contains all shape editing functionality including:
- Resizable shape items (rect, ellipse, line)
- Gradient and color dialogs
- Shadow/glow controls
- Layers panel
- Undo commands for shape transforms
"""

import math
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt6.QtGui import (
    QPixmap,
    QImage,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPalette,
    QLinearGradient,
    QUndoCommand,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsDropShadowEffect,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QAbstractItemView,
    QColorDialog,
)

if TYPE_CHECKING:
    from gui import MainWindow


# -----------------------------------------------------------------------------
# Custom Graphics Items with Resizing
# -----------------------------------------------------------------------------


class ResizableRectItem(QGraphicsRectItem):
    """Rectangle item with hover-based resize handles on corners and edges."""

    HANDLE_MARGIN = 12
    MIN_SIZE = 4

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptHoverEvents(True)
        self._resizing = False
        self._handle: str | None = None
        self._orig_rect: QRectF | None = None
        self._orig_pos: QPointF | None = None

    def _handle_at(self, pos: QPointF) -> str | None:
        r = self.rect()
        left, right, top, bottom = r.left(), r.right(), r.top(), r.bottom()
        x, y = pos.x(), pos.y()
        m = self.HANDLE_MARGIN

        on_left = abs(x - left) <= m
        on_right = abs(x - right) <= m
        on_top = abs(y - top) <= m
        on_bottom = abs(y - bottom) <= m

        if on_left and on_top:
            return "top_left"
        if on_right and on_top:
            return "top_right"
        if on_left and on_bottom:
            return "bottom_left"
        if on_right and on_bottom:
            return "bottom_right"
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        return None

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle in ("top_left", "bottom_right"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle in ("top_right", "bottom_left"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif handle in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif handle in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.pos())
            if handle:
                self._resizing = True
                self._handle = handle
                self._orig_rect = QRectF(self.rect())
                self._orig_pos = QPointF(event.pos())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resizing and self._orig_rect is not None and self._orig_pos is not None:
            delta = event.pos() - self._orig_pos
            r = QRectF(self._orig_rect)
            
            # Check if Shift is held for proportional resize
            shift_held = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            
            if shift_held:
                # Proportional resize from ANY handle (corner or edge)
                orig_w = self._orig_rect.width()
                orig_h = self._orig_rect.height()
                if orig_w == 0 or orig_h == 0:
                    return
                aspect = orig_w / orig_h
                center = self._orig_rect.center()
                
                # Determine scale based on handle type
                if self._handle in ("left", "right"):
                    # Horizontal edge - use X delta
                    new_w = orig_w + delta.x() if self._handle == "right" else orig_w - delta.x()
                    new_h = new_w / aspect
                elif self._handle in ("top", "bottom"):
                    # Vertical edge - use Y delta
                    new_h = orig_h + delta.y() if self._handle == "bottom" else orig_h - delta.y()
                    new_w = new_h * aspect
                else:
                    # Corner - use larger delta
                    dx = abs(delta.x())
                    dy = abs(delta.y())
                    if dx > dy:
                        new_w = orig_w + delta.x() if "right" in self._handle else orig_w - delta.x()
                        new_h = new_w / aspect
                    else:
                        new_h = orig_h + delta.y() if "bottom" in self._handle else orig_h - delta.y()
                        new_w = new_h * aspect
                
                if new_w >= self.MIN_SIZE and new_h >= self.MIN_SIZE:
                    # Resize from center for uniform scaling
                    r = QRectF(
                        center.x() - new_w / 2,
                        center.y() - new_h / 2,
                        new_w,
                        new_h
                    )
            else:
                # Normal resize (non-proportional)
                if "left" in self._handle:
                    new_left = r.left() + delta.x()
                    if r.right() - new_left >= self.MIN_SIZE:
                        r.setLeft(new_left)
                if "right" in self._handle:
                    new_right = r.right() + delta.x()
                    if new_right - r.left() >= self.MIN_SIZE:
                        r.setRight(new_right)
                if "top" in self._handle:
                    new_top = r.top() + delta.y()
                    if r.bottom() - new_top >= self.MIN_SIZE:
                        r.setTop(new_top)
                if "bottom" in self._handle:
                    new_bottom = r.bottom() + delta.y()
                    if new_bottom - r.top() >= self.MIN_SIZE:
                        r.setBottom(new_bottom)

            self.setRect(r)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resizing = False
        self._handle = None
        self._orig_rect = None
        self._orig_pos = None
        super().mouseReleaseEvent(event)


class ResizableEllipseItem(QGraphicsEllipseItem):
    """Ellipse/circle item with hover-based resize handles."""

    HANDLE_MARGIN = 12
    MIN_SIZE = 4

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptHoverEvents(True)
        self._resizing = False
        self._handle: str | None = None
        self._orig_rect: QRectF | None = None
        self._orig_pos: QPointF | None = None

    def _handle_at(self, pos: QPointF) -> str | None:
        r = self.rect()
        left, right, top, bottom = r.left(), r.right(), r.top(), r.bottom()
        x, y = pos.x(), pos.y()
        m = self.HANDLE_MARGIN

        on_left = abs(x - left) <= m
        on_right = abs(x - right) <= m
        on_top = abs(y - top) <= m
        on_bottom = abs(y - bottom) <= m

        if on_left and on_top:
            return "top_left"
        if on_right and on_top:
            return "top_right"
        if on_left and on_bottom:
            return "bottom_left"
        if on_right and on_bottom:
            return "bottom_right"
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        return None

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle in ("top_left", "bottom_right"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle in ("top_right", "bottom_left"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif handle in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif handle in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.pos())
            if handle:
                self._resizing = True
                self._handle = handle
                self._orig_rect = QRectF(self.rect())
                self._orig_pos = QPointF(event.pos())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resizing and self._orig_rect is not None and self._orig_pos is not None:
            delta = event.pos() - self._orig_pos
            r = QRectF(self._orig_rect)
            
            # Check if Shift is held for proportional resize
            shift_held = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            
            if shift_held:
                # Proportional resize from ANY handle (corner or edge)
                orig_w = self._orig_rect.width()
                orig_h = self._orig_rect.height()
                if orig_w == 0 or orig_h == 0:
                    return
                aspect = orig_w / orig_h
                center = self._orig_rect.center()
                
                # Determine scale based on handle type
                if self._handle in ("left", "right"):
                    # Horizontal edge - use X delta
                    new_w = orig_w + delta.x() if self._handle == "right" else orig_w - delta.x()
                    new_h = new_w / aspect
                elif self._handle in ("top", "bottom"):
                    # Vertical edge - use Y delta
                    new_h = orig_h + delta.y() if self._handle == "bottom" else orig_h - delta.y()
                    new_w = new_h * aspect
                else:
                    # Corner - use larger delta
                    dx = abs(delta.x())
                    dy = abs(delta.y())
                    if dx > dy:
                        new_w = orig_w + delta.x() if "right" in self._handle else orig_w - delta.x()
                        new_h = new_w / aspect
                    else:
                        new_h = orig_h + delta.y() if "bottom" in self._handle else orig_h - delta.y()
                        new_w = new_h * aspect
                
                if new_w >= self.MIN_SIZE and new_h >= self.MIN_SIZE:
                    # Resize from center for uniform scaling
                    r = QRectF(
                        center.x() - new_w / 2,
                        center.y() - new_h / 2,
                        new_w,
                        new_h
                    )
            else:
                # Normal resize (non-proportional)
                if "left" in self._handle:
                    new_left = r.left() + delta.x()
                    if r.right() - new_left >= self.MIN_SIZE:
                        r.setLeft(new_left)
                if "right" in self._handle:
                    new_right = r.right() + delta.x()
                    if new_right - r.left() >= self.MIN_SIZE:
                        r.setRight(new_right)
                if "top" in self._handle:
                    new_top = r.top() + delta.y()
                    if r.bottom() - new_top >= self.MIN_SIZE:
                        r.setTop(new_top)
                if "bottom" in self._handle:
                    new_bottom = r.bottom() + delta.y()
                    if new_bottom - r.top() >= self.MIN_SIZE:
                        r.setBottom(new_bottom)

            self.setRect(r)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resizing = False
        self._handle = None
        self._orig_rect = None
        self._orig_pos = None
        super().mouseReleaseEvent(event)


class ResizableLineItem(QGraphicsLineItem):
    """Line item with resize handles on its endpoints."""

    HANDLE_MARGIN = 12
    MIN_LENGTH = 2

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptHoverEvents(True)
        self._resizing = False
        self._handle: str | None = None
        self._orig_line: QLineF | None = None
        self._orig_pos: QPointF | None = None

    def _handle_at(self, pos: QPointF) -> str | None:
        line = self.line()
        start = line.p1()
        end = line.p2()
        m = self.HANDLE_MARGIN
        if (pos - start).manhattanLength() <= m:
            return "start"
        if (pos - end).manhattanLength() <= m:
            return "end"
        return None

    def hoverMoveEvent(self, event) -> None:
        handle = self._handle_at(event.pos())
        if handle:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.pos())
            if handle:
                self._resizing = True
                self._handle = handle
                self._orig_line = QLineF(self.line())
                self._orig_pos = QPointF(event.pos())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resizing and self._orig_line is not None and self._orig_pos is not None:
            delta = event.pos() - self._orig_pos
            line = QLineF(self._orig_line)

            if self._handle == "start":
                new_start = line.p1() + delta
                if (line.p2() - new_start).manhattanLength() >= self.MIN_LENGTH:
                    line.setP1(new_start)
            elif self._handle == "end":
                new_end = line.p2() + delta
                if (new_end - line.p1()).manhattanLength() >= self.MIN_LENGTH:
                    line.setP2(new_end)

            self.setLine(line)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resizing = False
        self._handle = None
        self._orig_line = None
        self._orig_pos = None
        super().mouseReleaseEvent(event)


# -----------------------------------------------------------------------------
# Shadow Direction Widget
# -----------------------------------------------------------------------------


class ShadowDirectionWidget(QWidget):
    """Small square control to pick glow direction."""

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__(owner)
        self._owner = owner
        self._mode: str = "all"
        self.setFixedSize(40, 40)

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        rect = self.rect().adjusted(2, 2, -2, -2)

        p.fillRect(rect, QColor("#202020"))

        base_pen = QPen(QColor("#888888"))
        base_pen.setWidth(1)
        p.setPen(base_pen)
        p.drawRect(rect)

        def draw_side(side: str, active: bool) -> None:
            color = QColor("#ffffff" if active else "#aaaaaa")
            pen = QPen(color)
            pen.setWidth(2)
            p.setPen(pen)

            cx = rect.center().x()
            cy = rect.center().y()
            margin = 4

            if side == "left":
                x = rect.left() + margin
                p.drawLine(int(x), int(rect.top() + margin), int(x), int(rect.bottom() - margin))
                p.drawLine(int(x), int(cy), int(x - 6), int(cy - 4))
                p.drawLine(int(x), int(cy), int(x - 6), int(cy + 4))
            elif side == "right":
                x = rect.right() - margin
                p.drawLine(int(x), int(rect.top() + margin), int(x), int(rect.bottom() - margin))
                p.drawLine(int(x), int(cy), int(x + 6), int(cy - 4))
                p.drawLine(int(x), int(cy), int(x + 6), int(cy + 4))
            elif side == "top":
                y = rect.top() + margin
                p.drawLine(int(rect.left() + margin), int(y), int(rect.right() - margin), int(y))
                p.drawLine(int(cx), int(y), int(cx - 4), int(y - 6))
                p.drawLine(int(cx), int(y), int(cx + 4), int(y - 6))
            else:  # bottom
                y = rect.bottom() - margin
                p.drawLine(int(rect.left() + margin), int(y), int(rect.right() - margin), int(y))
                p.drawLine(int(cx), int(y), int(cx - 4), int(y + 6))
                p.drawLine(int(cx), int(y), int(cx + 4), int(y + 6))

        all_active = self._mode == "all"
        draw_side("left", all_active or self._mode == "left")
        draw_side("right", all_active or self._mode == "right")
        draw_side("top", all_active or self._mode == "top")
        draw_side("bottom", all_active or self._mode == "bottom")

        p.end()

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        w = self.width()
        h = self.height()
        x = pos.x()
        y = pos.y()

        third_w = w / 3
        third_h = h / 3

        if third_w <= x <= 2 * third_w and third_h <= y <= 2 * third_h:
            mode = "all"
        elif x < third_w:
            mode = "left"
        elif x > 2 * third_w:
            mode = "right"
        elif y < third_h:
            mode = "top"
        else:
            mode = "bottom"

        self._owner.on_shadow_direction_changed(mode)
        super().mousePressEvent(event)


# -----------------------------------------------------------------------------
# Drag-to-change SpinBox
# -----------------------------------------------------------------------------


class DragSpinBox(QSpinBox):
    """QSpinBox that allows changing value by click-dragging vertically."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dragging = False
        self._start_pos: QPointF | None = None
        self._start_value: int | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_pos = event.position()
            self._start_value = self.value()
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and self._start_pos is not None and self._start_value is not None:
            dy = self._start_pos.y() - event.position().y()
            step = self.singleStep()
            delta = int(dy / 2) * step
            self.blockSignals(True)
            self.setValue(max(self.minimum(), min(self.maximum(), self._start_value + delta)))
            self.blockSignals(False)
            self.valueChanged.emit(self.value())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging:
            self._dragging = False
            self._start_pos = None
            self._start_value = None
            self.setCursor(Qt.CursorShape.IBeamCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


# -----------------------------------------------------------------------------
# Gradient Widgets
# -----------------------------------------------------------------------------


class GradientPreviewWidget(QWidget):
    """Simple preview bar with a gradient and a dot indicating the blend position."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color1 = QColor("#00e5ff")
        self.color2 = QColor("#ffffff")
        self.position = 50
        self.setFixedHeight(24)

    def set_values(self, c1: QColor, c2: QColor, pos: int) -> None:
        self.color1 = QColor(c1)
        self.color2 = QColor(c2)
        self.position = max(0, min(100, pos))
        self.update()

    def set_position(self, pos: int) -> None:
        self.position = max(0, min(100, pos))
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        rect = self.rect().adjusted(4, 4, -4, -4)

        grad = QLinearGradient(rect.left(), rect.center().y(), rect.right(), rect.center().y())
        t = self.position / 100.0
        t = max(0.0, min(1.0, t))
        grad.setColorAt(0.0, self.color1)
        grad.setColorAt(max(0.0, t - 0.05), self.color1)
        grad.setColorAt(min(1.0, t + 0.05), self.color2)
        grad.setColorAt(1.0, self.color2)

        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#444444")))
        p.drawRect(rect)

        x = rect.left() + t * rect.width()
        y = rect.center().y()
        p.setBrush(QBrush(QColor("#ffffff")))
        p.setPen(QPen(QColor("#000000")))
        p.drawEllipse(QPointF(x, y), 4, 4)
        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _update_from_pos(self, x: float) -> None:
        rect = self.rect().adjusted(4, 4, -4, -4)
        if rect.width() <= 0:
            return
        t = (x - rect.left()) / rect.width()
        self.position = int(max(0, min(100, round(t * 100))))
        self.update()
        parent = self.parent()
        if isinstance(parent, ColorStyleDialog):
            parent.on_preview_position_changed(self.position)


class GradientOrientationWidget(QWidget):
    """Square widget for controlling gradient angle and blend position."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color1 = QColor("#00e5ff")
        self.color2 = QColor("#ffffff")
        self.position = 50
        self.angle_deg = 0.0
        self.setFixedSize(120, 120)
        self._drag_mode: str | None = None

    def set_values(self, c1: QColor, c2: QColor, pos: int, angle_deg: float) -> None:
        self.color1 = QColor(c1)
        self.color2 = QColor(c2)
        self.position = max(0, min(100, pos))
        self.angle_deg = angle_deg
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        rect = self.rect().adjusted(6, 6, -6, -6)

        p.fillRect(rect, QColor("#202020"))
        p.setPen(QPen(QColor("#555555")))
        p.drawRect(rect)

        cx = rect.center().x()
        cy = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 - 4

        rad = math.radians(self.angle_deg)
        dx = radius * math.cos(rad)
        dy = radius * math.sin(rad)

        p1 = QPointF(cx - dx, cy - dy)
        p2 = QPointF(cx + dx, cy + dy)

        grad = QLinearGradient(p1, p2)
        t = max(0.0, min(1.0, self.position / 100.0))
        grad.setColorAt(0.0, self.color1)
        grad.setColorAt(max(0.0, t - 0.05), self.color1)
        grad.setColorAt(min(1.0, t + 0.05), self.color2)
        grad.setColorAt(1.0, self.color2)

        p.setPen(QPen(QBrush(grad), 3))
        p.drawLine(p1, p2)

        p.setBrush(QBrush(self.color1))
        p.setPen(QPen(QColor("#000000")))
        p.drawEllipse(p1, 3, 3)

        p.setBrush(QBrush(self.color2))
        p.drawEllipse(p2, 3, 3)

        mid = QPointF(p1.x() + t * (p2.x() - p1.x()), p1.y() + t * (p2.y() - p1.y()))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(mid, 3, 3)
        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.rect().adjusted(6, 6, -6, -6)
            cx = rect.center().x()
            cy = rect.center().y()
            radius = min(rect.width(), rect.height()) / 2 - 4
            rad = math.radians(self.angle_deg)
            dx = radius * math.cos(rad)
            dy = radius * math.sin(rad)
            p1 = QPointF(cx - dx, cy - dy)
            p2 = QPointF(cx + dx, cy + dy)
            t = max(0.0, min(1.0, self.position / 100.0))
            mid = QPointF(p1.x() + t * (p2.x() - p1.x()), p1.y() + t * (p2.y() - p1.y()))

            pos = event.position()
            dist_p1 = (pos - p1).manhattanLength()
            dist_p2 = (pos - p2).manhattanLength()
            dist_mid = (pos - mid).manhattanLength()
            handle_radius = 12.0

            if dist_p1 <= handle_radius or dist_p2 <= handle_radius:
                self._drag_mode = "angle"
            elif dist_mid <= handle_radius:
                self._drag_mode = "position"
            else:
                self._drag_mode = "angle"

            self._update_from_pos(pos)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _update_from_pos(self, pos: QPointF) -> None:
        rect = self.rect().adjusted(6, 6, -6, -6)
        cx = rect.center().x()
        cy = rect.center().y()
        v = QPointF(pos.x() - cx, pos.y() - cy)
        if v.x() == 0 and v.y() == 0:
            return

        radius = min(rect.width(), rect.height()) / 2 - 4

        if self._drag_mode == "position":
            angle_rad = math.radians(self.angle_deg)
            dir_vec = QPointF(math.cos(angle_rad), math.sin(angle_rad))
            proj = v.x() * dir_vec.x() + v.y() * dir_vec.y()
            t = (proj / (2 * radius)) + 0.5
            self.position = int(max(0, min(100, round(t * 100))))
        else:
            angle_rad = math.atan2(v.y(), v.x())
            self.angle_deg = math.degrees(angle_rad)

        self.update()

        parent = self.parent()
        if isinstance(parent, ColorStyleDialog):
            parent.on_orientation_changed(self.angle_deg, self.position)


class ColorStyleDialog(QDialog):
    """Dialog to choose solid vs gradient color style."""

    def __init__(
        self,
        parent: QWidget,
        title: str,
        initial_use_gradient: bool,
        color1: QColor,
        color2: QColor,
        position: int,
        angle: float,
        mode: str,
        width: int,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.mode = mode
        self.use_gradient = initial_use_gradient
        self.color1 = QColor(color1)
        self.color2 = QColor(color2)
        self.position = position
        self.angle = angle
        self.width_pct = width

        layout = QVBoxLayout(self)

        self.gradient_check = QCheckBox("Use gradient")
        self.gradient_check.setChecked(self.use_gradient)
        self.gradient_check.stateChanged.connect(self._refresh_ui)
        layout.addWidget(self.gradient_check)

        colors_layout = QHBoxLayout()
        self.color1_btn = QPushButton("Color A")
        self.color1_btn.clicked.connect(self.on_pick_color1)
        self.color2_btn = QPushButton("Color B")
        self.color2_btn.clicked.connect(self.on_pick_color2)
        colors_layout.addWidget(self.color1_btn)
        colors_layout.addWidget(self.color2_btn)
        layout.addLayout(colors_layout)

        self.orientation_label = QLabel("Gradient orientation")
        layout.addWidget(self.orientation_label)
        self.orientation = GradientOrientationWidget(self)
        layout.addWidget(self.orientation)

        self.width_label = QLabel("Blend size")
        layout.addWidget(self.width_label)
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(0, 100)
        self.width_slider.valueChanged.connect(self.on_width_changed)
        layout.addWidget(self.width_slider)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_ui()

    def _refresh_ui(self) -> None:
        self.color1_btn.setStyleSheet(f"background-color: {self.color1.name()};")
        self.color2_btn.setStyleSheet(f"background-color: {self.color2.name()};")
        self.orientation.set_values(self.color1, self.color2, self.position, self.angle)
        self.width_slider.blockSignals(True)
        self.width_slider.setValue(self.width_pct)
        self.width_slider.blockSignals(False)

        enabled = self.gradient_check.isChecked()
        self.color2_btn.setEnabled(enabled)
        self.orientation.setEnabled(enabled)
        self.width_slider.setEnabled(enabled)
        self.width_label.setEnabled(enabled)

    def on_pick_color1(self) -> None:
        color = QColorDialog.getColor(
            self.color1,
            self,
            "Select Color A",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self.color1 = color
            self._refresh_ui()
            self._notify_parent_preview()

    def on_pick_color2(self) -> None:
        color = QColorDialog.getColor(
            self.color2,
            self,
            "Select Color B",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self.color2 = color
            self._refresh_ui()
            self._notify_parent_preview()

    def on_preview_position_changed(self, value: int) -> None:
        self.position = value
        self.orientation.set_values(self.color1, self.color2, self.position, self.angle)
        self._notify_parent_preview()

    def on_orientation_changed(self, angle_deg: float, pos: int) -> None:
        self.angle = angle_deg
        self.position = pos
        self._notify_parent_preview()

    def on_width_changed(self, value: int) -> None:
        self.width_pct = max(0, min(100, value))
        self._notify_parent_preview()

    def get_result(self) -> tuple[bool, QColor, QColor, int, float]:
        return (
            self.gradient_check.isChecked(),
            self.color1,
            self.color2,
            self.position,
            self.angle,
        )

    def _notify_parent_preview(self) -> None:
        parent = self.parent()
        if not hasattr(parent, "apply_gradient_preview"):
            return
        use_grad = self.gradient_check.isChecked()
        if self.mode == "stroke":
            parent.apply_gradient_preview(
                kind="stroke",
                use_gradient=use_grad,
                color1=self.color1,
                color2=self.color2,
                position=self.position,
                angle=self.angle,
                width=self.width_pct,
            )
        else:
            parent.apply_gradient_preview(
                kind="fill",
                use_gradient=use_grad,
                color1=self.color1,
                color2=self.color2,
                position=self.position,
                angle=self.angle,
                width=self.width_pct,
            )


# -----------------------------------------------------------------------------
# Layers List Widget
# -----------------------------------------------------------------------------


class LayerListWidget(QListWidget):
    """Layers panel that supports drag-reorder and delete via keyboard."""

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__(owner)
        self._owner = owner

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._owner.delete_selected_shapes()
            event.accept()
            return
        super().keyPressEvent(event)


# -----------------------------------------------------------------------------
# Undo Commands
# -----------------------------------------------------------------------------


class ShapeTransformCommand(QUndoCommand):
    """Undoable command for moving/resizing a single shape."""

    def __init__(self, item, old_pos: QPointF, new_pos: QPointF, old_rect, new_rect):
        super().__init__("Transform shape")
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos
        self.old_rect = old_rect
        self.new_rect = new_rect

    def undo(self) -> None:
        self.item.setPos(self.old_pos)
        if hasattr(self.item, "setRect") and self.old_rect is not None:
            self.item.setRect(self.old_rect)
        elif isinstance(self.item, QGraphicsLineItem) and self.old_rect is not None:
            self.item.setLine(self.old_rect)

    def redo(self) -> None:
        self.item.setPos(self.new_pos)
        if hasattr(self.item, "setRect") and self.new_rect is not None:
            self.item.setRect(self.new_rect)
        elif isinstance(self.item, QGraphicsLineItem) and self.new_rect is not None:
            self.item.setLine(self.new_rect)


# -----------------------------------------------------------------------------
# Shape View
# -----------------------------------------------------------------------------


class ShapeView(QGraphicsView):
    """View used in the shape editor with zoom, color picking, and undo support."""

    def __init__(self, scene: QGraphicsScene, owner: "MainWindow") -> None:
        super().__init__(scene)
        self._owner = owner
        self._zoom = 1.0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Highlight, Qt.GlobalColor.white)
        self.setPalette(pal)
        self._press_item = None
        self._press_pos: QPointF | None = None
        self._press_geom = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._owner.color_pick_mode and self._owner.shape_base_item is not None:
                scene_pos = self.mapToScene(event.pos())
                item_pos = self._owner.shape_base_item.mapFromScene(scene_pos)
                x = int(item_pos.x())
                y = int(item_pos.y())
                img = self._owner.shape_base_image
                if img is not None and 0 <= x < img.width() and 0 <= y < img.height():
                    color = QColor(img.pixel(x, y))
                    if self._owner.color_pick_mode == "stroke":
                        self._owner.shape_stroke_color = color
                    else:
                        self._owner.shape_fill_color = color
                    self._owner._update_color_buttons()
                    self._owner.on_shape_style_changed()
                self._owner.color_pick_mode = None
                self._owner.pick_from_base_btn.setText("Pick from base (next click)")
            else:
                item = self.itemAt(event.pos())
                if item is not None:
                    self._press_item = item
                    self._press_pos = item.pos()
                    if hasattr(item, "rect"):
                        self._press_geom = QRectF(item.rect())
                    elif isinstance(item, QGraphicsLineItem):
                        self._press_geom = QLineF(item.line())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._press_item is None or self._owner.undo_stack is None:
            self._press_item = None
            self._press_pos = None
            self._press_geom = None
            return

        item = self._press_item
        new_pos = item.pos()
        new_geom = None
        if hasattr(item, "rect"):
            new_geom = QRectF(item.rect())
        elif isinstance(item, QGraphicsLineItem):
            new_geom = QLineF(item.line())

        if (
            self._press_pos is not None
            and (new_pos != self._press_pos
                 or (self._press_geom is not None and new_geom is not None and new_geom != self._press_geom))
        ):
            cmd = ShapeTransformCommand(item, self._press_pos, new_pos, self._press_geom, new_geom)
            self._owner.undo_stack.push(cmd)

        self._press_item = None
        self._press_pos = None
        self._press_geom = None

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        zoom_factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = self._zoom * zoom_factor
        if 0.1 <= new_zoom <= 10.0:
            self._zoom = new_zoom
            self.scale(zoom_factor, zoom_factor)
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if self._owner.shape_scene is None:
                super().keyPressEvent(event)
                return
            step = 10 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1
            dx = dy = 0
            if key == Qt.Key.Key_Left:
                dx = -step
            elif key == Qt.Key.Key_Right:
                dx = step
            elif key == Qt.Key.Key_Up:
                dy = -step
            elif key == Qt.Key.Key_Down:
                dy = step

            for item in self._owner.shape_scene.selectedItems():
                item.moveBy(dx, dy)

            event.accept()
            return

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._owner.delete_selected_shapes()
            event.accept()
            return

        super().keyPressEvent(event)

