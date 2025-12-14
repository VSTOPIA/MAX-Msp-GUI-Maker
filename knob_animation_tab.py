"""
Knob Animation Tab - Contains UI and logic for:
- Loading knob images
- Setting rotation center point
- Defining start/end rotation angles
- Previewing knob rotation
- Shape editing with neon effects
- Exporting rotation spritesheets
"""

import math
from pathlib import Path
from typing import TYPE_CHECKING, List

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPixmap, QPen, QColor, QBrush, QPainter, QTransform, QConicalGradient
from PyQt6.QtWidgets import (
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QFileDialog,
    QColorDialog,
    QGraphicsDropShadowEffect,
    QCheckBox,
    QScrollArea,
)

from PIL import Image

# Import shape classes from shape editor
from shape_editor_tab import (
    ResizableRectItem,
    ResizableEllipseItem,
    ResizableLineItem,
)

if TYPE_CHECKING:
    from gui import MainWindow


class AngleWheelWidget(QWidget):
    """A small draggable wheel to set an angle by rotating."""
    
    angleChanged = pyqtSignal(float)
    
    # Layout constants
    LABEL_HEIGHT = 16
    WHEEL_RADIUS = 26
    VALUE_HEIGHT = 16
    PADDING = 4
    
    def __init__(self, label: str, color: QColor, initial_angle: float = 0, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._angle = initial_angle
        self._dragging = False
        
        # Calculate widget size based on layout
        wheel_diameter = self.WHEEL_RADIUS * 2
        total_height = self.LABEL_HEIGHT + self.PADDING + wheel_diameter + self.PADDING + self.VALUE_HEIGHT
        self.setFixedSize(max(70, wheel_diameter + 10), total_height)
        self.setMouseTracking(True)
        
        # Wheel center Y position
        self._wheel_cy = self.LABEL_HEIGHT + self.PADDING + self.WHEEL_RADIUS
    
    def angle(self) -> float:
        return self._angle
    
    def setAngle(self, angle: float, emit: bool = True) -> None:
        self._angle = angle
        self.update()
        if emit:
            self.angleChanged.emit(angle)
    
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        radius = self.WHEEL_RADIUS
        cx = w // 2
        cy = self._wheel_cy
        
        # Draw label at top
        painter.setPen(QColor("#cccccc"))
        painter.drawText(QRectF(0, 0, w, self.LABEL_HEIGHT), Qt.AlignmentFlag.AlignCenter, self._label)
        
        # Draw outer ring (dark)
        painter.setPen(QPen(QColor("#333333"), 2))
        painter.setBrush(QBrush(QColor("#1a1a1a")))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        
        # Draw tick marks
        painter.setPen(QPen(QColor("#555555"), 1))
        for i in range(12):
            angle_rad = math.radians(i * 30)
            inner_r = radius - 4
            outer_r = radius - 1
            x1 = cx + inner_r * math.cos(angle_rad)
            y1 = cy + inner_r * math.sin(angle_rad)
            x2 = cx + outer_r * math.cos(angle_rad)
            y2 = cy + outer_r * math.sin(angle_rad)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        
        # Draw pointer line
        angle_rad = math.radians(self._angle)
        px = cx + (radius - 8) * math.cos(angle_rad)
        py = cy + (radius - 8) * math.sin(angle_rad)
        
        # Glow effect
        for glow_w in [8, 6, 4]:
            glow_color = QColor(self._color)
            glow_color.setAlpha(40)
            painter.setPen(QPen(glow_color, glow_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx, cy), QPointF(px, py))
        
        # Main pointer line
        painter.setPen(QPen(self._color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(cx, cy), QPointF(px, py))
        
        # Center dot
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 4, 4)
        
        # Draw angle value at bottom
        painter.setPen(QColor("#aaaaaa"))
        painter.drawText(QRectF(0, h - self.VALUE_HEIGHT, w, self.VALUE_HEIGHT), 
                        Qt.AlignmentFlag.AlignCenter, f"{self._angle:.0f}°")
    
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._update_angle_from_pos(event.pos())
    
    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._update_angle_from_pos(event.pos())
    
    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
    
    def _update_angle_from_pos(self, pos) -> None:
        cx = self.width() // 2
        cy = self._wheel_cy
        dx = pos.x() - cx
        dy = pos.y() - cy
        angle = math.degrees(math.atan2(dy, dx))
        self.setAngle(angle)


class KnobView(QGraphicsView):
    """Custom QGraphicsView for knob animation with shape editing support."""

    def __init__(self, scene: QGraphicsScene, owner: "KnobAnimationTab") -> None:
        super().__init__(scene)
        self._owner = owner
        self._set_center_mode = False  # When True, clicks set rotation center
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def set_center_mode(self, enabled: bool) -> None:
        """Toggle between shape selection mode and set-center mode."""
        self._set_center_mode = enabled

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if we clicked on an item
            item = self.itemAt(event.pos())
            
            # If in center mode or clicked on empty space with Ctrl held, set center
            if self._set_center_mode or (item is None and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                scene_pos = self.mapToScene(event.pos())
                self._owner.set_rotation_center(scene_pos)
                return
        
        super().mousePressEvent(event)


class KnobAnimationTab(QWidget):
    """Tab widget for knob rotation animation and spritesheet generation."""

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self._owner = owner

        # Knob state
        self.knob_path: Path | None = None
        self.knob_item: QGraphicsPixmapItem | None = None
        self.knob_pixmap: QPixmap | None = None
        
        # Rotation parameters
        self.rotation_center: QPointF | None = None
        self.pointer_angle: float = -135.0  # Where the pointer is in the original image
        self.start_angle: float = -135.0  # degrees, 0 = right, counter-clockwise
        self.end_angle: float = 135.0
        self.current_angle: float = -135.0
        
        # Visual indicators
        self.center_marker: QGraphicsEllipseItem | None = None
        self.rotation_circle: QGraphicsEllipseItem | None = None
        self.start_line: QGraphicsLineItem | None = None
        self.end_line: QGraphicsLineItem | None = None
        self.current_line: QGraphicsLineItem | None = None
        
        # Shape editing state
        self.shapes: List = []  # List of shape items added to the knob
        self.shape_stroke_color: QColor = QColor("#00ffff")
        self.shape_fill_color: QColor = QColor(0, 0, 0, 0)  # Transparent
        self.neon_enabled: bool = True
        self.neon_radius: int = 15
        self.neon_intensity: int = 200
        
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Graphics view for knob
        self.knob_scene = QGraphicsScene(self)
        self.knob_view = KnobView(self.knob_scene, owner=self)
        self.knob_view.setStyleSheet("background-color: #101010;")

        main_layout.addWidget(self.knob_view, stretch=3)

        # Controls on the right
        controls_layout = QVBoxLayout()

        load_knob_btn = QPushButton("Load knob image…")
        load_knob_btn.clicked.connect(self.on_load_knob)
        controls_layout.addWidget(load_knob_btn)

        # Sample knobs selector
        samples_layout = QHBoxLayout()
        self.sample_combo = QComboBox()
        self.sample_combo.addItems([
            "Metallic",
            "Neon Cyan", 
            "Neon Magenta",
            "Neon Green",
            "Simple",
            "Cyberpunk",
            "Metallic Large"
        ])
        samples_layout.addWidget(self.sample_combo)
        
        load_sample_btn = QPushButton("Load sample")
        load_sample_btn.clicked.connect(self.on_load_sample_knob)
        samples_layout.addWidget(load_sample_btn)
        controls_layout.addLayout(samples_layout)

        controls_layout.addSpacing(12)

        # Angle wheels for visual calibration
        wheels_group = QGroupBox("Angle calibration (drag to rotate)")
        wheels_layout = QHBoxLayout(wheels_group)
        
        # Pointer wheel (blue) - where the knob pointer is in original image
        self.pointer_wheel = AngleWheelWidget("Pointer", QColor("#00aaff"), -135)
        self.pointer_wheel.angleChanged.connect(self.on_pointer_wheel_changed)
        wheels_layout.addWidget(self.pointer_wheel)
        
        # Start angle wheel (green)
        self.start_wheel = AngleWheelWidget("Start", QColor("#00ff00"), -135)
        self.start_wheel.angleChanged.connect(self.on_start_wheel_changed)
        wheels_layout.addWidget(self.start_wheel)
        
        # End angle wheel (red)
        self.end_wheel = AngleWheelWidget("End", QColor("#ff4444"), 135)
        self.end_wheel.angleChanged.connect(self.on_end_wheel_changed)
        wheels_layout.addWidget(self.end_wheel)
        
        controls_layout.addWidget(wheels_group)

        controls_layout.addSpacing(8)

        # Rotation center button
        self.set_center_btn = QPushButton("📍 Set rotation center (Ctrl+Click)")
        self.set_center_btn.setCheckable(True)
        self.set_center_btn.setToolTip("When active, clicking on canvas sets the rotation center point")
        self.set_center_btn.toggled.connect(self.on_set_center_mode_toggled)
        controls_layout.addWidget(self.set_center_btn)

        # Rotation info labels
        self.center_label = QLabel("Center: –")
        self.current_angle_label = QLabel("Current: -135°")
        controls_layout.addWidget(self.center_label)
        controls_layout.addWidget(self.current_angle_label)

        controls_layout.addSpacing(8)

        # Additional settings
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout(settings_group)

        # Circle radius for visual guide
        self.guide_radius_spin = QSpinBox()
        self.guide_radius_spin.setRange(10, 500)
        self.guide_radius_spin.setValue(80)
        self.guide_radius_spin.valueChanged.connect(self.update_visual_guides)
        settings_layout.addRow("Guide radius (px)", self.guide_radius_spin)

        controls_layout.addWidget(settings_group)

        controls_layout.addSpacing(8)

        # ============== SHAPE TOOLS ==============
        shape_group = QGroupBox("Shape Tools (overlay effects)")
        shape_group.setCheckable(True)
        shape_group.setChecked(True)
        shape_layout = QVBoxLayout(shape_group)

        # Shape creation buttons
        shape_btns_layout = QHBoxLayout()
        
        add_rect_btn = QPushButton("▢")
        add_rect_btn.setToolTip("Add rectangle")
        add_rect_btn.setFixedSize(32, 32)
        add_rect_btn.clicked.connect(self.on_add_rect)
        shape_btns_layout.addWidget(add_rect_btn)
        
        add_circle_btn = QPushButton("○")
        add_circle_btn.setToolTip("Add circle")
        add_circle_btn.setFixedSize(32, 32)
        add_circle_btn.clicked.connect(self.on_add_circle)
        shape_btns_layout.addWidget(add_circle_btn)
        
        add_line_btn = QPushButton("╱")
        add_line_btn.setToolTip("Add line")
        add_line_btn.setFixedSize(32, 32)
        add_line_btn.clicked.connect(self.on_add_line)
        shape_btns_layout.addWidget(add_line_btn)
        
        del_shape_btn = QPushButton("🗑")
        del_shape_btn.setToolTip("Delete selected shape")
        del_shape_btn.setFixedSize(32, 32)
        del_shape_btn.clicked.connect(self.on_delete_shape)
        shape_btns_layout.addWidget(del_shape_btn)
        
        shape_btns_layout.addStretch()
        shape_layout.addLayout(shape_btns_layout)

        # Color pickers
        colors_layout = QHBoxLayout()
        
        self.stroke_color_btn = QPushButton()
        self.stroke_color_btn.setFixedSize(28, 28)
        self.stroke_color_btn.setStyleSheet(f"background-color: {self.shape_stroke_color.name()}; border: 2px solid #555;")
        self.stroke_color_btn.setToolTip("Stroke color")
        self.stroke_color_btn.clicked.connect(self.on_pick_stroke_color)
        colors_layout.addWidget(QLabel("Stroke:"))
        colors_layout.addWidget(self.stroke_color_btn)
        
        colors_layout.addSpacing(10)
        
        self.fill_color_btn = QPushButton()
        self.fill_color_btn.setFixedSize(28, 28)
        self.fill_color_btn.setStyleSheet("background-color: transparent; border: 2px solid #555;")
        self.fill_color_btn.setToolTip("Fill color")
        self.fill_color_btn.clicked.connect(self.on_pick_fill_color)
        colors_layout.addWidget(QLabel("Fill:"))
        colors_layout.addWidget(self.fill_color_btn)
        
        colors_layout.addStretch()
        shape_layout.addLayout(colors_layout)

        # Stroke width
        stroke_w_layout = QHBoxLayout()
        stroke_w_layout.addWidget(QLabel("Width:"))
        self.stroke_width_spin = QSpinBox()
        self.stroke_width_spin.setRange(1, 50)
        self.stroke_width_spin.setValue(3)
        self.stroke_width_spin.valueChanged.connect(self.on_shape_style_changed)
        stroke_w_layout.addWidget(self.stroke_width_spin)
        stroke_w_layout.addWidget(QLabel("px"))
        stroke_w_layout.addStretch()
        shape_layout.addLayout(stroke_w_layout)

        # Neon glow controls
        self.neon_checkbox = QCheckBox("Neon glow")
        self.neon_checkbox.setChecked(True)
        self.neon_checkbox.stateChanged.connect(self.on_shape_style_changed)
        shape_layout.addWidget(self.neon_checkbox)

        neon_layout = QFormLayout()
        self.neon_radius_spin = QSpinBox()
        self.neon_radius_spin.setRange(0, 100)
        self.neon_radius_spin.setValue(15)
        self.neon_radius_spin.valueChanged.connect(self.on_shape_style_changed)
        neon_layout.addRow("Glow radius:", self.neon_radius_spin)

        self.neon_intensity_spin = QSpinBox()
        self.neon_intensity_spin.setRange(0, 255)
        self.neon_intensity_spin.setValue(200)
        self.neon_intensity_spin.valueChanged.connect(self.on_shape_style_changed)
        neon_layout.addRow("Glow intensity:", self.neon_intensity_spin)
        
        shape_layout.addLayout(neon_layout)

        # Shapes rotate with knob option
        self.shapes_rotate_checkbox = QCheckBox("Shapes rotate with knob")
        self.shapes_rotate_checkbox.setChecked(True)
        self.shapes_rotate_checkbox.setToolTip("When checked, shapes will rotate along with the knob in export")
        shape_layout.addWidget(self.shapes_rotate_checkbox)

        controls_layout.addWidget(shape_group)

        controls_layout.addSpacing(8)

        # Preview slider
        controls_layout.addWidget(QLabel("Preview rotation"))
        self.preview_slider = QSlider(Qt.Orientation.Horizontal)
        self.preview_slider.setRange(0, 100)
        self.preview_slider.setValue(0)
        self.preview_slider.valueChanged.connect(self.on_preview_slider_changed)
        controls_layout.addWidget(self.preview_slider)

        # Reverse direction button
        reverse_btn = QPushButton("↻ Reverse direction")
        reverse_btn.clicked.connect(self.on_reverse_direction)
        controls_layout.addWidget(reverse_btn)

        controls_layout.addSpacing(12)

        # Spritesheet export parameters
        export_group = QGroupBox("Spritesheet export")
        export_layout = QFormLayout(export_group)

        self.frames_spin = QSpinBox()
        self.frames_spin.setRange(2, 256)
        self.frames_spin.setValue(64)
        export_layout.addRow("Frames", self.frames_spin)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Horizontal", "Vertical", "Grid"])
        export_layout.addRow("Layout", self.layout_combo)

        self.grid_cols_spin = QSpinBox()
        self.grid_cols_spin.setRange(1, 32)
        self.grid_cols_spin.setValue(8)
        export_layout.addRow("Grid columns", self.grid_cols_spin)

        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(0, 512)
        self.offset_spin.setValue(0)
        export_layout.addRow("Offset (px)", self.offset_spin)

        controls_layout.addWidget(export_group)

        export_btn = QPushButton("Export knob spritesheet")
        export_btn.clicked.connect(self.on_export_spritesheet)
        controls_layout.addWidget(export_btn)

        self.info_label = QLabel("")
        controls_layout.addWidget(self.info_label)

        controls_layout.addStretch(1)

        main_layout.addLayout(controls_layout, stretch=1)

    # ------------------------------------------------------------------ Actions

    def on_load_knob(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open knob image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.knob_path = Path(path)
            self.knob_pixmap = QPixmap(str(self.knob_path))

            if self.knob_item is not None:
                self.knob_scene.removeItem(self.knob_item)

            self.knob_item = QGraphicsPixmapItem(self.knob_pixmap)
            self.knob_item.setZValue(0)
            self.knob_scene.addItem(self.knob_item)

            # Set default rotation center to image center
            rect = self.knob_item.boundingRect()
            self.rotation_center = QPointF(rect.center())
            self.center_label.setText(f"Center: ({self.rotation_center.x():.0f}, {self.rotation_center.y():.0f})")

            self._refresh_scene_rect()
            self.update_visual_guides()

    def on_load_sample_knob(self) -> None:
        """Load a premade sample knob from the output/sample_knobs folder."""
        sample_files = {
            "Metallic": "knob_metallic.png",
            "Neon Cyan": "knob_neon_cyan.png",
            "Neon Magenta": "knob_neon_magenta.png",
            "Neon Green": "knob_neon_green.png",
            "Simple": "knob_simple.png",
            "Cyberpunk": "knob_cyberpunk.png",
            "Metallic Large": "knob_metallic_large.png",
        }
        
        selected = self.sample_combo.currentText()
        filename = sample_files.get(selected)
        if not filename:
            return
        
        sample_path = Path("output/sample_knobs") / filename
        if not sample_path.exists():
            self.info_label.setText(f"Sample not found! Run create_sample_knob.py first.")
            return
        
        self.knob_path = sample_path
        self.knob_pixmap = QPixmap(str(self.knob_path))

        if self.knob_item is not None:
            self.knob_scene.removeItem(self.knob_item)

        self.knob_item = QGraphicsPixmapItem(self.knob_pixmap)
        self.knob_item.setZValue(0)
        self.knob_scene.addItem(self.knob_item)

        # Set default rotation center to image center
        rect = self.knob_item.boundingRect()
        self.rotation_center = QPointF(rect.center())
        self.center_label.setText(f"Center: ({self.rotation_center.x():.0f}, {self.rotation_center.y():.0f})")

        self._refresh_scene_rect()
        self.update_visual_guides()
        self.info_label.setText(f"Loaded: {selected}")

    def on_set_center_mode_toggled(self, checked: bool) -> None:
        """Toggle the set-center mode on the view."""
        self.knob_view.set_center_mode(checked)
        if checked:
            self.set_center_btn.setText("📍 Click canvas to set center...")
        else:
            self.set_center_btn.setText("📍 Set rotation center (Ctrl+Click)")

    def set_rotation_center(self, pos: QPointF) -> None:
        self.rotation_center = pos
        self.center_label.setText(f"Center: ({pos.x():.0f}, {pos.y():.0f})")
        # Turn off center mode after setting
        self.set_center_btn.setChecked(False)
        self.update_visual_guides()

    # ------------------------------------------------------------------ Wheel handlers

    def on_pointer_wheel_changed(self, angle: float) -> None:
        """Update the angle where the pointer is in the original knob image."""
        self.pointer_angle = angle
        # Re-apply current rotation with new pointer angle
        if self.knob_item is not None:
            self._apply_rotation(self.current_angle)
        self.update_visual_guides()

    def on_start_wheel_changed(self, angle: float) -> None:
        """Update start angle from wheel."""
        self.start_angle = angle
        self.update_visual_guides()

    def on_end_wheel_changed(self, angle: float) -> None:
        """Update end angle from wheel."""
        self.end_angle = angle
        self.update_visual_guides()

    def on_reverse_direction(self) -> None:
        """Reverse the rotation direction - go the other way around the circle."""
        # Calculate the current arc length
        arc = self.end_angle - self.start_angle
        
        # Reverse by going the other way (add or subtract 360 from end)
        if arc > 0:
            new_end = self.end_angle - 360
        else:
            new_end = self.end_angle + 360
        
        # Update end angle via wheel
        self.end_angle = new_end
        self.end_wheel.setAngle(new_end, emit=False)
        
        # Recalculate current angle based on slider position and apply immediately
        t = self.preview_slider.value() / 100.0
        self.current_angle = self.start_angle + t * (self.end_angle - self.start_angle)
        self.current_angle_label.setText(f"Current: {self.current_angle:.0f}°")
        
        # Apply rotation to show the change immediately
        if self.knob_item is not None:
            self._apply_rotation(self.current_angle)
        
        self.update_visual_guides()

    def on_preview_slider_changed(self, value: int) -> None:
        if self.knob_item is None or self.rotation_center is None:
            return
        
        # Interpolate between start and end angles
        t = value / 100.0
        self.current_angle = self.start_angle + t * (self.end_angle - self.start_angle)
        self.current_angle_label.setText(f"Current: {self.current_angle:.0f}°")
        
        # Apply rotation to knob
        self._apply_rotation(self.current_angle)
        self.update_visual_guides()

    def _apply_rotation(self, target_angle: float) -> None:
        """Rotate the knob image so its pointer points at target_angle."""
        if self.knob_item is None or self.rotation_center is None:
            return
        
        # Calculate rotation needed: target_angle - pointer_angle
        # This makes the pointer (originally at pointer_angle) point to target_angle
        rotation = target_angle - self.pointer_angle
        
        # Reset and apply new transform
        transform = QTransform()
        # Move origin to rotation center
        transform.translate(self.rotation_center.x(), self.rotation_center.y())
        # Rotate
        transform.rotate(rotation)
        # Move origin back
        transform.translate(-self.rotation_center.x(), -self.rotation_center.y())
        
        self.knob_item.setTransform(transform)

    def update_visual_guides(self) -> None:
        """Update the visual rotation guide circle and angle lines."""
        if self.rotation_center is None:
            return

        cx = self.rotation_center.x()
        cy = self.rotation_center.y()
        radius = self.guide_radius_spin.value()

        # Center marker
        if self.center_marker is not None:
            self.knob_scene.removeItem(self.center_marker)
        self.center_marker = QGraphicsEllipseItem(cx - 5, cy - 5, 10, 10)
        self.center_marker.setPen(QPen(QColor("#ffffff"), 2))
        self.center_marker.setBrush(QBrush(QColor("#ff0000")))
        self.center_marker.setZValue(100)
        self.knob_scene.addItem(self.center_marker)

        # Rotation circle
        if self.rotation_circle is not None:
            self.knob_scene.removeItem(self.rotation_circle)
        self.rotation_circle = QGraphicsEllipseItem(cx - radius, cy - radius, radius * 2, radius * 2)
        pen = QPen(QColor("#666666"), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.rotation_circle.setPen(pen)
        self.rotation_circle.setBrush(QBrush(Qt.GlobalColor.transparent))
        self.rotation_circle.setZValue(50)
        self.knob_scene.addItem(self.rotation_circle)

        # Start angle line (green)
        if self.start_line is not None:
            self.knob_scene.removeItem(self.start_line)
        start_rad = math.radians(self.start_angle)
        start_x = cx + radius * math.cos(start_rad)
        start_y = cy + radius * math.sin(start_rad)
        self.start_line = QGraphicsLineItem(cx, cy, start_x, start_y)
        self.start_line.setPen(QPen(QColor("#00ff00"), 3))
        self.start_line.setZValue(100)
        self.knob_scene.addItem(self.start_line)

        # End angle line (red)
        if self.end_line is not None:
            self.knob_scene.removeItem(self.end_line)
        end_rad = math.radians(self.end_angle)
        end_x = cx + radius * math.cos(end_rad)
        end_y = cy + radius * math.sin(end_rad)
        self.end_line = QGraphicsLineItem(cx, cy, end_x, end_y)
        self.end_line.setPen(QPen(QColor("#ff0000"), 3))
        self.end_line.setZValue(100)
        self.knob_scene.addItem(self.end_line)

        # Current angle line (cyan)
        if self.current_line is not None:
            self.knob_scene.removeItem(self.current_line)
        current_rad = math.radians(self.current_angle)
        current_x = cx + radius * math.cos(current_rad)
        current_y = cy + radius * math.sin(current_rad)
        self.current_line = QGraphicsLineItem(cx, cy, current_x, current_y)
        self.current_line.setPen(QPen(QColor("#00ffff"), 2))
        self.current_line.setZValue(100)
        self.knob_scene.addItem(self.current_line)

    def on_export_spritesheet(self) -> None:
        if self.knob_path is None or self.rotation_center is None:
            self.info_label.setText("Load a knob image first!")
            return

        output_dir = Path("output").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load original image with PIL for rotation
        knob_img = Image.open(self.knob_path).convert("RGBA")
        
        frames_count = self.frames_spin.value()
        layout = self.layout_combo.currentText()
        offset = self.offset_spin.value()
        grid_cols = self.grid_cols_spin.value()

        frame_width = knob_img.width
        frame_height = knob_img.height

        # Calculate spritesheet dimensions
        if layout == "Horizontal":
            sheet_width = frame_width * frames_count + offset * (frames_count - 1)
            sheet_height = frame_height
        elif layout == "Vertical":
            sheet_width = frame_width
            sheet_height = frame_height * frames_count + offset * (frames_count - 1)
        else:  # Grid
            rows = math.ceil(frames_count / grid_cols)
            sheet_width = frame_width * grid_cols + offset * (grid_cols - 1)
            sheet_height = frame_height * rows + offset * (rows - 1)

        sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))

        # Rotation center in image coordinates
        cx = self.rotation_center.x()
        cy = self.rotation_center.y()

        # Check if we have shapes to include
        visible_shapes = [s for s in self.shapes if s.isVisible()]
        shapes_rotate = self.shapes_rotate_checkbox.isChecked()

        # Hide visual guides during export
        guides_to_hide = [self.center_marker, self.rotation_circle, 
                         self.start_line, self.end_line, self.current_line]
        for guide in guides_to_hide:
            if guide:
                guide.setVisible(False)

        for i in range(frames_count):
            t = i / (frames_count - 1) if frames_count > 1 else 0
            target_angle = self.start_angle + t * (self.end_angle - self.start_angle)
            
            # Calculate rotation: target_angle - pointer_angle
            rotation = target_angle - self.pointer_angle
            
            # Rotate knob image
            rotated = knob_img.rotate(
                -rotation,
                resample=Image.Resampling.BICUBIC,
                center=(cx, cy),
                expand=False
            )

            # If we have shapes, render them on top
            if visible_shapes:
                # Apply rotation to knob item in scene
                self._apply_rotation(target_angle)
                
                # Optionally rotate shapes too
                if shapes_rotate:
                    shape_transform = QTransform()
                    shape_transform.translate(cx, cy)
                    shape_transform.rotate(rotation)
                    shape_transform.translate(-cx, -cy)
                    for shape in visible_shapes:
                        shape.setTransform(shape_transform)
                
                # Render scene to QImage
                from PyQt6.QtGui import QImage
                qimg = QImage(frame_width, frame_height, QImage.Format.Format_ARGB32)
                qimg.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(qimg)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                # Render just the knob area
                source_rect = QRectF(0, 0, frame_width, frame_height)
                self.knob_scene.render(painter, QRectF(0, 0, frame_width, frame_height), source_rect)
                painter.end()
                
                # Reset shape transforms
                if shapes_rotate:
                    for shape in visible_shapes:
                        shape.setTransform(QTransform())
                
                # Convert QImage to PIL Image
                ptr = qimg.bits()
                ptr.setsize(qimg.sizeInBytes())
                frame_img = Image.frombytes("RGBA", (frame_width, frame_height), bytes(ptr), "raw", "BGRA")
            else:
                frame_img = rotated

            # Calculate position in spritesheet
            if layout == "Horizontal":
                x = i * (frame_width + offset)
                y = 0
            elif layout == "Vertical":
                x = 0
                y = i * (frame_height + offset)
            else:  # Grid
                col = i % grid_cols
                row = i // grid_cols
                x = col * (frame_width + offset)
                y = row * (frame_height + offset)

            sheet.paste(frame_img, (x, y))

        # Restore visual guides
        for guide in guides_to_hide:
            if guide:
                guide.setVisible(True)
        
        # Restore current rotation
        self._apply_rotation(self.current_angle)

        sheet_path = output_dir / "knob_spritesheet.png"
        sheet.save(sheet_path)
        self.info_label.setText(f"Exported {frames_count} frames to {sheet_path}")

    # ------------------------------------------------------------------ Shape Tools

    def on_add_rect(self) -> None:
        """Add a rectangle shape to the knob canvas."""
        if self.rotation_center is None:
            self.info_label.setText("Load a knob first!")
            return
        
        cx, cy = self.rotation_center.x(), self.rotation_center.y()
        rect = ResizableRectItem(cx - 40, cy - 40, 80, 80)
        self._setup_shape(rect)
        self.knob_scene.addItem(rect)
        self.shapes.append(rect)
        rect.setSelected(True)

    def on_add_circle(self) -> None:
        """Add a circle shape to the knob canvas."""
        if self.rotation_center is None:
            self.info_label.setText("Load a knob first!")
            return
        
        cx, cy = self.rotation_center.x(), self.rotation_center.y()
        circle = ResizableEllipseItem(cx - 50, cy - 50, 100, 100)
        self._setup_shape(circle)
        self.knob_scene.addItem(circle)
        self.shapes.append(circle)
        circle.setSelected(True)

    def on_add_line(self) -> None:
        """Add a line shape to the knob canvas."""
        if self.rotation_center is None:
            self.info_label.setText("Load a knob first!")
            return
        
        cx, cy = self.rotation_center.x(), self.rotation_center.y()
        line = ResizableLineItem(cx - 30, cy, cx + 30, cy)
        self._setup_shape(line)
        self.knob_scene.addItem(line)
        self.shapes.append(line)
        line.setSelected(True)

    def _setup_shape(self, shape) -> None:
        """Configure a newly created shape with current style settings."""
        shape.setZValue(50)  # Above knob, below guides
        shape.setFlag(shape.GraphicsItemFlag.ItemIsSelectable, True)
        shape.setFlag(shape.GraphicsItemFlag.ItemIsMovable, True)
        
        # Apply current colors
        pen = QPen(self.shape_stroke_color, self.stroke_width_spin.value())
        shape.setPen(pen)
        
        if self.shape_fill_color.alpha() > 0:
            shape.setBrush(QBrush(self.shape_fill_color))
        else:
            shape.setBrush(QBrush(Qt.GlobalColor.transparent))
        
        # Apply neon glow if enabled
        self._apply_neon_to_shape(shape)

    def _apply_neon_to_shape(self, shape) -> None:
        """Apply or remove neon glow effect from a shape."""
        if self.neon_checkbox.isChecked():
            effect = QGraphicsDropShadowEffect()
            effect.setBlurRadius(self.neon_radius_spin.value())
            effect.setOffset(0, 0)
            glow_color = QColor(self.shape_stroke_color)
            glow_color.setAlpha(self.neon_intensity_spin.value())
            effect.setColor(glow_color)
            shape.setGraphicsEffect(effect)
        else:
            shape.setGraphicsEffect(None)

    def on_delete_shape(self) -> None:
        """Delete the currently selected shape."""
        selected = self.knob_scene.selectedItems()
        for item in selected:
            if item in self.shapes:
                self.shapes.remove(item)
                item.setVisible(False)
                item.setGraphicsEffect(None)

    def on_pick_stroke_color(self) -> None:
        """Open color picker for stroke color."""
        color = QColorDialog.getColor(
            self.shape_stroke_color, self, "Pick stroke color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self.shape_stroke_color = color
            self.stroke_color_btn.setStyleSheet(
                f"background-color: {color.name()}; border: 2px solid #555;"
            )
            self.on_shape_style_changed()

    def on_pick_fill_color(self) -> None:
        """Open color picker for fill color."""
        color = QColorDialog.getColor(
            self.shape_fill_color, self, "Pick fill color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self.shape_fill_color = color
            if color.alpha() > 0:
                self.fill_color_btn.setStyleSheet(
                    f"background-color: rgba({color.red()},{color.green()},{color.blue()},{color.alpha()}); border: 2px solid #555;"
                )
            else:
                self.fill_color_btn.setStyleSheet("background-color: transparent; border: 2px solid #555;")
            self.on_shape_style_changed()

    def on_shape_style_changed(self) -> None:
        """Update all shapes with current style settings."""
        for shape in self.shapes:
            if not shape.isVisible():
                continue
            
            # Update pen (stroke)
            pen = QPen(self.shape_stroke_color, self.stroke_width_spin.value())
            shape.setPen(pen)
            
            # Update brush (fill)
            if self.shape_fill_color.alpha() > 0:
                shape.setBrush(QBrush(self.shape_fill_color))
            else:
                shape.setBrush(QBrush(Qt.GlobalColor.transparent))
            
            # Update neon effect
            self._apply_neon_to_shape(shape)

    # ------------------------------------------------------------------ Helpers

    def _refresh_scene_rect(self) -> None:
        rect = self.knob_scene.itemsBoundingRect()
        margin = 100
        rect.adjust(-margin, -margin, margin, margin)
        self.knob_scene.setSceneRect(rect)
        self.knob_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

