import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import httpx

from app.database import (
    get_all_pages, get_live_cookies, get_settings,
    upsert_page, upsert_daily_analytics, upsert_videos_batch,
    update_cookie_status
)
from app.scraper import resolve_page_info, scrape_page_videos

logger = logging.getLogger("CrawlerEngine")

# Trạng thái tiến trình quét toàn cục
CRAWLER_STATUS = {
    "is_running": False,
    "action": "",
    "total": 0,
    "current": 0,
    "current_item": "",
    "message": "Sẵn sàng",
    "last_completed": ""
}

async def run_sync_all_task(group_id: Optional[int] = None):
    """Tiến trình cào dữ liệu toàn bộ Page với độ trễ ngẫu nhiên và cơ chế chống Checkpoint."""
    global CRAWLER_STATUS

    if CRAWLER_STATUS["is_running"]:
        logger.warning("Một tiến trình quét khác đang chạy!")
        return

    CRAWLER_STATUS["is_running"] = True
    CRAWLER_STATUS["action"] = "SYNC"
    CRAWLER_STATUS["message"] = "Đang khởi tạo danh sách Fanpage..."
    CRAWLER_STATUS["current"] = 0

    try:
        pages = await get_all_pages(group_id)
        if not pages:
            CRAWLER_STATUS["is_running"] = False
            CRAWLER_STATUS["message"] = "Không có Fanpage nào để quét!"
            return

        cookies = await get_live_cookies()
        settings = await get_settings()

        min_delay = settings["min_delay"]
        max_delay = settings["max_delay"]
        batch_size = settings["batch_size"]
        rest_time = settings["rest_time"]
        rotate_cookies = settings["rotate_cookies"]

        CRAWLER_STATUS["total"] = len(pages)
        cookie_idx = 0

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for idx, p in enumerate(pages):
                current_num = idx + 1
                CRAWLER_STATUS["current"] = current_num
                CRAWLER_STATUS["current_item"] = p["page_name"]
                CRAWLER_STATUS["message"] = f"[{current_num}/{len(pages)}] Đang quét: {p['page_name']}..."

                # 1. Chọn cookie xoay vòng (nếu có)
                active_cookie = None
                if cookies and rotate_cookies:
                    active_cookie_obj = cookies[cookie_idx % len(cookies)]
                    active_cookie = active_cookie_obj["cookie_value"]
                    cookie_idx += 1
                elif cookies:
                    active_cookie = cookies[0]["cookie_value"]

                # 2. Quét thông tin trang (Followers, Name, Avatar)
                page_info = await resolve_page_info(client, p["page_url"], active_cookie)
                followers = page_info.get("followers_count", p.get("followers_count", 0))
                likes = page_info.get("likes_count", p.get("likes_count", 0))
                avatar = page_info.get("avatar_url", p.get("avatar_url", ""))
                status = "ACTIVE" if page_info.get("success", False) else "ERROR"
                err = page_info.get("message", "")

                await upsert_page(
                    page_id=p["page_id"],
                    page_name=page_info.get("page_name") or p["page_name"],
                    page_url=p["page_url"],
                    avatar_url=avatar,
                    followers_count=followers,
                    likes_count=likes,
                    group_id=p.get("group_id"),
                    status=status,
                    error_msg=err
                )

                # 3. Quét danh sách Video & Reels
                videos = await scrape_page_videos(client, p["page_url"], p["page_id"], active_cookie)
                total_views = sum(v["views_count"] for v in videos)

                if videos:
                    await upsert_videos_batch(p["page_id"], videos)

                # 4. Cập nhật bảng Analytics theo ngày
                today_str = datetime.now().strftime("%Y-%m-%d")
                await upsert_daily_analytics(
                    page_id=p["page_id"],
                    date_str=today_str,
                    total_views=total_views,
                    followers_count=followers
                )

                # 5. CƠ CHẾ NGHỈ NGƠI & ĐỘ TRỄ NGẪU NHIÊN (ANTI-CHECKPOINT)
                if current_num < len(pages):
                    # Kiểm tra xem có đến đợt nghỉ xả hơi (batch rest) không
                    if current_num % batch_size == 0 and rest_time > 0:
                        CRAWLER_STATUS["message"] = f"Đã quét {current_num} trang. Đang nghỉ xả hơi {rest_time}s chống xác minh..."
                        await asyncio.sleep(rest_time)
                    else:
                        # Random delay thông thường
                        delay = random.uniform(min_delay, max_delay)
                        CRAWLER_STATUS["message"] = f"Hoàn thành {p['page_name']}. Giãn cách an toàn {delay:.1f}s..."
                        await asyncio.sleep(delay)

        CRAWLER_STATUS["message"] = f"Quét thành công toàn bộ {len(pages)} Fanpage!"
        CRAWLER_STATUS["last_completed"] = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    except Exception as e:
        logger.error(f"Lỗi tiến trình cào dữ liệu: {e}", exc_info=True)
        CRAWLER_STATUS["message"] = f"Tiến trình gặp lỗi: {str(e)}"
    finally:
        CRAWLER_STATUS["is_running"] = False
