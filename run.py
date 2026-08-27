import uvicorn
import webbrowser
import threading
import time
from app.main import app

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("==================================================================")
    print("   FACEBOOK VIEW TRACKER & ANALYTICS (NO-TOKEN ENTERPRISE)")
    print("   Website: http://127.0.0.1:8000")
    print("==================================================================")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
