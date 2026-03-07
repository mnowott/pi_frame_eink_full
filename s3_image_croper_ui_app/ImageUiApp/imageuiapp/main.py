import argparse
import subprocess
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--address", default="0.0.0.0")
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
