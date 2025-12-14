# MAX-Msp GUI Maker

A comprehensive Python toolkit for creating UI assets for MAX/MSP and other audio software. Create professional fader spritesheets, knob animations, and custom shapes with neon effects.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Features

### 💾 Project Save/Load
- **Save and load projects** as `.guiproj` files
- Preserves all settings: knob images, rotation, shapes, colors, effects
- **Keyboard shortcuts**: Cmd+N (New), Cmd+O (Open), Cmd+S (Save), Cmd+Shift+S (Save As)
- JSON-based format for easy inspection and editing

### 🎨 Background Removal & Component Splitting
- Remove solid black backgrounds with adjustable threshold
- Automatically split images into separate components using connected components analysis
- Real-time preview while adjusting parameters
- Export individual component PNGs with transparency

### 🎚️ Fader Animation
- Load guide/slider and fader cap images
- Set start and end positions for fader movement
- Click to set center snap point
- Preview fader motion with real-time slider
- Export spritesheets with configurable:
  - Number of frames (2-256)
  - Layout (Horizontal/Vertical)
  - Offset between frames

### 🎛️ Knob Animation
- Load knob images and define rotation center
- **3 Draggable angle wheels** for intuitive calibration:
  - Pointer (blue) - where the knob pointer is in the original image
  - Start (green) - rotation start limit
  - End (red) - rotation end limit
- **Reverse direction** button to switch between inside/outside arc rotation
- Preview rotation with real-time slider
- **Integrated Shape Tools** - add overlays directly on knobs:
  - Rectangle, Circle, Line shapes with neon effects
  - Shapes can rotate with knob or stay static
  - All shape properties (colors, glow, stroke width)
- Export spritesheets with:
  - Configurable frame count
  - Horizontal, Vertical, or Grid layout
  - Custom grid columns
- **7 High-resolution sample knobs** (256×256, anti-aliased):
  - Metallic, Neon Cyan, Neon Magenta, Neon Green
  - Simple, Cyberpunk, Metallic Large (512×512)

### ✨ Shape Editor
- Create shapes: **Rectangles, Circles, Lines, Dots**
- Interactive resize handles on corners and edges
- **Shift+Drag for proportional resize** (maintains aspect ratio)
- **Delete/Backspace key** to delete selected shapes
- **Neon glow effects** with full control:
  - Glow radius (up to 999px)
  - Glow intensity (0-200%)
  - Glow offset X/Y
  - Glow direction selector (all sides or specific sides)
  - **Glow color source**: Stroke, Fill, or Custom
- **Color controls:**
  - Stroke and Fill color pickers with alpha channel
  - **Gradient support** with:
    - Two-color gradients
    - Visual angle/position control
    - Blend size adjustment
    - Live preview while editing
  - **Stroke and Fill opacity sliders** (0-100%)
  - **Stroke width control** (1-100px)
  - Pick colors from base image
- **Layers panel** (Photoshop-style):
  - Drag-reorder layers
  - Move Up/Down buttons
  - Delete with confirmation
  - Base image as a layer
- **Crop tool** with preview window
- **Zoom** with trackpad/mouse wheel
- **Arrow key nudging** (1px or 10px with Shift)
- **Multi-selection** with rubber band
- **Undo/Redo** support (Cmd+Z / Shift+Cmd+Z)
- Export overlay with transparent background

---

## Installation

### Requirements
- Python 3.9+
- PyQt6
- Pillow (PIL)
- OpenCV
- NumPy

### Quick Start

**macOS / Linux:**
```bash
cd MAX-Msp-GUI-Maker
bash run_gui.sh
```

**Windows (CMD):**
```cmd
cd MAX-Msp-GUI-Maker
run_gui.cmd
```

### Manual Setup

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gui.py
```

**Windows (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python gui.py
```

---

## Usage

### Project Management
- **File → New Project** (Cmd+N) - Start fresh
- **File → Open Project...** (Cmd+O) - Load a `.guiproj` file
- **File → Save Project** (Cmd+S) - Save current project
- **File → Save Project As...** (Cmd+Shift+S) - Save to new file

### Background Removal Tab
1. Click **Load image…** and select your PNG
2. Adjust **Background threshold** (higher = more aggressive removal)
3. Adjust **Min component area** to filter noise
4. Preview results in real-time
5. Click **Export components to output/**

### Fader Animation Tab
1. **Load guide/slider** image (the track)
2. **Load fader cap** image (the moving part)
3. Drag the cap to starting position, click **Set START edge**
4. Drag to end position, click **Set END edge**
5. Use the preview slider to test movement
6. Set frames, layout, and offset
7. Click **Export spritesheet**

### Knob Animation Tab
1. Select a sample knob or **Load knob image…**
2. Click **📍 Set rotation center** button, then click on canvas
   - Or use **Ctrl+Click** anytime to set center
3. **Drag the 3 wheel controls** to set angles:
   - **Pointer (blue)** - where the knob pointer points in the source image
   - **Start (green)** - minimum rotation angle
   - **End (red)** - maximum rotation angle
4. Use **↻ Reverse direction** to change rotation path
5. Preview with the slider
6. **Add shape overlays** (optional):
   - Click ▢ ○ ╱ buttons to add shapes
   - Adjust colors and glow effects
   - Toggle "Shapes rotate with knob"
7. Export spritesheet

### Shape Editor Tab
1. **Load base image** (optional)
2. Add shapes with **Rect, Circle, Line, Dot** buttons
3. Select shapes to edit properties:
   - Size (width/height)
   - Stroke width and opacity
   - Fill opacity
   - Neon glow settings
4. **Shift+Drag** corners/edges for proportional resize
5. Use **Stroke/Fill color** buttons for gradients
6. Organize with the **Layers panel**
7. **Export overlay** to save your creation

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Cmd+N | New Project |
| Cmd+O | Open Project |
| Cmd+S | Save Project |
| Cmd+Shift+S | Save Project As |
| Cmd+Z | Undo |
| Shift+Cmd+Z | Redo |
| Delete/Backspace | Delete selected shape |
| Arrow keys | Nudge shape 1px |
| Shift+Arrow | Nudge shape 10px |
| Ctrl+Click | Set rotation center (Knob tab) |
| Shift+Drag | Proportional resize |

---

## CLI Usage

The `process_fader_image.py` script provides command-line image processing:

### What it does:
1. Load the source PNG
2. Remove the black background (pixels darker than threshold become transparent)
3. Use the alpha channel to detect separate components
4. Export:
   - One **background-removed image** (`<name>_no_bg.png`)
   - Multiple **component images** (`component_1.png`, `component_2.png`, …)

### Basic usage:

**macOS / Linux:**
```bash
source .venv/bin/activate
python process_fader_image.py \
  --input "your_image.png" \
  --output-dir "output" \
  --threshold 10 \
  --min-area 2000
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
python process_fader_image.py ^
  --input "your_image.png" ^
  --output-dir "output" ^
  --threshold 10 ^
  --min-area 2000
```

### Arguments:
| Argument | Description | Default |
|----------|-------------|---------|
| `--input` | Path to source PNG image | Required |
| `--output-dir` | Directory for output files | `output` |
| `--threshold` | Black removal threshold (0-255) | `10` |
| `--min-area` | Minimum component area in pixels | `2000` |

### Output:
The script creates an `output` folder containing:
- `<original_name>_no_bg.png` – Background removed version
- `component_1.png`, `component_2.png`, … – Individual pieces (e.g., fader track and knob)

---

## Sample Knobs

Generate high-resolution anti-aliased sample knobs for testing:

```bash
python create_sample_knob.py
```

Creates 7 knob styles in `output/sample_knobs/`:
| Knob | Size | Description |
|------|------|-------------|
| `knob_metallic.png` | 256×256 | Classic 3D metal |
| `knob_neon_cyan.png` | 256×256 | Glowing cyan |
| `knob_neon_magenta.png` | 256×256 | Glowing magenta |
| `knob_neon_green.png` | 256×256 | Glowing green |
| `knob_simple.png` | 256×256 | Flat minimal |
| `knob_cyberpunk.png` | 256×256 | Neon lines with cyan pointer |
| `knob_metallic_large.png` | 512×512 | Large metal knob |

*All knobs use 2× supersampling + LANCZOS downscaling for smooth anti-aliased edges.*

---

## Project Structure

```
MAX-Msp-GUI-Maker/
├── gui.py                  # Main application entry point
├── background_tab.py       # Background removal module
├── animation_tab.py        # Fader animation module
├── knob_animation_tab.py   # Knob animation module
├── shape_editor_tab.py     # Shape editor components
├── process_fader_image.py  # CLI image processing
├── create_sample_knob.py   # Sample knob generator
├── run_gui.sh              # macOS/Linux launcher
├── run_gui.cmd             # Windows launcher
├── requirements.txt        # Python dependencies
├── *.guiproj               # Project save files
└── output/                 # Generated files
    └── sample_knobs/       # Sample knob images
```

---

## Roadmap

### Planned Features
- [ ] **SVG export** - Vector export for shapes
- [ ] **Animation timeline** - More complex multi-step animations
- [ ] **Batch processing** - Process multiple images at once
- [ ] **Custom knob designer** - Create knobs from scratch in the app
- [ ] **Audio-reactive preview** - Preview animations with audio input
- [ ] **MAX/MSP integration** - Direct export to MAX/MSP format
- [ ] **Theme system** - Dark/light mode and custom themes
- [ ] **Plugin architecture** - Extensible effect plugins
- [ ] **3D knob rendering** - Basic 3D knob generation

### Under Consideration
- MIDI learn for knob/fader preview
- Video export (GIF/MP4) for previews
- Cloud preset sharing
- Collaborative editing

---

## Contributing

We welcome contributions! If you have ideas for new features or improvements:

1. **Open an Issue** - Describe your feature request or bug report
2. **Submit a Pull Request** - Fork the repo and submit your changes

### How to Contribute

```bash
# Fork the repository on GitHub
git clone https://github.com/YOUR_USERNAME/MAX-Msp-GUI-Maker.git
cd MAX-Msp-GUI-Maker
git checkout -b feature/your-feature-name

# Make your changes
# ...

# Commit and push
git add .
git commit -m "Add: your feature description"
git push origin feature/your-feature-name

# Open a Pull Request on GitHub
```

### Contribution Guidelines
- Follow existing code style
- Add comments for complex logic
- Test your changes before submitting
- Update README if adding new features

---

## License

MIT License - feel free to use this in your projects!

---

## Acknowledgments

Built with:
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [Pillow](https://pillow.readthedocs.io/) - Image processing
- [OpenCV](https://opencv.org/) - Computer vision
- [NumPy](https://numpy.org/) - Numerical computing

---

**Made for the MAX/MSP and audio software community** 🎵
