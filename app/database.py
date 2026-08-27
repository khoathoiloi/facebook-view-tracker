import os
import json
import aiosqlite
from datetime import datetime, date
from typing import Optional, List, Dict, Any

DB_PATH = os.environ.get("DB_PATH", "tracker_data.db")

async def init_db():
    """Khởi tạo toàn bộ bảng trong cơ sở dữ liệu SQLite."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Bảng Nhóm / Nhân viên
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bảng Cookie phụ (Clone)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cookies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                cookie_value TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'LIVE', -- LIVE, DIE, RATE_LIMIT
                fb_dtsg TEXT DEFAULT '',
                user_id TEXT DEFAULT '',
                last_used TIMESTAMP,
                error_msg TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bảng Fanpage / Kênh theo dõi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT UNIQUE NOT NULL,
                page_name TEXT NOT NULL,
                page_url TEXT NOT NULL,
                avatar_url TEXT DEFAULT '',
                followers_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                group_id INTEGER DEFAULT NULL,
                status TEXT DEFAULT 'ACTIVE', -- ACTIVE, ERROR, NOT_FOUND
                last_scanned TIMESTAMP,
                error_msg TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE SET NULL
            )
        """)

        # Bảng Lịch sử thống kê View & Tăng trưởng theo ngày
        await db.execute("""
            CREATE TABLE IF NOT EXISTS page_analytics_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT NOT NULL,
                date TEXT NOT NULL, -- YYYY-MM-DD
                total_views INTEGER DEFAULT 0,
                followers_count INTEGER DEFAULT 0,
                followers_growth INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(page_id, date),
                FOREIGN KEY (page_id) REFERENCES pages (page_id) ON DELETE CASCADE
            )
        """)

        # Bảng Cache danh sách Video / Reels của từng page
        await db.execute("""
            CREATE TABLE IF NOT EXISTS videos_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT DEFAULT '',
                created_time TEXT DEFAULT '',
                views_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                url TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(page_id, video_id),
                FOREIGN KEY (page_id) REFERENCES pages (page_id) ON DELETE CASCADE
            )
        """)

        # Bảng Cấu hình chống Checkpoint & Delay
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Khởi tạo cài đặt mặc định nếu chưa có
        default_settings = {
            "min_delay": "1.5",
            "max_delay": "3.5",
            "batch_size": "15",
            "rest_time": "8.0",
            "rotate_cookies": "true"
        }
        for k, v in default_settings.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        await db.commit()

# ================= QUẢN LÝ NHÓM =================
async def get_all_groups() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM groups ORDER BY name ASC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def create_group(name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO groups (name) VALUES (?)", (name.strip(),))
        await db.commit()
        return cursor.lastrowid

async def delete_group(group_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE pages SET group_id = NULL WHERE group_id = ?", (group_id,))
        await db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        await db.commit()

# ================= QUẢN LÝ COOKIE =================
async def get_all_cookies() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name, status, user_id, last_used, error_msg, created_at, substr(cookie_value, 1, 15) || '...' as masked_cookie FROM cookies ORDER BY id DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_live_cookies() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM cookies WHERE status = 'LIVE' ORDER BY last_used ASC, id ASC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def upsert_cookie(cookie_value: str, name: str = "Clone", status: str = "LIVE", user_id: str = "", error_msg: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO cookies (name, cookie_value, status, user_id, error_msg)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cookie_value) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                user_id = excluded.user_id,
                error_msg = excluded.error_msg
        """, (name, cookie_value.strip(), status, user_id, error_msg))
        await db.commit()
        return cursor.lastrowid

async def update_cookie_status(cookie_id: int, status: str, error_msg: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE cookies SET status = ?, error_msg = ?, last_used = CURRENT_TIMESTAMP WHERE id = ?", (status, error_msg, cookie_id))
        await db.commit()

async def delete_cookie(cookie_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cookies WHERE id = ?", (cookie_id,))
        await db.commit()

# ================= QUẢN LÝ FANPAGE =================
async def get_all_pages(group_id: Optional[int] = None) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if group_id:
            cursor = await db.execute("""
                SELECT p.*, g.name as group_name
                FROM pages p
                LEFT JOIN groups g ON p.group_id = g.id
                WHERE p.group_id = ?
                ORDER BY p.followers_count DESC, p.id DESC
            """, (group_id,))
        else:
            cursor = await db.execute("""
                SELECT p.*, g.name as group_name
                FROM pages p
                LEFT JOIN groups g ON p.group_id = g.id
                ORDER BY p.followers_count DESC, p.id DESC
            """)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def upsert_page(page_id: str, page_name: str, page_url: str, avatar_url: str = "", followers_count: int = 0, likes_count: int = 0, group_id: Optional[int] = None, status: str = "ACTIVE", error_msg: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO pages (page_id, page_name, page_url, avatar_url, followers_count, likes_count, group_id, status, error_msg, last_scanned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(page_id) DO UPDATE SET
                page_name = CASE WHEN excluded.page_name != '' THEN excluded.page_name ELSE pages.page_name END,
                avatar_url = CASE WHEN excluded.avatar_url != '' THEN excluded.avatar_url ELSE pages.avatar_url END,
                followers_count = excluded.followers_count,
                likes_count = excluded.likes_count,
                status = excluded.status,
                error_msg = excluded.error_msg,
                last_scanned = CURRENT_TIMESTAMP
        """, (page_id, page_name, page_url, avatar_url, followers_count, likes_count, group_id, status, error_msg))
        await db.commit()

async def update_page_group(page_id: str, group_id: Optional[int]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE pages SET group_id = ? WHERE page_id = ?", (group_id, page_id))
        await db.commit()

async def delete_page(page_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM videos_cache WHERE page_id = ?", (page_id,))
        await db.execute("DELETE FROM page_analytics_daily WHERE page_id = ?", (page_id,))
        await db.execute("DELETE FROM pages WHERE page_id = ?", (page_id,))
        await db.commit()

# ================= QUẢN LÝ ANALYTICS & VIDEOS =================
async def upsert_daily_analytics(page_id: str, date_str: str, total_views: int, followers_count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Tìm followers_count của ngày gần nhất trước đó để tính growth
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT followers_count FROM page_analytics_daily WHERE page_id = ? AND date < ? ORDER BY date DESC LIMIT 1", (page_id, date_str))
        prev = await cursor.fetchone()
        prev_followers = prev['followers_count'] if prev else followers_count
        growth = max(0, followers_count - prev_followers) if prev else 0

        await db.execute("""
            INSERT INTO page_analytics_daily (page_id, date, total_views, followers_count, followers_growth)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(page_id, date) DO UPDATE SET
                total_views = excluded.total_views,
                followers_count = excluded.followers_count,
                followers_growth = excluded.followers_growth
        """, (page_id, date_str, total_views, followers_count, growth))
        await db.commit()

async def upsert_videos_batch(page_id: str, videos: List[Dict[str, Any]]):
    async with aiosqlite.connect(DB_PATH) as db:
        for v in videos:
            await db.execute("""
                INSERT INTO videos_cache (page_id, video_id, title, created_time, views_count, likes_count, comments_count, url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(page_id, video_id) DO UPDATE SET
                    title = excluded.title,
                    views_count = excluded.views_count,
                    likes_count = excluded.likes_count,
                    comments_count = excluded.comments_count,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                page_id,
                v.get("video_id", ""),
                v.get("title", ""),
                v.get("created_time", ""),
                v.get("views_count", 0),
                v.get("likes_count", 0),
                v.get("comments_count", 0),
                v.get("url", "")
            ))
        await db.commit()

async def get_page_videos(page_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM videos_cache WHERE page_id = ? ORDER BY views_count DESC, id DESC LIMIT 100", (page_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

# ================= THỐNG KÊ DASHBOARD =================
async def get_analytics_overview(period: str = "7d", group_id: Optional[int] = None) -> Dict[str, Any]:
    days_map = {"1d": 0, "7d": 7, "28d": 28, "30d": 30}
    days = days_map.get(period, 7)

    if days == 0:
        date_cond = "a.date = date('now', 'localtime')"
    else:
        date_cond = f"a.date >= date('now', 'localtime', '-{days} days')"

    group_cond = f"AND p.group_id = {int(group_id)}" if group_id else ""
    page_group_cond = f"WHERE group_id = {int(group_id)}" if group_id else ""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 1. KPI
        kpi_query = f"""
            SELECT 
                COALESCE(SUM(a.total_views), 0) as total_views,
                COALESCE(SUM(a.followers_growth), 0) as total_followers_growth
            FROM page_analytics_daily a
            JOIN pages p ON a.page_id = p.page_id
            WHERE {date_cond} {group_cond}
        """
        cursor = await db.execute(kpi_query)
        kpi_row = await cursor.fetchone()
        kpi = {
            "total_views": kpi_row["total_views"] if kpi_row else 0,
            "total_followers_growth": kpi_row["total_followers_growth"] if kpi_row else 0
        }

        # 2. Chi tiết theo ngày
        daily_query = f"""
            SELECT a.date, SUM(a.total_views) as views, SUM(a.followers_growth) as followers_growth
            FROM page_analytics_daily a
            JOIN pages p ON a.page_id = p.page_id
            WHERE {date_cond} {group_cond}
            GROUP BY a.date ORDER BY a.date DESC
        """
        cursor = await db.execute(daily_query)
        daily_rows = await cursor.fetchall()
        daily = [dict(r) for r in daily_rows]

        # 3. Danh sách Pages + Views
        pages_query = f"""
            SELECT 
                p.page_id, p.page_name, p.page_url, p.avatar_url, p.followers_count, p.likes_count, p.status, p.last_scanned,
                COALESCE(SUM(a.total_views), 0) as period_views,
                COALESCE(SUM(a.followers_growth), 0) as period_growth
            FROM pages p
            LEFT JOIN page_analytics_daily a ON p.page_id = a.page_id AND {date_cond}
            {page_group_cond}
            GROUP BY p.page_id
            ORDER BY period_views DESC, p.followers_count DESC
        """
        cursor = await db.execute(pages_query)
        pages_rows = await cursor.fetchall()
        pages = [dict(r) for r in pages_rows]

        return {
            "kpi": kpi,
            "daily": daily,
            "pages": pages
        }

# ================= CÀI ĐẶT =================
async def get_settings() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM settings")
        rows = await cursor.fetchall()
        res = {r["key"]: r["value"] for r in rows}
        return {
            "min_delay": float(res.get("min_delay", 1.5)),
            "max_delay": float(res.get("max_delay", 3.5)),
            "batch_size": int(res.get("batch_size", 15)),
            "rest_time": float(res.get("rest_time", 8.0)),
            "rotate_cookies": res.get("rotate_cookies", "true").lower() == "true"
        }

async def update_settings(data: Dict[str, Any]):
    async with aiosqlite.connect(DB_PATH) as db:
        for k, v in data.items():
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (str(k), str(v)))
        await db.commit()
