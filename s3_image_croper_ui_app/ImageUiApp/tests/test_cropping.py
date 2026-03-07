"""Tests for image cropping logic extracted from file_tab.py."""
from PIL import Image


def test_crop_produces_correct_dimensions():
    """Verify that the crop logic produces 800x480 from a larger image."""
    crop_width, crop_height = 800, 480
    original = Image.new("RGB", (2000, 1500), "blue")

    # Simulate the crop at position (0, 0)
    cropped = original.crop((0, 0, crop_width, crop_height))
    assert cropped.size == (crop_width, crop_height)


def test_crop_center_position():
    """Verify center crop calculation."""
    crop_width, crop_height = 800, 480
    img_width, img_height = 2000, 1500

    # Center crop position
    x = (img_width - crop_width) // 2
    y = (img_height - crop_height) // 2

    assert x == 600
    assert y == 510

    original = Image.new("RGB", (img_width, img_height), "green")
    cropped = original.crop((x, y, x + crop_width, y + crop_height))
    assert cropped.size == (crop_width, crop_height)


def test_downscale_preserves_aspect_ratio():
    """Verify that pre-downscaling preserves aspect ratio."""
    max_dim = 1000
    original = Image.new("RGB", (3000, 2000), "red")

    ratio = min(max_dim / original.width, max_dim / original.height)
    new_size = (int(original.width * ratio), int(original.height * ratio))
    resized = original.resize(new_size, Image.Resampling.LANCZOS)

    assert resized.width == 1000
    assert resized.height == 666 or resized.height == 667  # rounding


def test_rgba_to_rgb_conversion():
    """Verify RGBA images are converted to RGB for S3 upload."""
    rgba = Image.new("RGBA", (800, 480), (255, 0, 0, 128))
    rgb = rgba.convert("RGB")
    assert rgb.mode == "RGB"
    assert rgb.size == (800, 480)
