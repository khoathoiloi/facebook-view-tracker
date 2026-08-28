import sys
import os
import io
import socket
import webbrowser
import threading
import time
import traceback
import ctypes

def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
LOG_PATH = os.path.join(BASE_DIR, "tracker.log")

# Setup robust stdout/stderr redirection for PyInstaller --windowed
class FileOrNullStream:
    def __init__(self, filepath):
        self.filepath = filepath
        self.encoding = "utf-8"
        self.errors = "ignore"
    def write(self, text):
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass
    def flush(self):
        pass
    def isatty(self):
        return False
    def fileno(self):
        raise io.UnsupportedOperation("fileno not supported")

if sys.stdout is None:
    sys.stdout = FileOrNullStream(LOG_PATH)
if sys.stderr is None:
    sys.stderr = FileOrNullStream(LOG_PATH)
if sys.stdin is None:
    sys.stdin = io.StringIO()

def find_available_port(start_port: int = 8000, max_port: int = 8050) -> int:
    """Tự động dò tìm cổng mạng còn trống để tránh xung đột cổng 8000."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def open_browser(port: int):
    time.sleep(1.2)
    webbrowser.open(f"http://127.0.0.1:{port}")

if __name__ == "__main__":
    try:
        import uvicorn
        from app.main import app

        port = find_available_port(8000)
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=port, log_config=None)
    except Exception as e:
        err_msg = traceback.format_exc()
        crash_log = os.path.join(BASE_DIR, "crash_error.log")
        try:
            with open(crash_log, "w", encoding="utf-8") as f:
                f.write(err_msg)
            if hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'user32'):
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Ứng dụng gặp lỗi khi khởi động:\n\n{str(e)}\n\nChi tiết xem trong file:\n{crash_log}",
                    "Lỗi khởi động - Facebook View Tracker",
                    0x10
                )
        except Exception:
            pass
        sys.exit(1)

