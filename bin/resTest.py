import subprocess
from pathlib import Path
import argparse

def capture_libcamera(path: Path, resolution: str) -> bool:
    try:
        width, height = resolution.lower().split("x")
    except Exception:
        print(f"[WARN] Invalid resolution format '{resolution}', defaulting to 1920x1080")
        width, height = "1920", "1080"

    cmd = [
        "libcamera-still",
        "--autofocus-mode", "auto",
        "--autofocus-range", "normal",
        "--lens-position", "0.0",
        "--width", width,
        "--height", height,
        "--timeout", "3000",
        "-o", str(path)
    ]

    print(f"[INFO] Testing resolution: {width}x{height}")
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test libcamera-still capture with a given resolution")
    parser.add_argument("resolution", nargs="?", default="1920x1080", help="Resolution (e.g., 1640x922)")
    parser.add_argument("-o", "--output", type=Path, default=Path("/tmp/test_capture.jpg"), help="Output file path")

    args = parser.parse_args()
    success = capture_libcamera(args.output, args.resolution)

    if success:
        print(f"[SUCCESS] Capture succeeded at {args.resolution}")
        print(f"→ Saved to: {args.output}")
    else:
        print(f"[FAIL] Capture failed at {args.resolution}")
