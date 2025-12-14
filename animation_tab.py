"""
Animation Tab - Contains UI and logic for:
- Loading fader guide and cap images
- Setting start/end/center positions
- Previewing fader animation
- Exporting spritesheets
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPen, QColor
from PyQt6.QtWidgets import (
    QFormLayout,
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


class AnimView(QGraphicsView):
    """Custom QGraphicsView that reports click positions for snap points."""

    def __init__(self, scene: QGraphicsScene, owner: "AnimationTab") -> None:
        super().__init__(scene)
        self._owner = owner

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self._owner.on_anim_view_clicked(scene_pos.y())
        super().mousePressEvent(event)


class AnimationTab(QWidget):
    """Tab widget for fader animation and spritesheet generation."""

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self._owner = owner

        # Animation state
        self.guide_path: Path | None = None
        self.cap_path: Path | None = None
        self.guide_item: QGraphicsPixmapItem | None = None
        self.cap_item: QGraphicsPixmapItem | None = None
        self.start_edge_y: float | None = None
        self.end_edge_y: float | None = None
        self.center_edge_y: float | None = None
        self.start_line_item: QGraphicsLineItem | None = None
        self.end_line_item: QGraphicsLineItem | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

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

        controls_layout.addStretch(1)

        main_layout.addLayout(controls_layout, stretch=1)

    # ------------------------------------------------------------------ Actions

    def on_load_guide(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open guide image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.guide_path = Path(path)
            pixmap = QPixmap(str(self.guide_path))

            if self.guide_item is not None:
                self.anim_scene.removeItem(self.guide_item)

            self.guide_item = QGraphicsPixmapItem(pixmap)
            self.guide_item.setZValue(0)
            self.anim_scene.addItem(self.guide_item)

            self._refresh_scene_rect()

    def on_load_cap(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open fader cap image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.cap_path = Path(path)
            pixmap = QPixmap(str(self.cap_path))

            if self.cap_item is not None:
                self.anim_scene.removeItem(self.cap_item)

            self.cap_item = QGraphicsPixmapItem(pixmap)
            self.cap_item.setZValue(1)
            self.cap_item.setFlags(
                self.cap_item.flags()
                | QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable
            )
            self.anim_scene.addItem(self.cap_item)

            # Center cap on guide
            if self.guide_item is not None:
                gx = self.guide_item.boundingRect().center().x()
                cx = self.cap_item.boundingRect().center().x()
                self.cap_item.setX(gx - cx)

            self._refresh_scene_rect()

    def on_set_start_edge(self) -> None:
        if self.cap_item is None:
            return
        y = self.cap_item.y()
        self.start_edge_y = y
        self.start_label.setText(f"Start edge: {y:.1f}")
        self._update_edge_lines()

    def on_set_end_edge(self) -> None:
        if self.cap_item is None:
            return
        y = self.cap_item.y()
        self.end_edge_y = y
        self.end_label.setText(f"End edge: {y:.1f}")
        self._update_edge_lines()

    def on_anim_view_clicked(self, y: float) -> None:
        """Snap cap to clicked y position (acts as center snap)."""
        if self.cap_item is None:
            return
        cap_height = self.cap_item.boundingRect().height()
        self.cap_item.setY(y - cap_height / 2)
        self.center_edge_y = y
        self.center_label.setText(f"Center: {y:.1f}")

    def on_anim_slider_changed(self, value: int) -> None:
        if (
            self.cap_item is None
            or self.start_edge_y is None
            or self.end_edge_y is None
        ):
            return
        t = value / 100.0
        y = self.start_edge_y + t * (self.end_edge_y - self.start_edge_y)
        self.cap_item.setY(y)

    def on_export_spritesheet(self) -> None:
        if (
            self.guide_path is None
            or self.cap_path is None
            or self.start_edge_y is None
            or self.end_edge_y is None
        ):
            return

        output_dir = Path("output").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        guide_img = Image.open(self.guide_path).convert("RGBA")
        cap_img = Image.open(self.cap_path).convert("RGBA")

        frames = self.frames_spin.value()
        layout = self.layout_combo.currentText()
        offset = self.offset_spin.value()

        cap_x = int(self.cap_item.x()) if self.cap_item else 0

        frame_width = guide_img.width
        frame_height = guide_img.height

        if layout == "Horizontal":
            sheet_width = frame_width * frames + offset * (frames - 1)
            sheet_height = frame_height
        else:
            sheet_width = frame_width
            sheet_height = frame_height * frames + offset * (frames - 1)

        sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))

        for i in range(frames):
            t = i / (frames - 1) if frames > 1 else 0
            cap_y = int(self.start_edge_y + t * (self.end_edge_y - self.start_edge_y))

            frame = guide_img.copy()
            frame.paste(cap_img, (cap_x, cap_y), cap_img)

            if layout == "Horizontal":
                x = i * (frame_width + offset)
                y = 0
            else:
                x = 0
                y = i * (frame_height + offset)

            sheet.paste(frame, (x, y))

        sheet_path = output_dir / "fader_spritesheet.png"
        sheet.save(sheet_path)

    # ------------------------------------------------------------------ Helpers

    def _refresh_scene_rect(self) -> None:
        rect = self.anim_scene.itemsBoundingRect()
        margin = 50
        rect.adjust(-margin, -margin, margin, margin)
        self.anim_scene.setSceneRect(rect)
        self.anim_view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _update_edge_lines(self) -> None:
        pen = QPen(QColor("#ff0000"))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)

        rect = self.anim_scene.sceneRect()

        if self.start_line_item is not None:
            self.anim_scene.removeItem(self.start_line_item)
        if self.start_edge_y is not None:
            self.start_line_item = QGraphicsLineItem(
                rect.left(), self.start_edge_y, rect.right(), self.start_edge_y
            )
            self.start_line_item.setPen(pen)
            self.anim_scene.addItem(self.start_line_item)

        pen_end = QPen(QColor("#00ff00"))
        pen_end.setWidth(2)
        pen_end.setStyle(Qt.PenStyle.DashLine)

        if self.end_line_item is not None:
            self.anim_scene.removeItem(self.end_line_item)
        if self.end_edge_y is not None:
            self.end_line_item = QGraphicsLineItem(
                rect.left(), self.end_edge_y, rect.right(), self.end_edge_y
            )
            self.end_line_item.setPen(pen_end)
            self.anim_scene.addItem(self.end_line_item)

