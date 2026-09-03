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
import threading
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Selenium imports
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
        # Loại bỏ các ký tự dấu chấm, dấu ba chấm thừa ở đuôi
        norm = re.sub(r'[\.\s…]+$', '', cleaned).strip().lower()
        if not norm:
            return cleaned

        # 1. Tìm khớp chính xác (không hoa thường)
        if norm in self.name_map:
            return self.name_map[norm]

        # 2. Tìm khớp tiền tố (prefix match)
        candidates = []
        for p in self.catalog_pages:
            c_name = p["name"]
            c_low = c_name.lower()
            if c_low.startswith(norm):
                candidates.append(c_name)

        if len(candidates) == 1:
            return candidates[0]
        elif len(candidates) > 1:
            # Chọn ứng viên có độ dài tương tự hoặc tốt nhất
            candidates.sort(key=lambda x: len(x))
            return candidates[0]

        # 3. Tìm theo từng từ (word match)
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

    def get_or_start_driver(self):
        if self.driver:
            try:
                _ = self.driver.window_handles
                return self.driver
            except Exception:
                self.driver = None

        options = Options()
        if os.path.exists(BROWSER_PROFILE_DIR):
            options.add_argument(f"--user-data-dir={BROWSER_PROFILE_DIR}")
        
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
        Quét bảng kế hoạch / kết quả đăng bài của BlogB theo ngày cụ thể.
        target_date_str: định dạng YYYY-MM-DD
        """
        driver = self.get_or_start_driver()
        url = f"https://plan.blogb.io/app/plan?view=table&start_date={target_date_str}&end_date={target_date_str}"
        
        if progress_callback:
            progress_callback(f"Đang mở trang Kế hoạch BlogB ngày {target_date_str}...")

        driver.get(url)
        time.sleep(3.5)

        # Chờ bảng xuất hiện
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "table tbody tr, [role='row'], [data-testid*='row']")
            )
        except TimeoutException:
            pass

        # Cuộn trang để nạp toàn bộ danh sách (nếu có lazy loading)
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.8)

        # Tìm tất cả các dòng bài đăng
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr, [role='row']")
        if progress_callback:
            progress_callback(f"Tìm thấy {len(rows)} dòng bài đăng. Đang phân tích...")

        results = []
        for idx, row in enumerate(rows):
            try:
                row_text = row.text.strip()
                if not row_text:
                    continue

                # 1. Bóc tách Tên Fanpage
                raw_page_name = ""
                # Tìm element chứa tên page: có thể có title hoặc thẻ span/div
                page_candidates = row.find_elements(By.CSS_SELECTOR, "div, span, a, p")
                for el in page_candidates:
                    title_attr = el.get_attribute("title") or el.get_attribute("aria-label") or ""
                    txt = el.text.strip()
                    if title_attr and len(title_attr) > 2 and len(title_attr) < 100:
                        raw_page_name = title_attr
                        break
                    if txt and "..." in txt and len(txt) < 50:
                        raw_page_name = txt
                        break

                if not raw_page_name:
                    # Fallback lấy từ dòng đầu tiên của text
                    lines = [l.strip() for l in row_text.splitlines() if l.strip()]
                    if lines:
                        raw_page_name = lines[0]

                # Ánh xạ tên chuẩn 100% từ catalog
                full_page_name = self.resolver.resolve_name(raw_page_name)

                # 2. Bóc tách Trạng thái (Đã đăng / Thất bại)
                status = "UNKNOWN"
                error_detail = ""
                
                low_text = row_text.lower()
                if "thất bại" in low_text or "failed" in low_text:
                    status = "THẤT BÀI"
                elif "đã đăng" in low_text or "published" in low_text:
                    status = "ĐÃ ĐĂNG"
                elif "đang đăng" in low_text or "chờ" in low_text:
                    status = "ĐANG XỬ LÝ"

                # 3. Bóc tách Nội dung lỗi cụ thể
                if status == "THẤT BÀI":
                    # Tìm dòng thông báo lỗi
                    for line in row_text.splitlines():
                        l_strip = line.strip()
                        l_low = l_strip.lower()
                        if any(k in l_low for k in ["giới hạn", "facebook", "checkpoint", "xác minh", "lỗi", "error", "failed", "hết hạn", "token", "quản trị"]):
                            if l_low != "thất bại" and not l_low.startswith("thất bại"):
                                error_detail = l_strip
                                break
                    if not error_detail:
                        # Thử lấy element màu đỏ / class lỗi
                        error_els = row.find_elements(By.CSS_SELECTOR, "[class*='error'], [class*='danger'], [style*='red'], span, p")
                        for err_el in error_els:
                            e_txt = err_el.text.strip()
                            if e_txt and "giới hạn" in e_txt.lower():
                                error_detail = e_txt
                                break

                # 4. Bóc tách Giờ đăng & Tiêu đề
                post_time = ""
                time_match = re.search(r'\b(\d{1,2}:\d{2}(?:\s+\d{2}/\d{2}/\d{4})?)\b', row_text)
                if time_match:
                    post_time = time_match.group(1)

                # Tiêu đề bài viết
                post_title = ""
                lines = [l.strip() for l in row_text.splitlines() if l.strip()]
                for l in lines:
                    if len(l) > 15 and l != error_detail and l != raw_page_name and l != full_page_name:
                        post_title = l
                        break

                results.append({
                    "stt": idx + 1,
                    "raw_page_name": raw_page_name,
                    "page_name": full_page_name,
                    "status": status,
                    "error_detail": error_detail,
                    "post_time": post_time,
                    "post_title": post_title[:120] if post_title else "N/A",
                    "raw_text": row_text
                })

            except Exception as row_err:
                print(f"Lỗi dòng {idx}: {row_err}")
                continue

        return results

    def scan_notifications(self, progress_callback=None) -> list:
        """Bấm chuông thông báo 🔔 trên BlogB và trích xuất các thông báo lỗi."""
        driver = self.get_or_start_driver()
        if progress_callback:
            progress_callback("Đang tìm và mở chuông thông báo 🔔...")

        # Tìm nút chuông
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
        # Tìm các panel thông báo
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
        self.root.geometry("1100x680")
        self.root.minsize(900, 550)

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
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        
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

        # Control & Filter Bar
        ctrl_frame = tk.Frame(self.root, bg="#f8fafc", padx=20, pady=12)
        ctrl_frame.pack(fill="x")

        tk.Label(ctrl_frame, text="Chọn ngày quét:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#334155").pack(side="left", padx=(0, 6))
        
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_entry = ttk.Entry(ctrl_frame, textvariable=self.date_var, width=12, font=("Segoe UI", 10))
        self.date_entry.pack(side="left", padx=(0, 8))

        # Quick Date buttons
        btn_today = ttk.Button(ctrl_frame, text="Hôm nay", command=self._set_today)
        btn_today.pack(side="left", padx=2)
        
        btn_yesterday = ttk.Button(ctrl_frame, text="Hôm qua", command=self._set_yesterday)
        btn_yesterday.pack(side="left", padx=2)

        # Action Buttons
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
        self.tree.column("error_detail", width=360, anchor="w")
        self.tree.column("post_time", width=130, anchor="center")
        self.tree.column("post_title", width=220, anchor="w")

        # Tags for colored rows
        self.tree.tag_configure("failed_row", background="#fef2f2", foreground="#991b1b")
        self.tree.tag_configure("success_row", background="#f0fdf4", foreground="#166534")

        # Scrollbars
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
        # Chuẩn hóa ngày nếu người dùng gõ DD/MM/YYYY
        if "/" in date_val:
            parts = date_val.split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                date_val = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                self.date_var.set(date_val)

        self.btn_scan.config(state="disabled")
        self._update_status("Đang kết nối BlogB...")

        def _worker():
            try:
                results = self.scanner.scan_plan_by_date(date_val, progress_callback=self._update_status)
                self.scanned_data = results
                self.root.after(0, self._render_results)
            except Exception as err:
                self.root.after(0, lambda: messagebox.showerror("Lỗi quét dữ liệu", str(err)))
            finally:
                self.root.after(0, lambda: self.btn_scan.config(state="normal"))
                self.root.after(0, lambda: self._update_status("Quét hoàn tất!"))

        threading.Thread(target=_worker, daemon=True).start()

    def _start_bell_scan(self):
        self.btn_bell.config(state="disabled")
        self._update_status("Đang quét chuông thông báo...")

        def _worker():
            try:
                notices = self.scanner.scan_notifications(progress_callback=self._update_status)
                self.root.after(0, lambda: self._show_notifications_dialog(notices))
            except Exception as err:
                self.root.after(0, lambda: messagebox.showerror("Lỗi quét chuông", str(err)))
            finally:
                self.root.after(0, lambda: self.btn_bell.config(state="normal"))
                self.root.after(0, lambda: self._update_status("Sẵn sàng"))

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

        visible_count = 0
        for r in self.scanned_data:
            if filter_mode == "FAILED" and r["status"] != "THẤT BÀI":
                continue
            if filter_mode == "SUCCESS" and r["status"] != "ĐÃ ĐĂNG":
                continue

            tag = "failed_row" if r["status"] == "THẤT BÀI" else ("success_row" if r["status"] == "ĐÃ ĐĂNG" else "")
            self.tree.insert("", "end", values=(
                r["stt"],
                r["page_name"],
                r["status"],
                r["error_detail"] if r["error_detail"] else ("Thành công" if r["status"] == "ĐÃ ĐĂNG" else "—"),
                r["post_time"],
                r["post_title"]
            ), tags=(tag,))
            visible_count += 1

    def _apply_filter(self):
        self._render_results()

    def _copy_failed_pages(self):
        failed_pages = [r["page_name"] for r in self.scanned_data if r["status"] == "THẤT BÀI" and r["page_name"]]
        # Loại bỏ trùng lặp giữ nguyên thứ tự
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
            f"{'STT':<5} | {'TÊN FANPAGE':<30} | {'TRẠNG THÁI':<12} | {'CHI TIẾT LỖI':<35} | {'GIỜ ĐĂNG'}",
            "-" * 90
        ]

        for r in self.scanned_data:
            err = r["error_detail"] if r["error_detail"] else ("OK" if r["status"] == "ĐÃ ĐĂNG" else "—")
            lines.append(f"{r['stt']:<5} | {r['page_name']:<30} | {r['status']:<12} | {err:<35} | {r['post_time']}")

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
