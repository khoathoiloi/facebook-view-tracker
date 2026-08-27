# 🚀 Facebook View Tracker & Analytics (No-Token Enterprise)

> **Công cụ theo dõi, phân tích và lọc lượt xem (Views), tương tác (Likes/Comments) & người theo dõi (Followers) của Fanpage và Reels Facebook không cần Token chính thức, tích hợp cơ chế chống xác minh (Anti-Checkpoint) thông minh.**

---

## 🌟 Tính Năng Nổi Bật

- **🚫 Không cần Token Meta Graph API**: Quét dữ liệu trực tiếp thông qua cơ chế phân giải Link/ID và request bảo mật.
- **🛡️ Cơ chế Chống Xác Minh (Anti-Checkpoint)**:
  - **Độ trễ ngẫu nhiên (Jitter Delay)**: Tự động giãn cách `1.5s - 3.5s` (tùy chỉnh) giữa các lần quét.
  - **Nghỉ ngơi theo đợt (Smart Batching)**: Cứ sau `15 - 20` trang hệ thống tự động nghỉ xả hơi `5 - 10s`.
  - **Giả lập Header trình duyệt thật**: Ngăn chặn thuật toán bot detection của Facebook.
  - **Xoay vòng Cookie Clone (Multi-Cookie Pool)**: Chia đều tải cho nhiều nick phụ để đảm bảo an toàn tuyệt đối.
- **📊 Báo Cáo & Thống Kê Chuyên Nghiệp**:
  - Biểu đồ tăng trưởng lượt xem theo ngày (Hôm nay, 7 ngày, 28 ngày, 30 ngày).
  - Bảng xếp hạng Fanpage theo lượt view từ cao xuống thấp.
  - Xem chi tiết danh sách từng Video & Reels (Lượt xem, Tiêu đề, Ngày đăng, Link trực tiếp).
- **👥 Quản Lý Phân Nhóm & Nhân Viên**: Tạo nhóm, gán Fanpage cho từng nhóm/nhân viên phụ trách để theo dõi hiệu suất riêng biệt.
- **📥 Xuất Dữ Liệu Excel**: Xuất toàn bộ báo cáo phân tích ra file `.xlsx` gồm nhiều sheet (Tổng quan, Chi tiết theo ngày, Danh sách Video).

---

## 🏗️ Cấu Trúc Thư Mục

```text
facebook-view-tracker/
│
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI backend server & API routes
│   ├── database.py     # Quản lý SQLite database (aiosqlite)
│   ├── models.py       # Pydantic data models
│   ├── scraper.py      # Module bóc tách Fanpage, Video, Reels & Verify Cookie
│   ├── engine.py       # Bộ điều phối cào dữ liệu an toàn (Crawler Engine)
│   └── export.py       # Xuất báo cáo đa sheet ra Excel
│
├── static/
│   └── index.html      # Giao diện Web Dashboard hiện đại (Tailwind CSS, Chart.js)
│
├── run.py              # Launcher chạy 1 chạm (tự động bật server & mở trình duyệt)
├── requirements.txt    # Danh sách thư viện Python cần thiết
├── .gitignore
└── README.md
```

---

## ⚙️ Hướng Dẫn Cài Đặt & Chạy

### 1. Yêu cầu hệ thống
* Python 3.10 trở lên.
* Đã cài đặt `git` (tùy chọn).

### 2. Cài đặt thư viện
Mở Terminal / PowerShell và chạy:
```bash
pip install -r requirements.txt
```

### 3. Khởi chạy ứng dụng
Chạy lệnh sau:
```bash
python run.py
```
Ứng dụng sẽ tự động khởi động server tại `http://127.0.0.1:8000` và tự động mở trình duyệt cho bạn.

---

## 📖 Hướng Dẫn Sử Dụng Chi Tiết

### Bước 1: Quản lý Nhóm
* Bấm vào biểu tượng bánh răng ⚙️ ở Header để tạo các Nhóm làm việc (ví dụ: *Team 1, Kênh Tin Tức, Kênh Phim...*).

### Bước 2: Nạp Cookie Clone (Khuyên dùng)
* Chuyển sang Tab **"Cookie Clone"**.
* Dán chuỗi Cookie từ tài khoản Facebook phụ (Clone) vào ô nhập liệu rồi bấm **"Nạp & Kiểm tra Cookie"**.
* Hệ thống sẽ tự động xác minh trạng thái `LIVE` và lấy `User ID`.

### Bước 3: Thêm Fanpage cần theo dõi
* Chuyển sang Tab **"Quản lý Fanpage"**.
* Dán danh sách Link hoặc ID của các Fanpage (mỗi dòng 1 page).
* Chọn nhóm cần gán và bấm **"Thêm & Phân giải Trang"**.

### Bước 4: Bắt đầu cào dữ liệu
* Bấm nút **"Cào dữ liệu ngay"** ở góc trên bên phải.
* Hệ thống sẽ tự động quét tuần tự kèm thời gian nghỉ an toàn và hiển thị thanh tiến trình trực tiếp.

### Bước 5: Xem báo cáo & Xuất Excel
* Xem thống kê tổng quan, biểu đồ đường và chi tiết từng video của trang.
* Bấm nút **"Xuất Excel"** để tải file báo cáo về máy.

---

## 🔒 Bản quyền & Miễn trừ trách nhiệm
Dự án được xây dựng phục vụ mục đích nghiên cứu, tự động hóa quản lý nội dung số và phân tích dữ liệu công khai trên Facebook. Vui lòng tuân thủ điều khoản dịch vụ của nền tảng khi sử dụng.
