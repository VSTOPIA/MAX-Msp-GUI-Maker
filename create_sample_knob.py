"""
Generate sample knob images for testing the Knob Animation tab.
"""

from PIL import Image, ImageDraw, ImageFilter
import math
from pathlib import Path


def create_metallic_knob(size: int = 128, pointer_angle: float = -135) -> Image.Image:
    """
    Create a metallic-style knob with a pointer indicator.
    
    Args:
        size: Image size in pixels (square)
        pointer_angle: Angle of the pointer in degrees (0 = right, counter-clockwise)
    
    Returns:
        RGBA Image of the knob
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    outer_radius = size // 2 - 4
    inner_radius = outer_radius - 8
    pointer_radius = inner_radius - 6
    
    # Outer ring (dark edge)
    draw.ellipse(
        [center - outer_radius, center - outer_radius,
         center + outer_radius, center + outer_radius],
        fill=(40, 40, 45, 255),
        outline=(20, 20, 25, 255),
        width=2
    )
    
    # Main knob body with gradient-like effect
    for i in range(inner_radius, 0, -2):
        # Create a gradient from light gray to darker
        t = i / inner_radius
        gray = int(80 + 60 * t)
        color = (gray, gray, gray + 5, 255)
        draw.ellipse(
            [center - i, center - i, center + i, center + i],
            fill=color
        )
    
    # Highlight on top-left
    highlight_offset = inner_radius // 3
    draw.ellipse(
        [center - highlight_offset - 10, center - highlight_offset - 10,
         center - highlight_offset + 15, center - highlight_offset + 15],
        fill=(180, 180, 185, 100)
    )
    
    # Pointer/indicator line
    rad = math.radians(pointer_angle)
    px1 = center + int(10 * math.cos(rad))
    py1 = center + int(10 * math.sin(rad))
    px2 = center + int(pointer_radius * math.cos(rad))
    py2 = center + int(pointer_radius * math.sin(rad))
    
    # Pointer shadow
    draw.line([(px1 + 2, py1 + 2), (px2 + 2, py2 + 2)], fill=(30, 30, 35, 150), width=4)
    # Pointer main
    draw.line([(px1, py1), (px2, py2)], fill=(255, 80, 80, 255), width=3)
    # Pointer highlight
    draw.line([(px1, py1), (px2, py2)], fill=(255, 150, 150, 255), width=1)
    
    # Center cap
    cap_radius = 8
    draw.ellipse(
        [center - cap_radius, center - cap_radius,
         center + cap_radius, center + cap_radius],
        fill=(50, 50, 55, 255),
        outline=(30, 30, 35, 255)
    )
    
    return img


def create_neon_knob(size: int = 128, pointer_angle: float = -135, 
                     color: tuple = (0, 229, 255)) -> Image.Image:
    """
    Create a neon-style knob with glowing edges.
    
    Args:
        size: Image size in pixels
        pointer_angle: Angle of the pointer in degrees
        color: RGB tuple for the neon color
    
    Returns:
        RGBA Image of the knob
    """
    # Create larger image for glow effect
    glow_padding = 20
    full_size = size + glow_padding * 2
    img = Image.new("RGBA", (full_size, full_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = full_size // 2
    outer_radius = size // 2 - 4
    inner_radius = outer_radius - 6
    pointer_radius = inner_radius - 8
    
    r, g, b = color
    
    # Dark background circle
    draw.ellipse(
        [center - outer_radius - 2, center - outer_radius - 2,
         center + outer_radius + 2, center + outer_radius + 2],
        fill=(15, 15, 20, 255)
    )
    
    # Neon outer ring
    draw.ellipse(
        [center - outer_radius, center - outer_radius,
         center + outer_radius, center + outer_radius],
        outline=(r, g, b, 255),
        width=3
    )
    
    # Inner circle (dark)
    draw.ellipse(
        [center - inner_radius, center - inner_radius,
         center + inner_radius, center + inner_radius],
        fill=(20, 20, 25, 255)
    )
    
    # Pointer/indicator
    rad = math.radians(pointer_angle)
    px1 = center + int(12 * math.cos(rad))
    py1 = center + int(12 * math.sin(rad))
    px2 = center + int(pointer_radius * math.cos(rad))
    py2 = center + int(pointer_radius * math.sin(rad))
    
    # Pointer glow (draw multiple times with decreasing alpha)
    for glow in range(8, 0, -2):
        alpha = 50 - glow * 5
        draw.line([(px1, py1), (px2, py2)], fill=(r, g, b, alpha), width=glow + 4)
    
    # Pointer main
    draw.line([(px1, py1), (px2, py2)], fill=(r, g, b, 255), width=3)
    draw.line([(px1, py1), (px2, py2)], fill=(255, 255, 255, 200), width=1)
    
    # Center dot
    dot_radius = 5
    draw.ellipse(
        [center - dot_radius, center - dot_radius,
         center + dot_radius, center + dot_radius],
        fill=(r, g, b, 255)
    )
    
    # Apply gaussian blur for glow effect
    glow_layer = img.copy()
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=4))
    
    # Composite glow behind main image
    result = Image.new("RGBA", (full_size, full_size), (0, 0, 0, 0))
    result = Image.alpha_composite(result, glow_layer)
    result = Image.alpha_composite(result, img)
    
    # Crop to original size
    crop_box = (glow_padding, glow_padding, glow_padding + size, glow_padding + size)
    result = result.crop(crop_box)
    
    return result


def create_cyberpunk_knob(size: int = 128, pointer_angle: float = -135) -> Image.Image:
    """
    Create a cyberpunk-style knob with minimal neon lines and cyan pointer.
    
    Args:
        size: Image size in pixels
        pointer_angle: Angle of the pointer in degrees
    
    Returns:
        RGBA Image of the knob
    """
    glow_padding = 20
    full_size = size + glow_padding * 2
    img = Image.new("RGBA", (full_size, full_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = full_size // 2
    outer_radius = size // 2 - 6
    inner_radius = outer_radius - 15
    pointer_radius = inner_radius - 5
    
    # Cyberpunk colors
    cyan = (0, 255, 255)
    magenta = (255, 0, 128)
    dark_bg = (10, 10, 15, 255)
    
    # Dark background circle
    draw.ellipse(
        [center - outer_radius - 2, center - outer_radius - 2,
         center + outer_radius + 2, center + outer_radius + 2],
        fill=dark_bg
    )
    
    # Outer ring - magenta accent
    draw.arc(
        [center - outer_radius, center - outer_radius,
         center + outer_radius, center + outer_radius],
        start=0, end=360,
        fill=(*magenta, 180),
        width=2
    )
    
    # Inner ring - cyan
    draw.arc(
        [center - inner_radius, center - inner_radius,
         center + inner_radius, center + inner_radius],
        start=0, end=360,
        fill=(*cyan, 150),
        width=1
    )
    
    # Tick marks around the edge
    for angle in range(-135, 136, 30):
        rad = math.radians(angle)
        tick_start = outer_radius - 4
        tick_end = outer_radius + 2
        x1 = center + int(tick_start * math.cos(rad))
        y1 = center + int(tick_start * math.sin(rad))
        x2 = center + int(tick_end * math.cos(rad))
        y2 = center + int(tick_end * math.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=(*magenta, 200), width=1)
    
    # Pointer line - cyan, thin
    rad = math.radians(pointer_angle)
    px1 = center + int(8 * math.cos(rad))
    py1 = center + int(8 * math.sin(rad))
    px2 = center + int(pointer_radius * math.cos(rad))
    py2 = center + int(pointer_radius * math.sin(rad))
    
    # Pointer glow
    for glow in range(6, 0, -2):
        alpha = 40 - glow * 5
        draw.line([(px1, py1), (px2, py2)], fill=(*cyan, alpha), width=glow + 2)
    
    # Pointer main line
    draw.line([(px1, py1), (px2, py2)], fill=(*cyan, 255), width=2)
    
    # Small center dot
    dot_radius = 3
    draw.ellipse(
        [center - dot_radius, center - dot_radius,
         center + dot_radius, center + dot_radius],
        fill=(*cyan, 255)
    )
    
    # Apply glow
    glow_layer = img.copy()
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=3))
    
    result = Image.new("RGBA", (full_size, full_size), (0, 0, 0, 0))
    result = Image.alpha_composite(result, glow_layer)
    result = Image.alpha_composite(result, img)
    
    # Crop to original size
    crop_box = (glow_padding, glow_padding, glow_padding + size, glow_padding + size)
    result = result.crop(crop_box)
    
    return result


def create_simple_knob(size: int = 128, pointer_angle: float = -135) -> Image.Image:
    """
    Create a simple flat knob design.
    
    Args:
        size: Image size in pixels
        pointer_angle: Angle of the pointer in degrees
    
    Returns:
        RGBA Image of the knob
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    outer_radius = size // 2 - 4
    pointer_radius = outer_radius - 12
    
    # Main circle
    draw.ellipse(
        [center - outer_radius, center - outer_radius,
         center + outer_radius, center + outer_radius],
        fill=(60, 60, 65, 255),
        outline=(80, 80, 85, 255),
        width=2
    )
    
    # Pointer
    rad = math.radians(pointer_angle)
    px1 = center
    py1 = center
    px2 = center + int(pointer_radius * math.cos(rad))
    py2 = center + int(pointer_radius * math.sin(rad))
    
    draw.line([(px1, py1), (px2, py2)], fill=(255, 255, 255, 255), width=3)
    
    # Center dot
    dot_radius = 6
    draw.ellipse(
        [center - dot_radius, center - dot_radius,
         center + dot_radius, center + dot_radius],
        fill=(40, 40, 45, 255)
    )
    
    return img


def main():
    output_dir = Path("output").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    samples_dir = output_dir / "sample_knobs"
    samples_dir.mkdir(parents=True, exist_ok=True)
    
    # Create different knob styles
    print("Creating sample knobs...")
    
    # Metallic knob
    metallic = create_metallic_knob(size=128, pointer_angle=-135)
    metallic.save(samples_dir / "knob_metallic.png")
    print(f"  ✓ Saved: {samples_dir / 'knob_metallic.png'}")
    
    # Neon cyan knob
    neon_cyan = create_neon_knob(size=128, pointer_angle=-135, color=(0, 229, 255))
    neon_cyan.save(samples_dir / "knob_neon_cyan.png")
    print(f"  ✓ Saved: {samples_dir / 'knob_neon_cyan.png'}")
    
    # Neon magenta knob
    neon_magenta = create_neon_knob(size=128, pointer_angle=-135, color=(255, 0, 128))
    neon_magenta.save(samples_dir / "knob_neon_magenta.png")
    print(f"  ✓ Saved: {samples_dir / 'knob_neon_magenta.png'}")
    
    # Neon green knob
    neon_green = create_neon_knob(size=128, pointer_angle=-135, color=(0, 255, 100))
    neon_green.save(samples_dir / "knob_neon_green.png")
    print(f"  ✓ Saved: {samples_dir / 'knob_neon_green.png'}")
    
    # Simple knob
    simple = create_simple_knob(size=128, pointer_angle=-135)
    simple.save(samples_dir / "knob_simple.png")
    print(f"  ✓ Saved: {samples_dir / 'knob_simple.png'}")
    
    # Cyberpunk knob - neon lines with cyan pointer
    cyberpunk = create_cyberpunk_knob(size=128, pointer_angle=-135)
    cyberpunk.save(samples_dir / "knob_cyberpunk.png")
    print(f"  ✓ Saved: {samples_dir / 'knob_cyberpunk.png'}")
    
    # Larger metallic knob
    metallic_large = create_metallic_knob(size=200, pointer_angle=-135)
    metallic_large.save(samples_dir / "knob_metallic_large.png")
    print(f"  ✓ Saved: {samples_dir / 'knob_metallic_large.png'}")
    
    print(f"\nAll sample knobs saved to: {samples_dir}")
    print("\nYou can load these in the 'Knob animation' tab to test rotation and spritesheet export!")


if __name__ == "__main__":
    main()

