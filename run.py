import os
import sys
import webbrowser
import threading
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from server.app import run_server, ensure_assets

def open_browser(port: int):
    time.sleep(1.0)
    webbrowser.open(f"http://127.0.0.1:{port}/")

def main():
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    print(f"==================================================")
    print(f"       MLP STORE SUITE II - IN-GAME MEMORY PATCHER")
    print(f"       Version: v4.0.0 (Pure Functional Runtime)")
    print(f"==================================================")
    print(f"Target Process: MyLittlePony_x64.exe")
    print(f"Web Interface:  http://127.0.0.1:{port}/")
    print(f"Press Ctrl+C to stop the server.\n")

    # Verify and auto-extract portrait assets if needed
    ensure_assets(PROJECT_DIR)

    # Start browser opener in background thread
    t = threading.Thread(target=open_browser, args=(port,), daemon=True)
    t.start()

    run_server(port)

if __name__ == "__main__":
    main()
