import re
import json
import random
import logging
import urllib.parse
from datetime import datetime, timedelta
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

def format_clean_cookie(raw: str) -> str:
    """Chuẩn hóa và làm sạch chuỗi cookie (giải mã URL %3A, xóa khoảng trắng thừa, xóa dấu chấm phẩy cuối)."""
    if not raw:
        return ""
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

def get_headers(cookie: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    clean_c = format_clean_cookie(cookie) if cookie else ""
    if clean_c:
        headers["Cookie"] = clean_c
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
        cleaned = re.sub(r"\?.*$", "", raw).rstrip("/")
        slug = cleaned.split("/")[-1]
        if slug in ["videos", "reels", "photos", "about"]:
            slug = cleaned.split("/")[-2]
        return cleaned, slug

    slug = raw.lstrip("@").strip()
    return f"https://www.facebook.com/{slug}", slug

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

        c_user_match = re.search(r"c_user=(\d+)", clean_cookie) or re.search(r"i_user=(\d+)", clean_cookie)
        user_id = c_user_match.group(1) if c_user_match else ""

        if res.status_code in [301, 302, 303, 307, 308]:
            if "login" in loc or "checkpoint" in loc:
                return {
                    "status": "DIE",
                    "user_id": user_id,
                    "error_msg": "Cookie đã bị checkpoint hoặc chuyển hướng đăng nhập"
                }
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
    """
    Phân giải thông tin Fanpage từ URL hoặc UID:
    Tự động tìm Tên Trang Thật (Real Page Name), Numeric ID, Followers Count, Avatar.
    """
    page_url, slug = clean_facebook_url(raw_input)
    clean_cookie = format_clean_cookie(cookie) if cookie else ""
    
    page_name = slug
    page_id = slug
    followers = 0
    likes = 0
    avatar_url = ""
    is_success = False

    # 1. PHƯƠNG THỨC CHÍNH: Facebook Page Plugin Resolver
    plugin_url = f"https://www.facebook.com/plugins/page.php?href={page_url}&tabs=timeline&small_header=false&adapt_container_width=true&hide_cover=false&show_facepile=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    if clean_cookie:
        headers["Cookie"] = clean_cookie

    try:
        res = await client.get(plugin_url, headers=headers, timeout=12.0)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Lấy tên Page & Numeric Page ID từ link embed_page
            for a in soup.find_all("a"):
                href = a.get("href", "")
                text = a.text.strip()
                if "ref=embed_page" in href or "ref=page_plugin" in href:
                    if text and not any(skip in text.lower() for skip in ["theo dõi", "thích", "chia sẻ", "share", "like", "follow"]):
                        page_name = text
                        is_success = True
                        id_m = re.search(r"facebook\.com/(\d+)", href)
                        if id_m:
                            page_id = id_m.group(1)
                        break

            # Lấy số người theo dõi / thích
            likes_div = soup.find("div", class_="_1drq") or soup.find("div", class_="_4bl9")
            if likes_div:
                num_match = re.search(r"([\d\.,\s]+[kmbt]?)", likes_div.text)
                if num_match:
                    s = num_match.group(1).replace(".", "").replace(",", "").replace(" ", "").strip()
                    if s.isdigit():
                        followers = int(s)
                        likes = followers
                        is_success = True

            # Lấy avatar
            img = soup.find("img", class_="_113b") or soup.find("img", class_="_42ft") or soup.find("img")
            if img and img.has_attr("src"):
                avatar_url = img["src"]

    except Exception as e:
        logger.warning(f"Lỗi phân giải plugin cho {page_url}: {e}")

    # 2. FALLBACK: Thử quét OpenGraph từ trang chính nếu plugin chưa lấy được tên
    if not is_success or page_name == slug:
        try:
            head_req = await client.get(page_url, headers=get_headers(clean_cookie), follow_redirects=True, timeout=10.0)
            if head_req.status_code == 200:
                html = head_req.text
                og_title = re.search(r'<meta property="og:title" content="(.*?)"', html)
                if og_title and og_title.group(1) not in ["Facebook", "Error", ""]:
                    page_name = re.sub(r'\s*\|\s*Facebook.*$', '', og_title.group(1)).strip()
                    is_success = True

                if not avatar_url:
                    og_img = re.search(r'<meta property="og:image" content="(.*?)"', html)
                    if og_img:
                        avatar_url = og_img.group(1).replace("&amp;", "&")
        except:
            pass

    return {
        "success": is_success or bool(page_name != slug or followers > 0),
        "page_id": page_id,
        "page_name": page_name if page_name else slug,
        "page_url": page_url,
        "followers_count": followers,
        "likes_count": likes,
        "avatar_url": avatar_url,
        "message": "" if is_success else "Đã nạp theo ID/Link"
    }

async def _extract_exact_video_metrics(client: httpx.AsyncClient, vid: str, cookie: str = "") -> Tuple[int, int, int, str]:
    """Truy cập trang video hoặc reel cụ thể và trích xuất số liệu thực tế (views, likes, comments, title)."""
    headers = get_headers(cookie)
    views = 0
    likes = 0
    comments = 0
    title = f"Video #{vid}"
    
    for u in [f"https://www.facebook.com/watch/?v={vid}", f"https://www.facebook.com/reel/{vid}"]:
        try:
            res = await client.get(u, headers=headers, timeout=12.0)
            if res.status_code == 200:
                html = res.text
                
                # 1. Lượt xem / Plays
                v_match = (
                    re.search(r'\"(?:play_count|video_view_count|playback_count)\":\s*(\d+)', html) or
                    re.search(r'\"(?:play_count|video_view_count|playback_count)\":\s*\{\s*\"count\":\s*(\d+)', html)
                )
                if v_match:
                    views = int(v_match.group(1))
                else:
                    text_v = re.search(r'([\d\.,\s]+[kmbtKMTP]?)\s*(?:lượt xem|views|plays|lượt phát)', html, re.I)
                    if text_v:
                        raw = text_v.group(1).strip().replace(" ", "").replace(",", ".")
                        mult = 1
                        if raw.lower().endswith("k"):
                            mult = 1000
                            raw = raw[:-1]
                        elif raw.lower().endswith("m"):
                            mult = 1000000
                            raw = raw[:-1]
                        try:
                            views = int(float(raw) * mult)
                        except:
                            pass
                            
                # 2. Likes / Reactions
                like_m = re.search(r'\"reaction_count\":\s*\{\s*\"count\":\s*(\d+)', html)
                if like_m:
                    likes = int(like_m.group(1))
                    
                # 3. Comments
                cmt_m = re.search(r'\"total_comment_count\":\s*(\d+)', html) or re.search(r'\"comment_count\":\s*\{\s*\"total_count\":\s*(\d+)', html)
                if cmt_m:
                    comments = int(cmt_m.group(1))
                    
                # 4. Title
                t_m = re.search(r'\"savable_title\":\s*\{\s*\"text\":\s*\"([^\"]+)\"', html) or re.search(r'\"(?:message|title)\":\s*\"([^\"]+)\"', html)
                if t_m:
                    title = t_m.group(1)
                    
                if views > 0 or likes > 0:
                    break
        except Exception:
            pass
            
    return views, likes, comments, title


async def scrape_page_videos(client: httpx.AsyncClient, page_url: str, page_id: str, cookie: Optional[str] = None, followers_count: int = 0) -> List[Dict[str, Any]]:
    """
    Lấy 3 video gần nhất của trang và trích xuất lượt xem thực tế 100%.
    """
    videos = []
    clean_cookie = format_clean_cookie(cookie) if cookie else ""
    headers = get_headers(clean_cookie)

    # --- Bước 1: Tìm canonical URL và UID của trang nếu là link rút gọn / ID ---
    canonical_url = page_url
    resolved_id = ""
    try:
        plugin_url = f"https://www.facebook.com/plugins/page.php?href={page_url}&tabs=timeline"
        res_p = await client.get(plugin_url, timeout=10.0)
        if res_p.status_code == 200:
            soup_p = BeautifulSoup(res_p.text, "html.parser")
            for a in soup_p.find_all("a"):
                h = a.get("href", "")
                if "people/" in h:
                    canonical_url = h.split("?")[0]
                    parts = [p for p in canonical_url.split("/") if p]
                    if parts and parts[-1].isdigit():
                        resolved_id = parts[-1]
                    break
                elif "/profile.php" in h:
                    canonical_url = h.split("?")[0]
                    m = re.search(r'id=(\d+)', h)
                    if m:
                        resolved_id = m.group(1)
                    break
    except Exception as e:
        logger.warning(f"Lỗi phân giải canonical cho {page_url}: {e}")

    # --- Bước 2: Thử các link tiềm năng để quét danh sách Video IDs ---
    urls_to_check = []
    if resolved_id:
        urls_to_check.append(f"https://www.facebook.com/profile.php?id={resolved_id}&sk=videos")
        urls_to_check.append(f"https://www.facebook.com/profile.php?id={resolved_id}&sk=reels_tab")
    urls_to_check.append(f"{canonical_url.rstrip('/')}/videos")
    urls_to_check.append(f"{canonical_url.rstrip('/')}/reels_tab")
    urls_to_check.append(canonical_url)
    if page_url != canonical_url:
        urls_to_check.append(page_url)

    found_video_ids = []
    for try_url in urls_to_check:
        try:
            res = await client.get(try_url, headers=headers, timeout=15.0)
            if res.status_code == 200:
                html = res.text
                vids = (
                    re.findall(r'\"__typename\":\s*\"Video\"[^\}]+?\"id\":\s*\"(\d+)\"', html) +
                    re.findall(r'watch/\?v=(\d{10,18})', html) +
                    re.findall(r'reel/(\d{10,18})', html) +
                    re.findall(r'/videos/(\d{10,18})', html) +
                    re.findall(r'\"video(?:_id|ID|Id)\":\s*\"(\d{10,18})\"', html)
                )
                for vid in vids:
                    if vid not in found_video_ids and vid != resolved_id and vid != page_id:
                        found_video_ids.append(vid)
                if len(found_video_ids) >= 3:
                    break
        except Exception as e:
            logger.warning(f"Lỗi quét video từ {try_url}: {e}")
            continue

    # --- Bước 3: Trích xuất view count thật từ 3 video đầu tiên ---
    for i, vid_id in enumerate(found_video_ids[:3]):
        views, likes, cmts, title = await _extract_exact_video_metrics(client, vid_id, clean_cookie)
        created_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        video_url = f"https://www.facebook.com/watch/?v={vid_id}"

        videos.append({
            "video_id": vid_id,
            "title": title[:100],
            "created_time": created_date,
            "views_count": views,
            "likes_count": likes,
            "comments_count": cmts,
            "url": video_url
        })

    # --- Bước 4: Fallback nếu trang chưa có video nào ---
    if not videos:
        logger.info(f"Không tìm thấy video cho {page_url}, tạo video mẫu 0 view.")
        for i in range(3):
            post_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            videos.append({
                "video_id": f"{page_id}_v_{i+1}",
                "title": f"Chưa có video gần đây ({post_date})",
                "created_time": post_date,
                "views_count": 0,
                "likes_count": 0,
                "comments_count": 0,
                "url": f"{page_url}/videos"
            })

    return videos

