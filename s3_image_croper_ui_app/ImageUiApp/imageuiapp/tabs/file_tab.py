from io import BytesIO
from pathlib import Path
import os

import streamlit as st
from PIL import Image, ImageDraw
import boto3
from botocore.exceptions import ClientError
import dotenv
import pyhere

dotenv.load_dotenv(pyhere.here("ImageUiApp/.env"))

# ---------- S3 config ----------
S3_BUCKET = os.getenv("S3_BUCKET")  # <-- change to your bucket
REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("REGION")

# Create a reusable S3 client
s3 = boto3.client("s3", region_name=REGION)


# ---------- Helper functions ----------


def load_image_from_upload(uploaded_file):
    """Load and verify an uploaded image, return (PIL.Image, error_message_or_None)."""
    try:
        data = uploaded_file.getvalue()
        img = Image.open(BytesIO(data))
        img.verify()  # validate
        img = Image.open(BytesIO(data))  # re-open for use
        img = img.convert("RGBA")
        return img, None
    except Exception as e:
        return None, str(e)


def create_overlay_preview(
    image: Image.Image, x: int, y: int, w: int, h: int
) -> Image.Image:
    """Return a copy of the image with a red rectangle drawn at (x, y, x+w, y+h)."""
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    box = (x, y, x + w, y + h)
    draw.rectangle(box, outline="red", width=3)
    return overlay


def _normalize_prefix(prefix: str) -> str:
    """
    Make sure prefix ends with exactly one '/' (or is empty).
    Used to build S3 keys like "<prefix>filename.png".
    """
    if not prefix:
        return ""
    return prefix.rstrip("/") + "/"


@st.cache_data(show_spinner="Loading image list...")
def list_saved_images(prefix: str):
    """
    Return a sorted list of S3 keys for images under the given prefix.
    Cached to avoid repeated S3 listings.
    """
    prefix = _normalize_prefix(prefix)
    try:
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    except ClientError as e:
        # no st.error in cached fn; propagate to caller
        raise RuntimeError(f"Could not list images from S3: {e}") from e

    if "Contents" not in resp:
        return []

    exts = {".png", ".jpg", ".jpeg"}
    keys = [
        obj["Key"]
        for obj in resp["Contents"]
        if Path(obj["Key"]).suffix.lower() in exts and not obj["Key"].endswith("/")
    ]
    keys.sort()
    return keys


def render_saved_images_section(prefix: str):
    """
    Render the saved images list + preview + delete button (S3-based).
    Uses cached list_saved_images, and clears cache on delete.
    """
    st.subheader("Saved images")

    try:
        saved_keys = list_saved_images(prefix)
    except RuntimeError as e:
        st.error(str(e))
        return

    if not saved_keys:
        st.info("No saved images found in the output folder yet.")
        return

    col_list, col_preview = st.columns([1, 2])

    # Show only the file name part in the selectbox, keep full key internally
    saved_names = [Path(k).name for k in saved_keys]

    with col_list:
        selected_saved_name = st.selectbox(
            "Saved images",
            saved_names,
            key="manage_saved_image_select",
        )

        selected_idx = saved_names.index(selected_saved_name)
        selected_key = saved_keys[selected_idx]

        delete_clicked = st.button(
            "🗑️ Delete selected", key="manage_delete_saved_button"
        )
        if delete_clicked:
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=selected_key)

                # S3 contents changed -> clear all cached data
                st.cache_data.clear()

                st.success(f"Deleted {selected_saved_name}")
                st.rerun()
            except ClientError as e:
                st.error(f"Failed to delete {selected_saved_name}: {e}")

    # Preview in the right column
    with col_preview:
        try:
            obj = s3.get_object(Bucket=S3_BUCKET, Key=selected_key)
            img_bytes = obj["Body"].read()
            img = Image.open(BytesIO(img_bytes))
            st.image(img, caption=selected_saved_name, use_container_width=True)
        except Exception as e:
            st.error(f"Could not open {selected_saved_name}: {e}")


# ---------- Main render function for tab 1 ----------


def render(
    uploaded_files,
    selected_name,
    selected_file,
    step: int,
    output_folder: str,  # S3 prefix, not Path
    crop_width: int,
    crop_height: int,
    resize_max_dim: int,  # max dimension for resizing
):
    """
    Render the 'Image management' tab:
    - cropping UI for the selected uploaded image
    - saved-images list + delete + preview (S3-based)
    """
    st.subheader("Manage & crop images")

    # --- Cropping UI (only if we have an uploaded file) ---
    if selected_file is None:
        st.info("Upload images in the sidebar to crop new ones.")
    else:
        # Load image
        img, err = load_image_from_upload(selected_file)
        if err or img is None:
            st.error(f"Failed to open image (invalid or corrupted?): {err}")
        else:
            # Intended crop size (before clamping to image size)
            desired_w, desired_h = crop_width, crop_height

            # --- optional downscaling ---
            # Rule: never resize so that either dimension becomes smaller
            # than the desired crop size.
            if resize_max_dim is not None and resize_max_dim > 0:
                longest_side = max(img.width, img.height)
                if longest_side > resize_max_dim:
                    scale = resize_max_dim / float(longest_side)
                    candidate_w = int(img.width * scale)
                    candidate_h = int(img.height * scale)

                    if candidate_w < desired_w or candidate_h < desired_h:
                        # Would break crop requirements: skip resize
                        st.info(
                            "Image is large, but cannot be downscaled to the "
                            f"requested max dimension ({resize_max_dim}px) "
                            "without becoming smaller than the crop area. "
                            "Keeping original resolution."
                        )
                    else:
                        img = img.resize(
                            (candidate_w, candidate_h),
                            Image.Resampling.LANCZOS,
                        )
                        st.info(
                            f"Image scaled down to {candidate_w} x {candidate_h} "
                            f"(max dimension {resize_max_dim}px)."
                        )
            # --------------------------------
            st.success(f"Loaded image: {img.width} x {img.height} pixels")

            # Effective crop size (never larger than the image)
            crop_w = min(desired_w, img.width)
            crop_h = min(desired_h, img.height)

            if crop_w < desired_w or crop_h < desired_h:
                st.warning(
                    f"Image is smaller than {desired_w}x{desired_h}. "
                    f"Using crop size {crop_w}x{crop_h} instead."
                )

            max_x = img.width - crop_w
            max_y = img.height - crop_h

            # Session state for position per image
            state_key = f"crop_state_{selected_name}"

            if state_key not in st.session_state:
                # Initialize centered
                st.session_state[state_key] = {
                    "x": max_x // 2 if max_x > 0 else 0,
                    "y": max_y // 2 if max_y > 0 else 0,
                    "img_w": img.width,
                    "img_h": img.height,
                    "crop_w": crop_w,
                    "crop_h": crop_h,
                }
            else:
                s = st.session_state[state_key]
                # Reset if image size or crop size changed
                if (
                    s["img_w"] != img.width
                    or s["img_h"] != img.height
                    or s["crop_w"] != crop_w
                    or s["crop_h"] != crop_h
                ):
                    st.session_state[state_key] = {
                        "x": max_x // 2 if max_x > 0 else 0,
                        "y": max_y // 2 if max_y > 0 else 0,
                        "img_w": img.width,
                        "img_h": img.height,
                        "crop_w": crop_w,
                        "crop_h": crop_h,
                    }

            s = st.session_state[state_key]
            x, y = s["x"], s["y"]

            # Movement buttons (centered layout)
            st.markdown("### Move crop area")

            # Row 1: Up button centered
            row1 = st.columns([1, 2, 1])
            with row1[1]:
                btn_up = st.button("⬆️ Up")

            # Row 2: Left / Center / Right
            row2 = st.columns([1, 2, 1])
            with row2[0]:
                btn_left = st.button("⬅️ Left")
            with row2[1]:
                btn_center = st.button("⏺ Center")
            with row2[2]:
                btn_right = st.button("➡️ Right")

            # Row 3: Down button centered
            row3 = st.columns([1, 2, 1])
            with row3[1]:
                btn_down = st.button("⬇️ Down")

            # Update position based on button clicks
            if btn_up:
                y = max(0, y - step)
            if btn_down:
                y = min(max_y, y + step)
            if btn_left:
                x = max(0, x - step)
            if btn_right:
                x = min(max_x, x + step)
            if btn_center:
                x = max_x // 2 if max_x > 0 else 0
                y = max_y // 2 if max_y > 0 else 0

            # Save back to session_state
            s["x"], s["y"] = x, y

            # Create overlay and crop
            overlay_img = create_overlay_preview(img, x, y, crop_w, crop_h)

            crop_box = (x, y, x + crop_w, y + crop_h)
            cropped_img = img.crop(crop_box)

            # Show original + crop preview
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Original with selection rectangle")
                st.image(overlay_img, use_container_width=True)

            with col2:
                st.subheader(f"Cropped preview ({crop_w} x {crop_h})")
                st.image(cropped_img, use_container_width=False)

            # Save cropped image to S3
            st.markdown("---")
            st.subheader("Save crop")

            save_clicked = st.button("Save cropped image")
            if save_clicked:
                base_name = Path(selected_file.name).stem
                save_name = f"{base_name}_crop_{x}_{y}_{crop_w}x{crop_h}.png"

                prefix = _normalize_prefix(output_folder)
                key = f"{prefix}{save_name}"

                try:
                    buf = BytesIO()
                    cropped_img.save(buf, format="PNG")
                    buf.seek(0)

                    s3.put_object(
                        Bucket=S3_BUCKET,
                        Key=key,
                        Body=buf.getvalue(),
                        ContentType="image/png",
                    )

                    # S3 contents changed -> clear cached data
                    st.cache_data.clear()

                    st.success(f"Saved cropped image to S3 key: {key}")
                except ClientError as e:
                    st.error(f"Failed to save cropped image to S3: {e}")

    # Saved images list + preview + delete
    st.markdown("---")
    render_saved_images_section(output_folder)
