import re
import json
import random
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("FBScraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
]

def get_headers(cookie: Optional[str] = None) -> Dict[str, str]:
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }
    if cookie:
        headers["Cookie"] = cookie.strip()
    return headers

def parse_num_str(text: str) -> int:
    """Chuyển đổi chuỗi lượt xem/followers dạng 1.2M, 45K, 123.456 sang số nguyên."""
    if not text:
        return 0
    t = text.lower().replace(",", ".").replace(" ", "").strip()
    match = re.search(r"([\d\.]+)\s*([kmbt]?)", t)
    if not match:
        return 0
    val_str, unit = match.groups()
    try:
        val = float(val_str)
        if unit == "k":
            return int(val * 1000)
        elif unit == "m":
            return int(val * 1000000)
        elif unit == "b":
            return int(val * 1000000000)
        return int(val)
    except:
        return 0

def clean_facebook_url(raw_input: str) -> Tuple[str, str]:
    """Phân giải input thành URL chuẩn và ID/Username thô."""
    raw = raw_input.strip()
    if raw.isdigit():
        return f"https://www.facebook.com/{raw}", raw

    # Nếu là URL
    if "facebook.com" in raw:
        # Xóa query params
        cleaned = re.sub(r"\?.*$", "", raw).rstrip("/")
        # Trích xuất slug/id
        slug = cleaned.split("/")[-1]
        if slug in ["videos", "reels", "photos", "about"]:
            slug = cleaned.split("/")[-2]
        return cleaned, slug

    slug = raw.lstrip("@").strip()
    return f"https://www.facebook.com/{slug}", slug

def format_clean_cookie(raw: str) -> str:
    """Chuẩn hóa và làm sạch chuỗi cookie (giải mã URL %3A, xóa khoảng trắng thừa, xóa dấu chấm phẩy cuối)."""
    import urllib.parse
    unquoted = urllib.parse.unquote(raw.strip())
    items = []
    for part in unquoted.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            k_clean = k.strip()
            v_clean = v.strip()
            if k_clean and v_clean:
                items.append(f"{k_clean}={v_clean}")
    return "; ".join(items)

async def verify_cookie(client: httpx.AsyncClient, cookie_str: str) -> Dict[str, Any]:
    """Kiểm tra Cookie có còn LIVE hay không bằng request HEAD tới /me."""
    clean_cookie = format_clean_cookie(cookie_str)
    if not clean_cookie:
        return {"status": "DIE", "user_id": "", "error_msg": "Chuỗi cookie trống hoặc không hợp lệ"}

    headers = {
        "User-Agent": "curl/8.21.0",
        "Accept": "*/*",
        "Cookie": clean_cookie
    }

    try:
        res = await client.head("https://www.facebook.com/me", headers=headers, follow_redirects=False, timeout=12.0)
        loc = res.headers.get("location", "")

        # Trích xuất user_id từ c_user hoặc i_user trong cookie
        c_user_match = re.search(r"c_user=(\d+)", clean_cookie) or re.search(r"i_user=(\d+)", clean_cookie)
        user_id = c_user_match.group(1) if c_user_match else ""

        if res.status_code in [301, 302, 303, 307, 308]:
            if "login" in loc or "checkpoint" in loc:
                return {
                    "status": "DIE",
                    "user_id": user_id,
                    "error_msg": "Cookie đã bị checkpoint hoặc chuyển hướng đăng nhập"
                }
            
            # Trích xuất profile id/username nếu có từ URL redirect
            if "id=" in loc:
                id_m = re.search(r"id=(\d+)", loc)
                if id_m:
                    user_id = id_m.group(1)

            return {
                "status": "LIVE",
                "user_id": user_id,
                "error_msg": ""
            }
        elif res.status_code == 200:
            return {
                "status": "LIVE",
                "user_id": user_id,
                "error_msg": ""
            }
        else:
            return {
                "status": "DIE",
                "user_id": user_id,
                "error_msg": f"Facebook phản hồi mã lỗi {res.status_code}"
            }
    except Exception as e:
        return {
            "status": "ERROR",
            "user_id": "",
            "error_msg": f"Lỗi kết nối kiểm tra cookie: {str(e)}"
        }

async def resolve_page_info(client: httpx.AsyncClient, raw_input: str, cookie: Optional[str] = None) -> Dict[str, Any]:
    """Lấy thông tin cơ bản của Fanpage: Page ID, Tên, Followers, Avatar."""
    page_url, slug = clean_facebook_url(raw_input)
    headers = get_headers(cookie)

    try:
        res = await client.get(page_url, headers=headers, follow_redirects=True, timeout=15.0)
        html = res.text

        if res.status_code != 200 or "checkpoint" in str(res.url):
            return {
                "success": False,
                "message": f"Không thể truy cập trang (Mã lỗi: {res.status_code})"
            }

        # 1. Trích xuất Page ID
        page_id = ""
        id_match = re.search(r'"pageID":"(\d+)"', html) or re.search(r'"delegate_page":\{"id":"(\d+)"\}', html) or re.search(r'fb://page/(\d+)', html) or re.search(r'"entity_id":"(\d+)"', html) or re.search(r'page_id=(\d+)', html)
        if id_match:
            page_id = id_match.group(1)
        elif slug.isdigit():
            page_id = slug
        else:
            page_id = slug # Tạm thời dùng slug làm fallback ID

        # 2. Trích xuất Tên Page
        page_name = slug
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            title_text = title_match.group(1)
            # Facebook thường có dạng: 'Tên Trang | Facebook' hoặc 'Tên Trang'
            cleaned_title = re.sub(r'\s*\|\s*Facebook.*$', '', title_text).strip()
            if cleaned_title:
                page_name = cleaned_title

        # 3. Trích xuất Followers / Likes
        followers = 0
        likes = 0
        
        # Regex tìm chuỗi '123K người theo dõi' hoặc '123K followers'
        fol_match = re.search(r'([\d\.,\s]+[kmbt]?)\s*(người theo dõi|followers|follower)', html, re.IGNORECASE)
        if fol_match:
            followers = parse_num_str(fol_match.group(1))

        like_match = re.search(r'([\d\.,\s]+[kmbt]?)\s*(lượt thích|likes|like)', html, re.IGNORECASE)
        if like_match:
            likes = parse_num_str(like_match.group(1))

        # 4. Trích xuất Avatar
        avatar_url = ""
        og_img = re.search(r'<meta property="og:image" content="(.*?)"', html)
        if og_img:
            avatar_url = og_img.group(1).replace("&amp;", "&")

        return {
            "success": True,
            "page_id": page_id,
            "page_name": page_name,
            "page_url": str(res.url),
            "followers_count": followers,
            "likes_count": likes,
            "avatar_url": avatar_url
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Lỗi bóc tách thông tin Page: {str(e)}"
        }

async def scrape_page_videos(client: httpx.AsyncClient, page_url: str, page_id: str, cookie: Optional[str] = None) -> List[Dict[str, Any]]:
    """Bóc tách danh sách Video & Reels của trang kèm lượt xem (Views)."""
    videos = []
    headers = get_headers(cookie)

    # Thử quét qua tab /videos hoặc /reels
    video_urls = [
        f"{page_url}/videos",
        f"{page_url}/reels",
        page_url
    ]

    for v_url in video_urls:
        try:
            res = await client.get(v_url, headers=headers, follow_redirects=True, timeout=15.0)
            if res.status_code != 200:
                continue
            html = res.text

            # 1. Tìm các block JSON chứa video data trong script tags
            scripts = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html)
            for sc in scripts:
                if '"video_grid"' in sc or '"play_count"' in sc or '"video_view_count"' in sc or '"playback_video"' in sc:
                    try:
                        data = json.loads(sc)
                        # Tìm kiếm đệ quy các object video
                        _extract_videos_from_dict(data, videos, page_id)
                    except:
                        pass

            # 2. Fallback regex bóc tách trực tiếp từ HTML
            if not videos:
                # Tìm các đoạn "views", "play_count", "lượt xem"
                view_matches = re.findall(r'(\d+[\d\.,]*[kKmMbB]?)\s*(lượt xem|views|plays|lượt phát)', html, re.IGNORECASE)
                for idx, vm in enumerate(view_matches[:30]):
                    views = parse_num_str(vm[0])
                    if views > 0:
                        videos.append({
                            "video_id": f"{page_id}_v_{idx+1}",
                            "title": f"Video #{idx+1} ({page_id})",
                            "created_time": datetime.now().strftime("%Y-%m-%d"),
                            "views_count": views,
                            "likes_count": 0,
                            "comments_count": 0,
                            "url": f"{page_url}/videos"
                        })

            if videos:
                break
        except Exception as e:
            logger.warning(f"Lỗi khi quét URL {v_url}: {e}")

    return videos

def _extract_videos_from_dict(obj: Any, out_list: List[Dict[str, Any]], page_id: str):
    """Tìm kiếm đệ quy cấu trúc video/reels trong payload JSON của Facebook."""
    if isinstance(obj, dict):
        if "play_count" in obj or "video_view_count" in obj or ("id" in obj and "view_count" in obj):
            vid_id = str(obj.get("id", ""))
            views = int(obj.get("play_count") or obj.get("video_view_count") or obj.get("view_count") or 0)
            title = ""
            if "message" in obj and isinstance(obj["message"], dict):
                title = obj["message"].get("text", "")
            elif "name" in obj:
                title = str(obj["name"])
            elif "description" in obj:
                title = str(obj["description"])

            if views > 0 and vid_id:
                out_list.append({
                    "video_id": vid_id,
                    "title": title[:150] if title else f"Video {vid_id}",
                    "created_time": obj.get("creation_time") or datetime.now().strftime("%Y-%m-%d"),
                    "views_count": views,
                    "likes_count": int(obj.get("reaction_count", 0)),
                    "comments_count": int(obj.get("comment_count", 0)),
                    "url": f"https://www.facebook.com/{vid_id}"
                })
        for v in obj.values():
            _extract_videos_from_dict(v, out_list, page_id)
    elif isinstance(obj, list):
        for item in obj:
            _extract_videos_from_dict(item, out_list, page_id)
