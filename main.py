# main.py

import subprocess


def main():
    subprocess.run([
        "uvicorn",
        "antre.web_app.app:app",
        "--reload"
    ])


if __name__ == "__main__":
    main()