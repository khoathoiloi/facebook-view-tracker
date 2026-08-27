import sys
import os

# Khắc phục lỗi khi đóng gói PyInstaller ở chế độ --windowed (sys.stdout/stderr bị gán None)
class NullStream:
    def write(self, text):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False

if sys.stdout is None:
    sys.stdout = NullStream()
if sys.stderr is None:
    sys.stderr = NullStream()
if sys.stdin is None:
    sys.stdin = NullStream()

import uvicorn
import webbrowser
import threading
import time
from app.main import app

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
