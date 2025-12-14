"""
Knob Animation Tab - Contains UI and logic for:
- Loading knob images
- Setting rotation center point
- Defining start/end rotation angles
- Previewing knob rotation
- Exporting rotation spritesheets
"""

import math
from pathlib import Path
from typing import TYPE_CHECKING

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
)

from PIL import Image

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
    """Custom QGraphicsView for knob animation - click to set rotation center."""

    def __init__(self, scene: QGraphicsScene, owner: "KnobAnimationTab") -> None:
        super().__init__(scene)
        self._owner = owner

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self._owner.set_rotation_center(scene_pos)
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

        # Rotation info labels
        self.center_label = QLabel("Center: – (click on canvas to set)")
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

    def set_rotation_center(self, pos: QPointF) -> None:
        self.rotation_center = pos
        self.center_label.setText(f"Center: ({pos.x():.0f}, {pos.y():.0f})")
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
        
        # Update end angle via wheel (will trigger update)
        self.end_angle = new_end
        self.end_wheel.setAngle(new_end, emit=False)
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
        
        frames = self.frames_spin.value()
        layout = self.layout_combo.currentText()
        offset = self.offset_spin.value()
        grid_cols = self.grid_cols_spin.value()

        frame_width = knob_img.width
        frame_height = knob_img.height

        # Calculate spritesheet dimensions
        if layout == "Horizontal":
            sheet_width = frame_width * frames + offset * (frames - 1)
            sheet_height = frame_height
        elif layout == "Vertical":
            sheet_width = frame_width
            sheet_height = frame_height * frames + offset * (frames - 1)
        else:  # Grid
            rows = math.ceil(frames / grid_cols)
            sheet_width = frame_width * grid_cols + offset * (grid_cols - 1)
            sheet_height = frame_height * rows + offset * (rows - 1)

        sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))

        # Rotation center in image coordinates
        cx = self.rotation_center.x()
        cy = self.rotation_center.y()

        for i in range(frames):
            t = i / (frames - 1) if frames > 1 else 0
            target_angle = self.start_angle + t * (self.end_angle - self.start_angle)
            
            # Calculate rotation: target_angle - pointer_angle
            # This makes the pointer (originally at pointer_angle) point to target_angle
            rotation = target_angle - self.pointer_angle
            
            # Rotate image around center
            # PIL rotates counter-clockwise, so negate for clockwise rotation
            rotated = knob_img.rotate(
                -rotation,
                resample=Image.Resampling.BICUBIC,
                center=(cx, cy),
                expand=False
            )

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

            sheet.paste(rotated, (x, y))

        sheet_path = output_dir / "knob_spritesheet.png"
        sheet.save(sheet_path)
        self.info_label.setText(f"Exported {frames} frames to {sheet_path}")

    # ------------------------------------------------------------------ Helpers

    def _refresh_scene_rect(self) -> None:
        rect = self.knob_scene.itemsBoundingRect()
        margin = 100
        rect.adjust(-margin, -margin, margin, margin)
        self.knob_scene.setSceneRect(rect)
        self.knob_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

