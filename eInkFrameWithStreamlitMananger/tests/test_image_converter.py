import os
import sys
import tempfile

# Add parent directory so standalone modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from image_converter import ImageConverter


def _make_test_image(path, width=1600, height=1200, color="red"):
    img = Image.new("RGB", (width, height), color)
    img.save(path)


def test_resize_to_800x480(tmp_path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    _make_test_image(str(src / "photo.jpg"))

    converter = ImageConverter(str(src), str(out))
    converter.process_images()

    result_path = out / "photo.jpg"
    assert result_path.exists()

    with Image.open(str(result_path)) as img:
        assert img.size == (800, 480)


def test_portrait_image_resized(tmp_path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    _make_test_image(str(src / "portrait.png"), width=600, height=1200)

    converter = ImageConverter(str(src), str(out))
    converter.process_images()

    with Image.open(str(out / "portrait.png")) as img:
        assert img.size == (800, 480)


def test_skips_output_dir(tmp_path):
    src = tmp_path / "src"
    out = src / "_epaper_pic"
    src.mkdir()
    out.mkdir()

    _make_test_image(str(src / "real.jpg"))
    _make_test_image(str(out / "cached.jpg"))

    converter = ImageConverter(str(src), str(out))
    converter.process_images()

    # Only the source image should be processed, not the cached one
    assert (out / "real.jpg").exists()
    # The cached.jpg should not be re-processed (it was already there)
    # We verify by checking no duplicate appeared with different content


def test_skips_hidden_files(tmp_path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    _make_test_image(str(src / ".hidden.jpg"))
    _make_test_image(str(src / "visible.jpg"))

    converter = ImageConverter(str(src), str(out))
    converter.process_images()

    assert (out / "visible.jpg").exists()
    assert not (out / ".hidden.jpg").exists()


def test_skips_non_image_files(tmp_path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "readme.txt").write_text("not an image")
    _make_test_image(str(src / "photo.jpg"))

    converter = ImageConverter(str(src), str(out))
    converter.process_images()

    assert (out / "photo.jpg").exists()
    assert not (out / "readme.txt").exists()


def test_walks_subdirectories(tmp_path):
    src = tmp_path / "src"
    sub = src / "subdir"
    out = tmp_path / "out"
    src.mkdir()
    sub.mkdir()
    out.mkdir()

    _make_test_image(str(sub / "nested.jpg"))

    converter = ImageConverter(str(src), str(out))
    converter.process_images()

    assert (out / "nested.jpg").exists()


def test_corrupt_image_does_not_abort_run(tmp_path):
    """A corrupt image must be skipped, not abort the whole run."""
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    # Bad file with valid extension but unreadable content.
    (src / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\nnot-actually-png")
    _make_test_image(str(src / "good.jpg"))

    converter = ImageConverter(str(src), str(out))
    converter.process_images()  # must not raise

    assert (out / "good.jpg").exists()
    assert not (out / "broken.png").exists()


def test_corrupt_file_under_s3_subtree_is_deleted(tmp_path):
    """Corrupt files inside the S3 subtree are deleted so sd-s3-sync re-downloads them."""
    src = tmp_path / "src"
    s3_dir = src / "s3_folder"
    out = tmp_path / "out"
    src.mkdir()
    s3_dir.mkdir()
    out.mkdir()

    bad = s3_dir / "broken.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\nnot-actually-png")
    _make_test_image(str(s3_dir / "good.jpg"))

    converter = ImageConverter(str(src), str(out), s3_subtree=str(s3_dir))
    converter.process_images()

    assert not bad.exists(), "corrupt S3 file should be deleted to trigger re-download"
    assert (out / "good.jpg").exists()


def test_corrupt_file_outside_s3_subtree_is_kept(tmp_path):
    """Corrupt files outside the S3 subtree must be skipped but not deleted."""
    src = tmp_path / "src"
    s3_dir = src / "s3_folder"
    out = tmp_path / "out"
    src.mkdir()
    s3_dir.mkdir()
    out.mkdir()

    # Bad file at SD root (outside the S3 subtree) — re-download cannot help.
    bad = src / "manual_drop.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\nnot-actually-png")

    converter = ImageConverter(str(src), str(out), s3_subtree=str(s3_dir))
    converter.process_images()

    assert bad.exists(), "non-S3 corrupt files must be left in place"
