# 🚀 PAGE FB - Quản Lý Fanpage, Proxy & Đồng Bộ Google Sheet

Công cụ tự động hóa quản lý, phân loại, kiểm tra view và đồng bộ Fanpage Facebook kết nối BlogB và Google Sheets.

---

## 🌟 Tính Năng Chính

1. **Quản lý đa tài khoản & Profile riêng biệt:**
   - Hỗ trợ nhiều tài khoản BlogB độc lập.
   - Mỗi tài khoản sở hữu catalog và Chrome Profile riêng (`%LOCALAPPDATA%\PageFB\accounts\`).
   - Không lưu mật khẩu, bảo mật tuyệt đối.

2. **Tự động quét và phân loại Fanpage:**
   - Quét toàn bộ Channels/Fanpage từ BlogB thông qua Selenium Chrome.
   - Gắn nhãn phân loại: **Page Xanh** (ưu tiên), **Page Đỏ** (ngưng/loại trừ), **Page Thường**.
   - Quản lý theo từng Cụm Proxy, tự động lưu lịch sử cụm đã xóa.

3. **🔍 Kiểm Tra Lỗi Đăng Bài BlogB (Tích Hợp Trực Tiếp Trên Thanh Công Cụ):**
   - Nút **`Kiểm tra lỗi đăng bài`** nằm ngay trên thanh công cụ chính của app (cạnh nút `Copy tên Page`).
   - Quét bảng kế hoạch (`plan.blogb.io/app/plan`) theo ngày cố định và chuông thông báo (🔔).
   - Tự động quét toàn bộ ngày (không giới hạn số trang), có nút **Dừng** linh hoạt.
   - Tự động đóng Chrome sau khi quét xong để giải phóng CPU và RAM cho máy.
   - Bóc tách **Tên Fanpage chuẩn 100%** (khôi phục từ các tên bị cắt ngắn dấu `...`).
   - Phân loại rõ ràng bài **Đã đăng** và **Thất bại** (kèm dòng lỗi chi tiết).
   - Nút **"🔴 Chuyển các Page lỗi sang Page Đỏ"**: Tự động chuyển các Fanpage lỗi sang cột Page Đỏ và **làm mới giao diện chính của tool ngay lập tức**.

4. **Xuất danh sách Fanpage:**
   - Xuất file `.txt` chứa tên các Fanpage thường và xanh để phục vụ công việc.

---

## 📁 Cấu Trúc Thư Mục

```text
facebook-view-tracker/
│
├── page fb.exe                 # Ứng dụng quản lý catalog & đồng bộ Sheet (Portable EXE)
├── post_status_scanner.py      # Module quét tình trạng & lỗi đăng bài BlogB
├── Kiem_Tra_Loi_Dang_Bai.bat   # Launcher 1-chạm mở công cụ soát lỗi đăng bài
├── HUONG-DAN.txt               # Hướng dẫn sử dụng chi tiết
├── PageFB-Sheet-Sync.gs        # Script Google Apps Script để gắn vào Google Sheet
├── danh-sach-255-page.txt      # Danh sách 255 link Fanpage
├── .gitignore
└── README.md
```

---

## 📖 Hướng Dẫn Sử Dụng Nhanh

1. Mở file `page fb.exe`.
2. Chọn hoặc bấm **"Thêm tài khoản"** để tạo catalog và Chrome profile mới.
3. Bấm **"Mở Chrome / Đăng nhập"** để đăng nhập tài khoản BlogB, sau đó bấm **"Quét toàn bộ Page (Channels)"**.
4. Quản lý, gắn nhãn xanh/đỏ hoặc chọn Page rồi bấm **"Kiểm tra view Page"**.
5. Bấm **"Đồng bộ → Sheet"** để kết nối với Google Sheet thông qua Apps Script đi kèm.

Chi tiết xem tại [`HUONG-DAN.txt`](HUONG-DAN.txt).
