"""
MAX-Msp GUI Maker - Main Application Entry Point

This is the main window that hosts all tabs:
- Background removal (background_tab.py)
- Fader animation (animation_tab.py)
- Shape editor (shape_editor_tab.py)
"""

import sys
import math
import json
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
    QAction,
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
    QMenuBar,
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
        
        # Current project file path
        self.project_path: Path | None = None

        self._build_ui()
        self._setup_menu_bar()
        self._setup_undo_actions()

    def _setup_menu_bar(self) -> None:
        """Create the application menu bar."""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        
        new_action = QAction("&New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.on_new_project)
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.on_open_project)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("&Save Project", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.on_save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save Project &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self.on_save_project_as)
        file_menu.addAction(save_as_action)

    def _setup_undo_actions(self) -> None:
        """Create global Undo / Redo actions."""
        undo_action = self.undo_stack.createUndoAction(self, "Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(redo_action)

    # ------------------------------------------------------------------ Project Save/Load

    def on_new_project(self) -> None:
        """Create a new empty project."""
        reply = QMessageBox.question(
            self,
            "New Project",
            "Create a new project? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.project_path = None
            # Reset knob tab state
            self.knob_tab.knob_path = None
            self.knob_tab.knob_pixmap = None
            if self.knob_tab.knob_item:
                self.knob_tab.knob_scene.removeItem(self.knob_tab.knob_item)
                self.knob_tab.knob_item = None
            self.knob_tab.rotation_center = None
            self.knob_tab.shapes.clear()
            self.knob_tab.knob_scene.clear()
            self.knob_tab.center_label.setText("Center: –")
            self.knob_tab.pointer_wheel.setAngle(-135, emit=False)
            self.knob_tab.start_wheel.setAngle(-135, emit=False)
            self.knob_tab.end_wheel.setAngle(135, emit=False)
            self.knob_tab.pointer_angle = -135
            self.knob_tab.start_angle = -135
            self.knob_tab.end_angle = 135
            self.knob_tab.preview_slider.setValue(0)
            self.setWindowTitle("MAX-Msp GUI Maker – New Project")

    def on_open_project(self) -> None:
        """Open a project file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "GUI Maker Project (*.guiproj);;All Files (*)"
        )
        if path:
            self._load_project(Path(path))

    def on_save_project(self) -> None:
        """Save the current project."""
        if self.project_path is None:
            self.on_save_project_as()
        else:
            self._save_project(self.project_path)

    def on_save_project_as(self) -> None:
        """Save the project to a new file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "", "GUI Maker Project (*.guiproj);;All Files (*)"
        )
        if path:
            if not path.endswith(".guiproj"):
                path += ".guiproj"
            self._save_project(Path(path))

    def _save_project(self, path: Path) -> None:
        """Save project state to a JSON file."""
        project = {
            "version": 1,
            "knob_animation": self._serialize_knob_tab(),
        }
        
        try:
            with open(path, "w") as f:
                json.dump(project, f, indent=2)
            self.project_path = path
            self.setWindowTitle(f"MAX-Msp GUI Maker – {path.name}")
            QMessageBox.information(self, "Saved", f"Project saved to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save project: {e}")

    def _load_project(self, path: Path) -> None:
        """Load project state from a JSON file."""
        try:
            with open(path, "r") as f:
                project = json.load(f)
            
            version = project.get("version", 1)
            
            # Load knob animation tab state
            if "knob_animation" in project:
                self._deserialize_knob_tab(project["knob_animation"])
            
            self.project_path = path
            self.setWindowTitle(f"MAX-Msp GUI Maker – {path.name}")
            QMessageBox.information(self, "Loaded", f"Project loaded from {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load project: {e}")

    def _serialize_knob_tab(self) -> dict:
        """Serialize knob animation tab state to a dict."""
        tab = self.knob_tab
        data = {
            "knob_path": str(tab.knob_path) if tab.knob_path else None,
            "rotation_center": {
                "x": tab.rotation_center.x() if tab.rotation_center else 0,
                "y": tab.rotation_center.y() if tab.rotation_center else 0,
            } if tab.rotation_center else None,
            "pointer_angle": tab.pointer_angle,
            "start_angle": tab.start_angle,
            "end_angle": tab.end_angle,
            "guide_radius": tab.guide_radius_spin.value(),
            "export": {
                "frames": tab.frames_spin.value(),
                "layout": tab.layout_combo.currentText(),
                "grid_cols": tab.grid_cols_spin.value(),
                "offset": tab.offset_spin.value(),
            },
            "shapes": self._serialize_shapes(tab.shapes),
            "shape_settings": {
                "stroke_color": tab.shape_stroke_color.name(),
                "fill_color": tab.shape_fill_color.name() if tab.shape_fill_color.alpha() > 0 else None,
                "stroke_width": tab.stroke_width_spin.value(),
                "neon_enabled": tab.neon_checkbox.isChecked(),
                "neon_radius": tab.neon_radius_spin.value(),
                "neon_intensity": tab.neon_intensity_spin.value(),
                "shapes_rotate": tab.shapes_rotate_checkbox.isChecked(),
            },
        }
        return data

    def _deserialize_knob_tab(self, data: dict) -> None:
        """Restore knob animation tab state from a dict."""
        tab = self.knob_tab
        
        # Clear existing state
        tab.knob_scene.clear()
        tab.shapes.clear()
        tab.knob_item = None
        tab.center_marker = None
        tab.rotation_circle = None
        tab.start_line = None
        tab.end_line = None
        tab.current_line = None
        
        # Load knob image
        knob_path = data.get("knob_path")
        if knob_path and Path(knob_path).exists():
            tab.knob_path = Path(knob_path)
            tab.knob_pixmap = QPixmap(str(tab.knob_path))
            tab.knob_item = QGraphicsPixmapItem(tab.knob_pixmap)
            tab.knob_item.setZValue(0)
            tab.knob_scene.addItem(tab.knob_item)
        
        # Load rotation center
        center_data = data.get("rotation_center")
        if center_data:
            tab.rotation_center = QPointF(center_data["x"], center_data["y"])
            tab.center_label.setText(f"Center: ({center_data['x']:.0f}, {center_data['y']:.0f})")
        else:
            tab.rotation_center = None
            tab.center_label.setText("Center: –")
        
        # Load angles
        tab.pointer_angle = data.get("pointer_angle", -135)
        tab.start_angle = data.get("start_angle", -135)
        tab.end_angle = data.get("end_angle", 135)
        tab.pointer_wheel.setAngle(tab.pointer_angle, emit=False)
        tab.start_wheel.setAngle(tab.start_angle, emit=False)
        tab.end_wheel.setAngle(tab.end_angle, emit=False)
        
        # Load guide radius
        tab.guide_radius_spin.setValue(data.get("guide_radius", 80))
        
        # Load export settings
        export = data.get("export", {})
        tab.frames_spin.setValue(export.get("frames", 64))
        layout_text = export.get("layout", "Horizontal")
        idx = tab.layout_combo.findText(layout_text)
        if idx >= 0:
            tab.layout_combo.setCurrentIndex(idx)
        tab.grid_cols_spin.setValue(export.get("grid_cols", 8))
        tab.offset_spin.setValue(export.get("offset", 0))
        
        # Load shape settings
        shape_settings = data.get("shape_settings", {})
        stroke_color = shape_settings.get("stroke_color", "#00ffff")
        tab.shape_stroke_color = QColor(stroke_color)
        tab.stroke_color_btn.setStyleSheet(f"background-color: {stroke_color}; border: 2px solid #555;")
        
        fill_color = shape_settings.get("fill_color")
        if fill_color:
            tab.shape_fill_color = QColor(fill_color)
            tab.fill_color_btn.setStyleSheet(f"background-color: {fill_color}; border: 2px solid #555;")
        else:
            tab.shape_fill_color = QColor(0, 0, 0, 0)
            tab.fill_color_btn.setStyleSheet("background-color: transparent; border: 2px solid #555;")
        
        tab.stroke_width_spin.setValue(shape_settings.get("stroke_width", 3))
        tab.neon_checkbox.setChecked(shape_settings.get("neon_enabled", True))
        tab.neon_radius_spin.setValue(shape_settings.get("neon_radius", 15))
        tab.neon_intensity_spin.setValue(shape_settings.get("neon_intensity", 200))
        tab.shapes_rotate_checkbox.setChecked(shape_settings.get("shapes_rotate", True))
        
        # Load shapes
        shapes_data = data.get("shapes", [])
        self._deserialize_shapes(tab, shapes_data)
        
        # Refresh scene
        tab._refresh_scene_rect()
        tab.update_visual_guides()
        tab.preview_slider.setValue(0)

    def _serialize_shapes(self, shapes: list) -> list:
        """Serialize shape items to a list of dicts."""
        result = []
        for shape in shapes:
            if not shape.isVisible():
                continue
            
            shape_data = {
                "pen_color": shape.pen().color().name(),
                "pen_width": shape.pen().width(),
            }
            
            if isinstance(shape, ResizableRectItem):
                rect = shape.rect()
                shape_data["type"] = "rect"
                shape_data["x"] = rect.x()
                shape_data["y"] = rect.y()
                shape_data["width"] = rect.width()
                shape_data["height"] = rect.height()
                brush = shape.brush()
                if brush.style() != Qt.BrushStyle.NoBrush:
                    shape_data["fill_color"] = brush.color().name()
            elif isinstance(shape, ResizableEllipseItem):
                rect = shape.rect()
                shape_data["type"] = "ellipse"
                shape_data["x"] = rect.x()
                shape_data["y"] = rect.y()
                shape_data["width"] = rect.width()
                shape_data["height"] = rect.height()
                brush = shape.brush()
                if brush.style() != Qt.BrushStyle.NoBrush:
                    shape_data["fill_color"] = brush.color().name()
            elif isinstance(shape, ResizableLineItem):
                line = shape.line()
                shape_data["type"] = "line"
                shape_data["x1"] = line.x1()
                shape_data["y1"] = line.y1()
                shape_data["x2"] = line.x2()
                shape_data["y2"] = line.y2()
            
            # Save glow effect if present
            effect = shape.graphicsEffect()
            if isinstance(effect, QGraphicsDropShadowEffect):
                shape_data["glow"] = {
                    "radius": effect.blurRadius(),
                    "color": effect.color().name(),
                }
            
            result.append(shape_data)
        return result

    def _deserialize_shapes(self, tab, shapes_data: list) -> None:
        """Restore shapes from serialized data."""
        for shape_data in shapes_data:
            shape_type = shape_data.get("type")
            
            if shape_type == "rect":
                shape = ResizableRectItem(
                    shape_data["x"], shape_data["y"],
                    shape_data["width"], shape_data["height"]
                )
            elif shape_type == "ellipse":
                shape = ResizableEllipseItem(
                    shape_data["x"], shape_data["y"],
                    shape_data["width"], shape_data["height"]
                )
            elif shape_type == "line":
                shape = ResizableLineItem(
                    shape_data["x1"], shape_data["y1"],
                    shape_data["x2"], shape_data["y2"]
                )
            else:
                continue
            
            # Apply pen
            pen = QPen(QColor(shape_data.get("pen_color", "#00ffff")))
            pen.setWidth(shape_data.get("pen_width", 3))
            shape.setPen(pen)
            
            # Apply brush
            fill_color = shape_data.get("fill_color")
            if fill_color and shape_type != "line":
                shape.setBrush(QBrush(QColor(fill_color)))
            else:
                shape.setBrush(QBrush(Qt.GlobalColor.transparent))
            
            # Apply glow effect
            glow_data = shape_data.get("glow")
            if glow_data:
                effect = QGraphicsDropShadowEffect()
                effect.setBlurRadius(glow_data["radius"])
                effect.setColor(QColor(glow_data["color"]))
                effect.setOffset(0, 0)
                shape.setGraphicsEffect(effect)
            
            # Configure shape
            shape.setZValue(50)
            shape.setFlag(shape.GraphicsItemFlag.ItemIsSelectable, True)
            shape.setFlag(shape.GraphicsItemFlag.ItemIsMovable, True)
            
            tab.knob_scene.addItem(shape)
            tab.shapes.append(shape)

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
