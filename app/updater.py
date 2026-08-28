import os
import sys
import subprocess
import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger("AutoUpdater")

CURRENT_VERSION = "1.1.6"
GITHUB_REPO = "khoathoiloi/facebook-view-tracker"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def is_newer_version(latest: str, current: str) -> bool:
    """So sánh phiên bản dạng semantic version (vd: 1.0.1 > 1.0.0)."""
    try:
        l_parts = [int(p) for p in latest.lstrip("vV").split(".")]
        c_parts = [int(p) for p in current.lstrip("vV").split(".")]
        return l_parts > c_parts
    except:
        return latest.strip() != current.strip()

async def check_for_updates() -> Dict[str, Any]:
    """Kiểm tra xem GitHub có bản Release mới hơn bản hiện tại hay không."""
    try:
        headers = {"User-Agent": "FacebookViewTracker-AutoUpdater"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(GITHUB_API_URL, headers=headers)
            if res.status_code != 200:
                return {
                    "has_update": False,
                    "current_version": CURRENT_VERSION,
                    "latest_version": CURRENT_VERSION,
                    "message": "Không tìm thấy thông tin bản phát hành trên GitHub."
                }
            
            data = res.json()
            tag_name = data.get("tag_name", "").lstrip("vV")
            release_notes = data.get("body", "Bản cập nhật tính năng mới và sửa lỗi.")
            assets = data.get("assets", [])

            download_url = ""
            for asset in assets:
                name = asset.get("name", "")
                if name.endswith(".exe"):
                    download_url = asset.get("browser_download_url", "")
                    break

            if not download_url and assets:
                download_url = assets[0].get("browser_download_url", "")

            has_update = is_newer_version(tag_name, CURRENT_VERSION)

            return {
                "has_update": has_update,
                "current_version": CURRENT_VERSION,
                "latest_version": tag_name or CURRENT_VERSION,
                "release_notes": release_notes,
                "download_url": download_url,
                "published_at": data.get("published_at", "")
            }
    except Exception as e:
        logger.error(f"Lỗi kiểm tra cập nhật: {e}")
        return {
            "has_update": False,
            "current_version": CURRENT_VERSION,
            "latest_version": CURRENT_VERSION,
            "message": f"Không thể kết nối đến máy chủ cập nhật: {str(e)}"
        }

async def download_and_apply_update(download_url: str) -> Dict[str, Any]:
    """Tải file EXE mới từ GitHub và tự động khởi chạy script cập nhật thay thế."""
    if not download_url:
        return {"success": False, "message": "Không tìm thấy đường link tải bản cập nhật!"}

    try:
        # Đường dẫn file EXE hiện tại
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
        else:
            current_exe = os.path.abspath(sys.argv[0])

        current_dir = os.path.dirname(current_exe)
        temp_exe_name = "FacebookViewTracker_update.exe"
        temp_exe_path = os.path.join(current_dir, temp_exe_name)
        bat_script_path = os.path.join(current_dir, "update_launcher.bat")

        # Tải file mới
        headers = {"User-Agent": "FacebookViewTracker-AutoUpdater"}
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            res = await client.get(download_url, headers=headers)
            if res.status_code != 200:
                return {"success": False, "message": f"Tải file thất bại (Mã lỗi HTTP: {res.status_code})"}

            with open(temp_exe_path, "wb") as f:
                f.write(res.content)

        # Tạo file batch để hoán đổi file EXE khi tiến trình hiện tại tắt
        bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
:retry
move /y "{temp_exe_name}" "{os.path.basename(current_exe)}" > nul 2>&1
if exist "{temp_exe_name}" (
    timeout /t 1 /nobreak > nul
    goto retry
)
start "" "{os.path.basename(current_exe)}"
del "%~f0"
"""
        with open(bat_script_path, "w", encoding="utf-8") as bf:
            bf.write(bat_content)

        # Khởi chạy file batch ngầm
        subprocess.Popen(["cmd.exe", "/c", bat_script_path], cwd=current_dir, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

        return {"success": True, "message": "Tải bản cập nhật thành công! Ứng dụng sẽ tự khởi động lại sau 2 giây..."}

    except Exception as e:
        logger.error(f"Lỗi khi thực hiện tự động cập nhật: {e}", exc_info=True)
        return {"success": False, "message": f"Lỗi cập nhật: {str(e)}"}
