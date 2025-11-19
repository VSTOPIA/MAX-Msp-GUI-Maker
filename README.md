## MAX-Msp-GUI-Maker – Image Processing Toolkit

This mini-toolkit prepares UI assets (like your fader image) by:

- **Removing a solid black background** and replacing it with transparency.
- **Splitting the image into separate components** (e.g. fader track and knob) using connected components analysis.

Once this is working, we can extend it to generate fader spritesheets and add a UI on top.

---

### 1. Python environment setup

You’ll need **Python 3.9+**.

- **On macOS / Linux (bash/zsh):**

```bash
cd /Users/ostinsolo/Documents/Code/MAX-Msp-GUI-Maker
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

- **On Windows (CMD, not PowerShell):**

```cmd
cd C:\path\to\MAX-Msp-GUI-Maker
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

### 2. Processing the fader image (CLI)

The main script is `process_fader_image.py`. It will:

1. Load the source PNG.
2. Remove the black background (treat anything darker than a threshold as transparent).
3. Use the alpha channel to detect separate components.
4. Export:
   - One **background-removed image**.
   - Two (or more) **component images** (`component_1.png`, `component_2.png`, …).

---

### 3. Example: run it on your current PNG

Assuming the file name is exactly:

`Generated Image November 19, 2025 - 12_42AM.png`

and it lives in the project root:

- **macOS / Linux:**

```bash
cd /Users/ostinsolo/Documents/Code/MAX-Msp-GUI-Maker
source .venv/bin/activate
python process_fader_image.py \
  --input "Generated Image November 19, 2025 - 12_42AM.png" \
  --output-dir "output" \
  --threshold 10 \
  --min-area 2000
```

- **Windows (CMD):**

```cmd
cd C:\path\to\MAX-Msp-GUI-Maker
.venv\Scripts\activate.bat
python process_fader_image.py ^
  --input "Generated Image November 19, 2025 - 12_42AM.png" ^
  --output-dir "output" ^
  --threshold 10 ^
  --min-area 2000
```

This will create an `output` folder with:

- `<original_name>_no_bg.png` – background removed.
- `component_1.png`, `component_2.png`, … – individual pieces (e.g. fader track and knob).

---

### 4. Interactive GUI for tweaking parameters

You can also use a small PyQt6 GUI that gives **live feedback** while you adjust parameters.

Start it from the project root:

- **macOS / Linux:**

```bash
cd /Users/ostinsolo/Documents/Code/MAX-Msp-GUI-Maker
bash run_gui.sh
```

- **Windows (CMD):**

```cmd
cd C:\path\to\MAX-Msp-GUI-Maker
run_gui.cmd
```

In the GUI you can:

- **Load image…** – choose your PNG (e.g. the generated fader image).
- Adjust **Background threshold** – controls how aggressive the black removal is.
- Adjust **Min component area** – filters out tiny noise; keeps only big shapes like the track and knob.
- See side‑by‑side **Original** and **Processed/Components** preview.
- Click **Export components to output/** to run the processing with the current settings and write:
  - `<original_name>_no_bg.png`
  - `component_1.png`, `component_2.png`, … into the `output` folder.

---

### 5. Next steps

After we verify the two component images look clean:

- We’ll add code to generate **spritesheet frames** for the fader/knob.
- Then we can extend the GUI so you can:
  - Define and preview knob positions.
  - Export a complete spritesheet for use in MAX/MSP or other environments.

