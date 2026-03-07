from pathlib import Path

import streamlit as st
from tabs import info_tab, file_tab, view_tab, downloads_tab
import socket

# === CONFIG ===
CROP_WIDTH = 800
CROP_HEIGHT = 480


def has_internet(timeout: float = 3.0) -> bool:
    """
    Check if we have (likely) internet access by trying to open a TCP
    connection to Google's public DNS server (8.8.8.8) on port 53.

    This avoids DNS lookup and is a common, lightweight connectivity check.
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        return True
    except OSError:
        return False


st.set_page_config(
    page_title=f"Fanimly eInk Frame Image Cropper {CROP_HEIGHT}x{CROP_WIDTH}",
    page_icon="🖼️",
    layout="wide",
)

st.title(f"Local Image Cropper ({CROP_WIDTH} x {CROP_HEIGHT})")
st.write(
    "Upload an image, move the fixed-size selection with buttons, "
    "save crops, and manage/view saved images."
)

# ---------- Connectivity status ----------

online = has_internet()

status_col1, status_col2 = st.columns([1, 4])
with status_col1:
    if online:
        st.success("Internet: online")
    else:
        st.error("Internet: offline")
with status_col2:
    if not online:
        st.write(
            "Tabs **Image management** and **View** are disabled until an "
            "internet connection is available."
        )

# ---------- Sidebar: uploads, movement settings, output folder ----------

st.sidebar.header("Upload Images")
uploaded_files = st.sidebar.file_uploader(
    "Choose PNG/JPG images from your computer",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

if uploaded_files:
    names = [f.name for f in uploaded_files]
    selected_name = st.sidebar.selectbox(
        "Select image to edit",
        names,
        key="uploaded_image_select",
    )
    selected_file = uploaded_files[names.index(selected_name)]
else:
    selected_name = None
    selected_file = None  # type: ignore[assignment]

st.sidebar.header("Move Selection")
step = st.sidebar.number_input(
    "Step size (pixels)",
    min_value=1,
    max_value=500,
    value=20,
)

st.sidebar.header("Image resize")
max_dim = st.sidebar.slider(
    "Max dimension for processing (px)",
    min_value=500,
    max_value=4000,
    value=2000,  # default: 2000
    step=100,
    help=(
        "If the uploaded image is larger than this, it will be scaled down "
        "so that its longest side is at most this many pixels, keeping aspect ratio."
    ),
)

# no need for Path here anymore for S3
st.sidebar.header("Output folder / S3 prefix")

# e.g. "output" or "my-user/output"
output_folder = "images"

# ---------- Tabs ----------

tab_info, tab_manage, tab_view, tab_dl = st.tabs(
    ["Info", "Image management", "View", "Downloads"]
)

with tab_info:
    if not online:
        st.info(
            "🚫 No internet connection detected.\n\n"
            "Image management is temporarily disabled. "
            "Please connect to the internet and rerun."
        )
    else:
        info_tab.render()
with tab_manage:
    file_tab.render(
        uploaded_files=uploaded_files,
        selected_name=selected_name,
        selected_file=selected_file,
        step=step,
        output_folder=output_folder,
        crop_width=CROP_WIDTH,
        crop_height=CROP_HEIGHT,
        resize_max_dim=max_dim,  # NEW
    )

with tab_view:
    if not online:
        st.info(
            "🚫 No internet connection detected.\n\n"
            "Viewing saved images is temporarily disabled. "
            "Please connect to the internet and rerun."
        )
    else:
        view_tab.render(
            output_folder=output_folder,
        )
with tab_dl:
    if not online:
        st.info(
            "🚫 No internet connection detected.\n\n"
            "Image management is temporarily disabled. "
            "Please connect to the internet and rerun."
        )
    else:
        downloads_tab.render(
            output_folder=None,
            online=online,
        )
