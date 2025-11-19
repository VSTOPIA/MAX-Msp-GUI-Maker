import sys
from pathlib import Path

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
    QKeySequence,
    QUndoStack,
    QUndoCommand,
)
from PyQt6.QtWidgets import (
    QApplication,
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
    QMainWindow,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QAbstractItemView,
    QColorDialog,
)

import math

from PIL import Image
from process_fader_image import remove_black_background, split_components


class AnimView(QGraphicsView):
    """
    Custom QGraphicsView that reports click positions back to the main window
    so we can snap the fader cap to a clicked point on the guide.
    """

    def __init__(self, scene: QGraphicsScene, owner: "MainWindow") -> None:
        super().__init__(scene)
        self._owner = owner

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self._owner.on_anim_view_clicked(scene_pos.y())
        super().mousePressEvent(event)


class ShapeView(QGraphicsView):
    """
    View used in the shape editor so we can pick colors from the base image
    by clicking on it.
    """

    def __init__(self, scene: QGraphicsScene, owner: "MainWindow") -> None:
        super().__init__(scene)
        self._owner = owner
        self._zoom = 1.0
        # Zoom will be centered around the cursor position
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        # Enable rubber-band selection to drag a thin white rectangle that
        # selects multiple shapes when dragging on empty canvas.
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Highlight, Qt.GlobalColor.white)
        self.setPalette(pal)
        # For undo of move/resize
        self._press_item = None
        self._press_pos: QPointF | None = None
        self._press_geom = None

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
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
                    # Apply immediately to current shape if any
                    self._owner.on_shape_style_changed()
                # Reset mode after one pick
                self._owner.color_pick_mode = None
                self._owner.pick_from_base_btn.setText("Pick from base (next click)")
            else:
                # Normal interaction: remember starting state for undo
                item = self.itemAt(event.pos())
                if item is not None:
                    self._press_item = item
                    self._press_pos = item.pos()
                    if hasattr(item, "rect"):
                        self._press_geom = QRectF(item.rect())  # type: ignore[arg-type]
                    elif isinstance(item, QGraphicsLineItem):
                        self._press_geom = QLineF(item.line())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        # After the view and items have processed the release, see if the
        # focused item actually moved or resized; if so, push an undo command.
        if self._press_item is None or self._owner.undo_stack is None:
            self._press_item = None
            self._press_pos = None
            self._press_geom = None
            return

        item = self._press_item
        new_pos = item.pos()
        new_geom = None
        if hasattr(item, "rect"):
            new_geom = QRectF(item.rect())  # type: ignore[arg-type]
        elif isinstance(item, QGraphicsLineItem):
            new_geom = QLineF(item.line())

        # Only create an undo command if something actually changed.
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

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        # Use trackpad two-finger scroll / mouse wheel to zoom in/out.
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        zoom_factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = self._zoom * zoom_factor
        # Keep zoom within a reasonable range
        if 0.1 <= new_zoom <= 10.0:
            self._zoom = new_zoom
            self.scale(zoom_factor, zoom_factor)
        event.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        # Move selected shapes with arrow keys.
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if self._owner.shape_scene is None:
                super().keyPressEvent(event)
                return
            # Shift = larger step
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
            # Delegate deletion to the main window so it also works when
            # triggered from other widgets like the layers list.
            self._owner.delete_selected_shapes()
            event.accept()
            return

        super().keyPressEvent(event)


class ResizableRectItem(QGraphicsRectItem):
    """
    Rectangle item with hover-based resize handles on corners and edges.
    """

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
        # Use the item's rect (local geometry). This keeps handles stable even
        # when effects like drop shadows expand the boundingRect().
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

    def hoverMoveEvent(self, event) -> None:  # type: ignore[override]
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

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
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

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._resizing and self._orig_rect is not None and self._orig_pos is not None:
            delta = event.pos() - self._orig_pos
            r = QRectF(self._orig_rect)

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

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._resizing = False
        self._handle = None
        self._orig_rect = None
        self._orig_pos = None
        super().mouseReleaseEvent(event)


class ResizableEllipseItem(QGraphicsEllipseItem):
    """
    Ellipse / circle item with hover-based resize handles on corners and edges.
    Behavior mirrors ResizableRectItem but applied to the ellipse's bounding rect.
    """

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
        # Use the item's rect (local geometry). This keeps handles stable even
        # when effects like drop shadows expand the boundingRect().
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

    def hoverMoveEvent(self, event) -> None:  # type: ignore[override]
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

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
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

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._resizing and self._orig_rect is not None and self._orig_pos is not None:
            delta = event.pos() - self._orig_pos
            r = QRectF(self._orig_rect)

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

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._resizing = False
        self._handle = None
        self._orig_rect = None
        self._orig_pos = None
        super().mouseReleaseEvent(event)


class ResizableLineItem(QGraphicsLineItem):
    """
    Horizontal line with resize handles on its endpoints.
    """

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

    def hoverMoveEvent(self, event) -> None:  # type: ignore[override]
        handle = self._handle_at(event.pos())
        if handle:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
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

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
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

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._resizing = False
        self._handle = None
        self._orig_line = None
        self._orig_pos = None
        super().mouseReleaseEvent(event)

class ShadowDirectionWidget(QWidget):
    """
    Small square control to pick glow direction (all sides / left / right / top / bottom).
    Clicking different regions of the square updates the direction.
    """

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__(owner)
        self._owner = owner
        self._mode: str = "all"  # all, left, right, top, bottom
        self.setFixedSize(40, 40)

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        rect = self.rect().adjusted(2, 2, -2, -2)

        # Background
        p.fillRect(rect, QColor("#202020"))

        # Draw outer square (stroke only)
        base_pen = QPen(QColor("#888888"))
        base_pen.setWidth(1)
        p.setPen(base_pen)
        p.drawRect(rect)

        # Helper to draw side with optional arrow and highlight
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
                p.drawLine(x, rect.top() + margin, x, rect.bottom() - margin)
                # Arrow pointing left
                p.drawLine(x, cy, x - 6, cy - 4)
                p.drawLine(x, cy, x - 6, cy + 4)
            elif side == "right":
                x = rect.right() - margin
                p.drawLine(x, rect.top() + margin, x, rect.bottom() - margin)
                p.drawLine(x, cy, x + 6, cy - 4)
                p.drawLine(x, cy, x + 6, cy + 4)
            elif side == "top":
                y = rect.top() + margin
                p.drawLine(rect.left() + margin, y, rect.right() - margin, y)
                p.drawLine(cx, y, cx - 4, y - 6)
                p.drawLine(cx, y, cx + 4, y - 6)
            else:  # bottom
                y = rect.bottom() - margin
                p.drawLine(rect.left() + margin, y, rect.right() - margin, y)
                p.drawLine(cx, y, cx - 4, y + 6)
                p.drawLine(cx, y, cx + 4, y + 6)

        # Determine which sides are active
        all_active = self._mode == "all"
        draw_side("left", all_active or self._mode == "left")
        draw_side("right", all_active or self._mode == "right")
        draw_side("top", all_active or self._mode == "top")
        draw_side("bottom", all_active or self._mode == "bottom")

        p.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
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


class DragSpinBox(QSpinBox):
    """
    QSpinBox that allows changing the value by click-dragging vertically
    on the number (in addition to normal arrows / typing).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dragging = False
        self._start_pos: QPointF | None = None
        self._start_value: int | None = None

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_pos = event.position()
            self._start_value = self.value()
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging and self._start_pos is not None and self._start_value is not None:
            dy = self._start_pos.y() - event.position().y()
            step = self.singleStep()
            delta = int(dy / 2) * step  # every 2px moves one step
            self.blockSignals(True)
            self.setValue(max(self.minimum(), min(self.maximum(), self._start_value + delta)))
            self.blockSignals(False)
            # Emit valueChanged manually since we blocked signals
            self.valueChanged.emit(self.value())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging:
            self._dragging = False
            self._start_pos = None
            self._start_value = None
            self.setCursor(Qt.CursorShape.IBeamCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class GradientPreviewWidget(QWidget):
    """
    Simple preview bar with a gradient and a dot indicating the blend position.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color1 = QColor("#00e5ff")
        self.color2 = QColor("#ffffff")
        self.position = 50  # 0-100
        self.setFixedHeight(24)

    def set_values(self, c1: QColor, c2: QColor, pos: int) -> None:
        self.color1 = QColor(c1)
        self.color2 = QColor(c2)
        self.position = max(0, min(100, pos))
        self.update()

    def set_position(self, pos: int) -> None:
        self.position = max(0, min(100, pos))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        rect = self.rect().adjusted(4, 4, -4, -4)

        # Gradient bar
        grad = QLinearGradient(rect.left(), rect.center().y(), rect.right(), rect.center().y())
        # Compress blend around self.position
        t = self.position / 100.0
        t = max(0.0, min(1.0, t))
        grad.setColorAt(0.0, self.color1)
        grad.setColorAt(max(0.0, t - 0.05), self.color1)
        grad.setColorAt(min(1.0, t + 0.05), self.color2)
        grad.setColorAt(1.0, self.color2)

        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#444444")))
        p.drawRect(rect)

        # Position dot
        x = rect.left() + t * rect.width()
        y = rect.center().y()
        p.setBrush(QBrush(QColor("#ffffff")))
        p.setPen(QPen(QColor("#000000")))
        p.drawEllipse(QPointF(x, y), 4, 4)
        p.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._update_from_pos(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
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
        # Emit via parent slider if any
        parent = self.parent()
        if isinstance(parent, ColorStyleDialog):
            parent.on_preview_position_changed(self.position)


class GradientOrientationWidget(QWidget):
    """
    Square widget showing a line with endpoints representing the two colors and
    a middle dot representing the blend point. Dragging inside adjusts angle
    and blend position.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color1 = QColor("#00e5ff")
        self.color2 = QColor("#ffffff")
        self.position = 50  # 0–100 along the line
        self.angle_deg = 0.0  # 0 = left->right
        self.setFixedSize(120, 120)  # larger for better UX
        self._drag_mode: str | None = None  # "angle" or "position"

    def set_values(self, c1: QColor, c2: QColor, pos: int, angle_deg: float) -> None:
        self.color1 = QColor(c1)
        self.color2 = QColor(c2)
        self.position = max(0, min(100, pos))
        self.angle_deg = angle_deg
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        rect = self.rect().adjusted(6, 6, -6, -6)

        # Background
        p.fillRect(rect, QColor("#202020"))
        p.setPen(QPen(QColor("#555555")))
        p.drawRect(rect)

        # Line endpoints based on angle
        cx = rect.center().x()
        cy = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 - 4

        rad = math.radians(self.angle_deg)
        dx = radius * math.cos(rad)
        dy = radius * math.sin(rad)

        p1 = QPointF(cx - dx, cy - dy)
        p2 = QPointF(cx + dx, cy + dy)

        # Gradient along the line for preview
        grad = QLinearGradient(p1, p2)
        t = max(0.0, min(1.0, self.position / 100.0))
        grad.setColorAt(0.0, self.color1)
        grad.setColorAt(max(0.0, t - 0.05), self.color1)
        grad.setColorAt(min(1.0, t + 0.05), self.color2)
        grad.setColorAt(1.0, self.color2)

        p.setPen(QPen(QBrush(grad), 3))
        p.drawLine(p1, p2)

        # Endpoints markers
        p.setBrush(QBrush(self.color1))
        p.setPen(QPen(QColor("#000000")))
        p.drawEllipse(p1, 3, 3)

        p.setBrush(QBrush(self.color2))
        p.drawEllipse(p2, 3, 3)

        # Middle dot at blend point
        mid = QPointF(p1.x() + t * (p2.x() - p1.x()), p1.y() + t * (p2.y() - p1.y()))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(mid, 3, 3)
        p.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            # Decide whether we're adjusting angle (near endpoints) or
            # position (near middle of the line).
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

            # Prioritise endpoints for angle changes; only use the middle
            # handle for blend position when clearly closer to the middle.
            if dist_p1 <= handle_radius or dist_p2 <= handle_radius:
                self._drag_mode = "angle"
            elif dist_mid <= handle_radius:
                self._drag_mode = "position"
            else:
                # Clicked somewhere else: treat as angle adjustment.
                self._drag_mode = "angle"

            self._update_from_pos(pos)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
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
            # Move blend point along current angle, keep angle fixed.
            angle_rad = math.radians(self.angle_deg)
            dir_vec = QPointF(math.cos(angle_rad), math.sin(angle_rad))
            proj = v.x() * dir_vec.x() + v.y() * dir_vec.y()
            t = (proj / (2 * radius)) + 0.5
            self.position = int(max(0, min(100, round(t * 100))))
        else:
            # Adjust angle only; keep existing blend position.
            angle_rad = math.atan2(v.y(), v.x())
            self.angle_deg = math.degrees(angle_rad)

        self.update()

        parent = self.parent()
        if isinstance(parent, ColorStyleDialog):
            parent.on_orientation_changed(self.angle_deg, self.position)


class ColorStyleDialog(QDialog):
    """
    Dialog to choose solid vs gradient color style with two colors and
    a gradient preview/position control.
    """

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
        # "stroke" or "fill" – used to tell the main window what to preview.
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

        # Color pickers
        colors_layout = QHBoxLayout()
        self.color1_btn = QPushButton("Color A")
        self.color1_btn.clicked.connect(self.on_pick_color1)
        self.color2_btn = QPushButton("Color B")
        self.color2_btn.clicked.connect(self.on_pick_color2)
        colors_layout.addWidget(self.color1_btn)
        colors_layout.addWidget(self.color2_btn)
        layout.addLayout(colors_layout)

        # Orientation square (preview + control: angle & blend position)
        self.orientation_label = QLabel("Gradient orientation")
        layout.addWidget(self.orientation_label)
        self.orientation = GradientOrientationWidget(self)
        layout.addWidget(self.orientation)

        # Blend size slider
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
        # Keep orientation preview in sync with current colors, position, and angle
        self.orientation.set_values(self.color1, self.color2, self.position, self.angle)
        self.width_slider.blockSignals(True)
        self.width_slider.setValue(self.width_pct)
        self.width_slider.blockSignals(False)

        # Enable/disable gradient controls
        enabled = self.gradient_check.isChecked()
        self.color2_btn.setEnabled(enabled)
        self.orientation.setEnabled(enabled)
        self.width_slider.setEnabled(enabled)
        self.width_label.setEnabled(enabled)

    def on_pick_color1(self) -> None:
        color = QColorDialog.getColor(self.color1, self, "Select Color A")
        if color.isValid():
            self.color1 = color
            self._refresh_ui()
            self._notify_parent_preview()

    def on_pick_color2(self) -> None:
        color = QColorDialog.getColor(self.color2, self, "Select Color B")
        if color.isValid():
            self.color2 = color
            self._refresh_ui()
            self._notify_parent_preview()

    def on_preview_position_changed(self, value: int) -> None:
        # Kept for compatibility with GradientPreviewWidget, but orientation
        # is the primary control now.
        self.position = value
        self.orientation.set_values(self.color1, self.color2, self.position, self.angle)
        self._notify_parent_preview()

    def on_orientation_changed(self, angle_deg: float, pos: int) -> None:
        self.angle = angle_deg
        self.position = pos
        # Orientation widget drives position; nothing else to sync now.
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
        """
        Tell the main window to update the currently selected shape with the
        gradient settings as the user tweaks them, so we have live feedback.
        """
        parent = self.parent()
        if not isinstance(parent, MainWindow):
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

class LayerListWidget(QListWidget):
    """
    Layers panel that supports drag-reorder and delete via keyboard.
    """

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__(owner)
        self._owner = owner

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._owner.delete_selected_shapes()
            event.accept()
            return
        super().keyPressEvent(event)


class ShapeTransformCommand(QUndoCommand):
    """
    Undoable command for moving/resizing a single shape.
    Stores position and geometry before and after the user interaction.
    """

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
            self.item.setRect(self.old_rect)  # type: ignore[arg-type]
        elif isinstance(self.item, QGraphicsLineItem) and self.old_rect is not None:
            self.item.setLine(self.old_rect)  # type: ignore[arg-type]

    def redo(self) -> None:
        self.item.setPos(self.new_pos)
        if hasattr(self.item, "setRect") and self.new_rect is not None:
            self.item.setRect(self.new_rect)  # type: ignore[arg-type]
        elif isinstance(self.item, QGraphicsLineItem) and self.new_rect is not None:
            self.item.setLine(self.new_rect)  # type: ignore[arg-type]

def load_pixmap(path: Path, max_size: int = 480) -> QPixmap:
    """
    Load an image file into a QPixmap and scale it down to fit max_size.
    """
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap

    return pixmap.scaled(
        max_size,
        max_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MAX-Msp GUI Maker – Image Prep")
        self.resize(1200, 700)

        self.input_path: Path | None = None
        self.preview_dir = Path("preview").resolve()
        self.preview_dir.mkdir(parents=True, exist_ok=True)

        # Animation setup state
        self.guide_path: Path | None = None
        self.cap_path: Path | None = None
        self.guide_item: QGraphicsPixmapItem | None = None
        self.cap_item: QGraphicsPixmapItem | None = None
        self.start_edge_y: float | None = None
        self.end_edge_y: float | None = None
        self.center_edge_y: float | None = None
        self.start_line_item: QGraphicsLineItem | None = None
        self.end_line_item: QGraphicsLineItem | None = None

        # Shape editor state
        self.shape_scene: QGraphicsScene | None = None
        self.shape_view: QGraphicsView | None = None
        self.shape_base_path: Path | None = None
        self.shape_base_item: QGraphicsPixmapItem | None = None
        self.shape_base_image: QImage | None = None
        self.current_shape_item = None
        self.shape_stroke_color = QColor("#00e5ff")
        self.shape_fill_color = QColor("#00e5ff")
        # Gradient styles
        self.stroke_use_gradient = False
        self.stroke_grad_color1 = QColor("#00e5ff")
        self.stroke_grad_color2 = QColor("#ffffff")
        self.stroke_grad_pos = 50
        self.stroke_grad_angle = 0.0
        self.stroke_grad_width = 10  # blend size in percent
        self.fill_use_gradient = False
        self.fill_grad_color1 = QColor("#00e5ff")
        self.fill_grad_color2 = QColor("#ffffff")
        self.fill_grad_pos = 50
        self.fill_grad_angle = 0.0
        self.fill_grad_width = 10  # blend size in percent
        self.color_pick_mode: str | None = None  # "stroke", "fill", or None
        self.crop_rect_item: ResizableRectItem | None = None
        self.layers_list: QListWidget | None = None
        self.shadow_dir_widget: ShadowDirectionWidget | None = None

        # Undo/redo stack for all editing actions
        self.undo_stack = QUndoStack(self)

        self._build_ui()
        self._setup_undo_actions()

    # Live gradient preview from ColorStyleDialog
    def apply_gradient_preview(
        self,
        kind: str,
        use_gradient: bool,
        color1: QColor,
        color2: QColor,
        position: int,
        angle: float,
        width: int,
    ) -> None:
        if self.current_shape_item is None:
            return

        if kind == "stroke":
            self.stroke_use_gradient = use_gradient
            self.stroke_grad_color1 = color1
            self.stroke_grad_color2 = color2
            self.stroke_grad_pos = position
            self.stroke_grad_angle = angle
            self.stroke_grad_width = width
            self.shape_stroke_color = color1
        else:
            self.fill_use_gradient = use_gradient
            self.fill_grad_color1 = color1
            self.fill_grad_color2 = color2
            self.fill_grad_pos = position
            self.fill_grad_angle = angle
            self.fill_grad_width = width
            self.shape_fill_color = color1

        self._update_color_buttons()
        self.on_shape_style_changed()

    def _setup_undo_actions(self) -> None:
        """
        Create global Undo / Redo actions so Cmd+Z / Shift+Cmd+Z work everywhere.
        """
        undo_action = self.undo_stack.createUndoAction(self, "Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(redo_action)


    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        tabs = QTabWidget(self)
        self.setCentralWidget(tabs)

        # Tab 1: background removal / component split
        bg_tab = QWidget()
        self._build_bg_removal_tab(bg_tab)
        tabs.addTab(bg_tab, "Background removal")

        # Tab 2: fader animation setup
        anim_tab = QWidget()
        self._build_animation_tab(anim_tab)
        tabs.addTab(anim_tab, "Fader animation")

        # Tab 3: shape / overlay editor
        shape_tab = QWidget()
        self._build_shape_editor_tab(shape_tab)
        tabs.addTab(shape_tab, "Shape editor")

    def _build_bg_removal_tab(self, parent: QWidget) -> None:
        main_layout = QHBoxLayout(parent)

        # Left: original / processed preview
        preview_layout = QHBoxLayout()

        self.original_label = QLabel("Original")
        self.original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_label.setStyleSheet("background-color: #202020; color: #AAAAAA;")

        self.processed_label = QLabel("Processed / Components")
        self.processed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.processed_label.setStyleSheet("background-color: #202020; color: #AAAAAA;")

        preview_layout.addWidget(self.original_label, stretch=1)
        preview_layout.addWidget(self.processed_label, stretch=1)

        # Right: controls
        controls_layout = QVBoxLayout()

        load_button = QPushButton("Load image…")
        load_button.clicked.connect(self.on_load_image)
        controls_layout.addWidget(load_button)

        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)

        # Threshold slider + spinbox
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(10)
        self.threshold_slider.valueChanged.connect(self.on_params_changed)

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 100)
        self.threshold_spin.setValue(10)
        self.threshold_spin.valueChanged.connect(self.on_params_changed)

        # Keep slider and spinbox in sync
        self.threshold_slider.valueChanged.connect(self.threshold_spin.setValue)
        self.threshold_spin.valueChanged.connect(self.threshold_slider.setValue)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(self.threshold_slider)
        threshold_row.addWidget(self.threshold_spin)
        params_layout.addRow("Background threshold", threshold_row)

        # Min area spinbox
        self.min_area_spin = QSpinBox()
        self.min_area_spin.setRange(0, 100_000)
        self.min_area_spin.setSingleStep(500)
        self.min_area_spin.setValue(2_000)
        self.min_area_spin.valueChanged.connect(self.on_params_changed)
        params_layout.addRow("Min component area", self.min_area_spin)

        controls_layout.addWidget(params_group)

        # Component selection + export
        self.component_info_label = QLabel("Components: –")
        controls_layout.addWidget(self.component_info_label)

        export_button = QPushButton("Export components to output/")
        export_button.clicked.connect(self.on_export_components)
        controls_layout.addWidget(export_button)

        controls_layout.addStretch(1)

        main_layout.addLayout(preview_layout, stretch=3)
        main_layout.addLayout(controls_layout, stretch=1)

    def _build_animation_tab(self, parent: QWidget) -> None:
        main_layout = QHBoxLayout(parent)

        # Graphics view for guide + fader cap
        self.anim_scene = QGraphicsScene(self)
        self.anim_view = AnimView(self.anim_scene, owner=self)
        self.anim_view.setStyleSheet("background-color: #101010;")

        main_layout.addWidget(self.anim_view, stretch=3)

        # Controls on the right
        controls_layout = QVBoxLayout()

        load_guide_btn = QPushButton("Load guide / slider…")
        load_guide_btn.clicked.connect(self.on_load_guide)
        controls_layout.addWidget(load_guide_btn)

        load_cap_btn = QPushButton("Load fader cap…")
        load_cap_btn.clicked.connect(self.on_load_cap)
        controls_layout.addWidget(load_cap_btn)

        controls_layout.addSpacing(12)

        # Edge markers
        self.start_label = QLabel("Start edge: –")
        self.end_label = QLabel("End edge: –")
        self.center_label = QLabel("Center: –")
        controls_layout.addWidget(self.start_label)
        controls_layout.addWidget(self.end_label)
        controls_layout.addWidget(self.center_label)

        set_start_btn = QPushButton("Set START edge from cap position")
        set_start_btn.clicked.connect(self.on_set_start_edge)
        controls_layout.addWidget(set_start_btn)

        set_end_btn = QPushButton("Set END edge from cap position")
        set_end_btn.clicked.connect(self.on_set_end_edge)
        controls_layout.addWidget(set_end_btn)

        controls_layout.addSpacing(12)

        # Animation slider between edges
        self.anim_slider = QSlider(Qt.Orientation.Horizontal)
        self.anim_slider.setRange(0, 100)
        self.anim_slider.setValue(0)
        self.anim_slider.valueChanged.connect(self.on_anim_slider_changed)
        controls_layout.addWidget(QLabel("Preview fader motion"))
        controls_layout.addWidget(self.anim_slider)

        controls_layout.addSpacing(12)

        # Spritesheet export parameters
        frames_group = QGroupBox("Spritesheet export")
        frames_layout = QFormLayout(frames_group)

        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(2, 256)
        self.frames_spin.setValue(32)
        frames_layout.addRow("Frames", self.frames_spin)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Horizontal", "Vertical"])
        frames_layout.addRow("Layout", self.layout_combo)

        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(0, 512)
        self.offset_spin.setValue(0)
        frames_layout.addRow("Offset (px between frames)", self.offset_spin)

        controls_layout.addWidget(frames_group)

        export_sheet_btn = QPushButton("Export spritesheet to output/")
        export_sheet_btn.clicked.connect(self.on_export_spritesheet)
        controls_layout.addWidget(export_sheet_btn)

        self.sheet_info_label = QLabel("")
        controls_layout.addWidget(self.sheet_info_label)

        controls_layout.addStretch(1)

        main_layout.addLayout(controls_layout, stretch=1)

    def _build_shape_editor_tab(self, parent: QWidget) -> None:
        main_layout = QHBoxLayout(parent)

        # Scene + view
        self.shape_scene = QGraphicsScene(self)
        self.shape_view = ShapeView(self.shape_scene, owner=self)
        self.shape_view.setStyleSheet("background-color: #101010;")
        main_layout.addWidget(self.shape_view, stretch=3)

        controls_layout = QVBoxLayout()

        load_base_btn = QPushButton("Load base image…")
        load_base_btn.clicked.connect(self.on_shape_load_base)
        controls_layout.addWidget(load_base_btn)

        shape_group = QGroupBox("Add shape")
        shape_layout = QVBoxLayout(shape_group)

        add_rect_btn = QPushButton("Rectangle")
        add_rect_btn.clicked.connect(self.on_shape_add_rect)
        shape_layout.addWidget(add_rect_btn)

        add_circle_btn = QPushButton("Circle")
        add_circle_btn.clicked.connect(self.on_shape_add_circle)
        shape_layout.addWidget(add_circle_btn)

        add_line_btn = QPushButton("Line")
        add_line_btn.clicked.connect(self.on_shape_add_line)
        shape_layout.addWidget(add_line_btn)

        add_dot_btn = QPushButton("Dot")
        add_dot_btn.clicked.connect(self.on_shape_add_dot)
        shape_layout.addWidget(add_dot_btn)

        controls_layout.addWidget(shape_group)

        props_group = QGroupBox("Selected shape")
        props_layout = QFormLayout(props_group)

        self.shape_width_spin = DragSpinBox()
        self.shape_width_spin.setRange(1, 2000)
        self.shape_width_spin.setValue(50)
        self.shape_width_spin.valueChanged.connect(self.on_shape_size_changed)
        props_layout.addRow("Width (px)", self.shape_width_spin)

        self.shape_height_spin = DragSpinBox()
        self.shape_height_spin.setRange(1, 2000)
        self.shape_height_spin.setValue(50)
        self.shape_height_spin.valueChanged.connect(self.on_shape_size_changed)
        props_layout.addRow("Height (px)", self.shape_height_spin)

        self.shape_filled_check = QCheckBox("Filled")
        self.shape_filled_check.setChecked(True)
        self.shape_filled_check.stateChanged.connect(self.on_shape_style_changed)
        props_layout.addRow(self.shape_filled_check)

        self.shape_neon_check = QCheckBox("Neon glow")
        self.shape_neon_check.setChecked(True)
        self.shape_neon_check.stateChanged.connect(self.on_shape_style_changed)
        props_layout.addRow(self.shape_neon_check)

        self.neon_radius_spin = DragSpinBox()
        self.neon_radius_spin.setRange(0, 999)
        self.neon_radius_spin.setValue(25)
        self.neon_radius_spin.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow radius (px)", self.neon_radius_spin)

        self.neon_offset_x_spin = QSpinBox()
        self.neon_offset_x_spin.setRange(-100, 100)
        self.neon_offset_x_spin.setValue(0)
        self.neon_offset_x_spin.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow offset X", self.neon_offset_x_spin)

        self.neon_offset_y_spin = QSpinBox()
        self.neon_offset_y_spin.setRange(-100, 100)
        self.neon_offset_y_spin.setValue(0)
        self.neon_offset_y_spin.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow offset Y", self.neon_offset_y_spin)

        self.neon_intensity_slider = QSlider(Qt.Orientation.Horizontal)
        # Allow going beyond 100% to get a very strong, almost solid glow.
        self.neon_intensity_slider.setRange(0, 200)
        self.neon_intensity_slider.setValue(100)
        self.neon_intensity_slider.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow intensity", self.neon_intensity_slider)

        self.shadow_dir_widget = ShadowDirectionWidget(owner=self)
        props_layout.addRow("Glow direction", self.shadow_dir_widget)

        # Color controls
        self.stroke_color_btn = QPushButton("Stroke color")
        self.stroke_color_btn.clicked.connect(self.on_pick_stroke_color)
        props_layout.addRow(self.stroke_color_btn)

        self.fill_color_btn = QPushButton("Fill color")
        self.fill_color_btn.clicked.connect(self.on_pick_fill_color)
        props_layout.addRow(self.fill_color_btn)

        self.pick_from_base_btn = QPushButton("Pick from base (next click)")
        self.pick_from_base_btn.clicked.connect(self.on_pick_from_base_clicked)
        props_layout.addRow(self.pick_from_base_btn)

        controls_layout.addWidget(props_group)

        # Layers list (Photoshop-style)
        layers_label = QLabel("Layers")
        controls_layout.addWidget(layers_label)

        self.layers_list = LayerListWidget(owner=self)
        self.layers_list.currentItemChanged.connect(self.on_layer_selection_changed)
        self.layers_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.layers_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.layers_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        # Recompute z-order when user drags layers
        self.layers_list.model().rowsMoved.connect(self.on_layers_rows_moved)
        controls_layout.addWidget(self.layers_list)

        layer_buttons_layout = QHBoxLayout()
        layer_up_btn = QPushButton("Up")
        layer_up_btn.clicked.connect(self.on_layer_move_up)
        layer_buttons_layout.addWidget(layer_up_btn)
        layer_down_btn = QPushButton("Down")
        layer_down_btn.clicked.connect(self.on_layer_move_down)
        layer_buttons_layout.addWidget(layer_down_btn)
        controls_layout.addLayout(layer_buttons_layout)

        export_shape_btn = QPushButton("Export overlay to output/shape_overlay.png")
        export_shape_btn.clicked.connect(self.on_shape_export)
        controls_layout.addWidget(export_shape_btn)

        crop_btn = QPushButton("Create crop rectangle")
        crop_btn.clicked.connect(self.on_create_crop_rect)
        controls_layout.addWidget(crop_btn)

        apply_crop_btn = QPushButton("Apply crop to base image")
        apply_crop_btn.clicked.connect(self.on_apply_crop)
        controls_layout.addWidget(apply_crop_btn)

        self.shape_info_label = QLabel("")
        controls_layout.addWidget(self.shape_info_label)

        controls_layout.addStretch(1)

        main_layout.addLayout(controls_layout, stretch=1)

        # Track selection changes to reflect width/height
        self.shape_scene.selectionChanged.connect(self.on_shape_selection_changed)

    # ---------------------------------------------------------------- events
    def on_load_image(self) -> None:
        dialog = QFileDialog(self, "Select input PNG")
        dialog.setNameFilters(["PNG images (*.png)", "All files (*)"])
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                self.input_path = Path(selected[0]).resolve()
                self._update_original_preview()
                self._update_previews()

    def on_params_changed(self) -> None:
        self._update_previews()

    def on_export_components(self) -> None:
        if self.input_path is None:
            return

        output_dir = Path("output").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        threshold = self.threshold_spin.value()
        min_area = self.min_area_spin.value()

        no_bg_path = output_dir / f"{self.input_path.stem}_no_bg.png"

        remove_black_background(
            input_path=self.input_path,
            output_path=no_bg_path,
            threshold=threshold,
        )
        component_paths = split_components(
            input_path=no_bg_path,
            output_dir=output_dir,
            min_area=min_area,
        )

        self.component_info_label.setText(
            f"Exported {len(component_paths)} components to {output_dir.name}/"
        )

    # ---------------------------------------------------------------- helpers
    def _update_original_preview(self) -> None:
        if self.input_path is None:
            self.original_label.setText("Original")
            return

        pixmap = load_pixmap(self.input_path)
        if pixmap.isNull():
            self.original_label.setText("Could not load image")
        else:
            self.original_label.setPixmap(pixmap)

    def _update_previews(self) -> None:
        if self.input_path is None:
            self.processed_label.setText("Processed / Components")
            self.component_info_label.setText("Components: –")
            return

        threshold = self.threshold_spin.value()
        min_area = self.min_area_spin.value()

        self.preview_dir.mkdir(parents=True, exist_ok=True)
        no_bg_path = self.preview_dir / "preview_no_bg.png"

        # Generate background-removed preview
        remove_black_background(
            input_path=self.input_path,
            output_path=no_bg_path,
            threshold=threshold,
        )

        # Split into components (also in preview dir)
        component_paths = split_components(
            input_path=no_bg_path,
            output_dir=self.preview_dir,
            min_area=min_area,
        )

        # Show the full background-removed image so all components are visible.
        pixmap = load_pixmap(no_bg_path)

        if pixmap.isNull():
            self.processed_label.setText("No preview")
        else:
            self.processed_label.setPixmap(pixmap)

        self.component_info_label.setText(
            f"Components detected: {len(component_paths)}"
        )

    # --------------------------- animation tab handlers/helpers
    def _refresh_scene_rect(self) -> None:
        rect = self.anim_scene.itemsBoundingRect()
        self.anim_scene.setSceneRect(rect)
        if not rect.isNull():
            self.anim_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def on_load_guide(self) -> None:
        dialog = QFileDialog(self, "Select guide / slider PNG")
        dialog.setNameFilters(["PNG images (*.png)", "All files (*)"])
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if dialog.exec():
            selected = dialog.selectedFiles()
            if not selected:
                return

            self.guide_path = Path(selected[0]).resolve()
            pixmap = QPixmap(str(self.guide_path))
            if pixmap.isNull():
                return

            if self.guide_item is not None:
                self.anim_scene.removeItem(self.guide_item)

            self.guide_item = QGraphicsPixmapItem(pixmap)
            self.guide_item.setZValue(0)
            self.anim_scene.addItem(self.guide_item)

            self._refresh_scene_rect()

    def on_load_cap(self) -> None:
        dialog = QFileDialog(self, "Select fader cap PNG")
        dialog.setNameFilters(["PNG images (*.png)", "All files (*)"])
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if dialog.exec():
            selected = dialog.selectedFiles()
            if not selected:
                return

            self.cap_path = Path(selected[0]).resolve()
            pixmap = QPixmap(str(self.cap_path))
            if pixmap.isNull():
                return

            if self.cap_item is not None:
                self.anim_scene.removeItem(self.cap_item)

            self.cap_item = QGraphicsPixmapItem(pixmap)
            self.cap_item.setFlag(
                QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True
            )
            self.cap_item.setZValue(1)

            # Place roughly centered on the guide, if present.
            if self.guide_item is not None:
                guide_rect = self.guide_item.boundingRect()
                cap_rect = self.cap_item.boundingRect()
                x = guide_rect.center().x() - cap_rect.width() / 2
                y = guide_rect.center().y() - cap_rect.height() / 2
                self.cap_item.setPos(x, y)

            self.anim_scene.addItem(self.cap_item)
            self._refresh_scene_rect()

    def _update_edge_line(self, is_start: bool, y: float) -> None:
        rect = self.anim_scene.itemsBoundingRect()
        x1 = rect.left()
        x2 = rect.right()

        if is_start:
            if self.start_line_item is None:
                self.start_line_item = QGraphicsLineItem(x1, y, x2, y)
                self.start_line_item.setZValue(0.5)
                self.start_line_item.setPen(Qt.GlobalColor.green)
                self.anim_scene.addItem(self.start_line_item)
            else:
                self.start_line_item.setLine(x1, y, x2, y)
        else:
            if self.end_line_item is None:
                self.end_line_item = QGraphicsLineItem(x1, y, x2, y)
                self.end_line_item.setZValue(0.5)
                self.end_line_item.setPen(Qt.GlobalColor.red)
                self.anim_scene.addItem(self.end_line_item)
            else:
                self.end_line_item.setLine(x1, y, x2, y)

        self._refresh_scene_rect()

    def on_set_start_edge(self) -> None:
        if self.cap_item is None:
            return
        pos = self.cap_item.pos()
        self.start_edge_y = pos.y()
        self.start_label.setText(f"Start edge: y = {self.start_edge_y:.1f}")
        self._update_edge_line(is_start=True, y=self.start_edge_y)

    def on_set_end_edge(self) -> None:
        if self.cap_item is None:
            return
        pos = self.cap_item.pos()
        self.end_edge_y = pos.y()
        self.end_label.setText(f"End edge: y = {self.end_edge_y:.1f}")
        self._update_edge_line(is_start=False, y=self.end_edge_y)

    def on_anim_slider_changed(self, value: int) -> None:
        if (
            self.cap_item is None
            or self.start_edge_y is None
            or self.end_edge_y is None
        ):
            return

        t = value / 100.0  # 0..1
        y = self.start_edge_y + t * (self.end_edge_y - self.start_edge_y)
        current_pos = self.cap_item.pos()
        self.cap_item.setPos(current_pos.x(), y)
        self._refresh_scene_rect()

    # Clicking in the animation view to set a snap/center position
    def on_anim_view_clicked(self, scene_y: float) -> None:
        if self.cap_item is None or self.guide_item is None:
            return

        guide_rect = self.guide_item.boundingRect()
        cap_rect = self.cap_item.boundingRect()

        # Always keep the cap horizontally centered on the guide.
        x = guide_rect.center().x() - cap_rect.width() / 2
        y = scene_y - cap_rect.height() / 2

        self.cap_item.setPos(x, y)
        self.center_edge_y = self.cap_item.pos().y()
        self.center_label.setText(f"Center: y = {self.center_edge_y:.1f}")
        self._refresh_scene_rect()

    def on_export_spritesheet(self) -> None:
        if (
            self.guide_path is None
            or self.cap_path is None
            or self.start_edge_y is None
            or self.end_edge_y is None
        ):
            self.sheet_info_label.setText(
                "Load guide/cap and set START and END edges before exporting."
            )
            return

        num_frames = self.frames_spin.value()
        layout = self.layout_combo.currentText().lower()
        offset = self.offset_spin.value()

        guide_img = Image.open(self.guide_path).convert("RGBA")
        cap_img = Image.open(self.cap_path).convert("RGBA")

        W, H = guide_img.size

        # Use the current cap X position, mapped from the scene.
        cap_x = int(round(self.cap_item.pos().x()))

        frames = []
        for i in range(num_frames):
            t = i / (num_frames - 1) if num_frames > 1 else 0.0
            y = self.start_edge_y + t * (self.end_edge_y - self.start_edge_y)
            y_int = int(round(y))

            frame = guide_img.copy()
            frame.alpha_composite(cap_img, (cap_x, y_int))
            frames.append(frame)

        # Build spritesheet
        if layout.startswith("horizontal"):
            sheet_width = W * num_frames + offset * (num_frames - 1)
            sheet_height = H
            sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
            for i, frame in enumerate(frames):
                x = i * (W + offset)
                sheet.paste(frame, (x, 0))
            suffix = "h"
        else:
            sheet_width = W
            sheet_height = H * num_frames + offset * (num_frames - 1)
            sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
            for i, frame in enumerate(frames):
                y = i * (H + offset)
                sheet.paste(frame, (0, y))
            suffix = "v"

        output_dir = Path("output").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"fader_spritesheet_{num_frames}_{suffix}.png"
        sheet.save(out_path)

        self.sheet_info_label.setText(f"Saved spritesheet: {out_path.name}")

    # --------------------------- shape editor handlers/helpers
    def _ensure_shape_scene(self) -> None:
        if self.shape_scene is None:
            self.shape_scene = QGraphicsScene(self)
        if self.shape_view is not None:
            self.shape_view.setScene(self.shape_scene)

    def on_shape_load_base(self) -> None:
        self._ensure_shape_scene()

        dialog = QFileDialog(self, "Select base image")
        dialog.setNameFilters(["PNG images (*.png)", "All files (*)"])
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if dialog.exec():
            selected = dialog.selectedFiles()
            if not selected:
                return

            self.shape_base_path = Path(selected[0]).resolve()
            pixmap = QPixmap(str(self.shape_base_path))
            if pixmap.isNull():
                return

            if self.shape_base_item is not None:
                self.shape_scene.removeItem(self.shape_base_item)

            self.shape_base_item = QGraphicsPixmapItem(pixmap)
            self.shape_scene.addItem(self.shape_base_item)
            self.shape_scene.setSceneRect(self.shape_base_item.boundingRect())
            self.shape_base_image = pixmap.toImage()

            # Ensure base image is represented in layers list so it can be
            # stacked above/below other shapes.
            if self.layers_list is not None:
                # Remove any existing base-image layer entries
                for i in range(self.layers_list.count() - 1, -1, -1):
                    lw_item = self.layers_list.item(i)
                    data_item = lw_item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(data_item, QGraphicsPixmapItem):
                        self.layers_list.takeItem(i)
                base_label = (
                    f"Base: {self.shape_base_path.name}"
                    if self.shape_base_path is not None
                    else "Base image"
                )
                base_layer_item = QListWidgetItem(base_label)
                base_layer_item.setData(Qt.ItemDataRole.UserRole, self.shape_base_item)
                # Insert at the top so by default it's the furthest back; user
                # can reorder by dragging.
                self.layers_list.insertItem(0, base_layer_item)
                self.layers_list.setCurrentItem(base_layer_item)
                self._recompute_layer_z_values()

    def _create_shape_item(self, kind: str) -> QGraphicsRectItem | QGraphicsEllipseItem | QGraphicsLineItem:
        self._ensure_shape_scene()

        rect = self.shape_scene.sceneRect()
        if rect.isNull():
            rect = QRectF(0, 0, 512, 512)

        w = self.shape_width_spin.value()
        h = self.shape_height_spin.value()
        x = rect.center().x() - w / 2
        y = rect.center().y() - h / 2

        pen = QPen(self.shape_stroke_color)
        pen.setWidth(2)
        brush = QBrush(self.shape_fill_color) if self.shape_filled_check.isChecked() else QBrush(Qt.GlobalColor.transparent)

        if kind == "rect":
            item = ResizableRectItem(x, y, w, h)
        elif kind == "circle":
            item = ResizableEllipseItem(x, y, w, h)
        elif kind == "line":
            item = ResizableLineItem(x, y, x + w, y)
        else:  # dot -> small circle
            size = max(4, min(w, h))
            item = ResizableEllipseItem(x, y, size, size)

        item.setPen(pen)
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)) and kind != "line":
            item.setBrush(brush)

        item.setFlags(
            item.flags()
            | QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
        )

        # Optional neon glow using a drop shadow effect
        if self.shape_neon_check.isChecked():
            self._apply_neon_effect(item)

        self.shape_scene.addItem(item)
        self.current_shape_item = item

        # Add to layers list
        if self.layers_list is not None:
            name = f"{kind.capitalize()} {self.layers_list.count() + 1}"
            list_item = QListWidgetItem(name)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.layers_list.addItem(list_item)
            self.layers_list.setCurrentItem(list_item)

        return item

    def on_shape_add_rect(self) -> None:
        self._create_shape_item("rect")

    def on_shape_add_circle(self) -> None:
        self._create_shape_item("circle")

    def on_shape_add_line(self) -> None:
        self._create_shape_item("line")

    def on_shape_add_dot(self) -> None:
        self._create_shape_item("dot")

    def on_shape_selection_changed(self) -> None:
        items = self.shape_scene.selectedItems() if self.shape_scene is not None else []
        if not items:
            self.current_shape_item = None
            return
        item = items[0]
        self.current_shape_item = item
        rect = item.boundingRect()
        self.shape_width_spin.blockSignals(True)
        self.shape_height_spin.blockSignals(True)
        self.shape_width_spin.setValue(int(rect.width()))
        # For lines, height controls stroke thickness; for others, it's rect height.
        if isinstance(item, QGraphicsLineItem):
            pen = item.pen()
            self.shape_height_spin.setValue(pen.width())
        else:
            self.shape_height_spin.setValue(int(rect.height()))
        self.shape_width_spin.blockSignals(False)
        self.shape_height_spin.blockSignals(False)

        # Reflect current colors if item uses them
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            brush = item.brush()
            if brush.style() != Qt.BrushStyle.NoBrush:
                self.shape_fill_color = brush.color()
        pen = item.pen()
        self.shape_stroke_color = pen.color()
        self._update_color_buttons()

        # Reflect selection into layers list
        if self.layers_list is not None:
            for i in range(self.layers_list.count()):
                lw_item = self.layers_list.item(i)
                if lw_item.data(Qt.ItemDataRole.UserRole) is item:
                    self.layers_list.setCurrentRow(i)
                    break

    def on_shape_size_changed(self) -> None:
        if self.current_shape_item is None:
            return
        w = self.shape_width_spin.value()
        h = self.shape_height_spin.value()

        if isinstance(self.current_shape_item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            rect = self.current_shape_item.rect()  # type: ignore[attr-defined]
            self.current_shape_item.setRect(rect.x(), rect.y(), w, h)  # type: ignore[attr-defined]
        elif isinstance(self.current_shape_item, QGraphicsLineItem):
            line = self.current_shape_item.line()
            # Width = line length, Height = stroke thickness
            self.current_shape_item.setLine(line.x1(), line.y1(), line.x1() + w, line.y1())
            pen = self.current_shape_item.pen()
            pen.setWidth(max(1, h))
            self.current_shape_item.setPen(pen)

    def on_shape_style_changed(self) -> None:
        if self.current_shape_item is None:
            return
        # Apply fill & stroke styles (solid / gradient) to the current item.
        self._apply_fill_and_stroke_style(self.current_shape_item)

        # Update neon effect on current item
        if self.shape_neon_check.isChecked():
            self._apply_neon_effect(self.current_shape_item)
        else:
            self.current_shape_item.setGraphicsEffect(None)

    def _build_gradient_brush(
        self,
        rect: QRectF,
        use_gradient: bool,
        c1: QColor,
        c2: QColor,
        position: int,
        angle_deg: float,
        width_pct: int,
    ) -> QBrush:
        if not use_gradient:
            return QBrush(c1)

        t = max(0.0, min(1.0, position / 100.0))
        # Compute gradient line across rect center with the given angle.
        cx = rect.center().x()
        cy = rect.center().y()
        radius = max(rect.width(), rect.height())
        rad = math.radians(angle_deg)
        dx = radius * math.cos(rad)
        dy = radius * math.sin(rad)
        p1 = QPointF(cx - dx, cy - dy)
        p2 = QPointF(cx + dx, cy + dy)

        grad = QLinearGradient(p1, p2)
        # Blend width controls how wide the soft transition is between c1 and c2.
        w = max(0.0, min(1.0, width_pct / 100.0))
        half = w / 2.0
        grad.setColorAt(0.0, c1)
        grad.setColorAt(max(0.0, t - half), c1)
        grad.setColorAt(min(1.0, t + half), c2)
        grad.setColorAt(1.0, c2)
        return QBrush(grad)

    def _apply_fill_and_stroke_style(self, item) -> None:
        """
        Apply current stroke/fill settings (solid or gradient) to the given item.
        """
        rect = item.boundingRect()

        # Stroke
        stroke_brush = self._build_gradient_brush(
            rect,
            self.stroke_use_gradient,
            self.stroke_grad_color1,
            self.stroke_grad_color2,
            self.stroke_grad_pos,
            self.stroke_grad_angle,
            self.stroke_grad_width,
        )
        pen = item.pen()
        pen.setBrush(stroke_brush)
        item.setPen(pen)

        # Fill (for shapes that support it)
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            if self.shape_filled_check.isChecked():
                fill_brush = self._build_gradient_brush(
                    rect,
                    self.fill_use_gradient,
                    self.fill_grad_color1,
                    self.fill_grad_color2,
                    self.fill_grad_pos,
                    self.fill_grad_angle,
                    self.fill_grad_width,
                )
            else:
                fill_brush = QBrush(Qt.GlobalColor.transparent)
            item.setBrush(fill_brush)

    def on_layer_selection_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        if current is None or self.shape_scene is None:
            return
        item = current.data(Qt.ItemDataRole.UserRole)
        if item is None:
            return
        # Select only this item in the scene
        for it in self.shape_scene.selectedItems():
            it.setSelected(False)
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem)):
            item.setSelected(True)
            self.current_shape_item = item
            # Sync controls with this selection
            self.on_shape_selection_changed()

    def _recompute_layer_z_values(self) -> None:
        if self.layers_list is None:
            return
        # Lower index = lower z (background)
        for i in range(self.layers_list.count()):
            lw_item = self.layers_list.item(i)
            g_item = lw_item.data(Qt.ItemDataRole.UserRole)
            if g_item is not None:
                g_item.setZValue(i)

    def on_layer_move_up(self) -> None:
        if self.layers_list is None:
            return
        row = self.layers_list.currentRow()
        if row < 0 or row >= self.layers_list.count() - 1:
            return
        item = self.layers_list.takeItem(row)
        self.layers_list.insertItem(row + 1, item)
        self.layers_list.setCurrentRow(row + 1)
        self._recompute_layer_z_values()

    def on_layer_move_down(self) -> None:
        if self.layers_list is None:
            return
        row = self.layers_list.currentRow()
        if row <= 0:
            return
        item = self.layers_list.takeItem(row)
        self.layers_list.insertItem(row - 1, item)
        self.layers_list.setCurrentRow(row - 1)
        self._recompute_layer_z_values()

    def on_layers_rows_moved(self, *args) -> None:
        # Called when user drag-reorders layers in the list.
        self._recompute_layer_z_values()

    def _apply_neon_effect(self, item) -> None:
        effect = QGraphicsDropShadowEffect()
        # Intensity controls alpha; allow values > 100% but clamp at full opacity.
        alpha = int(self.neon_intensity_slider.value() / 100 * 255)
        alpha = max(0, min(255, alpha))
        glow_color = QColor(self.shape_stroke_color)
        glow_color.setAlpha(alpha)
        effect.setColor(glow_color)
        effect.setBlurRadius(self.neon_radius_spin.value())
        effect.setOffset(self.neon_offset_x_spin.value(), self.neon_offset_y_spin.value())
        item.setGraphicsEffect(effect)

    def _update_color_buttons(self) -> None:
        def style_for(color: QColor) -> str:
            return f"background-color: {color.name()};"

        self.stroke_color_btn.setStyleSheet(style_for(self.shape_stroke_color))
        self.fill_color_btn.setStyleSheet(style_for(self.shape_fill_color))

    def on_pick_stroke_color(self) -> None:
        dlg = ColorStyleDialog(
            self,
            "Stroke style",
            self.stroke_use_gradient,
            self.stroke_grad_color1,
            self.stroke_grad_color2,
            self.stroke_grad_pos,
            self.stroke_grad_angle,
            "stroke",
            self.stroke_grad_width,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            use_grad, c1, c2, pos, angle = dlg.get_result()
            self.stroke_use_gradient = use_grad
            self.stroke_grad_color1 = c1
            self.stroke_grad_color2 = c2
            self.stroke_grad_pos = pos
            self.stroke_grad_angle = angle
            # Primary stroke color uses color1
            self.shape_stroke_color = c1
            self._update_color_buttons()
            if self.current_shape_item is not None:
                self.on_shape_style_changed()

    def on_pick_fill_color(self) -> None:
        dlg = ColorStyleDialog(
            self,
            "Fill style",
            self.fill_use_gradient,
            self.fill_grad_color1,
            self.fill_grad_color2,
            self.fill_grad_pos,
            self.fill_grad_angle,
            "fill",
            self.fill_grad_width,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            use_grad, c1, c2, pos, angle = dlg.get_result()
            self.fill_use_gradient = use_grad
            self.fill_grad_color1 = c1
            self.fill_grad_color2 = c2
            self.fill_grad_pos = pos
            self.fill_grad_angle = angle
            self.shape_fill_color = c1
            self._update_color_buttons()
            if self.current_shape_item is not None:
                self.on_shape_style_changed()

    def on_pick_from_base_clicked(self) -> None:
        # Next click in the shape view picks color from the base image.
        # Toggle between stroke and fill pick; default to fill if nothing selected.
        if self.color_pick_mode == "stroke":
            self.color_pick_mode = "fill"
            self.pick_from_base_btn.setText("Pick FILL from base (next click)")
        elif self.color_pick_mode == "fill":
            self.color_pick_mode = None
            self.pick_from_base_btn.setText("Pick from base (next click)")
        else:
            self.color_pick_mode = "stroke"
            self.pick_from_base_btn.setText("Pick STROKE from base (next click)")

    def on_shadow_direction_changed(self, mode: str) -> None:
        """
        Update glow offset based on a simple direction picker:
        - all: centered glow (offset 0,0)
        - left/right/top/bottom: offset pushed in that direction
        """
        # Base magnitude for directional glow, reuse existing value if present.
        current_mag = max(abs(self.neon_offset_x_spin.value()), abs(self.neon_offset_y_spin.value()), 10)

        if mode == "all":
            self.neon_offset_x_spin.setValue(0)
            self.neon_offset_y_spin.setValue(0)
        elif mode == "left":
            self.neon_offset_x_spin.setValue(-current_mag)
            self.neon_offset_y_spin.setValue(0)
        elif mode == "right":
            self.neon_offset_x_spin.setValue(current_mag)
            self.neon_offset_y_spin.setValue(0)
        elif mode == "top":
            self.neon_offset_x_spin.setValue(0)
            self.neon_offset_y_spin.setValue(-current_mag)
        else:  # bottom
            self.neon_offset_x_spin.setValue(0)
            self.neon_offset_y_spin.setValue(current_mag)

        if self.shadow_dir_widget is not None:
            self.shadow_dir_widget.set_mode(mode)

        # Reapply neon effect with new offsets
        self.on_shape_style_changed()

    def _visible_items_bounding_rect(self) -> QRectF:
        """
        Compute bounding rect of only visible items so "deleted" (hidden)
        shapes don't affect export size.
        """
        if self.shape_scene is None:
            return QRectF()
        rect = QRectF()
        first = True
        for item in self.shape_scene.items():
            if not item.isVisible():
                continue
            bounds = item.sceneBoundingRect()
            if first:
                rect = QRectF(bounds)
                first = False
            else:
                rect = rect.united(bounds)
        # Expand by a padding based on current glow settings so that
        # drop-shadow neon effects aren't clipped at the export edges.
        if not rect.isNull():
            padding = 10.0
            try:
                radius = getattr(self, "neon_radius_spin", None)
                off_x = getattr(self, "neon_offset_x_spin", None)
                off_y = getattr(self, "neon_offset_y_spin", None)
                padding = max(
                    padding,
                    float(radius.value()) if radius is not None else 0.0,
                    abs(float(off_x.value())) if off_x is not None else 0.0,
                    abs(float(off_y.value())) if off_y is not None else 0.0,
                )
            except Exception:
                pass
            rect.adjust(-padding, -padding, padding, padding)
        return rect

    def delete_selected_shapes(self) -> None:
        """
        Delete (hide) selected shapes from the scene and layers list, with confirmation.
        This is triggered from both the ShapeView and the layers list.
        """
        if self.shape_scene is None:
            return

        selected = self.shape_scene.selectedItems()

        # If nothing is selected in the scene, fall back to the current layer.
        if not selected and self.layers_list is not None:
            lw_item = self.layers_list.currentItem()
            if lw_item is not None:
                g_item = lw_item.data(Qt.ItemDataRole.UserRole)
                if g_item is not None:
                    selected = [g_item]

        # Don't delete the scene entirely.
        if not selected:
            return

        count = len(selected)
        reply = QMessageBox.question(
            self,
            "Delete shape" if count == 1 else "Delete shapes",
            f"Are you sure you want to delete {count} selected shape(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.layers_list is not None:
            for g_item in selected:
                for i in range(self.layers_list.count() - 1, -1, -1):
                    lw_item = self.layers_list.item(i)
                    if lw_item.data(Qt.ItemDataRole.UserRole) is g_item:
                        self.layers_list.takeItem(i)
                        break

        for g_item in selected:
            g_item.setVisible(False)
            g_item.setSelected(False)
            g_item.setGraphicsEffect(None)

        self.current_shape_item = None

    def on_shape_export(self) -> None:
        if self.shape_scene is None:
            return

        # Export uses the visible-items bounds so hidden / deleted items don't
        # affect the region, and shapes far from the base image are included.
        rect = self._visible_items_bounding_rect()
        if rect.isNull():
            self.shape_info_label.setText("Nothing to export.")
            return

        image = self._render_overlay_image(rect)

        # Preview dialog to let user confirm the export region/size.
        dialog = QDialog(self)
        dialog.setWindowTitle("Export overlay preview")
        vbox = QVBoxLayout(dialog)

        size_label = QLabel(f"Size: {image.width()} × {image.height()} px")
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(size_label)

        preview_label = QLabel()
        pix = QPixmap.fromImage(image)
        max_dim = 320
        if pix.width() > max_dim or pix.height() > max_dim:
            pix = pix.scaled(
                max_dim,
                max_dim,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        preview_label.setPixmap(pix)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(preview_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        vbox.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            output_dir = Path("output").resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / "shape_overlay.png"
            image.save(str(out_path))
            self.shape_info_label.setText(f"Saved overlay: {out_path.name}")
        else:
            self.shape_info_label.setText("Overlay export cancelled.")

    def _render_overlay_image(self, rect: QRectF) -> QImage:
        width = int(rect.width())
        height = int(rect.height())
        if width <= 0 or height <= 0:
            width = height = 512

        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        # Render only the requested rectangle region so shapes far from the
        # origin are included correctly.
        target = QRectF(0, 0, width, height)
        self.shape_scene.render(painter, target, rect)
        painter.end()

        return image

    def on_create_crop_rect(self) -> None:
        if self.shape_scene is None or self.shape_base_item is None:
            return

        base_rect = self.shape_base_item.boundingRect()
        inset = 10
        min_size = 32
        crop_rect = QRectF(
            base_rect.left() + inset,
            base_rect.top() + inset,
            max(min_size, base_rect.width() - 2 * inset),
            max(min_size, base_rect.height() - 2 * inset),
        )

        if self.crop_rect_item is not None:
            self.shape_scene.removeItem(self.crop_rect_item)

        self.crop_rect_item = ResizableRectItem(crop_rect)
        pen = QPen(QColor("#ffcc00"))
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidth(2)
        self.crop_rect_item.setPen(pen)
        self.crop_rect_item.setBrush(QBrush(Qt.GlobalColor.transparent))
        self.crop_rect_item.setZValue(2)
        self.shape_scene.addItem(self.crop_rect_item)

    def on_apply_crop(self) -> None:
        if (
            self.shape_scene is None
            or self.shape_base_item is None
            or self.shape_base_image is None
            or self.crop_rect_item is None
        ):
            return

        # Compute cropped image from current crop rectangle
        cropped = self._compute_cropped_image()
        if cropped is None:
            return

        # Show preview dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Crop preview")
        vbox = QVBoxLayout(dialog)

        preview_label = QLabel()
        pix = QPixmap.fromImage(cropped)
        max_dim = 320
        if pix.width() > max_dim or pix.height() > max_dim:
            pix = pix.scaled(max_dim, max_dim, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        preview_label.setPixmap(pix)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(preview_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        vbox.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Apply crop to base image
            self.shape_base_image = cropped
            self.shape_base_item.setPixmap(QPixmap.fromImage(cropped))
            self.shape_scene.setSceneRect(self.shape_base_item.boundingRect())

            # Remove crop rect
            self.shape_scene.removeItem(self.crop_rect_item)
            self.crop_rect_item = None

            self.shape_info_label.setText("Base image cropped.")
        else:
            self.shape_info_label.setText("Crop cancelled.")

    def _compute_cropped_image(self) -> QImage | None:
        if (
            self.shape_base_item is None
            or self.shape_base_image is None
            or self.crop_rect_item is None
        ):
            return None

        crop_rect_item_rect = self.crop_rect_item.rect()
        top_left_scene = self.crop_rect_item.mapToScene(crop_rect_item_rect.topLeft())
        bottom_right_scene = self.crop_rect_item.mapToScene(
            crop_rect_item_rect.bottomRight()
        )
        top_left_in_base = self.shape_base_item.mapFromScene(top_left_scene)
        bottom_right_in_base = self.shape_base_item.mapFromScene(bottom_right_scene)

        x1 = int(round(min(top_left_in_base.x(), bottom_right_in_base.x())))
        y1 = int(round(min(top_left_in_base.y(), bottom_right_in_base.y())))
        x2 = int(round(max(top_left_in_base.x(), bottom_right_in_base.x())))
        y2 = int(round(max(top_left_in_base.y(), bottom_right_in_base.y())))

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(self.shape_base_image.width(), x2)
        y2 = min(self.shape_base_image.height(), y2)

        w = max(1, x2 - x1)
        h = max(1, y2 - y1)

        return self.shape_base_image.copy(x1, y1, w, h)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


