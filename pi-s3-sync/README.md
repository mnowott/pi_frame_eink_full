# pi-s3-sync

`pi-s3-sync` periodically syncs an S3 bucket **to a removable SD/USB drive** (if present)  
or **to `$HOME/s3_folder`** as a fallback, on a Raspberry Pi Zero 2W running Raspberry Pi OS Lite.

Additionally, if configured, it can **ensure the Pi is connected to a specific Wi-Fi network** (via `nmcli`) before syncing.

- Sync runs every **15 minutes** via a `systemd` timer.
- Configuration (AWS + Wi-Fi) is stored in a simple **`wifi.json`** file.
- The script is written to work well on a **headless** Pi.

---

## 1. How it works (high level)

Every 15 minutes, `systemd` runs `sync_s3_from_sd.py`. The script does:

1. **Find config location (`wifi.json`):**

   - Scan all mounted filesystems (from `/proc/mounts`) for a **`wifi.json` at the root**.
     - If found, that mount becomes the **base path** (e.g. `/media/usb0`), and the sync target will be `/media/usb0/s3_folder`.
   - If **no mounted filesystem** with `wifi.json` is found:
     - Use the home directory of the invoking user as base path.
     - When run by `systemd` (configured to run as `pi`), this is **`/home/pi`**.
     - So the fallback config path is `/home/pi/wifi.json`, and fallback sync target is `/home/pi/s3_folder`.

2. **Read `wifi.json`:**

   - Load AWS keys, bucket name, region. (if they are not provided we look for them in the env)
   - Optionally load Wi-Fi SSID + password.

3. **(Optional) Ensure Wi-Fi connection:**

   - If `wifi_name` and `wifi_password` are present:
     - Check the current connection using `nmcli`.
     - If already connected to that SSID → do nothing.
     - If not connected → try `nmcli dev wifi connect <ssid> password <password>`.

   > If `nmcli` / NetworkManager is not available or Wi-Fi config fails,  
   > the script **continues anyway** and attempts the S3 sync.

4. **Sync S3 → local folder:**

   - Using `aws s3 sync s3://<bucket> <base_path>/s3_folder`  
   - Credentials are passed via environment variables, taken from `wifi.json`.

---

## 2. `wifi.json` configuration

`wifi.json` is the **only configuration file**.  
The script looks for it in **this order**:

1. On any **mounted filesystem** at its **root**, e.g.:

   - `/media/usb0/wifi.json`
   - `/mnt/sdcard/wifi.json`

2. If none are found, as fallback: **`$HOME/wifi.json`**

   - For the `systemd` service (configured with `User=pi`), this is `/home/pi/wifi.json`.

### 2.1 Example `wifi.json`

On the external drive **(root folder)** **or** in `/home/pi/wifi.json` (fallback):

```json
{
  "aws_access_key_id": "AKIAEXAMPLE...",
  "aws_secret_access_key": "your-secret-key-here",
  "aws_region": "eu-central-1",
  "s3_bucket": "your-bucket-name-here",

  "wifi_name": "YourSSID",
  "wifi_password": "YourWifiPassword"
}
