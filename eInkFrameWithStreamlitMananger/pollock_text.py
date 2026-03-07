import math
import random
import sys
import socket
import json
import os
import datetime
from datetime import datetime, timezone

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------- BASE CONFIG ----------

BASE_WIDTH, BASE_HEIGHT = 800, 480
SCALE = 1  # supersampling factor

WIDTH, HEIGHT = BASE_WIDTH * SCALE, BASE_HEIGHT * SCALE
OUTPUT_FILE = "text.png"   # change this to point into messages/ if you like

SCRIPT_DIR = Path(__file__).resolve().parent

# ---------- SETTINGS CONFIG ----------

from settings_loader import load_settings as _shared_load_settings, DEFAULT_SETTINGS


# ---------- RUNTIME HELPERS ----------

def has_internet(timeout: float = 3.0) -> bool:
    """Check if we likely have internet access via TCP to 8.8.8.8:53."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        return True
    except OSError:
        return False


def load_settings() -> dict:
    return _shared_load_settings(caller="pollock_text")


def summarize_settings(settings: dict) -> str:
    """
    Turn the settings dict into a short human-readable summary string
    for embedding into the status text.
    """
    mode = settings.get("picture_mode", DEFAULT_SETTINGS["picture_mode"])
    interval = settings.get("change_interval_minutes", DEFAULT_SETTINGS["change_interval_minutes"])
    s3_folder = settings.get("s3_folder", DEFAULT_SETTINGS["s3_folder"])

    quiet = settings.get("stop_rotation_between")
    if quiet and isinstance(quiet, dict):
        evening = quiet.get("evening", "?")
        morning = quiet.get("morning", "?")
        quiet_str = f"{evening}–{morning}"
    else:
        quiet_str = "off"

    parts = [
        f"mode={mode}",
        f"interval={interval}min",
        # f"s3={s3_folder}",
        # f"quiet={quiet_str}",
    ]
    summary = ", ".join(parts)

    if "_error" in settings:
        summary += f" (settings error: {settings['_error']})"

    return summary


def build_status_text() -> str:
    """
    Build the dynamic text to render into the Pollock card.
    """
    online = has_internet()
    hostname = socket.gethostname()
    settings = load_settings()
    settings_summary = summarize_settings(settings)

    internet_line = "Internet active." if online else "Internet offline."
    settings_line = f"Current settings: {settings_summary}"
    change_line = f"Change settings unter http://{hostname}/ in the browser."

    # Use explicit newlines so our wrapper keeps the structure
    return f"{internet_line}\n{settings_line}\n{change_line}"


# ---------- POLLOCK-STYLE BACKGROUND ----------

palettes = {
    "early_morning": [  # soft, cool, slightly muted
        (12, 16, 30),     # deep pre-dawn blue
        (220, 225, 235),  # soft misty gray
        (90, 120, 180),   # cool sky blue
        (230, 180, 160),  # pale peach sunrise
        (170, 190, 210),  # cool light blue-gray
        (120, 145, 135),  # muted teal/green
    ],

    "late_morning": [  # bright, clear, higher contrast
        (20, 30, 60),    # deep blue shadow
        (240, 245, 250), # bright daylight white
        (70, 130, 200),  # vivid sky blue
        (240, 190, 80),  # warm sunlight yellow
        (80, 160, 110),  # fresh green
        (200, 90, 80),   # warm brick/red accent
    ],

    "afternoon_golden": [  # warm, golden, slightly richer
        (30, 25, 45),    # deep muted violet/blue shadow
        (245, 235, 220), # warm light cream
        (80, 110, 170),  # softened sky blue
        (230, 170, 70),  # golden hour orange
        (200, 110, 70),  # warm terracotta
        (120, 150, 90),  # sunlit olive/green
    ],

    "evening_night": [  # deep, moody, with a few “neon” accents
        (8, 10, 25),     # near-black navy
        (220, 225, 235), # cool pale gray highlight
        (40, 70, 140),   # deep blue
        (180, 60, 80),   # muted magenta/red accent
        (240, 190, 90),  # warm lamp light
        (60, 140, 120),  # deep teal accent
    ],
}


def get_time_of_day_palette(now: datetime | None = None):
    """
    Pick a palette based on the current local time.
    """
    if now is None:
        now = datetime.now()

    h = now.hour

    if 4 <= h < 8:
        key = "early_morning"
    elif 8 <= h < 12:
        key = "late_morning"
    elif 12 <= h < 18:
        key = "afternoon_golden"
    else:
        key = "evening_night"

    return palettes[key]


def pollock_background(width, height, scale):
    """
    Create a Pollock-like splatter painting background.

    Uses a time-of-day dependent color palette so the mood changes
    over the day.
    """
    # Light base (kept neutral so the card text stays readable)
    base = Image.new("RGB", (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(base)

    # Pick palette for current time of day
    palette = get_time_of_day_palette()

    random.seed(int(datetime.now(timezone.utc).second))

    # ---- Long splatter strokes with modulated width ----
    num_strokes = 2000
    for _ in range(num_strokes):
        color = random.choice(palette)

        max_width = random.randint(6 * scale, 20 * scale)
        min_width = max(1 * scale, int(max_width * random.uniform(0.2, 0.6)))

        length = random.randint(width // 4, int(width * 1.2))
        x0 = random.randint(-width // 4, width + width // 4)
        y0 = random.randint(-height // 4, height + height // 4)

        points = [(x0, y0)]
        steps = random.randint(3, 8)
        direction = random.choice([-1, 1])

        for s in range(1, steps + 1):
            dx = (length / steps) * s * direction * random.uniform(0.7, 1.3)
            dy = random.uniform(-0.3, 0.3) * (length / 4)
            x = x0 + dx
            y = y0 + dy
            points.append((x, y))

        n_seg = len(points) - 1
        if n_seg <= 0:
            continue

        for i in range(n_seg):
            t = i / max(1, n_seg - 1)
            thickness_factor = math.sin(math.pi * t)
            width_t = int(min_width + (max_width - min_width) * thickness_factor)
            width_t = max(1, width_t)

            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            draw.line([(x1, y1), (x2, y2)], fill=color, width=width_t)

    # ---- Small splatter dots ----
    num_dots = 300
    for _ in range(num_dots):
        color = random.choice(palette)
        r = random.randint(1 * scale, 5 * scale)
        x = random.randint(-r, width + r)
        y = random.randint(-r, height + r)
        bbox = [x - r, y - r, x + r, y + r]
        draw.ellipse(bbox, fill=color)

    base = base.filter(ImageFilter.GaussianBlur(radius=1 * scale))
    return base


# ---------- TEXT HELPERS ----------

# Prefer absolute font paths on Raspberry Pi so size REALLY changes.
FONT_CANDIDATES = [
    # 1) Optional project-local font (if you want to drop a TTF into ./fonts/)
    SCRIPT_DIR / "fonts" / "DejaVuSans.ttf",

    # 2) Common system paths on Raspberry Pi OS
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),

    # 3) Name-only fallbacks (searched via fontconfig)
    Path("DejaVuSans.ttf"),
    Path("DejaVuSans-Bold.ttf"),
    Path("DejaVuSerif.ttf"),
    Path("Times New Roman.ttf"),
    Path("Times.ttf"),
    Path("Georgia.ttf"),
]


def get_text_size(draw, text, font):
    if hasattr(draw, "textbbox"):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    else:
        return draw.textsize(text, font=font)


def wrap_text_to_lines(draw, text, font, max_width):
    """
    Wrap text into multiple lines so that each line fits max_width.
    Respects explicit newlines as paragraph breaks.
    """
    paragraphs = text.split("\n")
    lines = []

    for para in paragraphs:
        words = para.split()
        if not words:
            lines.append("")
            continue

        current_line = words[0]
        for word in words[1:]:
            test_line = current_line + " " + word
            w, _ = get_text_size(draw, test_line, font)
            if w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

    return lines


def load_classy_font(size):
    """
    Try to load a serif/sans font from known paths.
    Falls back to default if absolutely nothing is found.
    """
    last_error = None
    for path in FONT_CANDIDATES:
        path_str = str(path)
        try:
            font = ImageFont.truetype(path_str, size)
            print(f"[pollock_text] Using TTF font '{path_str}' size={size}")
            return font
        except IOError as e:
            # Only log for existing files or first few candidates to avoid spam
            if isinstance(path, Path) and path.exists():
                print(f"[pollock_text] Found font file but could not load '{path_str}': {e}")
            last_error = e
            continue

    # Fallback – but default font ignores size, so log loudly.
    print(f"[pollock_text] WARNING: Falling back to PIL default bitmap font. "
          f"Font size changes will NOT be visible. Last error: {last_error}")
    return ImageFont.load_default()


def draw_centered_text_on_white_card(img, text, scale):
    """
    Draw wrapped multi-line text on a white rounded rectangle
    centered on the image.

    This version makes the text large, using much of the available area,
    but with font sizes reduced by ~4x compared to the previous version.
    """
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Let the card use almost the full display
    max_card_width = int(width * 0.99)
    max_card_height = int(height * 0.99)

    # -------- FONT SIZE RANGE (4x smaller than before) --------
    raw_max = int(height * 0.40) * scale
    raw_min = int(height * 0.10) * scale

    max_font_size = max(3 * scale, raw_max // 4)
    min_font_size = max(2 * scale, raw_min // 4)
    # ----------------------------------------------------------

    chosen = None

    # Try decreasing font sizes until the text fits into our max_card_height
    for font_size in range(max_font_size, min_font_size - 1, -2 * scale):
        font = load_classy_font(font_size)

        # Allow text to go almost edge-to-edge
        max_text_width = int(width * 0.97)
        lines = wrap_text_to_lines(draw, text, font, max_text_width)
        line_sizes = [get_text_size(draw, line, font) for line in lines]

        if not line_sizes:
            continue

        max_line_width = max(w for w, _ in line_sizes)

        # Tight spacing and padding
        line_spacing = int(font_size * 0.10)
        padding_x = int(font_size * 0.25)
        padding_y = int(font_size * 0.20)

        total_text_height = (
            sum(h for _, h in line_sizes)
            + (len(line_sizes) - 1) * line_spacing
        )

        card_width = min(max_line_width + 2 * padding_x, max_card_width)
        card_height = total_text_height + 2 * padding_y

        if card_height <= max_card_height:
            chosen = (
                font,
                lines,
                line_sizes,
                card_width,
                card_height,
                padding_x,
                padding_y,
                line_spacing,
                font_size,
            )
            break

    # If even the smallest font doesn't fit, truncate with "..."
    if chosen is None:
        font_size = min_font_size
        font = load_classy_font(font_size)
        max_text_width = int(width * 0.97)
        all_lines = wrap_text_to_lines(draw, text, font, max_text_width)

        line_spacing = int(font_size * 0.10)
        padding_x = int(font_size * 0.25)
        padding_y = int(font_size * 0.20)

        lines = []
        line_sizes = []
        total_text_height = 0

        for line in all_lines:
            w, h = get_text_size(draw, line, font)
            projected = total_text_height + (line_spacing if lines else 0) + h
            if projected + 2 * padding_y > max_card_height:
                if lines:
                    last = lines[-1].rstrip(".")
                    if not last.endswith("..."):
                        last = (last + "...") if last else "..."
                    lines[-1] = last
                    line_sizes[-1] = get_text_size(draw, lines[-1], font)
                else:
                    lines = ["..."]
                    line_sizes = [get_text_size(draw, "...", font)]
                break

            if lines:
                total_text_height += line_spacing
            total_text_height += h
            lines.append(line)
            line_sizes.append((w, h))

        if not lines:
            lines = [""]
            line_sizes = [get_text_size(draw, "", font)]
            total_text_height = line_sizes[0][1]

        max_line_width = max(w for w, _ in line_sizes)
        card_width = min(max_line_width + 2 * padding_x, max_card_width)
        card_height = total_text_height + 2 * padding_y

        chosen = (
            font,
            lines,
            line_sizes,
            card_width,
            card_height,
            padding_x,
            padding_y,
            line_spacing,
            font_size,
        )

    (
        font,
        lines,
        line_sizes,
        card_width,
        card_height,
        padding_x,
        padding_y,
        line_spacing,
        used_font_size,
    ) = chosen

    print(f"[pollock_text] Final chosen font size: {used_font_size}, "
          f"lines={len(lines)}, card={card_width}x{card_height}")

    card_left = (width - card_width) // 2
    card_top = (height - card_height) // 2
    card_right = card_left + card_width
    card_bottom = card_top + card_height

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(overlay)

    border_color = (220, 220, 225, 255)
    radius = 30 * scale

    if hasattr(o_draw, "rounded_rectangle"):
        o_draw.rounded_rectangle(
            [card_left, card_top, card_right, card_bottom],
            radius=radius,
            fill=(255, 255, 255, 255),
            outline=border_color,
            width=3 * scale,
        )
    else:
        o_draw.rectangle(
            [card_left, card_top, card_right, card_bottom],
            fill=(255, 255, 255, 255),
            outline=border_color,
            width=3 * scale,
        )

    current_y = card_top + padding_y
    text_color = (40, 40, 50, 255)

    for (line, (w, h)) in zip(lines, line_sizes):
        x_line = card_left + (card_width - w) // 2
        o_draw.text((x_line, current_y), line, font=font, fill=text_color)
        current_y += h + line_spacing

    img.alpha_composite(overlay)


def generate_status_image(custom_text: str | None = None) -> Image.Image:
    """
    Build the Pollock-style status image as a PIL.Image object.

    If custom_text is None, it uses build_status_text().
    """
    if custom_text is None:
        text = build_status_text()
    else:
        text = custom_text

    # 1) Create Pollock-style background at high res
    bg = pollock_background(WIDTH, HEIGHT, SCALE).convert("RGBA")

    # 2) Draw centered text on a white card
    draw_centered_text_on_white_card(bg, text, SCALE)

    # 3) Downscale to final display resolution
    final = bg.resize((BASE_WIDTH, BASE_HEIGHT), resample=Image.LANCZOS)
    return final


# ---------- MAIN ----------

def main():
    # If you pass text on the command line, use that; otherwise build
    # the dynamic Pi status string.
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = build_status_text()

    final = generate_status_image(custom_text=text)
    final.save(OUTPUT_FILE, "PNG")
    print(f"Saved status image to {OUTPUT_FILE} with text:\n{text}")


if __name__ == "__main__":
    main()
