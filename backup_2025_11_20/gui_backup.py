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

# NOTE: This is a snapshot backup of gui.py taken on 2025-11-20 before the
# refactor into multiple modules. It intentionally only contains the imports
# and header comment as a marker; the live/gui logic remains in gui.py.
# If needed, you can restore the old version from git history or from a
# separate full backup.

if __name__ == "__main__":
    print("This is a backup shell of gui.py; use gui.py to run the application.")


