import io
import pandas as pd
from typing import Optional
from app.database import get_analytics_overview, get_all_pages, aiosqlite, DB_PATH

async def export_analytics_to_excel(period: str = "7d", group_id: Optional[int] = None) -> io.BytesIO:
    """Xuất toàn bộ báo cáo phân tích ra file Excel gồm nhiều sheet."""
    data = await get_analytics_overview(period, group_id)
    
    # 1. Sheet Tổng quan & Danh sách Pages
    pages_df = pd.DataFrame(data.get("pages", []))
    if not pages_df.empty:
        # Đổi tên cột cho thân thiện
        rename_dict = {
            "page_id": "Page ID",
            "page_name": "Tên Fanpage",
            "page_url": "Đường dẫn",
            "followers_count": "Người theo dõi",
            "likes_count": "Lượt thích",
            "period_views": f"Lượt xem ({period})",
            "period_growth": f"Tăng trưởng Follower ({period})",
            "status": "Trạng thái",
            "last_scanned": "Lần quét gần nhất"
        }
        pages_df = pages_df.rename(columns={k: v for k, v in rename_dict.items() if k in pages_df.columns})
        if "avatar_url" in pages_df.columns:
            pages_df = pages_df.drop(columns=["avatar_url"])

    # 2. Sheet Chi tiết theo ngày
    daily_df = pd.DataFrame(data.get("daily", []))
    if not daily_df.empty:
        daily_df = daily_df.rename(columns={
            "date": "Ngày",
            "views": "Tổng Lượt xem",
            "followers_growth": "Tăng trưởng Người theo dõi"
        })

    # 3. Sheet Chi tiết tất cả Video
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT v.page_id, p.page_name, v.video_id, v.title, v.views_count, v.created_time, v.url
            FROM videos_cache v
            JOIN pages p ON v.page_id = p.page_id
            ORDER BY v.views_count DESC
            LIMIT 500
        """)
        v_rows = await cursor.fetchall()
        videos_df = pd.DataFrame([dict(r) for r in v_rows])
        if not videos_df.empty:
            videos_df = videos_df.rename(columns={
                "page_id": "Page ID",
                "page_name": "Tên Fanpage",
                "video_id": "Video ID",
                "title": "Tiêu đề Video",
                "views_count": "Lượt xem",
                "created_time": "Ngày đăng",
                "url": "Link Video"
            })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not pages_df.empty:
            pages_df.to_excel(writer, sheet_name='Danh Sách Fanpage', index=False)
        else:
            pd.DataFrame([{"Thông báo": "Chưa có dữ liệu Fanpage"}]).to_excel(writer, sheet_name='Danh Sách Fanpage', index=False)

        if not daily_df.empty:
            daily_df.to_excel(writer, sheet_name='Chi Tiết Theo Ngày', index=False)
            
        if not videos_df.empty:
            videos_df.to_excel(writer, sheet_name='Chi Tiết Video & Reels', index=False)

    output.seek(0)
    return output
