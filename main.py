# main.py

import subprocess
import sys


def main():
    # Use the current Python executable to run uvicorn as a module so
    # the project's virtualenv interpreter is used even when uvicorn
    # isn't on PATH.
    subprocess.run([
        sys.executable,
        "-m",
        "uvicorn",
        "antre.web_app.app:app",
        "--host",
        "0.0.0.0",
    ])


if __name__ == "__main__":
    main()