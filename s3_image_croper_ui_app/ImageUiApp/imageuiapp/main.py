import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8501)
    # Default to localhost: when running behind a reverse proxy (Caddy on EC2),
    # only the proxy should be exposed publicly. Pass --address 0.0.0.0 to
    # bind all interfaces for local dev or non-proxied setups.
    parser.add_argument("--address", default="127.0.0.1")
    args = parser.parse_args()

    app_path = Path(__file__).resolve().parent / "app.py"
    subprocess.run(
        [
            "streamlit",
            "run",
            str(app_path),
            "--server.port",
            str(args.port),
            "--server.address",
            args.address,
        ],
        check=True,
    )
