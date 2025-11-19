import argparse
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image


def remove_black_background(
    input_path: Path,
    output_path: Path,
    threshold: int = 10,
) -> None:
    """
    Remove (near-)black background from an image and save an RGBA PNG.

    Anything darker than `threshold` in the grayscale image is treated as
    background and becomes fully transparent. Everything else becomes opaque.
    """
    img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {input_path}")

    # Ensure we have at least 3 channels (BGR). IMREAD_UNCHANGED may already
    # give us 4 channels, but we construct the alpha ourselves anyway.
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError("Expected an RGB/RGBA image.")

    # Use the color channels to derive a grayscale image.
    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)

    # Pixels darker than `threshold` become background (alpha = 0).
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # Split out B, G, R channels. Ignore any existing alpha, we are replacing it.
    b, g, r = cv2.split(img[:, :, :3])
    rgba = cv2.merge([r, g, b, mask])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba).save(output_path)


def split_components(
    input_path: Path,
    output_dir: Path,
    min_area: int = 2000,
) -> List[Path]:
    """
    Split an RGBA image into separate components based on the alpha channel.

    Returns a list of output file paths for the extracted components.
    """
    img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {input_path}")

    if img.ndim != 3 or img.shape[2] != 4:
        raise ValueError("Expected a 4-channel RGBA image for splitting.")

    # Alpha channel indicates where "stuff" exists.
    b, g, r, a = cv2.split(img)

    # Binary mask: alpha > 0 is foreground.
    _, mask = cv2.threshold(a, 0, 255, cv2.THRESH_BINARY)

    # Optionally clean up very small specks with morphology.
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    component_paths: List[Path] = []

    component_index = 1
    for label in range(1, num_labels):  # label 0 is background
        x, y, w, h, area = stats[label]
        if area < min_area:
            continue

        crop = img[y : y + h, x : x + w]
        # Convert BGR(A) (OpenCV) to RGBA (Pillow).
        crop_rgba = cv2.cvtColor(crop, cv2.COLOR_BGRA2RGBA)
        comp_img = Image.fromarray(crop_rgba)

        out_path = output_dir / f"component_{component_index}.png"
        comp_img.save(out_path)
        component_paths.append(out_path)
        component_index += 1

    return component_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove black background from an image and split it into separate components."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input PNG image.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where processed images will be written.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=10,
        help=(
            "Grayscale threshold for treating pixels as foreground. "
            "Lower values keep more dark detail; higher values remove more."
        ),
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=2000,
        help=(
            "Minimum pixel area for a connected component to be kept. "
            "Use this to ignore tiny specks/noise."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.is_file():
        raise FileNotFoundError(f"Input image does not exist: {input_path}")

    no_bg_path = output_dir / f"{input_path.stem}_no_bg.png"

    print(f"Removing black background from: {input_path}")
    remove_black_background(
        input_path=input_path,
        output_path=no_bg_path,
        threshold=args.threshold,
    )
    print(f"Saved background-removed image to: {no_bg_path}")

    print("Splitting into components based on alpha channel...")
    component_paths = split_components(
        input_path=no_bg_path,
        output_dir=output_dir,
        min_area=args.min_area,
    )

    if not component_paths:
        print("No components found (check threshold/min-area settings).")
    else:
        print("Saved component images:")
        for p in component_paths:
            print(f"  - {p}")


if __name__ == "__main__":
    main()


