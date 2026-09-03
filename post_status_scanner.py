# -*- coding: utf-8 -*-
"""
Post Status & Error Scanner for BlogB
Công cụ quét tình trạng đăng bài của các Fanpage trên BlogB theo ngày cố định,
bóc tách chính xác tên Fanpage đầy đủ 100% cùng chi tiết lỗi thực tế.
"""

import os
import sys
import re
import json
import time
import shutil
import threading
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException, StaleElementReferenceException
except ImportError:
    webdriver = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
STATE_JSON_PATH = os.path.join(LOCALAPPDATA, "PageFB", "state.json")
CHROMEDRIVER_PATH = os.path.join(BASE_DIR, "chromedriver.exe")
BROWSER_PROFILE_DIR = os.path.join(LOCALAPPDATA, "PageFB", "ChromeProfile")
SCANNER_PROFILE_DIR = os.path.join(LOCALAPPDATA, "PageFB", "ScannerProfile")

# ================= 1. BỘ PHÂN GIẢI TÊN FANPAGE CHUẨN 100% =================
class PageCatalogResolver:
    """Tải 255 Fanpage từ state.json và ánh xạ tên bị cắt ngắn (...) sang tên đầy đủ 100%."""
    def __init__(self, state_path: str = STATE_JSON_PATH):
        self.catalog_pages = []
        self.name_map = {}
        self.load_catalog(state_path)

    def load_catalog(self, state_path: str):
        if not os.path.exists(state_path):
            return
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            groups = data.get("page_catalog", {}).get("groups", {})
            for gid, g in groups.items():
                for p in g.get("pages", []):
                    name = p.get("name", "").strip()
                    fbid = p.get("facebook_id", "")
                    if name:
                        self.catalog_pages.append({
                            "name": name,
                            "facebook_id": fbid,
                            "group": gid,
                            "key": p.get("key", "")
                        })
                        self.name_map[name.lower()] = name
        except Exception as e:
            print(f"Lỗi đọc catalog state.json: {e}")

    def resolve_name(self, raw_text: str) -> str:
        """Chuyển đổi tên bị rút gọn như 'Vertex Hi...' thành 'Vertex Hill Circle'."""
        if not raw_text:
            return ""
        
        cleaned = raw_text.strip()
        norm = re.sub(r'[\.\s…]+$', '', cleaned).strip().lower()
        if not norm:
            return cleaned

        if norm in self.name_map:
            return self.name_map[norm]

        candidates = []
        for p in self.catalog_pages:
            c_name = p["name"]
            c_low = c_name.lower()
            if c_low.startswith(norm):
                candidates.append(c_name)

        if len(candidates) == 1:
            return candidates[0]
        elif len(candidates) > 1:
            candidates.sort(key=lambda x: len(x))
            return candidates[0]

        words = norm.split()
        if words:
            for p in self.catalog_pages:
                c_low = p["name"].lower()
                if all(w in c_low for w in words):
                    return p["name"]

        return cleaned

# ================= 2. BỘ ĐIỀU KHIỂN & CÀO DỮ LIỆU BLOGB =================
class BlogBPostScanner:
    def __init__(self, resolver: PageCatalogResolver):
        self.resolver = resolver
        self.driver = None

    def sync_scanner_profile(self):
        """Sao chép session và cookies từ ChromeProfile sang ScannerProfile để không bao giờ bị khóa profile."""
        if not os.path.exists(BROWSER_PROFILE_DIR):
            return SCANNER_PROFILE_DIR
        try:
            os.makedirs(os.path.join(SCANNER_PROFILE_DIR, "Default", "Network"), exist_ok=True)
            
            src_local_state = os.path.join(BROWSER_PROFILE_DIR, "Local State")
            dst_local_state = os.path.join(SCANNER_PROFILE_DIR, "Local State")
            if os.path.exists(src_local_state):
                shutil.copy2(src_local_state, dst_local_state)

            src_cookies = os.path.join(BROWSER_PROFILE_DIR, "Default", "Network", "Cookies")
            dst_cookies = os.path.join(SCANNER_PROFILE_DIR, "Default", "Network", "Cookies")
            if os.path.exists(src_cookies):
                shutil.copy2(src_cookies, dst_cookies)

            src_prefs = os.path.join(BROWSER_PROFILE_DIR, "Default", "Preferences")
            dst_prefs = os.path.join(SCANNER_PROFILE_DIR, "Default", "Preferences")
            if os.path.exists(src_prefs):
                shutil.copy2(src_prefs, dst_prefs)
        except Exception as e:
            print(f"Lưu ý sao chép session: {e}")
        return SCANNER_PROFILE_DIR

    def get_or_start_driver(self):
        if self.driver:
            try:
                _ = self.driver.window_handles
                return self.driver
            except Exception:
                self.driver = None

        profile_dir = self.sync_scanner_profile()

        options = Options()
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = Service(CHROMEDRIVER_PATH) if os.path.exists(CHROMEDRIVER_PATH) else None
        
        try:
            if service:
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(60)
            return self.driver
        except Exception as e:
            raise RuntimeError(f"Không thể khởi động Google Chrome: {e}")

    def scan_plan_by_date(self, target_date_str: str, progress_callback=None) -> list:
        """
        Quét bảng kế hoạch / kết quả đăng bài của BlogB theo ngày cụ thể (duyệt toàn bộ các trang).
        target_date_str: định dạng YYYY-MM-DD
        """
        driver = self.get_or_start_driver()
        results = []
        page_num = 1
        max_pages = 10

        while page_num <= max_pages:
            url = f"https://plan.blogb.io/app/plan?view=table&start_date={target_date_str}&end_date={target_date_str}&page={page_num}"
            
            if progress_callback:
                progress_callback(f"Đang mở trang {page_num} của ngày {target_date_str}...")

            driver.get(url)
            time.sleep(3.5)

            current_url = driver.current_url.lower()
            if "login" in current_url or "auth." in current_url:
                raise RuntimeError("Chưa đăng nhập BlogB! Vui lòng đăng nhập trên cửa sổ Chrome vừa mở rồi quét lại.")

            # Chờ bảng xuất hiện
            try:
                WebDriverWait(driver, 8).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, "table tbody tr")
                )
            except TimeoutException:
                pass

            # Cuộn trang nhẹ để tải hết
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.0)

            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            if not rows:
                if page_num == 1 and progress_callback:
                    progress_callback(f"Không tìm thấy bài đăng nào vào ngày {target_date_str}.")
                break

            if progress_callback:
                progress_callback(f"Trang {page_num}: Đang phân tích {len(rows)} bài đăng...")

            new_in_page = 0
            for idx, row in enumerate(rows):
                try:
                    tds = row.find_elements(By.TAG_NAME, "td")
                    if not tds or len(tds) < 3:
                        continue

                    # Cột 1: Tên Fanpage
                    raw_page_name = tds[0].text.strip()
                    # Thử lấy thêm tooltip / title nếu có
                    for el in tds[0].find_elements(By.CSS_SELECTOR, "[title], [aria-label], span, div"):
                        t_val = el.get_attribute("title") or el.get_attribute("aria-label") or ""
                        if t_val and len(t_val) > len(raw_page_name):
                            raw_page_name = t_val
                            break

                    full_page_name = self.resolver.resolve_name(raw_page_name)

                    # Cột 2: Tiêu đề video / bài viết
                    title_text = tds[1].text.strip()
                    t_lines = [tl.strip() for tl in title_text.splitlines() if tl.strip()]
                    post_title = t_lines[0] if t_lines else "N/A"

                    # Cột 3: Trạng thái & Chi tiết lỗi
                    col3_text = tds[2].text.strip()
                    col3_lines = [cl.strip() for cl in col3_text.splitlines() if cl.strip()]
                    
                    status = "UNKNOWN"
                    error_detail = ""

                    col3_low = col3_text.lower()
                    if "failed" in col3_low or "thất bại" in col3_low:
                        status = "THẤT BÀI"
                        # Dòng tiếp theo chính là chi tiết lỗi
                        if len(col3_lines) > 1:
                            error_detail = "\n".join(col3_lines[1:])
                        else:
                            # Tìm lỗi từ thuộc tính hoặc thẻ con
                            err_els = tds[2].find_elements(By.CSS_SELECTOR, "[class*='error'], [class*='danger'], [style*='red'], span, p")
                            for ee in err_els:
                                etxt = ee.text.strip()
                                if etxt and etxt.lower() not in ["failed", "thất bại"]:
                                    error_detail = etxt
                                    break
                    elif "published" in col3_low or "đã đăng" in col3_low:
                        status = "ĐÃ ĐĂNG"
                    elif "pending" in col3_low or "đang" in col3_low:
                        status = "CHỜ ĐĂNG"

                    # Cột 8 hoặc 9: Giờ đăng thực tế
                    post_time = ""
                    if len(tds) >= 9 and tds[8].text.strip():
                        post_time = tds[8].text.strip()
                    elif len(tds) >= 8 and tds[7].text.strip():
                        post_time = tds[7].text.strip()

                    # Creator
                    creator = ""
                    if len(tds) >= 8 and tds[7].text.strip():
                        creator = tds[7].text.strip()

                    item_data = {
                        "stt": len(results) + 1,
                        "raw_page_name": raw_page_name,
                        "page_name": full_page_name,
                        "status": status,
                        "error_detail": error_detail,
                        "post_time": post_time,
                        "post_title": post_title,
                        "creator": creator
                    }
                    results.append(item_data)
                    new_in_page += 1

                except Exception as row_err:
                    print(f"Lỗi parse dòng {idx}: {row_err}")
                    continue

            # Nếu trang này có ít hơn 20 bài thì đã hết các trang
            if len(rows) < 20 or new_in_page == 0:
                break
            page_num += 1

        return results

    def scan_notifications(self, progress_callback=None) -> list:
        """Bấm chuông thông báo 🔔 trên BlogB và trích xuất các thông báo lỗi."""
        driver = self.get_or_start_driver()
        if progress_callback:
            progress_callback("Đang tìm và mở chuông thông báo 🔔...")

        bell_selectors = [
            "button:has(svg)", "[aria-label*='notification']", "[aria-label*='thông báo']",
            "[data-icon='bell']", ".ant-badge", "[class*='notification']"
        ]
        bell_found = False
        for sel in bell_selectors:
            try:
                bells = driver.find_elements(By.CSS_SELECTOR, sel)
                for b in bells:
                    if b.is_displayed():
                        b.click()
                        bell_found = True
                        time.sleep(1.5)
                        break
                if bell_found:
                    break
            except Exception:
                continue

        if progress_callback:
            progress_callback("Đang đọc danh sách thông báo...")

        notices = []
        panel_items = driver.find_elements(By.CSS_SELECTOR, "[role='dialog'] li, [role='menu'] div, .ant-popover-inner, [class*='notification-item'], [class*='popover']")
        for item in panel_items:
            try:
                t = item.text.strip()
                if t and len(t) > 10:
                    notices.append(t)
            except Exception:
                continue

        return notices

# ================= 3. GIAO DIỆN NGƯỜI DÙNG HIỆN ĐẠI (TKINTER) =================
class PostStatusScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Page FB — Quét Tình Trạng & Lỗi Đăng Bài BlogB")
        self.root.geometry("1120x700")
        self.root.minsize(920, 560)

        self.resolver = PageCatalogResolver()
        self.scanner = BlogBPostScanner(self.resolver)
        self.scanned_data = []

        self._configure_styles()
        self._build_ui()

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("Header.TLabel", font=("Segoe UI", 15, "bold"), foreground="#0f172a")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#64748b")
        
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background="#2563eb", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#f1f5f9", foreground="#1e293b")
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=28)
        style.map("Treeview", background=[("selected", "#e0e7ff")], foreground=[("selected", "#1e1b4b")])

    def _build_ui(self):
        # Top Header Frame
        header_frame = tk.Frame(self.root, bg="#ffffff", padx=20, pady=12, bd=1, relief="solid")
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(header_frame, text="🔍 BẢNG SOÁT LỖI & TÌNH TRẠNG ĐĂNG BÀI (BLOGB)", style="Header.TLabel", background="#ffffff")
        title_lbl.pack(anchor="w")
        desc_lbl = ttk.Label(header_frame, text="Tự động bóc tách trạng thái, thời gian và chi tiết lỗi kèm tên Fanpage đầy đủ 100% của ngày đã chọn.", style="SubHeader.TLabel", background="#ffffff")
        desc_lbl.pack(anchor="w", pady=(2, 0))

        # Control Bar
        ctrl_frame = tk.Frame(self.root, bg="#f8fafc", padx=20, pady=12)
        ctrl_frame.pack(fill="x")

        tk.Label(ctrl_frame, text="Ngày quét (YYYY-MM-DD):", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#334155").pack(side="left", padx=(0, 6))
        
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_entry = ttk.Entry(ctrl_frame, textvariable=self.date_var, width=13, font=("Segoe UI", 10))
        self.date_entry.pack(side="left", padx=(0, 8))

        btn_today = ttk.Button(ctrl_frame, text="Hôm nay", command=self._set_today)
        btn_today.pack(side="left", padx=2)
        
        btn_yesterday = ttk.Button(ctrl_frame, text="Hôm qua", command=self._set_yesterday)
        btn_yesterday.pack(side="left", padx=2)

        self.btn_scan = ttk.Button(ctrl_frame, text="🚀 Bắt đầu quét BlogB", style="Primary.TButton", command=self._start_scan)
        self.btn_scan.pack(side="left", padx=(18, 6))

        self.btn_bell = ttk.Button(ctrl_frame, text="🔔 Quét chuông thông báo", command=self._start_bell_scan)
        self.btn_bell.pack(side="left", padx=6)

        # Filter Radios
        tk.Label(ctrl_frame, text="Hiển thị:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#334155").pack(side="left", padx=(25, 6))
        self.filter_var = tk.StringVar(value="ALL")
        for text, mode in [("Tất cả", "ALL"), ("🔴 Thất bại (Lỗi)", "FAILED"), ("🟢 Đã đăng", "SUCCESS")]:
            rb = ttk.Radiobutton(ctrl_frame, text=text, variable=self.filter_var, value=mode, command=self._apply_filter)
            rb.pack(side="left", padx=4)

        # Summary Metrics Bar
        summary_frame = tk.Frame(self.root, bg="#ffffff", padx=20, pady=8, bd=1, relief="groove")
        summary_frame.pack(fill="x", padx=15, pady=(8, 4))

        self.lbl_total = tk.Label(summary_frame, text="📊 Tổng bài: 0", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#1e293b")
        self.lbl_total.pack(side="left", padx=15)

        self.lbl_success = tk.Label(summary_frame, text="🟢 Thành công: 0", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#16a34a")
        self.lbl_success.pack(side="left", padx=15)

        self.lbl_failed = tk.Label(summary_frame, text="🔴 Thất bại: 0", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#dc2626")
        self.lbl_failed.pack(side="left", padx=15)

        self.lbl_status_msg = tk.Label(summary_frame, text="Sẵn sàng", font=("Segoe UI", 9, "italic"), bg="#ffffff", fg="#64748b")
        self.lbl_status_msg.pack(side="right", padx=15)

        # Table Frame
        table_frame = tk.Frame(self.root, padx=15, pady=6)
        table_frame.pack(fill="both", expand=True)

        columns = ("stt", "page_name", "status", "error_detail", "post_time", "post_title")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("stt", text="STT")
        self.tree.heading("page_name", text="Tên Fanpage (Chuẩn 100%)")
        self.tree.heading("status", text="Trạng thái")
        self.tree.heading("error_detail", text="Chi tiết lỗi chính xác")
        self.tree.heading("post_time", text="Giờ đăng")
        self.tree.heading("post_title", text="Tiêu đề bài viết")

        self.tree.column("stt", width=50, anchor="center")
        self.tree.column("page_name", width=220, anchor="w")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("error_detail", width=380, anchor="w")
        self.tree.column("post_time", width=140, anchor="center")
        self.tree.column("post_title", width=220, anchor="w")

        self.tree.tag_configure("failed_row", background="#fef2f2", foreground="#991b1b")
        self.tree.tag_configure("success_row", background="#f0fdf4", foreground="#166534")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bottom Action Bar
        bottom_frame = tk.Frame(self.root, bg="#f8fafc", padx=20, pady=12)
        bottom_frame.pack(fill="x")

        btn_copy_err = ttk.Button(bottom_frame, text="📋 Copy danh sách Page lỗi", command=self._copy_failed_pages)
        btn_copy_err.pack(side="left", padx=5)

        btn_mark_red = ttk.Button(bottom_frame, text="🔴 Chuyển các Page lỗi sang Page Đỏ", command=self._mark_pages_as_red)
        btn_mark_red.pack(side="left", padx=5)

        btn_export = ttk.Button(bottom_frame, text="📥 Xuất báo cáo TXT", command=self._export_report)
        btn_export.pack(side="right", padx=5)

    def _set_today(self):
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))

    def _set_yesterday(self):
        self.date_var.set((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))

    def _update_status(self, msg: str):
        self.lbl_status_msg.config(text=msg)
        self.root.update_idletasks()

    def _start_scan(self):
        date_val = self.date_var.get().strip()
        if "/" in date_val:
            parts = date_val.split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                date_val = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                self.date_var.set(date_val)

        self.btn_scan.config(state="disabled")
        self._update_status("Đang khởi động Chrome...")

        def _worker():
            try:
                results = self.scanner.scan_plan_by_date(date_val, progress_callback=self._update_status)
                self.scanned_data = results
                self.root.after(0, self._render_results)
                
                success_count = sum(1 for r in results if r["status"] == "ĐÃ ĐĂNG")
                failed_count = sum(1 for r in results if r["status"] == "THẤT BÀI")
                if results:
                    final_msg = f"Quét thành công! Tổng {len(results)} bài ({success_count} thành công, {failed_count} lỗi)."
                else:
                    final_msg = f"Không tìm thấy bài đăng nào trong ngày {date_val}."
                self.root.after(0, lambda: self._update_status(final_msg))
            except Exception as err:
                err_msg = str(err)
                self.root.after(0, lambda: messagebox.showerror("Lỗi quét dữ liệu", err_msg))
                self.root.after(0, lambda: self._update_status(f"Lỗi: {err_msg[:60]}"))
            finally:
                self.root.after(0, lambda: self.btn_scan.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _start_bell_scan(self):
        self.btn_bell.config(state="disabled")
        self._update_status("Đang quét chuông thông báo...")

        def _worker():
            try:
                notices = self.scanner.scan_notifications(progress_callback=self._update_status)
                self.root.after(0, lambda: self._show_notifications_dialog(notices))
                self.root.after(0, lambda: self._update_status(f"Đã đọc {len(notices)} thông báo."))
            except Exception as err:
                self.root.after(0, lambda: messagebox.showerror("Lỗi quét chuông", str(err)))
                self.root.after(0, lambda: self._update_status("Lỗi quét chuông."))
            finally:
                self.root.after(0, lambda: self.btn_bell.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_notifications_dialog(self, notices: list):
        if not notices:
            messagebox.showinfo("Chuông thông báo", "Không tìm thấy thông báo mới nào trên thanh thông báo.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Thông báo từ Chuông 🔔 BlogB")
        dlg.geometry("700x500")

        tk.Label(dlg, text=f"Đã tìm thấy {len(notices)} thông báo:", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=10)
        
        txt = tk.Text(dlg, wrap="word", padx=10, pady=10, font=("Segoe UI", 9))
        txt.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        for idx, n in enumerate(notices, 1):
            txt.insert("end", f"[{idx}] {n}\n--------------------------------------------------\n")
        txt.config(state="disabled")

    def _render_results(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        filter_mode = self.filter_var.get()
        total = len(self.scanned_data)
        success = sum(1 for r in self.scanned_data if r["status"] == "ĐÃ ĐĂNG")
        failed = sum(1 for r in self.scanned_data if r["status"] == "THẤT BÀI")

        self.lbl_total.config(text=f"📊 Tổng bài: {total}")
        self.lbl_success.config(text=f"🟢 Thành công: {success}")
        self.lbl_failed.config(text=f"🔴 Thất bại: {failed}")

        for r in self.scanned_data:
            if filter_mode == "FAILED" and r["status"] != "THẤT BÀI":
                continue
            if filter_mode == "SUCCESS" and r["status"] != "ĐÃ ĐĂNG":
                continue

            tag = "failed_row" if r["status"] == "THẤT BÀI" else ("success_row" if r["status"] == "ĐÃ ĐĂNG" else "")
            
            err_show = r["error_detail"] if r["error_detail"] else ("Thành công" if r["status"] == "ĐÃ ĐĂNG" else "—")
            self.tree.insert("", "end", values=(
                r["stt"],
                r["page_name"],
                r["status"],
                err_show,
                r["post_time"],
                r["post_title"]
            ), tags=(tag,))

    def _apply_filter(self):
        self._render_results()

    def _copy_failed_pages(self):
        failed_pages = [r["page_name"] for r in self.scanned_data if r["status"] == "THẤT BÀI" and r["page_name"]]
        unique_failed = list(dict.fromkeys(failed_pages))
        if not unique_failed:
            messagebox.showinfo("Thông báo", "Không có Fanpage nào bị lỗi trong danh sách hiện tại.")
            return

        text = "\n".join(unique_failed)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Đã copy", f"Đã copy danh sách {len(unique_failed)} Fanpage bị lỗi vào bộ nhớ tạm (Clipboard)!")

    def _mark_pages_as_red(self):
        failed_pages = [r["page_name"] for r in self.scanned_data if r["status"] == "THẤT BÀI" and r["page_name"]]
        unique_failed = set(failed_pages)
        if not unique_failed:
            messagebox.showinfo("Thông báo", "Không có Fanpage nào bị lỗi để đánh dấu.")
            return

        if not messagebox.askyesno("Xác nhận", f"Bạn có chắc muốn tự động chuyển {len(unique_failed)} Fanpage bị lỗi sang 'Page Đỏ' trong state.json của hệ thống?"):
            return

        if not os.path.exists(STATE_JSON_PATH):
            messagebox.showerror("Lỗi", "Không tìm thấy file state.json của hệ thống.")
            return

        try:
            with open(STATE_JSON_PATH, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            count = 0
            groups = state_data.get("page_catalog", {}).get("groups", {})
            for gid, g in groups.items():
                for p in g.get("pages", []):
                    if p.get("name") in unique_failed:
                        p["default_status"] = "red"
                        count += 1

            with open(STATE_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)

            messagebox.showinfo("Thành công", f"Đã cập nhật trạng thái 'Page Đỏ' cho {count} Fanpage trong hệ thống!")
        except Exception as e:
            messagebox.showerror("Lỗi cập nhật", f"Lỗi khi lưu state.json: {e}")

    def _export_report(self):
        if not self.scanned_data:
            messagebox.showinfo("Thông báo", "Chưa có dữ liệu quét để xuất báo cáo.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile=f"Bao_cao_loi_dang_bai_{self.date_var.get()}.txt"
        )
        if not filepath:
            return

        lines = [
            f"BÁO CÁO TÌNH TRẠNG ĐĂNG BÀI FANPAGE (BLOGB)",
            f"Ngày quét: {self.date_var.get()}",
            f"Xuất lúc: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}",
            f"Tổng số bài: {len(self.scanned_data)}",
            f"Thành công: {sum(1 for r in self.scanned_data if r['status'] == 'ĐÃ ĐĂNG')}",
            f"Thất bại: {sum(1 for r in self.scanned_data if r['status'] == 'THẤT BÀI')}",
            "=" * 90,
            f"{'STT':<5} | {'TÊN FANPAGE':<30} | {'TRẠNG THÁI':<12} | {'CHI TIẾT LỖI':<40} | {'GIỜ ĐĂNG'}",
            "-" * 90
        ]

        for r in self.scanned_data:
            err = r["error_detail"] if r["error_detail"] else ("OK" if r["status"] == "ĐÃ ĐĂNG" else "—")
            lines.append(f"{r['stt']:<5} | {r['page_name']:<30} | {r['status']:<12} | {err:<40} | {r['post_time']}")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Thành công", f"Đã lưu báo cáo thành công vào:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Lỗi xuất file", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = PostStatusScannerApp(root)
    root.mainloop()
