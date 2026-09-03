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

3. **Kiểm tra View Page & Reel:**
   - Tự động kiểm tra lượt xem tối đa 3 Reel gần nhất của từng Page hoặc toàn bộ Page hoạt động.

4. **Đồng bộ hai chiều với Google Sheets:**
   - **Đồng bộ lên Sheet (`Đồng bộ → Sheet`):** Xuất gói `page-fb-sheet-sync.json` và `page-fb-sheet-sync.tsv` gồm thông tin tài khoản, cụm proxy, tên, ID, trạng thái, Link Reel và số liệu Reel 1–3.
   - **Đồng bộ ngược (`Đồng bộ từ Sheet`):** Đọc file TSV/CSV/JSON tải từ Google Sheets để cập nhật trạng thái vào hệ thống.
   - Tích hợp sẵn script Google Apps Script: [`PageFB-Sheet-Sync.gs`](PageFB-Sheet-Sync.gs).

5. **Xuất danh sách Fanpage:**
   - Xuất file `.txt` chứa tên các Fanpage thường và xanh để phục vụ công việc.

---

## 📁 Cấu Trúc Thư Mục

```text
facebook-view-tracker/
│
├── page fb.exe             # Ứng dụng chạy trực tiếp (Portable Executable)
├── HUONG-DAN.txt           # Hướng dẫn sử dụng chi tiết
├── PageFB-Sheet-Sync.gs    # Script Google Apps Script để gắn vào Google Sheet
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
