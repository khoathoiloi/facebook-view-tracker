import os
import sys
import io
import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, Query, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

from app.models import (
    CreateGroupRequest, ImportPagesRequest, ImportCookiesRequest,
    UpdatePageGroupRequest, UpdateSettingsRequest, TriggerSyncRequest
)
from app.database import (
    init_db, get_all_groups, create_group, delete_group,
    get_all_cookies, upsert_cookie, delete_cookie,
    get_all_pages, upsert_page, update_page_group, delete_page,
    get_page_videos, get_analytics_overview, get_settings, update_settings
)
from app.scraper import resolve_page_info, verify_cookie, clean_facebook_url
from app.engine import CRAWLER_STATUS, run_sync_all_task
from app.export import export_analytics_to_excel
from app.updater import CURRENT_VERSION, check_for_updates, download_and_apply_update

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
logger = logging.getLogger("App")

def resource_path(relative_path: str) -> str:
    """Hỗ trợ đường dẫn file khi chạy từ mã nguồn hoặc khi đóng gói trong file PyInstaller .exe"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)

app = FastAPI(title="Facebook View Tracker - Enterprise Local", version=CURRENT_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gắn thư mục static
STATIC_DIR = resource_path("static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
async def on_startup():
    await init_db()
    logger.info(f"--- HỆ THỐNG FASTAPI BACKEND KHỞI ĐỘNG THÀNH CÔNG (v{CURRENT_VERSION}) ---")

@app.get("/")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Facebook View Tracker API is running!", "version": CURRENT_VERSION})

# ================= APIS TỰ ĐỘNG CẬP NHẬT (AUTO-UPDATE) =================
@app.get("/api/update/check")
async def check_update_api():
    return await check_for_updates()

@app.post("/api/update/install")
async def install_update_api(background_tasks: BackgroundTasks):
    info = await check_for_updates()
    if not info.get("has_update") or not info.get("download_url"):
        return {"success": False, "message": "Không có bản cập nhật mới nào để tải về!"}

    async def _do_update_and_exit(url: str):
        res = await download_and_apply_update(url)
        if res.get("success"):
            await asyncio.sleep(1.0)
            os._exit(0) # Tắt tiến trình hiện tại để file batch hoán đổi file exe

    background_tasks.add_task(_do_update_and_exit, info["download_url"])
    return {
        "success": True,
        "message": f"Đang tải bản cập nhật v{info['latest_version']}. Ứng dụng sẽ tự khởi động lại sau giây lát!"
    }

# ================= APIS QUẢN LÝ NHÓM =================
@app.get("/api/groups")
async def list_groups():
    return await get_all_groups()

@app.post("/api/groups")
async def add_group(req: CreateGroupRequest):
    try:
        gid = await create_group(req.name)
        return {"success": True, "message": f"Tạo nhóm '{req.name}' thành công!", "group_id": gid}
    except Exception as e:
        return {"success": False, "message": f"Lỗi tạo nhóm: {str(e)}"}

@app.delete("/api/groups/{group_id}")
async def remove_group(group_id: int):
    await delete_group(group_id)
    return {"success": True, "message": "Đã xóa nhóm thành công!"}

# ================= APIS QUẢN LÝ COOKIE =================
@app.get("/api/cookies")
async def list_cookies():
    return await get_all_cookies()

@app.post("/api/cookies/import")
async def import_cookies(req: ImportCookiesRequest):
    lines = [l.strip() for l in req.cookies_raw.splitlines() if l.strip()]
    if not lines:
        return {"success": False, "message": "Vui lòng nhập ít nhất 1 cookie!"}

    count = 0
    async with httpx.AsyncClient(timeout=15.0) as client:
        for idx, line in enumerate(lines):
            name = f"{req.name} #{idx+1}" if len(lines) > 1 else req.name
            ver = await verify_cookie(client, line)
            await upsert_cookie(
                cookie_value=line,
                name=name,
                status=ver["status"],
                user_id=ver["user_id"],
                error_msg=ver["error_msg"]
            )
            count += 1

    return {"success": True, "message": f"Đã import và kiểm tra thành công {count} cookie!"}

@app.delete("/api/cookies/{cookie_id}")
async def remove_cookie(cookie_id: int):
    await delete_cookie(cookie_id)
    return {"success": True, "message": "Đã xóa cookie thành công!"}

# ================= APIS QUẢN LÝ FANPAGE =================
@app.get("/api/pages")
async def list_pages(group_id: Optional[int] = None):
    return await get_all_pages(group_id)

@app.post("/api/pages/import")
async def import_pages(req: ImportPagesRequest, background_tasks: BackgroundTasks):
    lines = [l.strip() for l in req.pages_raw.splitlines() if l.strip()]
    if not lines:
        return {"success": False, "message": "Vui lòng nhập danh sách link hoặc ID Fanpage!"}

    # 1. Nạp ngay lập tức toàn bộ danh sách vào database để không bị sót bất kỳ page nào
    for item in lines:
        page_url, slug = clean_facebook_url(item)
        await upsert_page(
            page_id=slug,
            page_name=slug,
            page_url=page_url,
            group_id=req.group_id,
            status="PENDING"
        )

    # 2. Phân giải thông tin trang ở nền (nếu cần)
    async def _resolve_all_background(pages_list: list, gid: Optional[int]):
        async with httpx.AsyncClient(timeout=12.0) as client:
            for item in pages_list:
                try:
                    page_url, slug = clean_facebook_url(item)
                    info = await resolve_page_info(client, item)
                    p_id = info.get("page_id") or slug
                    p_name = info.get("page_name") or slug
                    p_url = info.get("page_url") or page_url

                    await upsert_page(
                        page_id=p_id,
                        page_name=p_name,
                        page_url=p_url,
                        avatar_url=info.get("avatar_url", ""),
                        followers_count=info.get("followers_count", 0),
                        likes_count=info.get("likes_count", 0),
                        group_id=gid,
                        status="ACTIVE" if info.get("success") else "ACTIVE",
                        error_msg=info.get("message", "")
                    )
                except Exception as err:
                    logger.warning(f"Lỗi phân giải nền {item}: {err}")

    background_tasks.add_task(_resolve_all_background, lines, req.group_id)
    return {"success": True, "message": f"Đã nạp thành công toàn bộ {len(lines)} Fanpage vào hệ thống!"}

@app.put("/api/pages/{page_id}/group")
async def change_page_group(page_id: str, req: UpdatePageGroupRequest):
    await update_page_group(page_id, req.group_id)
    return {"success": True, "message": "Cập nhật nhóm cho Fanpage thành công!"}

@app.delete("/api/pages/{page_id}")
async def remove_page(page_id: str):
    await delete_page(page_id)
    return {"success": True, "message": "Đã xóa Fanpage và dữ liệu liên quan thành công!"}

@app.get("/api/pages/{page_id}/videos")
async def get_videos(page_id: str):
    videos = await get_page_videos(page_id)
    return {"success": True, "videos": videos}

# ================= APIS ANALYTICS & CRAWLER =================
@app.get("/api/analytics/overview")
async def get_overview(period: str = "yesterday", group_id: Optional[int] = None):
    return await get_analytics_overview(period, group_id)

@app.post("/api/analytics/sync")
async def trigger_sync(background_tasks: BackgroundTasks, group_id: Optional[int] = None):
    if CRAWLER_STATUS["is_running"]:
        return {"success": False, "message": "Hệ thống đang bận thực hiện tác vụ quét khác!"}
    
    background_tasks.add_task(run_sync_all_task, group_id)
    return {"success": True, "message": "Đã kích hoạt tiến trình quét dữ liệu an toàn!"}

@app.get("/api/status")
async def get_status():
    return CRAWLER_STATUS

# ================= APIS CÀI ĐẶT & XUẤT EXCEL =================
@app.get("/api/settings")
async def read_settings():
    return await get_settings()

@app.post("/api/settings")
async def save_settings(req: UpdateSettingsRequest):
    await update_settings(req.model_dump())
    return {"success": True, "message": "Lưu cấu hình chống Checkpoint thành công!"}

@app.get("/api/export/excel")
async def export_excel(period: str = "7d", group_id: Optional[int] = None):
    excel_stream = await export_analytics_to_excel(period, group_id)
    filename = f"Facebook_Analytics_{period}.xlsx"
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
