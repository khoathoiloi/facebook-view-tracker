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
        self.title("Page FB — Quét Tình Trạng & Lỗi Đăng Bài BlogB")
        self.geometry("1120x700")
        self.minsize(920, 560)

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
        style.configure("Header.TLabel", font=("Segoe UI", 15, "bold"), foreground="#0f172a")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#64748b")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background="#2563eb", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#f1f5f9", foreground="#1e293b")
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=28)
        style.map("Treeview", background=[("selected", "#e0e7ff")], foreground=[("selected", "#1e1b4b")])

    def _build_ui(self):
        import threading
        from datetime import datetime, timedelta

        header_frame = tk.Frame(self, bg="#ffffff", padx=20, pady=12, bd=1, relief="solid")
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(header_frame, text="🔍 BẢNG SOÁT LỖI & TÌNH TRẠNG ĐĂNG BÀI (BLOGB)", style="Header.TLabel", background="#ffffff")
        title_lbl.pack(anchor="w")
        desc_lbl = ttk.Label(header_frame, text="Tự động bóc tách trạng thái, thời gian và chi tiết lỗi kèm tên Fanpage đầy đủ 100% của ngày đã chọn.", style="SubHeader.TLabel", background="#ffffff")
        desc_lbl.pack(anchor="w", pady=(2, 0))

        ctrl_frame = tk.Frame(self, bg="#f8fafc", padx=20, pady=12)
        ctrl_frame.pack(fill="x")

        tk.Label(ctrl_frame, text="Ngày quét (YYYY-MM-DD):", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#334155").pack(side="left", padx=(0, 6))
        
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_entry = ttk.Entry(ctrl_frame, textvariable=self.date_var, width=13, font=("Segoe UI", 10))
        self.date_entry.pack(side="left", padx=(0, 8))

        btn_today = ttk.Button(ctrl_frame, text="Hôm nay", command=lambda: self.date_var.set(datetime.now().strftime("%Y-%m-%d")))
        btn_today.pack(side="left", padx=2)
        
        btn_yesterday = ttk.Button(ctrl_frame, text="Hôm qua", command=lambda: self.date_var.set((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")))
        btn_yesterday.pack(side="left", padx=2)

        tk.Label(ctrl_frame, text="Số trang:", font=("Segoe UI", 9), bg="#f8fafc", fg="#334155").pack(side="left", padx=(12, 4))
        self.pages_var = tk.StringVar(value="Tất cả (hết ngày)")
        self.pages_combo = ttk.Combobox(ctrl_frame, textvariable=self.pages_var, values=["Tất cả (hết ngày)", "10 trang", "20 trang", "30 trang", "50 trang"], width=15, state="readonly")
        self.pages_combo.pack(side="left", padx=(0, 10))

        self.btn_scan = ttk.Button(ctrl_frame, text="🚀 Bắt đầu quét BlogB", style="Primary.TButton", command=self._start_scan)
        self.btn_scan.pack(side="left", padx=(6, 4))

        self.btn_stop = ttk.Button(ctrl_frame, text="⏹ Dừng", command=self._stop_scan, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 6))

        self.btn_bell = ttk.Button(ctrl_frame, text="🔔 Quét chuông thông báo", command=self._start_bell_scan)
        self.btn_bell.pack(side="left", padx=6)

        tk.Label(ctrl_frame, text="Hiển thị:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#334155").pack(side="left", padx=(20, 6))
        self.filter_var = tk.StringVar(value="ALL")
        for text, mode in [("Tất cả", "ALL"), ("🔴 Thất bại (Lỗi)", "FAILED"), ("🟢 Đã đăng", "SUCCESS")]:
            rb = ttk.Radiobutton(ctrl_frame, text=text, variable=self.filter_var, value=mode, command=self._apply_filter)
            rb.pack(side="left", padx=3)

        # Summary Metrics
        summary_frame = tk.Frame(self, bg="#ffffff", padx=20, pady=8, bd=1, relief="groove")
        summary_frame.pack(fill="x", padx=15, pady=(8, 4))

        self.lbl_total = tk.Label(summary_frame, text="📊 Tổng bài: 0", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#1e293b")
        self.lbl_total.pack(side="left", padx=15)

        self.lbl_success = tk.Label(summary_frame, text="🟢 Thành công: 0", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#16a34a")
        self.lbl_success.pack(side="left", padx=15)

        self.lbl_failed = tk.Label(summary_frame, text="🔴 Thất bại: 0", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#dc2626")
        self.lbl_failed.pack(side="left", padx=15)

        self.lbl_status_msg = tk.Label(summary_frame, text="Sẵn sàng", font=("Segoe UI", 9, "italic"), bg="#ffffff", fg="#64748b")
        self.lbl_status_msg.pack(side="right", padx=15)

        # Treeview
        table_frame = tk.Frame(self, padx=15, pady=6)
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

        # Bottom Bar
        bottom_frame = tk.Frame(self, bg="#f8fafc", padx=20, pady=12)
        bottom_frame.pack(fill="x")

        btn_copy_err = ttk.Button(bottom_frame, text="📋 Copy danh sách Page lỗi", command=self._copy_failed_pages)
        btn_copy_err.pack(side="left", padx=5)

        btn_mark_red = ttk.Button(bottom_frame, text="🔴 Chuyển các Page lỗi sang Page Đỏ", command=self._mark_pages_as_red_and_update_main_ui)
        btn_mark_red.pack(side="left", padx=5)

        btn_export = ttk.Button(bottom_frame, text="📥 Xuất báo cáo TXT", command=self._export_report)
        btn_export.pack(side="right", padx=5)

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

    # 1. Xóa bỏ 3 chức năng Đồng bộ Sheet theo yêu cầu của người dùng
    buttons_to_remove = ["Đồng bộ → Sheet", "Mở cập nhật Trang tính2", "Đồng bộ từ Sheet"]
    toolbar = None
    ref_btn = None

    for child in self.winfo_children():
        for sub in child.winfo_children():
            for b in sub.winfo_children():
                try:
                    t = b.cget("text")
                    if t in buttons_to_remove:
                        toolbar = sub
                        b.destroy()
                    elif t == "Kiểm tra view Page":
                        ref_btn = b
                        toolbar = sub
                except Exception:
                    pass

    # 2. Nối chức năng 'Kiểm tra lỗi đăng bài' vào toolbar
    if toolbar:
        self.btn_post_error_scan = ttk.Button(
            toolbar,
            text="Kiểm tra lỗi đăng bài",
            style="Action.TButton",
            command=self._open_post_error_scanner
        )
        if ref_btn:
            # Pack trước Kiểm tra view Page hoặc sau
            self.btn_post_error_scan.pack(side="left", padx=(0, 6), before=ref_btn)
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
