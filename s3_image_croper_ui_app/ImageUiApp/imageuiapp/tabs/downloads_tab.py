# tabs/download_tab.py
from io import BytesIO
from pathlib import Path
import zipfile
from datetime import datetime, timezone

import streamlit as st
import boto3
from botocore.exceptions import ClientError
import os

# ---------- S3 config ----------
S3_BUCKET = os.getenv("S3_BUCKET")       # <-- change to your bucket
REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("REGION")

s3 = boto3.client("s3", region_name=REGION)


def _normalize_prefix(prefix: str) -> str:
    """
    Make sure prefix ends with exactly one '/' (or is empty).
    Used to build S3 keys like "<prefix>filename.png".
    """
    if not prefix or len(prefix) == 0:
        return ""
    return prefix.rstrip("/") + "/"


@st.cache_data(show_spinner="Listing images for ZIP...")
def list_s3_objects(prefix: str):
    """
    Return a list of all S3 keys under a prefix.
    Cached to avoid repeated S3 listings.
    """
    prefix = _normalize_prefix(prefix)
    try:
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    except ClientError as e:
        raise RuntimeError(f"Could not list images from S3: {e}") from e

    if "Contents" not in resp:
        return []

    keys = [obj["Key"] for obj in resp["Contents"] if not obj["Key"].endswith("/")]
    keys.sort()
    return keys


def create_zip_upload_and_get_url(prefix: str, expires_in: int = 3600) -> str:
    """
    Create a ZIP archive in memory containing all S3 objects under `prefix`,
    upload it to S3, and return a pre-signed URL for downloading the ZIP.

    expires_in: seconds until the pre-signed URL expires (default: 1 hour).
    """
    keys = list_s3_objects(prefix)
    if not keys:
        raise RuntimeError("No S3 objects found under this prefix to ZIP.")

    normalized_prefix = _normalize_prefix(prefix)
    buf = BytesIO()

    # Build the ZIP in memory
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key in keys:
            try:
                obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
                data = obj["Body"].read()

                # Store paths inside the ZIP without the prefix
                if normalized_prefix and key.startswith(normalized_prefix):
                    arcname = key[len(normalized_prefix) :]
                else:
                    arcname = key

                zf.writestr(arcname, data)
            except ClientError as e:
                # Skip problematic objects but log/show something
                st.warning(f"Skipping {key}: {e}")

    buf.seek(0)
    zip_bytes = buf.getvalue()

    # Choose a key to store the ZIP in S3.
    # Example: "zips/output_20250101_120000UTC.zip"
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%SUTC")

    safe_prefix = prefix.strip().replace("/", "_") or "root"
    zip_key = f"zips/{safe_prefix}_{ts}.zip"

    # Upload ZIP to S3
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=zip_key,
            Body=zip_bytes,
            ContentType="application/zip",
        )
    except ClientError as e:
        raise RuntimeError(f"Could not upload ZIP to S3: {e}") from e

    # Generate pre-signed URL
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": zip_key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise RuntimeError(f"Could not create pre-signed URL: {e}") from e

    return url


def render_wifi_download_section():
    st.markdown("### Download Wi-Fi configuration")

    wifi_path = Path(__file__).parent.parent / "data" /"wifi.json"

    try:
        wifi_bytes = wifi_path.read_bytes()
        st.download_button(
            label="📥 Download wifi.json",
            data=wifi_bytes,
            file_name="wifi.json",
            mime="application/json",
        )
    except FileNotFoundError:
        st.error("wifi.json not found in the repository root/data.")
    except Exception as e:
        st.error(f"Error reading wifi.json: {e}")


def render_s3_zip_section(output_folder: str, online: bool):
    st.markdown("### Generate pre-signed ZIP link for S3 images")

    if not online:
        st.info(
            "🚫 No internet connection detected.\n\n"
            "Cannot access S3 to create the ZIP archive."
        )
        return

    if "s3_zip_url" not in st.session_state:
        st.session_state["s3_zip_url"] = None

    generate = st.button("🧩 Create pre-signed ZIP link")

    if generate:
        try:
            url = create_zip_upload_and_get_url(output_folder, expires_in=3600)
            st.session_state["s3_zip_url"] = url
            st.success("Pre-signed ZIP link created.")
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Failed to create ZIP archive: {e}")

    if st.session_state.get("s3_zip_url"):
        st.markdown(
            f"[📦 Download S3 images ZIP]({st.session_state['s3_zip_url']})  \n"
            "_Link valid for 1 hour._"
        )


def render(output_folder: str|None, online: bool):
    """Render the 'Download' tab."""
    st.subheader("Downloads")
    if output_folder is None:
        output_folder = ""
    # wifi.json is local, always available if the file exists
    render_wifi_download_section()

    st.markdown("---")

    # S3 ZIP -> pre-signed URL
    render_s3_zip_section(output_folder=output_folder, online=online)
