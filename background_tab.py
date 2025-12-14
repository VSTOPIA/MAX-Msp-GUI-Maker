"""
Background Removal Tab - Contains UI and logic for:
- Loading images
- Removing black backgrounds
- Splitting into components
- Exporting processed images
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from PIL import Image
from process_fader_image import remove_black_background, split_components

if TYPE_CHECKING:
    from gui import MainWindow


def load_pixmap(path: Path, max_size: int = 480) -> QPixmap:
    """Load an image file into a QPixmap and scale it down to fit max_size."""
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap

    return pixmap.scaled(
        max_size,
        max_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class BackgroundTab(QWidget):
    """Tab widget for background removal and component splitting."""

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self._owner = owner
        self.input_path: Path | None = None
        self.preview_dir = Path("preview").resolve()
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

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

    # ------------------------------------------------------------------ Actions

    def on_load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.input_path = Path(path)
            self._update_original_preview()
            self.on_params_changed()

    def on_params_changed(self) -> None:
        if self.input_path is None:
            return
        threshold = self.threshold_slider.value()
        min_area = self.min_area_spin.value()

        # Process image and generate previews
        img = Image.open(self.input_path).convert("RGBA")
        no_bg = remove_black_background(img, threshold=threshold)

        # Split components
        components = split_components(no_bg, min_area=min_area)

        # Save previews
        preview_path = self.preview_dir / "no_bg.png"
        no_bg.save(preview_path)

        # Composite preview with all components
        if components:
            composite = Image.new("RGBA", no_bg.size, (0, 0, 0, 0))
            for i, comp in enumerate(components):
                # Save each component preview
                comp_path = self.preview_dir / f"component_{i}.png"
                comp.save(comp_path)
                composite = Image.alpha_composite(composite, comp)

            composite_path = self.preview_dir / "composite.png"
            composite.save(composite_path)
            self._update_previews(composite_path)
            self.component_info_label.setText(f"Components: {len(components)}")
        else:
            self._update_previews(preview_path)
            self.component_info_label.setText("Components: 0")

    def on_export_components(self) -> None:
        if self.input_path is None:
            return

        output_dir = Path("output").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        threshold = self.threshold_slider.value()
        min_area = self.min_area_spin.value()

        img = Image.open(self.input_path).convert("RGBA")
        no_bg = remove_black_background(img, threshold=threshold)

        # Save no-background version
        stem = self.input_path.stem
        no_bg_path = output_dir / f"{stem}_no_bg.png"
        no_bg.save(no_bg_path)

        # Split and save components
        components = split_components(no_bg, min_area=min_area)
        for i, comp in enumerate(components):
            comp_path = output_dir / f"{stem}_component_{i}.png"
            comp.save(comp_path)

        self.component_info_label.setText(
            f"Exported {len(components)} components to {output_dir}"
        )

    # ------------------------------------------------------------------ Helpers

    def _update_original_preview(self) -> None:
        if self.input_path is None:
            return
        pixmap = load_pixmap(self.input_path)
        if not pixmap.isNull():
            self.original_label.setPixmap(pixmap)

    def _update_previews(self, processed_path: Path) -> None:
        pixmap = load_pixmap(processed_path)
        if not pixmap.isNull():
            self.processed_label.setPixmap(pixmap)

