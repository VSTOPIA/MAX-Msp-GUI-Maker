# MAX-Msp GUI Maker

A comprehensive Python toolkit for creating UI assets for MAX/MSP and other audio software. Create professional fader spritesheets, knob animations, and custom shapes with neon effects.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## Features

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
- Set start and end angles by clicking on a visual guide circle
- **+180° flip buttons** for quick alignment adjustments
- **Reverse direction** button to switch between inside/outside arc rotation
- Preview rotation with real-time slider
- Export spritesheets with:
  - Configurable frame count
  - Horizontal, Vertical, or Grid layout
  - Custom grid columns
- **7 Sample knobs included:**
  - Metallic, Neon Cyan, Neon Magenta, Neon Green
  - Simple, Cyberpunk, Metallic Large

### ✨ Shape Editor
- Create shapes: **Rectangles, Circles, Lines, Dots**
- Interactive resize handles on corners and edges
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
2. Use **Click mode** to set:
   - Rotation center (red dot)
   - Start angle (green line)
   - End angle (red line)
3. Use **+180° buttons** to flip angles if misaligned
4. Use **↻ Reverse direction** to change rotation path
5. Preview with the slider
6. Export spritesheet

### Shape Editor Tab
1. **Load base image** (optional)
2. Add shapes with **Rect, Circle, Line, Dot** buttons
3. Select shapes to edit properties:
   - Size (width/height)
   - Stroke width and opacity
   - Fill opacity
   - Neon glow settings
4. Use **Stroke/Fill color** buttons for gradients
5. Organize with the **Layers panel**
6. **Export overlay** to save your creation

---

## CLI Usage

For batch processing without the GUI:

```bash
python process_fader_image.py \
  --input "your_image.png" \
  --output-dir "output" \
  --threshold 10 \
  --min-area 2000
```

---

## Sample Knobs

Generate sample knobs for testing:

```bash
python create_sample_knob.py
```

Creates 7 knob styles in `output/sample_knobs/`:
- `knob_metallic.png` - Classic 3D metal
- `knob_neon_cyan.png` - Glowing cyan
- `knob_neon_magenta.png` - Glowing magenta
- `knob_neon_green.png` - Glowing green
- `knob_simple.png` - Flat minimal
- `knob_cyberpunk.png` - Neon lines with cyan pointer
- `knob_metallic_large.png` - 200px metal knob

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
└── output/                 # Generated files
    └── sample_knobs/       # Sample knob images
```

---

## Roadmap

### Planned Features
- [ ] **Preset system** - Save and load shape/effect presets
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
