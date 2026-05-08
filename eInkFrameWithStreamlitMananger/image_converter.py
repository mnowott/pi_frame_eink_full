import os
from PIL import Image, ImageEnhance, ImageOps


class ImageConverter:
    """
    Class to convert images for display on the e-Paper screen.
    """

    def __init__(self, source_dir, output_dir):
        # Use absolute paths so comparisons work reliably
        self.source_dir = os.path.abspath(source_dir)
        self.output_dir = os.path.abspath(output_dir)

    # Finds valid image files in the source directory to process.
    def process_images(self):
        valid_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff")

        for root, dirs, files in os.walk(self.source_dir):
            root_abs = os.path.abspath(root)

            # ------------------------------------------------------
            # IMPORTANT:
            #   Never walk into our own output directory subtree.
            #   This avoids re-processing already converted images
            #   and prevents any processing loops.
            # ------------------------------------------------------
            if root_abs == self.output_dir or root_abs.startswith(
                self.output_dir + os.sep
            ):
                dirs[:] = []  # don't descend further
                continue

            # Also prune the output directory from the current dirs list,
            # in case output_dir is a direct child of this root.
            dirs[:] = [
                d
                for d in dirs
                if os.path.abspath(os.path.join(root_abs, d)) != self.output_dir
            ]
            # ------------------------------------------------------

            for img in files:
                if img.startswith("."):
                    continue

                if not img.lower().endswith(valid_extensions):
                    continue

                img_path = os.path.join(root, img)
                print(f"Found file: {img_path}")
                try:
                    self.resize_image(img_path, img)
                except Exception as e:
                    # Skip corrupt or unreadable images so a single bad file does
                    # not abort processing of the rest of the SD card. Without
                    # this, one bad PNG empties the processed-image cache and
                    # the display falls back to "no valid images".
                    print(
                        f"[image_converter] Skipping {img_path}: "
                        f"{type(e).__name__}: {e}",
                        flush=True,
                    )
                    continue

    # Resizes the image to fit the target dimensions while maintaining aspect ratio.
    # Crops the image to the target dimensions and enhances color and contrast.
    # Saves the processed image to the output directory.
    def resize_image(self, img_path, file_name):
        # Screen target size dims
        target_width = 800
        target_height = 480

        with Image.open(img_path) as img:
            img = ImageOps.exif_transpose(img)

            # Original dimensions
            orig_width, orig_height = img.size

            original_aspect_ratio = orig_width / orig_height
            target_aspect_ratio = target_width / target_height

            # Fit height and crop sides
            if original_aspect_ratio > target_aspect_ratio:
                new_height = target_height
                new_width = int(new_height * original_aspect_ratio)
            # Fit width and crop top/bottom
            else:
                new_width = target_width
                new_height = int(new_width / original_aspect_ratio)

            print("Resizing image...")
            # Resize the image while maintaining aspect ratio
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Calculate the cropping box to center the crop
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height

            print("Cropping image...")
            # Crop the image
            cropped_img = resized_img.crop((left, top, right, bottom))

            print("Enchancing image...")
            color = ImageEnhance.Color(cropped_img)
            cropped_img = color.enhance(1.5)

            contrast = ImageEnhance.Contrast(cropped_img)
            cropped_img = contrast.enhance(1.5)

            print("Saving image...")
            # Save the final image
            os.makedirs(self.output_dir, exist_ok=True)
            cropped_img.save(os.path.join(self.output_dir, file_name))
