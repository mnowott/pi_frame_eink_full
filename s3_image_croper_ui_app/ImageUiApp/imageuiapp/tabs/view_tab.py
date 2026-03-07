from pathlib import Path
from io import BytesIO

import streamlit as st
from PIL import Image
import boto3
from botocore.exceptions import ClientError
import dotenv
import pyhere
import os

dotenv.load_dotenv(pyhere.here("ImageUiApp/.env"))

# ---------- S3 config ----------
S3_BUCKET = os.getenv("S3_BUCKET")       # <-- change to your bucket
REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("REGION")

s3 = boto3.client("s3", region_name=REGION)


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix.rstrip("/") + "/"


@st.cache_data(show_spinner="Loading image list...")
def list_saved_images(prefix: str):
    """
    Return a sorted list of S3 keys in the given prefix.
    This result is cached to avoid repeatedly listing S3.
    """
    prefix = _normalize_prefix(prefix)
    try:
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    except ClientError as e:
        # Cannot st.error here, because cached funcs should be pure.
        # Just re-raise and handle in the caller.
        raise RuntimeError(f"Could not list images from S3: {e}") from e

    if "Contents" not in resp:
        return []

    exts = {".png", ".jpg", ".jpeg"}
    keys = [
        obj["Key"]
        for obj in resp["Contents"]
        if Path(obj["Key"]).suffix.lower() in exts
           and not obj["Key"].endswith("/")
    ]
    keys.sort()
    return keys


@st.cache_data(show_spinner="Loading image...")
def load_image_bytes_from_s3(key: str) -> bytes:
    """
    Return raw image bytes for a given S3 key.
    Cached so repeated viewing of the same image is fast.
    """
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return obj["Body"].read()
    except ClientError as e:
        raise RuntimeError(f"Could not load image from S3: {e}") from e


def render_saved_images_view(prefix: str):
    """
    Render the saved images list + preview (view-only) from S3.
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

    saved_names = [Path(k).name for k in saved_keys]

    with col_list:
        selected_saved_name = st.selectbox(
            "Saved images",
            saved_names,
            key="view_saved_image_select",
        )

        selected_idx = saved_names.index(selected_saved_name)
        selected_key = saved_keys[selected_idx]

    # Preview in the right column
    with col_preview:
        try:
            img_bytes = load_image_bytes_from_s3(selected_key)
            img = Image.open(BytesIO(img_bytes))
            st.image(img, caption=selected_saved_name, use_container_width=True)
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Could not open {selected_saved_name}: {e}")


def render(output_folder: str):
    """Render the 'View' tab (S3-based)."""
    st.subheader("View saved images")
    render_saved_images_view(output_folder)
