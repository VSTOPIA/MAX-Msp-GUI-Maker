"""
MAX-Msp GUI Maker - Main Application Entry Point

This is the main window that hosts all tabs:
- Background removal (background_tab.py)
- Fader animation (animation_tab.py)
- Shape editor (shape_editor_tab.py)
"""

import sys
import math
from pathlib import Path

from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt6.QtGui import (
    QPixmap,
    QImage,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QLinearGradient,
    QKeySequence,
    QUndoStack,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
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
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QListWidgetItem,
    QMessageBox,
    QAbstractItemView,
    QColorDialog,
)

# Import tab modules
from background_tab import BackgroundTab
from animation_tab import AnimationTab
from knob_animation_tab import KnobAnimationTab
from shape_editor_tab import (
    ShapeView,
    ResizableRectItem,
    ResizableEllipseItem,
    ResizableLineItem,
    ShadowDirectionWidget,
    DragSpinBox,
    ColorStyleDialog,
    LayerListWidget,
)


class MainWindow(QMainWindow):
    """Main application window with tabbed interface."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MAX-Msp GUI Maker – Image Prep")
        self.resize(1200, 700)

        # Shape editor state
        self.shape_scene: QGraphicsScene | None = None
        self.shape_view: ShapeView | None = None
        self.shape_base_path: Path | None = None
        self.shape_base_item: QGraphicsPixmapItem | None = None
        self.shape_base_image: QImage | None = None
        self.current_shape_item = None
        self.shape_stroke_color = QColor("#00e5ff")
        self.shape_fill_color = QColor("#00e5ff")
        # Dedicated neon glow color (independent of stroke/fill)
        self.neon_glow_color = QColor("#00ffff")
        # Gradient styles
        self.stroke_use_gradient = False
        self.stroke_grad_color1 = QColor("#00e5ff")
        self.stroke_grad_color2 = QColor("#ffffff")
        self.stroke_grad_pos = 50
        self.stroke_grad_angle = 0.0
        self.stroke_grad_width = 10
        self.fill_use_gradient = False
        self.fill_grad_color1 = QColor("#00e5ff")
        self.fill_grad_color2 = QColor("#ffffff")
        self.fill_grad_pos = 50
        self.fill_grad_angle = 0.0
        self.fill_grad_width = 10
        # Opacity values (0-100%)
        self.stroke_opacity = 100
        self.fill_opacity = 100
        self.color_pick_mode: str | None = None
        self.crop_rect_item: ResizableRectItem | None = None
        self.layers_list: LayerListWidget | None = None
        self.shadow_dir_widget: ShadowDirectionWidget | None = None

        # Undo/redo stack for all editing actions
        self.undo_stack = QUndoStack(self)

        self._build_ui()
        self._setup_undo_actions()

    def _setup_undo_actions(self) -> None:
        """Create global Undo / Redo actions."""
        undo_action = self.undo_stack.createUndoAction(self, "Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(redo_action)

    def _build_ui(self) -> None:
        tabs = QTabWidget(self)
        self.setCentralWidget(tabs)

        # Tab 1: background removal / component split
        self.bg_tab = BackgroundTab(owner=self)
        tabs.addTab(self.bg_tab, "Background removal")

        # Tab 2: fader animation setup
        self.anim_tab = AnimationTab(owner=self)
        tabs.addTab(self.anim_tab, "Fader animation")

        # Tab 3: knob animation setup
        self.knob_tab = KnobAnimationTab(owner=self)
        tabs.addTab(self.knob_tab, "Knob animation")

        # Tab 4: shape / overlay editor
        shape_tab = QWidget()
        self._build_shape_editor_tab(shape_tab)
        tabs.addTab(shape_tab, "Shape editor")

    # ------------------------------------------------------------------ Shape Editor Tab

    def _build_shape_editor_tab(self, parent: QWidget) -> None:
        main_layout = QHBoxLayout(parent)

        # Graphics scene/view for shape editing
        self.shape_scene = QGraphicsScene(self)
        self.shape_view = ShapeView(self.shape_scene, owner=self)
        self.shape_view.setStyleSheet("background-color: #181818;")
        self.shape_scene.selectionChanged.connect(self.on_shape_selection_changed)

        main_layout.addWidget(self.shape_view, stretch=3)

        # Controls on the right
        controls_layout = QVBoxLayout()

        load_base_btn = QPushButton("Load base image…")
        load_base_btn.clicked.connect(self.on_shape_load_base)
        controls_layout.addWidget(load_base_btn)

        # Shape creation buttons
        shapes_layout = QHBoxLayout()
        rect_btn = QPushButton("Rect")
        rect_btn.clicked.connect(self.on_shape_add_rect)
        shapes_layout.addWidget(rect_btn)

        circle_btn = QPushButton("Circle")
        circle_btn.clicked.connect(self.on_shape_add_circle)
        shapes_layout.addWidget(circle_btn)

        line_btn = QPushButton("Line")
        line_btn.clicked.connect(self.on_shape_add_line)
        shapes_layout.addWidget(line_btn)

        dot_btn = QPushButton("Dot")
        dot_btn.clicked.connect(self.on_shape_add_dot)
        shapes_layout.addWidget(dot_btn)

        controls_layout.addLayout(shapes_layout)

        # Shape properties
        props_group = QGroupBox("Shape properties")
        props_layout = QFormLayout(props_group)

        self.shape_filled_check = QCheckBox("Filled")
        self.shape_filled_check.setChecked(True)
        self.shape_filled_check.stateChanged.connect(self.on_shape_style_changed)
        props_layout.addRow(self.shape_filled_check)

        self.shape_width_spin = DragSpinBox()
        self.shape_width_spin.setRange(1, 9999)
        self.shape_width_spin.setValue(100)
        self.shape_width_spin.setSuffix(" px")
        self.shape_width_spin.valueChanged.connect(self.on_shape_size_changed)
        props_layout.addRow("Width", self.shape_width_spin)

        self.shape_height_spin = DragSpinBox()
        self.shape_height_spin.setRange(1, 9999)
        self.shape_height_spin.setValue(100)
        self.shape_height_spin.setSuffix(" px")
        self.shape_height_spin.valueChanged.connect(self.on_shape_size_changed)
        props_layout.addRow("Height", self.shape_height_spin)

        # Stroke width control (affects how visible the glow is on the stroke)
        self.stroke_width_spin = DragSpinBox()
        self.stroke_width_spin.setRange(1, 100)
        self.stroke_width_spin.setValue(2)
        self.stroke_width_spin.setSuffix(" px")
        self.stroke_width_spin.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Stroke width", self.stroke_width_spin)

        # Neon / glow controls
        self.shape_neon_check = QCheckBox("Neon glow")
        self.shape_neon_check.stateChanged.connect(self.on_shape_style_changed)
        props_layout.addRow(self.shape_neon_check)

        self.neon_radius_spin = DragSpinBox()
        self.neon_radius_spin.setRange(0, 999)
        self.neon_radius_spin.setValue(25)
        self.neon_radius_spin.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow radius (px)", self.neon_radius_spin)

        self.neon_offset_x_spin = QSpinBox()
        self.neon_offset_x_spin.setRange(-200, 200)
        self.neon_offset_x_spin.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow offset X", self.neon_offset_x_spin)

        self.neon_offset_y_spin = QSpinBox()
        self.neon_offset_y_spin.setRange(-200, 200)
        self.neon_offset_y_spin.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow offset Y", self.neon_offset_y_spin)

        self.neon_intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.neon_intensity_slider.setRange(0, 200)
        self.neon_intensity_slider.setValue(100)
        self.neon_intensity_slider.valueChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow intensity", self.neon_intensity_slider)

        self.shadow_dir_widget = ShadowDirectionWidget(owner=self)
        props_layout.addRow("Glow direction", self.shadow_dir_widget)

        # Glow color source: use stroke, fill, or custom color
        from PyQt6.QtWidgets import QComboBox
        self.glow_color_source = QComboBox()
        self.glow_color_source.addItems(["Stroke color", "Fill color", "Custom"])
        self.glow_color_source.setCurrentIndex(0)  # Default to stroke
        self.glow_color_source.currentIndexChanged.connect(self.on_shape_style_changed)
        props_layout.addRow("Glow color from", self.glow_color_source)

        # Custom glow color picker (used when "Custom" is selected)
        self.neon_color_btn = QPushButton("Custom glow color")
        self.neon_color_btn.clicked.connect(self.on_pick_neon_color)
        props_layout.addRow(self.neon_color_btn)

        # Color controls
        self.stroke_color_btn = QPushButton("Stroke color")
        self.stroke_color_btn.clicked.connect(self.on_pick_stroke_color)
        props_layout.addRow(self.stroke_color_btn)

        # Stroke opacity slider
        self.stroke_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.stroke_opacity_slider.setRange(0, 100)
        self.stroke_opacity_slider.setValue(100)
        self.stroke_opacity_slider.valueChanged.connect(self.on_stroke_opacity_changed)
        props_layout.addRow("Stroke opacity %", self.stroke_opacity_slider)

        self.fill_color_btn = QPushButton("Fill color")
        self.fill_color_btn.clicked.connect(self.on_pick_fill_color)
        props_layout.addRow(self.fill_color_btn)

        # Fill opacity slider
        self.fill_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.fill_opacity_slider.setRange(0, 100)
        self.fill_opacity_slider.setValue(100)
        self.fill_opacity_slider.valueChanged.connect(self.on_fill_opacity_changed)
        props_layout.addRow("Fill opacity %", self.fill_opacity_slider)

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

        self._update_color_buttons()

    # ------------------------------------------------------------------ Shape Editor Actions

    def on_shape_load_base(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open base image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.shape_base_path = Path(path)
            pixmap = QPixmap(str(self.shape_base_path))

            if self.shape_base_item is not None:
                self.shape_scene.removeItem(self.shape_base_item)

            self.shape_base_item = QGraphicsPixmapItem(pixmap)
            self.shape_base_item.setZValue(-1000)
            self.shape_scene.addItem(self.shape_base_item)
            self.shape_base_image = pixmap.toImage()

            # Add base image to layers
            if self.layers_list is not None:
                list_item = QListWidgetItem("Base Image")
                list_item.setData(Qt.ItemDataRole.UserRole, self.shape_base_item)
                self.layers_list.insertItem(0, list_item)

    def _create_shape_item(self, kind: str):
        if self.shape_scene is None:
            return None

        x = 50
        y = 50
        w = self.shape_width_spin.value()
        h = self.shape_height_spin.value()

        pen = QPen(self.shape_stroke_color)
        pen.setWidth(self.stroke_width_spin.value())
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

        # Optional neon glow
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
        if isinstance(item, QGraphicsLineItem):
            pen = item.pen()
            self.shape_height_spin.setValue(pen.width())
        else:
            self.shape_height_spin.setValue(int(rect.height()))
        self.shape_width_spin.blockSignals(False)
        self.shape_height_spin.blockSignals(False)

        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            brush = item.brush()
            if brush.style() != Qt.BrushStyle.NoBrush:
                self.shape_fill_color = brush.color()
        pen = item.pen()
        self.shape_stroke_color = pen.color()
        # Reflect current stroke width
        self.stroke_width_spin.blockSignals(True)
        self.stroke_width_spin.setValue(pen.width())
        self.stroke_width_spin.blockSignals(False)
        self._update_color_buttons()

        # Reflect selection into layers list
        if self.layers_list is not None:
            for i in range(self.layers_list.count()):
                lw_item = self.layers_list.item(i)
                if lw_item.data(Qt.ItemDataRole.UserRole) is item:
                    self.layers_list.blockSignals(True)
                    self.layers_list.setCurrentRow(i)
                    self.layers_list.blockSignals(False)
                    break

    def on_shape_size_changed(self) -> None:
        if self.current_shape_item is None:
            return
        item = self.current_shape_item
        w = self.shape_width_spin.value()
        h = self.shape_height_spin.value()

        if isinstance(item, QGraphicsLineItem):
            line = item.line()
            # For lines, height controls stroke width
            pen = item.pen()
            pen.setWidth(h)
            item.setPen(pen)
            # Width controls line length
            new_line = QLineF(line.p1(), QPointF(line.p1().x() + w, line.p1().y()))
            item.setLine(new_line)
        elif hasattr(item, "setRect"):
            old_rect = item.rect()
            item.setRect(QRectF(old_rect.x(), old_rect.y(), w, h))

    def on_shape_style_changed(self) -> None:
        if self.current_shape_item is None:
            return
        item = self.current_shape_item

        # Apply stroke opacity to color
        stroke_alpha = int(self.stroke_opacity * 255 / 100)
        stroke_color = QColor(self.shape_stroke_color)
        stroke_color.setAlpha(stroke_alpha)

        # Build pen with gradient or solid color
        stroke_width = self.stroke_width_spin.value()
        if self.stroke_use_gradient:
            pen_brush = self._build_gradient_brush(
                item,
                self.stroke_grad_color1,
                self.stroke_grad_color2,
                self.stroke_grad_pos,
                self.stroke_grad_angle,
                self.stroke_grad_width,
                opacity=self.stroke_opacity,
            )
            pen = QPen(pen_brush, stroke_width)
        else:
            pen = QPen(stroke_color)
            pen.setWidth(stroke_width)
        item.setPen(pen)

        # Apply fill opacity to color
        fill_alpha = int(self.fill_opacity * 255 / 100)
        fill_color = QColor(self.shape_fill_color)
        fill_color.setAlpha(fill_alpha)

        # Build brush with gradient or solid color
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            if self.shape_filled_check.isChecked():
                if self.fill_use_gradient:
                    brush = self._build_gradient_brush(
                        item,
                        self.fill_grad_color1,
                        self.fill_grad_color2,
                        self.fill_grad_pos,
                        self.fill_grad_angle,
                        self.fill_grad_width,
                        opacity=self.fill_opacity,
                    )
                else:
                    brush = QBrush(fill_color)
            else:
                brush = QBrush(Qt.GlobalColor.transparent)
            item.setBrush(brush)

        # Update neon effect
        if self.shape_neon_check.isChecked():
            self._apply_neon_effect(item)
        else:
            item.setGraphicsEffect(None)

    def on_stroke_opacity_changed(self, value: int) -> None:
        self.stroke_opacity = value
        self.on_shape_style_changed()

    def on_fill_opacity_changed(self, value: int) -> None:
        self.fill_opacity = value
        self.on_shape_style_changed()

    def _build_gradient_brush(
        self,
        item,
        color1: QColor,
        color2: QColor,
        position: int,
        angle: float,
        width: int,
        opacity: int = 100,
    ) -> QBrush:
        rect = item.boundingRect()
        cx = rect.center().x()
        cy = rect.center().y()
        radius = max(rect.width(), rect.height()) / 2

        rad = math.radians(angle)
        dx = radius * math.cos(rad)
        dy = radius * math.sin(rad)

        p1 = QPointF(cx - dx, cy - dy)
        p2 = QPointF(cx + dx, cy + dy)

        # Apply opacity to gradient colors
        alpha = int(opacity * 255 / 100)
        c1 = QColor(color1)
        c1.setAlpha(alpha)
        c2 = QColor(color2)
        c2.setAlpha(alpha)

        grad = QLinearGradient(p1, p2)
        t = max(0.0, min(1.0, position / 100.0))
        w = max(0.01, width / 100.0)

        grad.setColorAt(0.0, c1)
        grad.setColorAt(max(0.0, t - w / 2), c1)
        grad.setColorAt(min(1.0, t + w / 2), c2)
        grad.setColorAt(1.0, c2)

        return QBrush(grad)

    def _apply_neon_effect(self, item) -> None:
        effect = QGraphicsDropShadowEffect()
        alpha = int(self.neon_intensity_slider.value() / 100 * 255)
        alpha = max(0, min(255, alpha))

        # Determine glow color based on source selection
        source_index = self.glow_color_source.currentIndex()
        if source_index == 0:  # Stroke color
            base_color = self.shape_stroke_color
        elif source_index == 1:  # Fill color
            base_color = self.shape_fill_color
        else:  # Custom color
            base_color = self.neon_glow_color

        glow_color = QColor(base_color)
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
        self.neon_color_btn.setStyleSheet(style_for(self.neon_glow_color))

    def on_pick_neon_color(self) -> None:
        """Open color dialog for neon glow color."""
        color = QColorDialog.getColor(
            self.neon_glow_color,
            self,
            "Select Neon Glow Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self.neon_glow_color = color
            self._update_color_buttons()
            if self.current_shape_item is not None and self.shape_neon_check.isChecked():
                self._apply_neon_effect(self.current_shape_item)

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
        if self.color_pick_mode == "stroke":
            self.color_pick_mode = "fill"
            self.pick_from_base_btn.setText("Pick from base: FILL")
        elif self.color_pick_mode == "fill":
            self.color_pick_mode = None
            self.pick_from_base_btn.setText("Pick from base (next click)")
        else:
            self.color_pick_mode = "stroke"
            self.pick_from_base_btn.setText("Pick from base: STROKE")

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

    def on_shadow_direction_changed(self, mode: str) -> None:
        if self.shadow_dir_widget is not None:
            self.shadow_dir_widget.set_mode(mode)

        direction_offsets = {
            "all": (0, 0),
            "left": (-10, 0),
            "right": (10, 0),
            "top": (0, -10),
            "bottom": (0, 10),
        }
        ox, oy = direction_offsets.get(mode, (0, 0))
        self.neon_offset_x_spin.blockSignals(True)
        self.neon_offset_y_spin.blockSignals(True)
        self.neon_offset_x_spin.setValue(ox)
        self.neon_offset_y_spin.setValue(oy)
        self.neon_offset_x_spin.blockSignals(False)
        self.neon_offset_y_spin.blockSignals(False)
        self.on_shape_style_changed()

    # ------------------------------------------------------------------ Layers

    def on_layer_selection_changed(self) -> None:
        if self.layers_list is None or self.shape_scene is None:
            return
        item = self.layers_list.currentItem()
        if item is None:
            return
        g_item = item.data(Qt.ItemDataRole.UserRole)
        if g_item is None:
            return
        self.shape_scene.clearSelection()
        g_item.setSelected(True)
        self.current_shape_item = g_item

    def on_layer_move_down(self) -> None:
        if self.layers_list is None:
            return
        row = self.layers_list.currentRow()
        if row < 0 or row >= self.layers_list.count() - 1:
            return
        item = self.layers_list.takeItem(row)
        self.layers_list.insertItem(row + 1, item)
        self.layers_list.setCurrentRow(row + 1)
        self._recompute_layer_z_values()

    def on_layer_move_up(self) -> None:
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
        self._recompute_layer_z_values()

    def _recompute_layer_z_values(self) -> None:
        if self.layers_list is None:
            return
        count = self.layers_list.count()
        for i in range(count):
            lw_item = self.layers_list.item(i)
            g_item = lw_item.data(Qt.ItemDataRole.UserRole)
            if g_item is not None:
                g_item.setZValue(count - i)

    def delete_selected_shapes(self) -> None:
        if self.shape_scene is None:
            return

        selected = self.shape_scene.selectedItems()

        if not selected and self.layers_list is not None:
            lw_item = self.layers_list.currentItem()
            if lw_item is not None:
                g_item = lw_item.data(Qt.ItemDataRole.UserRole)
                if g_item is not None:
                    selected = [g_item]

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

    # ------------------------------------------------------------------ Export & Crop

    def on_shape_export(self) -> None:
        if self.shape_scene is None:
            return

        rect = self._visible_items_bounding_rect()
        if rect.isNull():
            self.shape_info_label.setText("Nothing to export.")
            return

        image = self._render_overlay_image(rect)

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

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        output_dir = Path("output").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / "shape_overlay.png"
        image.save(str(out_path))
        self.shape_info_label.setText(f"Exported to {out_path}")

    def _visible_items_bounding_rect(self) -> QRectF:
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

    def _render_overlay_image(self, rect: QRectF) -> QImage:
        width = int(rect.width())
        height = int(rect.height())
        if width <= 0 or height <= 0:
            width = height = 512

        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
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
        pen = QPen(QColor("#ffff00"))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.crop_rect_item.setPen(pen)
        self.crop_rect_item.setBrush(QBrush(Qt.GlobalColor.transparent))
        self.crop_rect_item.setZValue(10000)
        self.crop_rect_item.setFlags(
            self.crop_rect_item.flags()
            | QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.shape_scene.addItem(self.crop_rect_item)

    def on_apply_crop(self) -> None:
        if (
            self.shape_scene is None
            or self.shape_base_item is None
            or self.crop_rect_item is None
        ):
            return

        crop_rect = self.crop_rect_item.sceneBoundingRect()

        base_rect = self.shape_base_item.sceneBoundingRect()
        intersected = crop_rect.intersected(base_rect)
        if intersected.isEmpty():
            self.shape_info_label.setText("Crop rect doesn't overlap base image.")
            return

        local_rect = self.shape_base_item.mapFromScene(intersected).boundingRect()
        x = int(local_rect.x())
        y = int(local_rect.y())
        w = int(local_rect.width())
        h = int(local_rect.height())

        if self.shape_base_image is None:
            return

        cropped = self.shape_base_image.copy(x, y, w, h)

        dialog = QDialog(self)
        dialog.setWindowTitle("Crop preview")
        vbox = QVBoxLayout(dialog)

        pix = QPixmap.fromImage(cropped)
        max_dim = 320
        if pix.width() > max_dim or pix.height() > max_dim:
            pix = pix.scaled(
                max_dim,
                max_dim,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        preview_label = QLabel()
        preview_label.setPixmap(pix)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(preview_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        vbox.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_pixmap = QPixmap.fromImage(cropped)
        self.shape_base_item.setPixmap(new_pixmap)
        self.shape_base_item.setPos(crop_rect.topLeft())
        self.shape_base_image = cropped

        self.shape_scene.removeItem(self.crop_rect_item)
        self.crop_rect_item = None
        self.shape_info_label.setText(f"Cropped to {w}×{h}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
