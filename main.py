# -*- coding: utf-8 -*-
"""
Main Application Launcher for Page FB
Tích hợp trực tiếp chức năng 'Kiểm tra lỗi đăng bài' vào thanh công cụ của Page FB,
loại bỏ 3 nút Đồng bộ Sheet và cập nhật trạng thái Page Đỏ trực tiếp lên giao diện.
"""

import os
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# Thêm đường dẫn _engine vào sys.path
BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
ENGINE_DIR = BASE_DIR / "_engine"
if ENGINE_DIR.is_dir():
    sys.path.insert(0, str(ENGINE_DIR))
else:
    alt_engine = Path(__file__).resolve().parent / "_engine"
    if alt_engine.is_dir():
        sys.path.insert(0, str(alt_engine))

import core
import automation
import page_fb
from core import install_page_catalog
from post_status_scanner import BlogBPostScanner, PageCatalogResolver

class EmbeddedPostStatusScannerDialog(tk.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.main_app = parent_app
        self.title("Page FB — Kiểm Tra Lỗi Đăng Bài BlogB")
        self.geometry("1200x720")
        self.minsize(1000, 580)

        # Trỏ đến state.json hiện tại của tài khoản đang chọn
        current_acc = self.main_app.account_registry.current() if hasattr(self.main_app, "account_registry") else None
        state_path = current_acc.get("state_path") if current_acc else str(self.main_app.repository.path)
        
        self.resolver = PageCatalogResolver(state_path)
        self.scanner = BlogBPostScanner(self.resolver, main_app=self.main_app)
        self.scanned_data = []
        self.stop_event = None

        self._configure_styles()
        self._build_ui()

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # ── Sidebar / panel nền
        BG_MAIN   = "#f0f2f5"
        BG_SIDEBAR= "#1e2433"
        BG_CARD   = "#ffffff"

        # ── Buttons
        style.configure("Scan.TButton",
            font=("Segoe UI", 10, "bold"),
            background="#3b82f6", foreground="#ffffff",
            padding=(14, 8), relief="flat", borderwidth=0)
        style.map("Scan.TButton",
            background=[("active","#2563eb"), ("disabled","#94a3b8")],
            foreground=[("disabled","#e2e8f0")])

        style.configure("Stop.TButton",
            font=("Segoe UI", 10),
            background="#ef4444", foreground="#ffffff",
            padding=(10, 8), relief="flat", borderwidth=0)
        style.map("Stop.TButton",
            background=[("active","#dc2626"), ("disabled","#fca5a5")],
            foreground=[("disabled","#ffffff")])

        style.configure("Action.TButton",
            font=("Segoe UI", 9),
            background="#334155", foreground="#f1f5f9",
            padding=(10, 7), relief="flat", borderwidth=0)
        style.map("Action.TButton",
            background=[("active","#475569")])

        style.configure("Danger.TButton",
            font=("Segoe UI", 9, "bold"),
            background="#dc2626", foreground="#ffffff",
            padding=(10, 7), relief="flat", borderwidth=0)
        style.map("Danger.TButton",
            background=[("active","#b91c1c")])

        style.configure("Bell.TButton",
            font=("Segoe UI", 9),
            background="#7c3aed", foreground="#ffffff",
            padding=(10, 7), relief="flat", borderwidth=0)
        style.map("Bell.TButton",
            background=[("active","#6d28d9")])

        # ── Table
        style.configure("Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#1e2433", foreground="#e2e8f0",
            padding=8, relief="flat")
        style.configure("Treeview",
            font=("Segoe UI", 9),
            rowheight=30,
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1e293b",
            borderwidth=0)
        style.map("Treeview",
            background=[("selected","#dbeafe")],
            foreground=[("selected","#1e40af")])

        # ── Radiobutton filter
        style.configure("Filter.TRadiobutton",
            font=("Segoe UI", 9),
            background=BG_SIDEBAR,
            foreground="#e2e8f0")
        style.map("Filter.TRadiobutton",
            background=[("active", BG_SIDEBAR)],
            foreground=[("active", "#93c5fd")])

        # ── Combobox
        style.configure("TCombobox",
            font=("Segoe UI", 9),
            fieldbackground="#ffffff",
            background="#ffffff")

        # store for usage in build
        self._BG_MAIN = BG_MAIN
        self._BG_SIDEBAR = BG_SIDEBAR
        self._BG_CARD = BG_CARD

    def _build_ui(self):
        import threading
        from datetime import datetime, timedelta

        BG         = self._BG_MAIN
        SIDEBAR    = self._BG_SIDEBAR
        CARD       = self._BG_CARD
        TEXT_MAIN  = "#1e293b"
        TEXT_MUTED = "#64748b"
        ACCENT     = "#3b82f6"

        self.configure(bg=BG)

        # ════════════════════════════════════════════════════
        # ROOT layout: sidebar (trái) + main (phải)
        # ════════════════════════════════════════════════════
        root_frame = tk.Frame(self, bg=BG)
        root_frame.pack(fill="both", expand=True)

        # ────────────── SIDEBAR ──────────────
        sidebar = tk.Frame(root_frame, bg=SIDEBAR, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo / title
        tk.Label(sidebar, text="📋", font=("Segoe UI", 28),
                 bg=SIDEBAR, fg=ACCENT).pack(pady=(28, 4))
        tk.Label(sidebar, text="Soát Lỗi\nĐăng Bài", font=("Segoe UI", 13, "bold"),
                 bg=SIDEBAR, fg="#f1f5f9", justify="center").pack()
        tk.Label(sidebar, text="BlogB Auto-Scanner", font=("Segoe UI", 8),
                 bg=SIDEBAR, fg="#64748b").pack(pady=(2, 24))

        # Separator
        tk.Frame(sidebar, bg="#2d3748", height=1).pack(fill="x", padx=16, pady=(0, 20))

        # ── Ngày quét
        tk.Label(sidebar, text="NGÀY QUÉT", font=("Segoe UI", 8, "bold"),
                 bg=SIDEBAR, fg="#64748b").pack(anchor="w", padx=20, pady=(0, 4))

        date_frame = tk.Frame(sidebar, bg=SIDEBAR)
        date_frame.pack(fill="x", padx=16, pady=(0, 8))
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = tk.Entry(date_frame, textvariable=self.date_var,
                              font=("Segoe UI", 11), width=14,
                              bg="#2d3748", fg="#f1f5f9",
                              insertbackground="#f1f5f9",
                              relief="flat", bd=6)
        date_entry.pack(fill="x")

        quick_frame = tk.Frame(sidebar, bg=SIDEBAR)
        quick_frame.pack(fill="x", padx=16, pady=(0, 18))

        def _make_quick_btn(parent, label, cmd):
            b = tk.Button(parent, text=label,
                          font=("Segoe UI", 8), command=cmd,
                          bg="#2d3748", fg="#94a3b8",
                          activebackground="#374151", activeforeground="#e2e8f0",
                          relief="flat", bd=0, padx=8, pady=4, cursor="hand2")
            return b

        btn_today = _make_quick_btn(quick_frame, "Hôm nay",
            lambda: self.date_var.set(datetime.now().strftime("%Y-%m-%d")))
        btn_today.pack(side="left", expand=True, fill="x", padx=(0, 4))

        btn_yest = _make_quick_btn(quick_frame, "Hôm qua",
            lambda: self.date_var.set((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")))
        btn_yest.pack(side="left", expand=True, fill="x")

        # ── Số trang
        tk.Label(sidebar, text="SỐ TRANG TỐI ĐA", font=("Segoe UI", 8, "bold"),
                 bg=SIDEBAR, fg="#64748b").pack(anchor="w", padx=20, pady=(0, 4))

        self.pages_var = tk.StringVar(value="Tất cả")
        pages_combo = ttk.Combobox(sidebar, textvariable=self.pages_var,
                                   values=["Tất cả", "10 trang", "20 trang", "30 trang", "50 trang"],
                                   state="readonly", font=("Segoe UI", 9), width=18)
        pages_combo.pack(padx=16, fill="x", pady=(0, 24))

        tk.Frame(sidebar, bg="#2d3748", height=1).pack(fill="x", padx=16, pady=(0, 20))

        # ── Nút chính: Quét
        self.btn_scan = tk.Button(sidebar, text="▶  Bắt đầu quét",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg="#ffffff",
            activebackground="#2563eb", activeforeground="#ffffff",
            relief="flat", bd=0, padx=0, pady=12,
            cursor="hand2", command=self._start_scan)
        self.btn_scan.pack(fill="x", padx=16, pady=(0, 6))

        self.btn_stop = tk.Button(sidebar, text="■  Dừng quét",
            font=("Segoe UI", 10),
            bg="#7f1d1d", fg="#fca5a5",
            activebackground="#991b1b", activeforeground="#ffffff",
            relief="flat", bd=0, padx=0, pady=10,
            cursor="hand2", state="disabled", command=self._stop_scan)
        self.btn_stop.pack(fill="x", padx=16, pady=(0, 18))

        self.btn_bell = tk.Button(sidebar, text="🔔  Quét chuông",
            font=("Segoe UI", 9),
            bg="#312e81", fg="#c7d2fe",
            activebackground="#3730a3", activeforeground="#ffffff",
            relief="flat", bd=0, padx=0, pady=9,
            cursor="hand2", command=self._start_bell_scan)
        self.btn_bell.pack(fill="x", padx=16, pady=(0, 20))

        tk.Frame(sidebar, bg="#2d3748", height=1).pack(fill="x", padx=16, pady=(0, 20))

        # ── Bộ lọc hiển thị
        tk.Label(sidebar, text="BỘ LỌC", font=("Segoe UI", 8, "bold"),
                 bg=SIDEBAR, fg="#64748b").pack(anchor="w", padx=20, pady=(0, 8))

        self.filter_var = tk.StringVar(value="ALL")
        filter_defs = [
            ("Tất cả bài", "ALL", "#e2e8f0"),
            ("Thất bại / Lỗi", "FAILED", "#fca5a5"),
            ("Đã đăng thành công", "SUCCESS", "#86efac"),
        ]
        for label, mode, color in filter_defs:
            row = tk.Frame(sidebar, bg=SIDEBAR, cursor="hand2")
            row.pack(fill="x", padx=16, pady=1)
            dot = tk.Label(row, text="●", font=("Segoe UI", 8),
                           bg=SIDEBAR, fg=color)
            dot.pack(side="left", padx=(0, 6))
            rb = tk.Radiobutton(row, text=label,
                                variable=self.filter_var, value=mode,
                                command=self._apply_filter,
                                font=("Segoe UI", 9),
                                bg=SIDEBAR, fg="#cbd5e1",
                                activebackground=SIDEBAR, activeforeground="#ffffff",
                                selectcolor="#0f172a", bd=0)
            rb.pack(side="left", fill="x")

        # ── Nút hành động (dưới cùng sidebar)
        tk.Frame(sidebar, bg=SIDEBAR).pack(expand=True, fill="y")   # spacer
        tk.Frame(sidebar, bg="#2d3748", height=1).pack(fill="x", padx=16, pady=(0, 14))

        self.btn_copy_err = tk.Button(sidebar, text="📋  Copy Page lỗi",
            font=("Segoe UI", 9),
            bg="#1e3a5f", fg="#93c5fd",
            activebackground="#1e40af", activeforeground="#ffffff",
            relief="flat", bd=0, pady=9, cursor="hand2",
            command=self._copy_failed_pages)
        self.btn_copy_err.pack(fill="x", padx=16, pady=(0, 5))

        self.btn_mark_red = tk.Button(sidebar, text="🔴  Chuyển sang Page Đỏ",
            font=("Segoe UI", 9, "bold"),
            bg="#7f1d1d", fg="#fca5a5",
            activebackground="#991b1b", activeforeground="#ffffff",
            relief="flat", bd=0, pady=9, cursor="hand2",
            command=self._mark_pages_as_red_and_update_main_ui)
        self.btn_mark_red.pack(fill="x", padx=16, pady=(0, 5))

        self.btn_export = tk.Button(sidebar, text="📥  Xuất báo cáo TXT",
            font=("Segoe UI", 9),
            bg="#1c3a2e", fg="#86efac",
            activebackground="#166534", activeforeground="#ffffff",
            relief="flat", bd=0, pady=9, cursor="hand2",
            command=self._export_report)
        self.btn_export.pack(fill="x", padx=16, pady=(0, 20))

        # ════════════════════════════════════════════════════
        # MAIN PANEL
        # ════════════════════════════════════════════════════
        main_panel = tk.Frame(root_frame, bg=BG)
        main_panel.pack(side="left", fill="both", expand=True)

        # ── Topbar với stats cards
        topbar = tk.Frame(main_panel, bg=BG, pady=12)
        topbar.pack(fill="x", padx=16)

        def _stat_card(parent, label, value_text, value_color, icon):
            card = tk.Frame(parent, bg=CARD, padx=18, pady=12,
                            relief="flat", bd=0,
                            highlightbackground="#e2e8f0",
                            highlightthickness=1)
            card.pack(side="left", padx=(0, 10), fill="y")
            top_row = tk.Frame(card, bg=CARD)
            top_row.pack(anchor="w")
            tk.Label(top_row, text=icon, font=("Segoe UI", 13),
                     bg=CARD, fg=value_color).pack(side="left", padx=(0, 6))
            val_lbl = tk.Label(top_row, text=value_text,
                               font=("Segoe UI", 18, "bold"),
                               bg=CARD, fg=value_color)
            val_lbl.pack(side="left")
            tk.Label(card, text=label,
                     font=("Segoe UI", 8),
                     bg=CARD, fg=TEXT_MUTED).pack(anchor="w")
            return val_lbl

        self._val_total   = _stat_card(topbar, "TỔNG BÀI ĐĂNG",  "0", TEXT_MAIN,  "📄")
        self._val_success = _stat_card(topbar, "ĐÃ ĐĂNG",         "0", "#16a34a",  "✅")
        self._val_failed  = _stat_card(topbar, "THẤT BẠI",        "0", "#dc2626",  "❌")

        # Status bar nằm bên phải topbar
        self.lbl_status_msg = tk.Label(topbar,
            text="Sẵn sàng — chọn ngày và bấm Bắt đầu quét.",
            font=("Segoe UI", 9, "italic"),
            bg=BG, fg=TEXT_MUTED,
            wraplength=340, justify="right")
        self.lbl_status_msg.pack(side="right", padx=(10, 0), anchor="e")

        # Thêm alias để code cũ vẫn hoạt động
        self.lbl_total   = self._val_total
        self.lbl_success = self._val_success
        self.lbl_failed  = self._val_failed

        # ── Bảng dữ liệu
        table_outer = tk.Frame(main_panel, bg=BG, padx=16, pady=(0, 10))
        table_outer.pack(fill="both", expand=True)

        # Card bao bên ngoài bảng
        table_card = tk.Frame(table_outer, bg=CARD,
                              highlightbackground="#e2e8f0",
                              highlightthickness=1)
        table_card.pack(fill="both", expand=True)

        columns = ("stt", "page_name", "status", "error_detail", "post_time", "post_title")
        self.tree = ttk.Treeview(table_card, columns=columns,
                                 show="headings", selectmode="extended")

        self.tree.heading("stt",          text="#",      anchor="center")
        self.tree.heading("page_name",    text="Tên Fanpage",    anchor="w")
        self.tree.heading("status",       text="Trạng thái",     anchor="center")
        self.tree.heading("error_detail", text="Chi tiết lỗi",   anchor="w")
        self.tree.heading("post_time",    text="Giờ đăng",       anchor="center")
        self.tree.heading("post_title",   text="Tiêu đề bài",    anchor="w")

        self.tree.column("stt",          width=44,  minwidth=36,  anchor="center",  stretch=False)
        self.tree.column("page_name",    width=200, minwidth=140, anchor="w")
        self.tree.column("status",       width=105, minwidth=90,  anchor="center",  stretch=False)
        self.tree.column("error_detail", width=380, minwidth=200, anchor="w")
        self.tree.column("post_time",    width=130, minwidth=100, anchor="center",  stretch=False)
        self.tree.column("post_title",   width=200, minwidth=120, anchor="w")

        self.tree.tag_configure("failed_row",  background="#fff1f2", foreground="#9f1239")
        self.tree.tag_configure("success_row", background="#f0fdf4", foreground="#14532d")
        self.tree.tag_configure("alt_row",     background="#f8fafc")

        vsb = ttk.Scrollbar(table_card, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(table_card, orient="horizontal",  command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_card.grid_rowconfigure(0, weight=1)
        table_card.grid_columnconfigure(0, weight=1)

    def _update_status(self, msg: str):
        self.lbl_status_msg.config(text=msg)
        self.update_idletasks()

    def _stop_scan(self):
        if self.stop_event:
            self.stop_event.set()
        self._update_status("Đang gửi yêu cầu dừng quét...")
        self.btn_stop.config(state="disabled")

    def _start_scan(self):
        import threading
        date_val = self.date_var.get().strip()
        if "/" in date_val:
            parts = date_val.split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                date_val = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                self.date_var.set(date_val)

        p_opt = self.pages_var.get()
        if "10" in p_opt:
            max_pages = 10
        elif "20" in p_opt:
            max_pages = 20
        elif "30" in p_opt:
            max_pages = 30
        elif "50" in p_opt:
            max_pages = 50
        else:
            max_pages = 500

        self.stop_event = threading.Event()
        self.btn_scan.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._update_status("Đang khởi động Chrome...")

        def _worker():
            try:
                results = self.scanner.scan_plan_by_date(
                    date_val,
                    max_pages=max_pages,
                    progress_callback=self._update_status,
                    stop_event=self.stop_event
                )
                self.scanned_data = results
                self.after(0, self._render_results)
                
                success_count = sum(1 for r in results if r["status"] == "ĐÃ ĐĂNG")
                failed_count = sum(1 for r in results if r["status"] == "THẤT BÀI")
                if results:
                    final_msg = f"Quét thành công! Tổng {len(results)} bài ({success_count} thành công, {failed_count} lỗi)."
                else:
                    final_msg = f"Không tìm thấy bài đăng nào trong ngày {date_val}."
                self.after(0, lambda: self._update_status(final_msg))
            except Exception as err:
                err_msg = str(err)
                self.after(0, lambda: messagebox.showerror("Lỗi quét dữ liệu", err_msg, parent=self))
                self.after(0, lambda: self._update_status(f"Lỗi: {err_msg[:60]}"))
            finally:
                # Tự động tắt Chrome để giải phóng bộ nhớ & nhẹ máy
                self.scanner.close_driver()
                self.after(0, lambda: self.btn_scan.config(state="normal"))
                self.after(0, lambda: self.btn_stop.config(state="disabled"))

        threading.Thread(target=_worker, daemon=True).start()

    def _start_bell_scan(self):
        import threading
        self.btn_bell.config(state="disabled")
        self._update_status("Đang quét chuông thông báo...")

        def _worker():
            try:
                notices = self.scanner.scan_notifications(progress_callback=self._update_status)
                self.after(0, lambda: self._show_notifications_dialog(notices))
                self.after(0, lambda: self._update_status(f"Đã đọc {len(notices)} thông báo."))
            except Exception as err:
                self.after(0, lambda: messagebox.showerror("Lỗi quét chuông", str(err), parent=self))
                self.after(0, lambda: self._update_status("Lỗi quét chuông."))
            finally:
                # Tự động tắt Chrome sau khi quét chuông xong
                self.scanner.close_driver()
                self.after(0, lambda: self.btn_bell.config(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_notifications_dialog(self, notices: list):
        if not notices:
            messagebox.showinfo("Chuông thông báo", "Không tìm thấy thông báo mới nào trên thanh thông báo.", parent=self)
            return

        dlg = tk.Toplevel(self)
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

        # Cập nhật stat cards
        self._val_total.config(text=str(total))
        self._val_success.config(text=str(success))
        self._val_failed.config(text=str(failed))

        row_idx = 0
        for r in self.scanned_data:
            if filter_mode == "FAILED" and r["status"] != "THẤT BÀI":
                continue
            if filter_mode == "SUCCESS" and r["status"] != "ĐÃ ĐĂNG":
                continue

            if r["status"] == "THẤT BÀI":
                tag = "failed_row"
            elif r["status"] == "ĐÃ ĐĂNG":
                tag = "success_row"
            elif row_idx % 2 == 1:
                tag = "alt_row"
            else:
                tag = ""

            err_show = r["error_detail"] if r["error_detail"] else ("Thành công" if r["status"] == "ĐÃ ĐĂNG" else "—")
            self.tree.insert("", "end", values=(
                r["stt"],
                r["page_name"],
                r["status"],
                err_show,
                r["post_time"],
                r["post_title"]
            ), tags=(tag,))
            row_idx += 1

    def _apply_filter(self):
        self._render_results()

    def _copy_failed_pages(self):
        failed_pages = [r["page_name"] for r in self.scanned_data if r["status"] == "THẤT BÀI" and r["page_name"]]
        unique_failed = list(dict.fromkeys(failed_pages))
        if not unique_failed:
            messagebox.showinfo("Thông báo", "Không có Fanpage nào bị lỗi trong danh sách hiện tại.", parent=self)
            return

        text = "\n".join(unique_failed)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Đã copy", f"Đã copy danh sách {len(unique_failed)} Fanpage bị lỗi vào bộ nhớ tạm (Clipboard)!", parent=self)

    def _mark_pages_as_red_and_update_main_ui(self):
        """Chuyển các Page lỗi sang Page Đỏ và tự động cập nhật ngay trên giao diện chính."""
        failed_pages = [r["page_name"] for r in self.scanned_data if r["status"] == "THẤT BÀI" and r["page_name"]]
        unique_failed = set(failed_pages)
        if not unique_failed:
            messagebox.showinfo("Thông báo", "Không có Fanpage nào bị lỗi để đánh dấu.", parent=self)
            return

        if not messagebox.askyesno("Xác nhận chuyển sang Page Đỏ", 
                                   f"Tìm thấy {len(unique_failed)} Fanpage bị lỗi đăng bài.\n\n"
                                   "Bạn có chắc muốn tự động chuyển các Page này sang 'Page Đỏ' và cập nhật ngay vào giao diện chính?", 
                                   parent=self):
            return

        # Thực hiện cập nhật vào state_data của main_app
        state = self.main_app.state_data
        catalog = state.get("page_catalog", {})
        groups = catalog.get("groups", {})
        count = 0

        for raw_gid, group_data in groups.items():
            gid = int(raw_gid)
            red_keys = set(state.setdefault("blocked", {}).get(str(gid), []))
            green_keys = set(state.setdefault("green_pages", {}).get(str(gid), []))
            changed = False
            for row in group_data.get("pages", []):
                name = row.get("name", "").strip()
                key = row.get("key", "").strip()
                if name in unique_failed and key:
                    row["default_status"] = "red"
                    red_keys.add(key)
                    green_keys.discard(key)
                    changed = True
                    count += 1
            if changed:
                state["blocked"][str(gid)] = sorted(list(red_keys))
                state["green_pages"][str(gid)] = sorted(list(green_keys))
                page_fb.set_page_category(state, gid, list(red_keys), "red")

        install_page_catalog(state)
        self.main_app.repository.save(state)
        
        # Làm mới toàn bộ giao diện chính của PageFBApp
        self.main_app.status_var.set(f"Đã chuyển {count} Page lỗi sang Page Đỏ và cập nhật giao diện.")
        self.main_app._refresh_all()

        messagebox.showinfo("Cập nhật thành công!", 
                            f"Đã chuyển thành công {count} Fanpage lỗi sang cột 'Page đỏ'!\n\n"
                            "Giao diện chính của tool đã được cập nhật ngay lập tức.", 
                            parent=self)

    def _export_report(self):
        from tkinter import filedialog
        from datetime import datetime

        if not self.scanned_data:
            messagebox.showinfo("Thông báo", "Chưa có dữ liệu quét để xuất báo cáo.", parent=self)
            return

        filepath = filedialog.asksaveasfilename(
            parent=self,
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
            messagebox.showinfo("Thành công", f"Đã lưu báo cáo thành công vào:\n{filepath}", parent=self)
        except Exception as e:
            messagebox.showerror("Lỗi xuất file", str(e), parent=self)


# ================= GẮN VÀO GIAO DIỆN CHÍNH PAGE FB =================
orig_build_ui = page_fb.PageFBApp._build_ui

def custom_build_ui(self):
    orig_build_ui(self)

    # 1. Xóa bỏ các nút Sheet và 'Kiểm tra view Page'
    buttons_to_remove = ["Đồng bộ → Sheet", "Mở cập nhật Trang tính2", "Đồng bộ từ Sheet", "Kiểm tra view Page"]
    toolbar = None
    copy_btn = None

    for child in self.winfo_children():
        for sub in child.winfo_children():
            for b in sub.winfo_children():
                try:
                    t = b.cget("text")
                    if t in buttons_to_remove:
                        toolbar = sub
                        b.destroy()
                    elif t == "Copy tên Page":
                        copy_btn = b
                        toolbar = sub
                except Exception:
                    pass

    # 2. Nối chức năng 'Kiểm tra lỗi đăng bài' vào toolbar ngay cạnh 'Copy tên Page'
    if toolbar:
        self.btn_post_error_scan = ttk.Button(
            toolbar,
            text="Kiểm tra lỗi đăng bài",
            style="Action.TButton",
            command=self._open_post_error_scanner
        )
        if copy_btn:
            self.btn_post_error_scan.pack(side="left", padx=(0, 6), after=copy_btn)
        else:
            self.btn_post_error_scan.pack(side="left", padx=(0, 6))

def _open_post_error_scanner(self):
    """Mở cửa sổ Kiểm tra lỗi đăng bài BlogB."""
    if hasattr(self, "_scanner_window") and self._scanner_window and self._scanner_window.winfo_exists():
        self._scanner_window.lift()
        self._scanner_window.focus_force()
        return

    self._scanner_window = EmbeddedPostStatusScannerDialog(self)

page_fb.PageFBApp._build_ui = custom_build_ui
page_fb.PageFBApp._open_post_error_scanner = _open_post_error_scanner


def main():
    app = page_fb.PageFBApp()
    app.mainloop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
