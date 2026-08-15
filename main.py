# main.py

import subprocess


def main():
    subprocess.run([
        "uvicorn",
        "antre.web_app.app:app",
        "--reload",
        "--host", "0.0.0.0",
    ])


if __name__ == "__main__":
    main()