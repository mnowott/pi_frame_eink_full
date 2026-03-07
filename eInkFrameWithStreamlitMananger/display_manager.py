import os
import sys
import time
import random
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.join(SCRIPT_DIR, 'lib')

# Make sure the Waveshare lib is importable
if LIB_PATH not in sys.path:
    sys.path.append(LIB_PATH)

from lib.waveshare_epd import epd7in3f

# Robust import of pollock_text
try:
    import pollock_text
except Exception as e:
    pollock_text = None
    print(f"Warning: could not import pollock_text: {e}")


class DisplayManager:
    """
    Class to manage the display of images on the e-Paper screen.
    """

    def __init__(self, image_folder, refresh_time):
        """
        Initializes the display using the epd7in3f library.
        Sets the rotation and refresh time for the display.
        Initializes the last display time and selected image to None.
        """
        self.last_display_time = time.time()
        self.last_selected_image = None
        self.image_folder = image_folder
        self.rotation = 0
        self.refresh_time = refresh_time
        self.epd = epd7in3f.EPD()
        self.epd.init()
        self.stop_display = False

    # ---------- INTERNAL HELPERS ----------

    def _display_pil_image(self, img: Image.Image):
        """
        Internal helper: rotate (if needed) and send a PIL image to the panel.
        """
        # Rotate image if required
        if self.rotation:
            img = img.rotate(self.rotation)

        # For 7in3f, epd.getbuffer usually accepts RGB / 1-bit or palette images.
        # If your pollock output is RGBA, convert to RGB.
        if img.mode == "RGBA":
            img = img.convert("RGB")

        self.epd.display(self.epd.getbuffer(img))

    # ---------- IMAGE ROTATION LOGIC ----------

    # Fetches the image files from the specified folder.
    def fetch_image_files(self):
        return [f for f in os.listdir(self.image_folder)]

    # Selects a random image from the list of images.
    def select_random_image(self, images):
        # If one image or less
        if len(images) <= 1:
            return images[0]

        # Select a random image unless it was previously selected
        random_image = random.choice(
            [img for img in images if img != self.last_selected_image]
        )
        return random_image

    # Continuously loop to display a random image from the specified folder at the specified refresh time.
    def display_images(self):
        self.stop_display = False

        images = self.fetch_image_files()

        if not images:
            print("No images found, displaying default image.")
            # If pollock_text is available, use a dynamic Pollock status;
            # otherwise fall back to a static message image.
            if pollock_text is not None:
                self.display_pollock_status('no_valid_images.jpg')
            else:
                self.display_message('no_valid_images.jpg')
            return

        random_image = self.select_random_image(images)
        self.last_selected_image = random_image

        # Open and display the image
        with Image.open(os.path.join(self.image_folder, random_image)) as pic:
            print(f"Displaying image: {random_image}")
            self._display_pil_image(pic)
            self.last_display_time = time.time()

        while not self.stop_display:
            current_time = time.time()
            elapsed_time = current_time - self.last_display_time

            if elapsed_time >= self.refresh_time:
                images = self.fetch_image_files()
                if not images:
                    print("No images found during rotation, showing Pollock or fallback.")
                    if pollock_text is not None:
                        self.display_pollock_status('no_valid_images.jpg')
                    else:
                        self.display_message('no_valid_images.jpg')
                    return

                random_image = self.select_random_image(images)
                self.last_selected_image = random_image

                # Open and display the image
                with Image.open(os.path.join(self.image_folder, random_image)) as pic:
                    print(f"Displaying new image: {random_image}")
                    self._display_pil_image(pic)
                    self.last_display_time = time.time()
            time.sleep(1.0)  # throttle to save cpu usage

    # ---------- MESSAGE / STATUS SCREENS ----------

    def display_message(self, message_file):
        """
        Display a static image from the messages/ folder.
        """
        msg_path = os.path.join(SCRIPT_DIR, "messages", message_file)
        with Image.open(msg_path) as img_start:
            self._display_pil_image(img_start)

    def display_pollock_status(self, text=None):
        """
        Display a Pollock-style status card with time-of-day palette and
        auto-shrinking text (handled in pollock_text.generate_status_image).

        :param text: Optional custom text. If None, the dynamic status text
                     from pollock_text.build_status_text is used.
        """
        if pollock_text is None:
            print("pollock_text not available, cannot display Pollock status.")
            # Fall back to a default static message if you want:
            self.display_message('no_valid_images.jpg')
            return

        status_img = pollock_text.generate_status_image(custom_text=text)
        self._display_pil_image(status_img)


# ---------- CLI TEST HARNESS / __main__ ----------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Simple eInk test tool using DisplayManager."
    )
    parser.add_argument(
        "--image-folder",
        "-f",
        default=os.path.join(SCRIPT_DIR, "pic"),
        help="Folder with images for --slideshow (default: ./pic).",
    )
    parser.add_argument(
        "--refresh",
        "-r",
        type=int,
        default=60,
        help="Refresh time in seconds for --slideshow (default: 60).",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--pollock",
        "-p",
        nargs="?",
        const="",
        help="Show a Pollock status card. Optional custom text as argument.",
    )
    mode_group.add_argument(
        "--message",
        "-m",
        help="Show a single image from messages/ by filename, e.g. start.jpg.",
    )
    mode_group.add_argument(
        "--slideshow",
        "-s",
        action="store_true",
        help="Run a slideshow from --image-folder.",
    )

    args = parser.parse_args()

    dm = DisplayManager(image_folder=args.image_folder, refresh_time=args.refresh)

    if args.pollock is not None:
        # If user gave a string, use it; if just --pollock with no value, use default text
        custom_text = args.pollock if args.pollock != "" else "Test Pollock card"
        print(f"[display_manager] Showing Pollock card with text: {custom_text!r}")
        dm.display_pollock_status(text=custom_text)

    elif args.message:
        print(f"[display_manager] Showing message image from messages/: {args.message}")
        dm.display_message(args.message)

    elif args.slideshow:
        print(
            f"[display_manager] Starting slideshow from {args.image_folder} "
            f"with refresh={args.refresh}s"
        )
        dm.display_images()

    else:
        # Default: simple Pollock test
        print("[display_manager] No mode specified, defaulting to Pollock test.")
        dm.display_pollock_status(text="Pollock test image")
